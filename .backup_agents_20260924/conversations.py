"""agents/conversations.py — Stockage et recherche des conversations Jinx."""
from __future__ import annotations

import datetime
import logging
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional

from .base import Agent, AgentDB, sans_accents

log = logging.getLogger("jinx.conv")


# ===========================================================================
# STORE — accès direct à la base
# ===========================================================================

class ConversationStore:
    """Enregistre et interroge toutes les conversations."""

    def __init__(self, dossier: str):
        self.db_path = os.path.join(dossier, "conversations.db")
        self._init_schema()

    def _init_schema(self):
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts        TEXT DEFAULT CURRENT_TIMESTAMP,
                    agent     TEXT,
                    question  TEXT,
                    reponse   TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ts ON conversations(ts);
                CREATE INDEX IF NOT EXISTS idx_agent ON conversations(agent);
            """)
            # FTS5 pour la recherche full-text (bonus si disponible)
            try:
                cur.executescript("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts
                    USING fts5(question, reponse, agent, content=conversations,
                               content_rowid=id);
                    CREATE TRIGGER IF NOT EXISTS conv_ai
                    AFTER INSERT ON conversations BEGIN
                        INSERT INTO conversations_fts(rowid, question, reponse, agent)
                        VALUES (new.id, new.question, new.reponse, new.agent);
                    END;
                    CREATE TRIGGER IF NOT EXISTS conv_ad
                    AFTER DELETE ON conversations BEGIN
                        INSERT INTO conversations_fts(conversations_fts, rowid,
                            question, reponse, agent)
                        VALUES('delete', old.id, old.question, old.reponse, old.agent);
                    END;
                """)
                self._fts = True
            except Exception as e:
                log.warning("FTS5 indispo: %s", e)
                self._fts = False
            con.commit()
            con.close()
        except Exception as e:
            log.error("ConversationStore init: %s", e)

    def enregistrer(self, question: str, reponse: str, agent: str = "echo"):
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                "INSERT INTO conversations(agent, question, reponse) VALUES (?,?,?)",
                (agent, question, reponse),
            )
            con.commit()
            con.close()
        except Exception as e:
            log.error("enregistrer: %s", e)

    def rechercher(self, terme: str, limite: int = 20) -> List[Dict]:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            if self._fts:
                # FTS5 match
                safe = re.sub(r"[^\w\s]", " ", terme)
                safe = " OR ".join(safe.split())
                cur.execute(
                    "SELECT c.ts, c.agent, c.question, c.reponse "
                    "FROM conversations_fts f JOIN conversations c ON c.id = f.rowid "
                    "WHERE conversations_fts MATCH ? ORDER BY c.ts DESC LIMIT ?",
                    (safe, limite),
                )
            else:
                like = f"%{terme}%"
                cur.execute(
                    "SELECT ts, agent, question, reponse FROM conversations "
                    "WHERE question LIKE ? OR reponse LIKE ? "
                    "ORDER BY ts DESC LIMIT ?",
                    (like, like, limite),
                )
            rows = cur.fetchall()
            con.close()
            return [{"ts": r[0], "agent": r[1], "question": r[2], "reponse": r[3]}
                    for r in rows]
        except Exception as e:
            log.error("rechercher: %s", e)
            return []

    def lister(self, limite: int = 50, offset: int = 0) -> List[Dict]:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                "SELECT ts, agent, question, reponse FROM conversations "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limite, offset),
            )
            rows = cur.fetchall()
            con.close()
            return [{"ts": r[0], "agent": r[1], "question": r[2], "reponse": r[3]}
                    for r in rows]
        except Exception as e:
            log.error("lister: %s", e)
            return []

    def compter(self) -> int:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM conversations")
            n = cur.fetchone()[0]
            con.close()
            return n
        except Exception:
            return 0

    def effacer_tout(self) -> int:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM conversations")
            n = cur.fetchone()[0]
            cur.execute("DELETE FROM conversations")
            con.commit()
            con.close()
            return n
        except Exception as e:
            log.error("effacer_tout: %s", e)
            return 0

    def effacer_avant(self, jours: int) -> int:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            seuil = (datetime.datetime.now()
                     - datetime.timedelta(days=jours)).strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("DELETE FROM conversations WHERE ts < ?", (seuil,))
            n = cur.rowcount
            con.commit()
            con.close()
            return n
        except Exception as e:
            log.error("effacer_avant: %s", e)
            return 0


# ===========================================================================
# AGENT — interroge la base via langage naturel
# ===========================================================================

class ConversationAgent(Agent):
    """Agent qui cherche dans l'historique des conversations."""
    name = "conversations"
    description = ("Consulte et recherche dans l'historique des conversations "
                   "passées avec Jinx.")
    keywords = ["historique", "conversation", "on a dit", "on a parlé",
                "avons-nous discuté", "souviens-toi", "qu'est-ce qu'on",
                "hier", "avant-hier", "la dernière fois"]
    requires_model = None   # pas besoin de LLM

    _R = re.compile(
        r"\b(historique|conversations?|on\s+a\s+(dit|parl[ée])|"
        r"avons[- ]nous\s+(discut[ée]|parl[ée])|"
        r"qu'?est[- ]ce\s+qu'?on\s+a\s+(dit|parl[ée])|"
        r"combien\s+de\s+conversations?|"
        r"(montre|affiche|liste)[- ]moi\s+(l'?historique|les\s+conversations?|ce\s+qu'?on)|"
        r"cherche\s+dans\s+(nos\s+)?(conversations?|l'?historique)|"
        r"la\s+derni[èe]re\s+fois|"
        r"efface\s+l'?historique|supprime\s+l'?historique)\b",
        re.IGNORECASE,
    )

    def __init__(self, dossier: str, llm_fn=None):
        super().__init__(dossier)
        self.llm_fn = llm_fn
        self.store = ConversationStore(dossier)

    def match(self, query: str) -> float:
        return 0.92 if self._R.search(sans_accents(query)) else 0.0

    def run(self, query: str, context: Dict[str, Any]) -> str:
        q = sans_accents(query).lower()

        # Effacer historique
        if re.search(r"efface\s+l'?historique|supprime\s+l'?historique", q):
            n = self.store.effacer_tout()
            return f"Historique effacé : {n} conversations supprimées."

        # Combien de conversations
        if re.search(r"combien\s+de\s+conversations", q):
            n = self.store.compter()
            if n == 0:
                return "Nous n'avons aucune conversation enregistrée."
            return f"Nous avons {n} conversation(s) enregistrée(s)."

        # Recherche par mots-clés
        m = re.search(
            r"(?:sur|à propos de|au sujet de|concernant|dis[ -]?moi\s+sur)\s+(.+)",
            query, re.IGNORECASE)
        terme = m.group(1).strip(" ?!.,;:") if m else None

        # Si pas de "sur X", on cherche un mot-clé connu
        if not terme:
            mots_cles = ["hier", "avant-hier", "aujourd'hui",
                         "la dernière fois"]
            for mc in mots_cles:
                if mc in q:
                    terme = mc
                    break

        if terme:
            res = self.store.rechercher(terme, limite=5)
            if not res:
                return f"Rien trouvé sur « {terme} » dans nos conversations."
            lignes = [f"J'ai trouvé {len(res)} conversation(s) sur « {terme} » :"]
            for r in res[:3]:
                q_court = (r["question"][:60] + "…"
                           if len(r["question"]) > 60 else r["question"])
                lignes.append(f"• [{r['ts']}] {q_court}")
            return "\n".join(lignes)

        # Sinon, montre les dernières
        res = self.store.lister(limite=5)
        if not res:
            return "Aucune conversation enregistrée pour l'instant."
        lignes = ["Voici vos 5 dernières conversations :"]
        for r in res:
            q_court = (r["question"][:55] + "…"
                       if len(r["question"]) > 55 else r["question"])
            lignes.append(f"• [{r['ts']}] ({r['agent']}) {q_court}")
        return "\n".join(lignes)
