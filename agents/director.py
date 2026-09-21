"""
agents/director.py — Agent Directeur pour Jinx
Gère, contrôle et orchestre plusieurs sous-agents.

Agents par défaut :
  - time          : heure et date
  - math          : calculs arithmétiques
  - dictionnaire  : définitions de mots (avec cache SQLite)
  - memory        : mémoire utilisateur (SQLite)
  - echo          : modèle local Qwen (fallback général)

L'agent echo et dictionnaire utilisent llm_fn (injectée depuis main.py)
pour conserver les réglages PERSO / EXEMPLES / LONG / etc.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib import request

log = logging.getLogger("jinx.director")

LLAMA_URL = "http://127.0.0.1:8080/v1/chat/completions"


# ===========================================================================
# STRUCTURES DE BASE
# ===========================================================================

@dataclass
class AgentResult:
    agent: str
    output: str
    success: bool = True
    error: Optional[str] = None
    elapsed: float = 0.0


class Agent:
    """Classe de base. Surcharger name, description, keywords, run()."""
    name: str = "agent"
    description: str = "Agent générique"
    keywords: List[str] = []

    def run(self, query: str, context: Dict[str, Any]) -> str:
        raise NotImplementedError

    def can_handle(self, query: str) -> float:
        if not self.keywords:
            return 0.0
        q = query.lower()
        hits = sum(1 for kw in self.keywords if kw.lower() in q)
        return min(1.0, hits / max(1, len(self.keywords)) * 2)


# ===========================================================================
# SOUS-AGENTS
# ===========================================================================

class TimeAgent(Agent):
    name = "time"
    description = "Donne l'heure et la date actuelles."
    keywords = ["heure", "date", "aujourd'hui", "maintenant", "quel jour"]

    def run(self, query, context):
        return datetime.datetime.now().strftime("Il est %H:%M, le %d/%m/%Y.")


class MathAgent(Agent):
    name = "math"
    description = "Calcule des opérations arithmétiques simples."
    keywords = ["calcul", "combien", "fois", "divisé", "multiplié",
                "plus", "moins", "addition", "soustraction"]

    def run(self, query, context):
        expr = re.sub(r"[^0-9+\-*/(). ]", "", query).strip()
        if not expr:
            return "Je n'ai pas trouvé d'expression à calculer."
        try:
            result = eval(expr, {"__builtins__": None}, {})
            return f"Résultat : {result}"
        except Exception as e:
            return f"Impossible de calculer : {e}"


class DictionnaireAgent(Agent):
    """
    Définit un mot : nature, sens, synonymes, exemple.
    Cache SQLite pour réponse instantanée dès la 2e demande.
    """
    name = "dictionnaire"
    description = ("Donne la définition d'un mot, sa nature grammaticale, "
                   "ses synonymes et un exemple d'usage.")
    keywords = ["définition", "definition", "définis", "definis",
                "que veut dire", "signification", "synonyme", "synonymes",
                "sens du mot", "c'est quoi le mot", "signifie", "veut dire"]

    def __init__(self, db_path: str, llm_fn: Optional[Callable] = None):
        self.db_path = db_path
        self.llm_fn = llm_fn

    def _extraire_mot(self, q: str) -> Optional[str]:
        q = q.strip().lower()
        patterns = [
            r"d[ée]finition\s+(?:du\s+mot\s+|de\s+|d')(.+)",
            r"d[ée]finis\s+(?:le\s+mot\s+|moi\s+)?(.+)",
            r"que\s+veut\s+dire\s+(?:le\s+mot\s+)?(.+)",
            r"signification\s+(?:du\s+mot\s+|de\s+|d')(.+)",
            r"synonyme[s]?\s+(?:de\s+|du\s+mot\s+)(.+)",
            r"c'?est\s+quoi\s+(?:le\s+mot\s+)?(.+)",
            r"sens\s+du\s+mot\s+(.+)",
            r"(.+?)\s+signifie\s+quoi",
        ]
        for p in patterns:
            m = re.search(p, q, re.IGNORECASE)
            if m:
                mot = m.group(1).strip(" ?!.,;:")
                mot = re.sub(r"^(le |la |les |l'|un |une |des )", "", mot)
                return mot.split()[0] if mot else None
        return None

    def _lire_cache(self, mot: str) -> Optional[str]:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS dictionnaire("
                        "mot TEXT PRIMARY KEY, definition TEXT)")
            cur.execute("SELECT definition FROM dictionnaire WHERE mot = ?",
                        (mot.lower(),))
            row = cur.fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def _ecrire_cache(self, mot: str, definition: str) -> None:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS dictionnaire("
                        "mot TEXT PRIMARY KEY, definition TEXT)")
            cur.execute("INSERT OR REPLACE INTO dictionnaire(mot, definition) "
                        "VALUES (?, ?)", (mot.lower(), definition))
            con.commit()
            con.close()
        except Exception:
            pass

    def run(self, query, context):
        mot = self._extraire_mot(query)
        if not mot:
            return "Quel mot veux-tu que je définisse ?"

        cached = self._lire_cache(mot)
        if cached:
            log.info("Dictionnaire : cache pour « %s »", mot)
            return cached

        prompt = (
            f"Donne la définition du mot « {mot} » en français, avec :\n"
            f"1) sa nature grammaticale (nom, verbe, adjectif…)\n"
            f"2) une définition courte et claire\n"
            f"3) deux synonymes\n"
            f"4) un exemple d'usage\n"
            f"Réponds en 4 lignes maximum."
        )

        if self.llm_fn:
            try:
                rep = self.llm_fn(prompt, context)
                self._ecrire_cache(mot, rep)
                return rep
            except Exception as e:
                return f"Erreur dictionnaire : {e}"

        # Fallback HTTP si llm_fn absente
        try:
            payload = {
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 200,
                "stream": False,
            }
            data = json.dumps(payload).encode("utf-8")
            req = request.Request(
                LLAMA_URL, data=data,
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req, timeout=60) as r:
                body = json.loads(r.read().decode("utf-8"))
            rep = body["choices"][0]["message"]["content"].strip()
            self._ecrire_cache(mot, rep)
            return rep
        except Exception as e:
            return f"Je n'ai pas pu définir « {mot} » : {e}"


class MemoryAgent(Agent):
    """Mémoire utilisateur — table SQLite facts(key, value)."""
    name = "memory"
    description = "Retient et restitue des informations sur l'utilisateur."
    keywords = ["souviens", "rappelle", "retiens", "mémoire", "remember"]

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self, query, context):
        q = query.lower()
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS facts("
                        "key TEXT PRIMARY KEY, value TEXT)")

            m = re.search(r"(?:retiens|souviens[- ]toi)\s+que\s+(.+)", q)
            if m:
                fact = m.group(1).strip()
                cur.execute("INSERT OR REPLACE INTO facts(key, value) "
                            "VALUES (?, ?)", (fact, fact))
                con.commit()
                con.close()
                return f"C'est noté : {fact}"

            m = re.search(r"(?:rappelle[- ]moi|tu sais sur)\s+(.+)", q)
            if m:
                key = m.group(1).strip()
                cur.execute("SELECT value FROM facts WHERE key LIKE ?",
                            (f"%{key}%",))
                rows = cur.fetchall()
                con.close()
                if rows:
                    return "Je me souviens : " + " ; ".join(r[0] for r in rows)
                return "Je n'ai rien en mémoire là-dessus."

            con.close()
            return "Dis-moi quoi retenir ou quoi me rappeler."
        except Exception as e:
            return f"Erreur mémoire : {e}"


class EchoAgent(Agent):
    """
    Agent généraliste. Utilise llm_fn (demander_ia de main.py) si fournie,
    sinon appelle directement l'API HTTP.
    """
    name = "echo"
    description = "Répond aux questions générales via le modèle local."
    keywords = []  # Toujours en fallback, jamais en routage direct

    def __init__(self, llm_fn: Optional[Callable] = None,
                 url: str = LLAMA_URL, timeout: int = 180):
        self.llm_fn = llm_fn
        self.url = url
        self.timeout = timeout

    def run(self, query, context):
        if self.llm_fn:
            try:
                memoire = context.get("memoire", "")
                exemples = context.get("exemples", [])
                return self.llm_fn(query, (memoire, exemples))
            except Exception as e:
                log.warning("llm_fn a échoué, fallback HTTP : %s", e)

        system = context.get(
            "system_prompt",
            "Tu es Jinx, un assistant utile, concis et amical."
        )
        previous = context.get("previous", "").strip()
        if previous:
            system += f"\nContexte déjà collecté :{previous}"

        messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
        for ex in context.get("exemples", []):
            messages.append(ex)
        messages.append({"role": "user", "content": query})

        payload = {
            "messages": messages,
            "temperature": context.get("temperature", 0.3),
            "max_tokens": context.get("max_tokens", 256),
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.url, data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Le modèle local ne répond pas : {e}"


# ===========================================================================
# DIRECTEUR
# ===========================================================================

class Director:
    """
    Le directeur :
      1. Reçoit la requête utilisateur
      2. Choisit les agents à appeler (LLM ou mots-clés)
      3. Les exécute dans l'ordre
      4. Agrège les résultats
    """

    def __init__(self, url: str = LLAMA_URL):
        self.url = url
        self.agents: Dict[str, Agent] = {}
        self.history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # --- gestion des agents ---
    def register(self, agent: Agent) -> None:
        with self._lock:
            self.agents[agent.name] = agent
            log.info("Agent enregistré : %s", agent.name)

    def unregister(self, name: str) -> None:
        with self._lock:
            self.agents.pop(name, None)

    def list_agents(self) -> List[str]:
        return list(self.agents.keys())

    def get_agents_info(self) -> List[Dict[str, Any]]:
        """Pour le panneau paramètres : nom + description + mots-clés."""
        return [
            {
                "name": a.name,
                "description": a.description,
                "keywords": list(a.keywords),
            }
            for a in self.agents.values()
        ]

    # --- routage ---
    def _routing_messages(self, query: str) -> List[Dict[str, str]]:
        catalogue = "\n".join(
            f"- {a.name} : {a.description}" for a in self.agents.values()
        )
        system = (
            "Tu es le directeur d'une équipe d'agents.\n"
            "Agents disponibles :\n" + catalogue + "\n\n"
            "Choisis UNIQUEMENT les agents nécessaires, dans l'ordre d'exécution.\n"
            "Réponds par un tableau JSON de noms. Exemples :\n"
            '  ["time"]\n'
            '  ["dictionnaire"]\n'
            '  ["memory", "echo"]\n'
            '  []  (si aucun agent spécialisé ne convient)\n'
            "Réponse (JSON uniquement, rien d'autre) :"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ]

    def _ask_llm(self, messages, timeout: int = 20) -> str:
        payload = {
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 48,
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.url, data=data,
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()

    def _parse(self, raw: str) -> List[str]:
        m = re.search(r"\[(.*?)\]", raw, re.DOTALL)
        if not m:
            return []
        try:
            names = json.loads("[" + m.group(1) + "]")
        except Exception:
            names = re.findall(r'"([^"]+)"', m.group(1))
        return [n for n in names if n in self.agents]

    def select_agents(self, query: str, max_agents: int = 3) -> List[str]:
        # 1) Tentative par LLM
        try:
            raw = self._ask_llm(self._routing_messages(query))
            picked = self._parse(raw)
            if picked:
                log.info("Routage LLM → %s", picked)
                return picked[:max_agents]
        except Exception as e:
            log.warning("Routage LLM échoué : %s", e)

        # 2) Fallback mots-clés
        scored = []
        for name, agent in self.agents.items():
            s = agent.can_handle(query)
            if s > 0:
                scored.append((s, name))
        scored.sort(reverse=True)
        picked = [n for _, n in scored[:max_agents]]
        log.info("Routage mots-clés → %s", picked)
        return picked

    # --- exécution ---
    def handle(self, query: str,
               context: Optional[Dict[str, Any]] = None) -> str:
        context = context or {}
        picked = self.select_agents(query)

        # Aucun agent spécialisé → echo direct
        if not picked:
            picked = ["echo"] if "echo" in self.agents else []
        if not picked:
            return "Aucun agent disponible pour cette demande."

        results: List[AgentResult] = []
        accumulated = ""

        for name in picked:
            agent = self.agents[name]
            t0 = time.time()
            try:
                ctx = dict(context)
                ctx["previous"] = accumulated
                out = agent.run(query, ctx)
                results.append(
                    AgentResult(name, out, True, None, time.time() - t0)
                )
                accumulated += f"\n[{name}] {out}"
            except Exception as e:
                log.exception("Agent %s a planté", name)
                results.append(
                    AgentResult(name, "", False, str(e), time.time() - t0)
                )

        # Un seul agent → réponse directe
        if len(results) == 1:
            r = results[0]
            return r.output if r.success else f"Erreur : {r.error}"

        # Plusieurs agents → liste formatée
        return "\n".join(
            f"• {r.agent} : {r.output}" if r.success
            else f"• {r.agent} : échec ({r.error})"
            for r in results
        )

    def handle_async(self, query: str,
                     callback: Callable[[str], None],
                     context: Optional[Dict[str, Any]] = None) -> None:
        """Appel non bloquant, callback planifié sur le thread Kivy."""
        def worker():
            try:
                out = self.handle(query, context)
            except Exception as e:
                out = f"Erreur directeur : {e}"
            try:
                from kivy.clock import Clock
                Clock.schedule_once(lambda *_: callback(out), 0)
            except Exception:
                callback(out)
        threading.Thread(target=worker, daemon=True).start()


# ===========================================================================
# FABRIQUE
# ===========================================================================

def build_default_director(db_path: str = "jinx.db",
                           url: str = LLAMA_URL,
                           llm_fn: Optional[Callable] = None) -> Director:
    """Construit un directeur avec les 5 agents par défaut."""
    d = Director(url=url)
    d.register(TimeAgent())
    d.register(MathAgent())
    d.register(DictionnaireAgent(db_path, llm_fn=llm_fn))
    d.register(MemoryAgent(db_path))
    d.register(EchoAgent(llm_fn=llm_fn, url=url))
    return d
