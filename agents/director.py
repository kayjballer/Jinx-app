"""agents/director.py — Un seul cerveau : Qwen 3B + contexte système."""
from __future__ import annotations

import datetime
import json
import logging
import threading
from typing import Any, Callable, Dict, Optional
from urllib import request

log = logging.getLogger("jinx.director")


class Director:
    def __init__(self, model_manager=None):
        self.model_manager = model_manager
        self.core = None
        self.conv_store = None
        self._lock = threading.Lock()

    def set_core(self, core):
        self.core = core

    def _contexte_systeme(self) -> str:
        if not self.core:
            return ""
        try:
            parties = []
            now = datetime.datetime.now()
            jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi",
                     "samedi", "dimanche"]
            mois = ["janvier", "février", "mars", "avril", "mai", "juin",
                    "juillet", "août", "septembre", "octobre", "novembre",
                    "décembre"]
            date_str = f"{jours[now.weekday()]} {now.day} {mois[now.month-1]} {now.year}"
            parties.append(f"Date/heure : {date_str}, {now.strftime('%H:%M')}")

            b = self.core.batterie()
            if b.get("niveau", -1) >= 0:
                etat = "en charge" if b.get("en_charge") else "sur batterie"
                parties.append(f"Batterie : {b['niveau']}% ({etat})")

            w = self.core.wifi()
            if w.get("connecte"):
                t = w.get("type", "")
                if t == "wifi":
                    parties.append("Réseau : WiFi connecté")
                elif t == "cell":
                    parties.append("Réseau : données mobiles")
                else:
                    parties.append("Réseau : connecté")
            else:
                parties.append("Réseau : déconnecté")

            r = self.core.ram()
            if r.get("total_mo", 0) > 0:
                parties.append(f"RAM libre : {r['libre_mo']:.0f} Mo")

            s = self.core.stockage()
            if s.get("total_go", 0) > 0:
                parties.append(f"Stockage libre : {s['libre_go']:.1f} Go")

            return "\n".join(f"- {p}" for p in parties)
        except Exception as e:
            log.warning("contexte_systeme: %s", e)
            return ""

    def _prompt_complet(self, query: str, contexte: str,
                        memoire: str = "") -> str:
        parties = [
            "Tu es Jinx, un assistant vocal personnel. "
            "Tu réponds en français, de manière naturelle, chaleureuse et concise. "
            "Si on te demande l'heure, la date, la batterie ou le réseau, "
            "utilise le contexte système fourni ci-dessous."
        ]
        if contexte:
            parties.append(f"\nContexte système :\n{contexte}")
        if memoire:
            parties.append(f"\nCe que tu sais de l'utilisateur :\n{memoire}")
        parties.append(f"\nUtilisateur : {query}")
        parties.append("\nJinx :")
        return "\n".join(parties)

    def _appeler_llm(self, prompt: str, url: str, timeout: int = 120) -> str:
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6,
            "top_p": 0.9,
            "top_k": 40,
            "repeat_penalty": 1.1,
            "max_tokens": 256,       # Réponses courtes = plus rapide
            "stream": False,
            # Stop tokens pour éviter les répétitions
            "stop": ["\nUtilisateur :", "\nUser :", "\n\nJinx"],
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data,
                              headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.error("appel_llm: %s", e)
            return f"Erreur LLM : {e}"

    def handle(self, query: str,
               context: Optional[Dict[str, Any]] = None) -> str:
        context = context or {}
        contexte = self._contexte_systeme()
        memoire = context.get("memoire", "")
        prompt = self._prompt_complet(query, contexte, memoire)

        if not self.model_manager:
            return "Aucun modèle disponible."

        url = self.model_manager.ensure("intelligent")
        if not url:
            url = self.model_manager.ensure("rapide")
            if not url:
                return "Impossible de charger le modèle."

        rep = self._appeler_llm(prompt, url)

        if self.conv_store:
            try:
                self.conv_store.enregistrer(query, rep, "jinx")
            except Exception:
                pass

        return rep

    def handle_async(self, query: str, callback: Callable[[str], None],
                     context: Optional[Dict[str, Any]] = None) -> None:
        def worker():
            try:
                out = self.handle(query, context)
            except Exception as e:
                out = f"Erreur : {e}"
            try:
                from kivy.clock import Clock
                Clock.schedule_once(lambda *_: callback(out), 0)
            except Exception:
                callback(out)
        threading.Thread(target=worker, daemon=True).start()


def build_default_director(dossier: str, model_manager=None) -> Director:
    d = Director(model_manager=model_manager)
    return d
