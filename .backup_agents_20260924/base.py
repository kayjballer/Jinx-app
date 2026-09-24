"""agents/base.py — Classes de base pour tous les agents."""
from __future__ import annotations

import logging
import os
import sqlite3
import unicodedata
from typing import Any, Dict, Optional

log = logging.getLogger("jinx.agents")


def sans_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).lower()


class AgentDB:
    def __init__(self, path: str, schema: str = ""):
        self.path = path
        self.schema = schema
        self._ensure()

    def _ensure(self) -> None:
        try:
            con = sqlite3.connect(self.path)
            if self.schema:
                con.executescript(self.schema)
            con.commit()
            con.close()
        except Exception as e:
            log.error("AgentDB %s: %s", self.path, e)

    def conn(self):
        return sqlite3.connect(self.path)

    def execute(self, sql: str, params: tuple = ()) -> list:
        try:
            con = self.conn()
            cur = con.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall() if sql.strip().upper().startswith("SELECT") else []
            con.commit()
            con.close()
            return rows
        except Exception as e:
            log.error("AgentDB execute: %s", e)
            return []

    def size_mo(self) -> float:
        try:
            return os.path.getsize(self.path) / 1e6
        except Exception:
            return 0.0


class Agent:
    name: str = "agent"
    description: str = "Agent générique"
    keywords: list = []
    requires_model: Optional[str] = None

    def __init__(self, dossier: str):
        self.dossier = dossier
        self.db: Optional[AgentDB] = None
        self.llm_fn = None

    def match(self, query: str) -> float:
        return 0.0

    def run(self, query: str, context: Dict[str, Any]) -> str:
        raise NotImplementedError

    def _llm(self, prompt: str, context: Dict[str, Any]) -> str:
        if not self.llm_fn:
            return "Aucun modèle LLM disponible."
        try:
            return self.llm_fn(prompt, context)
        except Exception as e:
            return f"Erreur LLM : {e}"
