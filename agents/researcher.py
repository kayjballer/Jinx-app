"""
agents/researcher.py — Agent chercheur : Wikipedia + cache web.
"""
from __future__ import annotations

import json
import logging
import os
import re
import ssl
import sqlite3
from typing import Any, Dict, Optional
from urllib import request, parse

from .base import Agent, sans_accents

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()

log = logging.getLogger("jinx.researcher")

WIKI_API = "https://fr.wikipedia.org/api/rest_v1/page/summary/"


class WebCache:
    def __init__(self, dossier: str):
        self.db_path = os.path.join(dossier, "web_cache.db")
        self._init()

    def _init(self):
        try:
            con = sqlite3.connect(self.db_path)
            con.executescript("""
                CREATE TABLE IF NOT EXISTS cache_web (
                    sujet    TEXT PRIMARY KEY,
                    contenu  TEXT,
                    source   TEXT,
                    ts       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            con.commit()
            con.close()
        except Exception as e:
            log.error("WebCache init: %s", e)

    def get(self, sujet: str) -> Optional[str]:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute("SELECT contenu FROM cache_web WHERE sujet = ?",
                        (sujet.lower(),))
            row = cur.fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def set(self, sujet: str, contenu: str, source: str = "wikipedia"):
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO cache_web(sujet, contenu, source) "
                "VALUES (?,?,?)",
                (sujet.lower(), contenu, source))
            con.commit()
            con.close()
        except Exception as e:
            log.error("WebCache set: %s", e)

    def compter(self) -> int:
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM cache_web")
            n = cur.fetchone()[0]
            con.close()
            return n
        except Exception:
            return 0


class ResearcherAgent(Agent):
    name = "researcher"
    description = "Cherche sur Wikipedia et stocke les resultats."
    keywords = ["cherche sur internet", "recherche web", "va chercher",
                "apprends", "enrichis", "actualise"]
    requires_model = None

    # Verbe + mot "web/internet/wiki" dans les 40 caractères suivants
    _R = re.compile(
        r"\b(cherche|chercher|recherche|rechercher|trouve|trouver|"
        r"apprends|apprendre|enrichis|enrichir|actualise|actualiser|"
        r"va\s+chercher|va\s+voir|"
        r"regarde|regarder)\b"
        r".{0,40}"
        r"\b(internet|web|wiki|wikipedia|google|en\s+ligne|"
        r"la\s+v[ée]rit[ée]|des\s+infos?|des\s+informations?)\b",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, dossier: str, llm_fn=None):
        super().__init__(dossier)
        self.llm_fn = llm_fn
        self.dossier = dossier
        self.cache = WebCache(dossier)

    def match(self, query: str) -> float:
        return 0.93 if self._R.search(sans_accents(query)) else 0.0

    def _wikipedia(self, sujet: str) -> Optional[Dict[str, str]]:
        try:
            enc = parse.quote(sujet.replace(" ", "_"))
            req = request.Request(WIKI_API + enc,
                                  headers={"User-Agent": "Jinx/1.0"})
            with request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
                d = json.loads(r.read().decode("utf-8"))
            return {"titre": d.get("title", sujet),
                    "extrait": d.get("extract", "")}
        except Exception as e:
            log.warning("wiki %s: %s", sujet, e)
            return None

    def run(self, query: str, context: Dict[str, Any]) -> str:
        q = query.lower()
        m = re.search(
            r"(?:apprends\s+(?:le\s+mot\s+)?|"
            r"cherche\s+sur\s+internet\s+|"
            r"recherche\s+web\s+|va\s+chercher\s+)"
            r"[\"«]?([a-zà-ÿ\- ]{2,60})[\"»]?",
            q)
        if not m:
            return ("Dis-moi : « cherche sur internet la tour Eiffel » "
                    "ou « apprends le mot algorithmique ».")
        sujet = m.group(1).strip(" ?!.,;:")

        cached = self.cache.get(sujet)
        if cached:
            return f"(cache) {cached[:500]}"

        res = self._wikipedia(sujet)
        if not res or not res["extrait"]:
            return f"Aucun resultat Wikipedia pour « {sujet} »."

        self.cache.set(sujet, res["extrait"])
        return f"{res['titre']} : {res['extrait'][:600]}"
