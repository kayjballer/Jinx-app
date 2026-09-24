"""agents/workers.py — 6 agents, chacun avec sa base + son modèle."""
from __future__ import annotations

import datetime
import logging
import os
import re
import ssl

from .base import Agent, AgentDB, sans_accents

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()

log = logging.getLogger("jinx.workers")


# ==================== TIME ====================
class TimeAgent(Agent):
    name = "time"
    description = "Heure, date, jour — modèle 0.5B dédié."
    keywords = ["heure", "date", "quel jour", "quelle heure"]
    requires_model = "time"

    _R = re.compile(
        r"\b(quelle?\s+heure|il\s+est\s+quelle\s+heure|quel\s+jour|"
        r"quelle?\s+date|on\s+est\s+quel|donne[- ]moi\s+l'?heure)\b",
        re.IGNORECASE)

    def match(self, query):
        return 0.95 if self._R.search(sans_accents(query)) else 0.0

    def run(self, query, context):
        brut = datetime.datetime.now().strftime("Il est %H:%M, le %d/%m/%Y.")
        if self.llm_fn:
            prompt = (f"Reformule en une phrase naturelle et courte : « {brut} »")
            rep = self._llm(prompt, context)
            if rep and "Erreur" not in rep and len(rep) < 200:
                return rep
        return brut


# ==================== MATH ====================
class MathAgent(Agent):
    name = "math"
    description = "Calculs, formules, constantes — modèle Math 1.5B."
    keywords = ["calcul", "combien font", "calcule", "constante"]
    requires_model = "math"

    _DECL = re.compile(
        r"\b(calcul|calcule|combien\s+font?|combien\s+fait|"
        r"r[ée]sultat\s+de|additionne|soustrais|multiplie|divise)\b",
        re.IGNORECASE)
    _PIEGES = ["definition", "definis", "signifie", "veut dire", "animal",
               "capitale", "qui est", "mot le plus", "code", "fonction"]

    def __init__(self, dossier, llm_fn=None):
        super().__init__(dossier)
        self.llm_fn = llm_fn
        self.db = AgentDB(
            os.path.join(dossier, "math.db"),
            schema="""CREATE TABLE IF NOT EXISTS constantes(
                nom TEXT PRIMARY KEY, valeur TEXT, description TEXT);""")
        for n, v, d in [("pi", "3.141592653589793", "Pi"),
                        ("e", "2.718281828459045", "Euler"),
                        ("phi", "1.618033988749895", "Nombre d'or")]:
            self.db.execute("INSERT OR IGNORE INTO constantes VALUES (?,?,?)",
                            (n, v, d))

    @staticmethod
    def _nettoyer(q):
        s = q
        s = re.sub(r"\b(fois|multiplie)\b", "*", s, flags=re.I)
        s = re.sub(r"\b(divise)\b", "/", s, flags=re.I)
        s = re.sub(r"\b(plus|ajoute)\b", "+", s, flags=re.I)
        s = re.sub(r"\b(moins|retire)\b", "-", s, flags=re.I)
        s = s.replace("×", "*").replace("÷", "/")
        s = s.replace("x", "*").replace("X", "*")
        s = re.sub(r"[^0-9\+\-\*/eE()., ]", "", s)
        return s.replace(",", ".").strip()

    def match(self, query):
        q = sans_accents(query)
        if any(p in q for p in self._PIEGES):
            return 0.0
        cleaned = self._nettoyer(query)
        a_calc = bool(re.search(r"\d+\s*[\+\-\*/]\s*\d+", cleaned))
        if self._DECL.search(q) and a_calc:
            return 0.92
        if a_calc and len(query) < 40:
            return 0.78
        if q.strip() in ("pi", "e", "phi"):
            return 0.85
        return 0.0

    def run(self, query, context):
        expr = self._nettoyer(query)
        brut = ""
        if expr and re.search(r"\d", expr):
            try:
                r = eval(expr, {"__builtins__": None}, {})
                if isinstance(r, float) and r.is_integer():
                    r = int(r)
                brut = f"Résultat : {r}"
            except Exception as e:
                brut = f"Calcul simple impossible : {e}"
        if self.llm_fn:
            prompt = (f"Résous ce problème mathématique : « {query} ». "
                      f"Réponse courte et claire.")
            rep = self._llm(prompt, context)
            if rep and "Erreur" not in rep:
                return rep
        return brut or "Je n'ai pas compris le calcul."


# ==================== DICTIONNAIRE ====================
class DictionnaireAgent(Agent):
    name = "dictionnaire"
    description = "Définitions, nature, synonymes (base locale + modèle 1.5B)."
    keywords = ["définition", "définis", "signification", "synonyme"]
    requires_model = "dictionnaire"

    _R = re.compile(
        r"(?:"
        r"(?:d[ée]finis?|d[ée]finition\s*(?:de|du|d'|pour)?)\s*[- ]?\s*(?:moi\s+)?"
        r"(?:le\s+mot\s+|l[' ]|le\s+|la\s+|les\s+|un\s+|une\s+)?"
        r"([a-zàâäéèêëïîôöùûüç][a-zàâäéèêëïîôöùûüç\-']{1,40})"
        r"|que\s+veut\s+dire\s+(?:le\s+mot\s+)?"
        r"([a-zàâäéèêëïîôöùûüç][a-zàâäéèêëïîôöùûüç\-']{1,40})"
        r"|(?:signification|sens)\s+(?:du\s+mot\s+|de\s+|d')"
        r"([a-zàâäéèêëïîôöùûüç][a-zàâäéèêëïîôöùûüç\-']{1,40})"
        r"|synonymes?\s+(?:de\s+|du\s+mot\s+)"
        r"([a-zàâäéèêëïîôöùûüç][a-zàâäéèêëïîôöùûüç\-']{1,40})"
        r")", re.IGNORECASE)

    _STOP = {"le", "la", "les", "un", "une", "des", "de", "du", "ce", "cet",
             "cette", "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa",
             "ses", "moi", "toi", "lui", "nous", "vous", "ils", "elles"}

    def __init__(self, dossier, llm_fn=None):
        super().__init__(dossier)
        self.llm_fn = llm_fn
        self.db = AgentDB(
            os.path.join(dossier, "dict_cache.db"),
            schema="""CREATE TABLE IF NOT EXISTS cache(
                mot TEXT PRIMARY KEY, definition TEXT);""")
        self.db_lourd = os.path.join(dossier, "dict.db")

    def _extraire(self, query):
        m = self._R.search(query)
        if not m:
            return None
        for g in m.groups():
            if g:
                mot = g.strip().lower()
                if mot not in self._STOP and len(mot) >= 2:
                    return mot
        return None

    def match(self, query):
        return 0.95 if self._extraire(query) else 0.0

    def _cache_get(self, mot):
        rows = self.db.execute("SELECT definition FROM cache WHERE mot=?", (mot,))
        return rows[0][0] if rows else None

    def _cache_set(self, mot, txt):
        self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?)", (mot, txt))

    def _db_lourd_get(self, mot):
        if not os.path.exists(self.db_lourd):
            return None
        try:
            import sqlite3
            con = sqlite3.connect(self.db_lourd)
            cur = con.cursor()
            cur.execute("SELECT definition, synonymes, categorie FROM mots "
                        "WHERE mot=? OR lemme=? LIMIT 1", (mot, mot))
            row = cur.fetchone()
            con.close()
            if row and row[0]:
                return {"definition": row[0], "synonymes": row[1],
                        "categorie": row[2]}
        except Exception as e:
            log.warning("dict.db: %s", e)
        return None

    def run(self, query, context):
        mot = self._extraire(query)
        if not mot:
            return "Quel mot veux-tu que je définisse ?"
        cached = self._cache_get(mot)
        if cached:
            return cached
        local = self._db_lourd_get(mot)
        if local:
            txt = self._formater(mot, local)
            self._cache_set(mot, txt)
            return txt
        prompt = (f"Définis le mot « {mot} » en français.\n"
                  f"1) Nature 2) Sens 3) 2 synonymes 4) Exemple. 4 lignes max.")
        rep = self._llm(prompt, context)
        if rep and "Erreur" not in rep:
            self._cache_set(mot, rep)
        return rep

    @staticmethod
    def _formater(mot, d):
        out = [f"**{mot}**"]
        if d.get("categorie"):
            out.append(f"Nature : {d['categorie']}")
        if d.get("definition"):
            out.append(f"Sens : {d['definition']}")
        if d.get("synonymes"):
            out.append(f"Synonymes : {d['synonymes']}")
        return "\n".join(out)


# ==================== MEMORY ====================
class MemoryAgent(Agent):
    """
    Mémoire unifiée : faits utilisateur + historique conversations.
    """
    name = "memory"
    description = ("Retient des faits + consulte l'historique des conversations.")
    keywords = ["souviens", "rappelle", "retiens", "mémoire",
                "historique", "conversations", "on a dit", "on a parlé"]
    requires_model = None

    _RETENIR = re.compile(
        r"\b(?:retiens|souviens[- ]toi|m[ée]morise)\s+que\s+(.+)", re.IGNORECASE)
    # Exclut les cas avec un délai (dans X minutes) → gérés par alarm
    # Tolère les variations STT : "qu'est-ce" / "qu est ce" / "quest ce"
    _RAPPELER = re.compile(
        r"\b(?:"
        r"rappelle[- ]moi(?!\s+dans)|"
        r"qu\s*'?\s*est\s*[- ]?\s*ce\s+que\s+tu\s+sais\s+sur|"
        r"que\s+sais[- ]tu\s+sur|"
        r"tu\s+te\s+souviens\s+de|"
        r"tu\s+sais\s+quoi\s+sur"
        r")\s*(.+)", re.IGNORECASE)
    _HISTORIQUE = re.compile(
        r"\b(historique|conversations?|on\s+a\s+(dit|parl[ée])|"
        r"combien\s+de\s+conversations?|"
        r"(montre|affiche|liste)[- ]moi\s+(l'?historique|les\s+conversations?)|"
        r"cherche\s+dans\s+(nos\s+)?(conversations?|l'?historique)|"
        r"la\s+derni[èe]re\s+fois|"
        r"efface\s+l'?historique|supprime\s+l'?historique)\b",
        re.IGNORECASE)

    def __init__(self, dossier, llm_fn=None):
        super().__init__(dossier)
        self.llm_fn = llm_fn
        self.db = AgentDB(
            os.path.join(dossier, "memory.db"),
            schema="""CREATE TABLE IF NOT EXISTS facts(
                key TEXT PRIMARY KEY, value TEXT,
                cree_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
        # ConversationStore pour l'historique
        self._conv = None

    def _get_conv(self):
        if self._conv is None:
            try:
                from .conversations import ConversationStore
                self._conv = ConversationStore(self.dossier)
            except Exception as e:
                log.warning("conv store: %s", e)
        return self._conv

    def match(self, query):
        q = sans_accents(query)
        # Ne pas intercepter les rappels temporels (dans X minutes)
        if re.search(r"dans\s+\d+\s*(seconde|minute|heure|sec|min|h)s?",
                     q, re.IGNORECASE):
            return 0.0
        if self._RETENIR.search(query) or self._RAPPELER.search(query):
            return 0.95
        if self._HISTORIQUE.search(q):
            return 0.92
        return 0.0

    def run(self, query, context):
        q = sans_accents(query).lower()

        # --- Historique conversations ---
        if self._HISTORIQUE.search(q):
            return self._reponse_historique(q, query)

        # --- Faits utilisateur ---
        m = self._RETENIR.search(query)
        if m:
            fact = m.group(1).strip(" .!?")
            self.db.execute("INSERT OR REPLACE INTO facts(key,value) VALUES (?,?)",
                            (fact, fact))
            return f"C'est noté : {fact}"

        m = self._RAPPELER.search(query)
        if m:
            key = m.group(1).strip(" .!?")
            rows = self.db.execute("SELECT value FROM facts WHERE key LIKE ?",
                                   (f"%{key}%",))
            if rows:
                return "Je me souviens : " + " ; ".join(r[0] for r in rows)
            return "Je n'ai rien en mémoire là-dessus."

        return "Dis-moi quoi retenir ou quoi me rappeler."

    def _reponse_historique(self, q, query):
        store = self._get_conv()
        if not store:
            return "Historique indisponible."

        # Effacer
        if "efface" in q or "supprime" in q:
            n = store.effacer_tout()
            return f"Historique effacé : {n} conversations supprimées."

        # Combien
        if "combien" in q:
            n = store.compter()
            if n == 0:
                return "Aucune conversation enregistrée."
            return f"Nous avons {n} conversation(s) enregistrée(s)."

        # Recherche par mots-clés
        m = re.search(
            r"(?:sur|à propos de|au sujet de|concernant|dis[ -]?moi\s+sur)\s+(.+)",
            query, re.IGNORECASE)
        terme = m.group(1).strip(" ?!.,;:") if m else None
        if not terme:
            for mc in ["hier", "avant-hier", "aujourd'hui", "la dernière fois"]:
                if mc in q:
                    terme = mc
                    break

        if terme:
            res = store.rechercher(terme, limite=5)
            if not res:
                return f"Rien trouvé sur « {terme} »."
            lignes = [f"J'ai trouvé {len(res)} conversation(s) :"]
            for r in res[:3]:
                qc = r["question"][:60]
                lignes.append(f"• [{r['ts']}] {qc}")
            return "\n".join(lignes)

        # Liste
        res = store.lister(limite=5)
        if not res:
            return "Aucune conversation."
        lignes = ["Voici vos 5 dernières conversations :"]
        for r in res:
            qc = r["question"][:55]
            lignes.append(f"• [{r['ts']}] ({r['agent']}) {qc}")
        return "\n".join(lignes)


# ==================== CODE ====================
class CodeAgent(Agent):
    name = "code"
    description = "Programmation (Python, JS, C, Rust…) — Qwen Coder 3B."
    keywords = ["code", "programme", "fonction", "python", "javascript",
                "html", "css", "sql", "rust", "java", "cpp", "bug"]
    requires_model = "code"

    _R = re.compile(
        r"\b(code|programme|fonction|python|javascript|js|html|css|sql|"
        r"rust|java|c\+\+|cpp|script|algorithme|classe|variable|"
        r"bug|erreur|debug|syntaxe|compil|"
        r"[ée]cris[- ]moi\s+un|comment\s+faire\s+en)\b", re.IGNORECASE)

    def __init__(self, dossier, llm_fn=None):
        super().__init__(dossier)
        self.llm_fn = llm_fn
        self.db = AgentDB(
            os.path.join(dossier, "code.db"),
            schema="""CREATE TABLE IF NOT EXISTS historique(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT, reponse TEXT,
                cree_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")

    def match(self, query):
        if self._R.search(sans_accents(query)):
            return 0.92
        if any(s in query for s in ["def ", "function ", "class ", "import ",
                                     "console.log", "print(", "(){"]):
            return 0.90
        return 0.0

    def run(self, query, context):
        system = ("Tu es un expert en programmation. Réponds en français.\n"
                  "Donne du code complet, fonctionnel, dans un bloc markdown.")
        rep = self._llm(f"{system}\n\nDemande : {query}", context)
        if rep and "Erreur" not in rep:
            self.db.execute("INSERT INTO historique(question,reponse) VALUES (?,?)",
                            (query, rep))
        return rep


# ==================== ECHO ====================
class EchoAgent(Agent):
    name = "echo"
    description = "Questions générales, conversation — Qwen 3B."
    keywords = []
    requires_model = "echo"

    def __init__(self, dossier, llm_fn=None):
        super().__init__(dossier)
        self.llm_fn = llm_fn
        self.db = AgentDB(
            os.path.join(dossier, "echo.db"),
            schema="""CREATE TABLE IF NOT EXISTS historique(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT, reponse TEXT,
                cree_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")

    def match(self, query):
        return 0.30

    def run(self, query, context):
        rep = self._llm(query, context)
        if rep and "Erreur" not in rep:
            self.db.execute("INSERT INTO historique(question,reponse) VALUES (?,?)",
                            (query, rep))
        return rep
