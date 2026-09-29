"""agents/director.py — Un seul cerveau : Qwen 3.5 2B + contexte système."""
from __future__ import annotations

import datetime
import json
import logging
import threading
from typing import Any, Callable, Dict, Optional
from urllib import request

log = logging.getLogger("jinx.director")

# Bypass proxy Android (127.0.0.1 ne doit PAS passer par un proxy)
import http.client
import urllib.request as _ur
_OPENER = _ur.build_opener(_ur.ProxyHandler({}))


class Director:
    def __init__(self, model_manager=None):
        self.model_manager = model_manager
        self.core = None
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

    def _prompt_complet(self, query: str, contexte: str) -> str:
        return (
            "Tu es Jinx, un assistant vocal personnel. "
            "Tu réponds en français, de manière naturelle, chaleureuse et concise. "
            "Si on te demande l'heure, la date, la batterie ou le réseau, "
            "utilise le contexte système fourni.\n\n"
            f"Contexte système :\n{contexte}\n\n"
            f"Utilisateur : {query}\nJinx :"
        )

    def _appeler_llm(self, prompt, url, timeout=120):
        """Appel HTTP direct via socket (contourne proxy Android)."""
        import re as _re
        m = _re.match(r"http://([^:/]+):(\d+)(.*)", url)
        if not m:
            return "URL invalide : " + url
        host = m.group(1)
        port = int(m.group(2))
        path = m.group(3)

        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6,
            "top_p": 0.9,
            "max_tokens": 256,
            "stream": False,
            "stop": ["\nUtilisateur :", "\nUser :"],
        }
        body = json.dumps(payload).encode("utf-8")

        try:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
            conn.request("POST", path, body=body, headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Jinx/1.0",
                "Connection": "close",
            })
            resp = conn.getresponse()
            data = resp.read().decode("utf-8")
            conn.close()

            if resp.status != 200:
                try:
                    with open("/sdcard/jinx_crash.log", "a") as f:
                        f.write("\n=== HTTP " + str(resp.status) + " ===\n")
                        f.write("URL : " + url + "\n")
                        f.write(data[:500] + "\n")
                except Exception:
                    pass
                return "Erreur HTTP " + str(resp.status)

            parsed = json.loads(data)
            return parsed["choices"][0]["message"]["content"].strip()
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            log.error("appel_llm: %s", err)
            try:
                with open("/sdcard/jinx_crash.log", "a") as f:
                    f.write("\n=== ERREUR LLM ===\n")
                    f.write("URL : " + url + "\n")
                    f.write("Erreur : " + str(e) + "\n")
                    f.write(err)
            except Exception:
                pass
            return "Erreur LLM : " + str(e)


    def handle(self, query: str,
               context: Optional[Dict[str, Any]] = None) -> str:
        contexte = self._contexte_systeme()
        prompt = self._prompt_complet(query, contexte)

        if not self.model_manager:
            return "Aucun modèle disponible."

        url = self.model_manager.ensure("default")
        if not url:
            return "Impossible de charger le modèle."

        return self._appeler_llm(prompt, url)

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
    return Director(model_manager=model_manager)
