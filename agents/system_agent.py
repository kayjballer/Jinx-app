"""
agents/system_agent.py — Agent système : répond aux questions sur le téléphone.
Niveau : 🟢 PASSIF (lecture seule, aucune action).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict

from .base import Agent, sans_accents
from .core import get_core

log = logging.getLogger("julie.system")


class SystemAgent(Agent):
    """
    Lit les infos du téléphone : batterie, WiFi, RAM, stockage, écran, avion.
    PASSIF : aucune modification, aucune permission dangereuse.
    """
    name = "system"
    description = ("Donne l'état du téléphone : batterie, WiFi, RAM, "
                   "stockage, écran allumé, mode avion.")
    keywords = ["batterie", "charge", "wifi", "ram", "mémoire", "stockage",
                "espace", "écran", "avion", "réseau", "internet"]
    requires_model = None  # Pas besoin de LLM, réponse directe

    _R_BATTERIE = re.compile(
        r"\b(batterie|charge|niveau\s+de\s+(batterie|charge)|"
        r"combien\s+de\s+batterie|autonomie|reste\s+combien|"
        r"il\s+me\s+reste)\b", re.IGNORECASE)

    _R_WIFI = re.compile(
        r"\b(wifi|wi[- ]?fi|r[ée]seau|connexion|internet|"
        r"connect[ée]\s+[àa]|ssid|suis[- ]je\s+connect)\b", re.IGNORECASE)

    _R_RAM = re.compile(
        r"\b(ram|m[ée]moire\s+(vive|libre)|combien\s+de\s+ram|"
        r"m[ée]moire\s+utilis[ée]e)\b", re.IGNORECASE)

    _R_STOCKAGE = re.compile(
        r"\b(stockage|espace\s+(libre|disque|restant)|disque|"
        r"combien\s+d'?espace|place\s+(libre|restante)|"
        r"gb\s+libres|go\s+libres)\b", re.IGNORECASE)

    _R_ECRAN = re.compile(
        r"\b([ée]cran|allum[ée]|veille|affichage|"
        r"[ée]cran\s+allum[ée])\b", re.IGNORECASE)

    _R_AVION = re.compile(
        r"\b(mode\s+avion|avion|a[ée]roport|offline)\b", re.IGNORECASE)

    _R_RESUME = re.compile(
        r"\b([ée]tat\s+(du|de\s+mon|de\s+la)|"
        r"comment\s+va\s+(mon|le)\s+(t[ée]l[ée]phone|syst[è]me)|"
        r"diagnostic|r[ée]sum[ée]\s+du\s+syst[è]me|"
        r"tout\s+va\s+bien|sant[ée]\s+du\s+t[ée]l)\b", re.IGNORECASE)

    def __init__(self, dossier: str, llm_fn=None):
        super().__init__(dossier)
        self.llm_fn = llm_fn
        self.core = get_core()

    def match(self, query: str) -> float:
        q = sans_accents(query)
        for regex in (self._R_BATTERIE, self._R_WIFI, self._R_RAM,
                      self._R_STOCKAGE, self._R_ECRAN, self._R_AVION,
                      self._R_RESUME):
            if regex.search(q):
                return 0.92
        return 0.0

    def run(self, query: str, context: Dict[str, Any]) -> str:
        q = sans_accents(query)

        # 1) Batterie
        if self._R_BATTERIE.search(q) and not self._R_RESUME.search(q):
            return self._reponse_batterie()

        # 2) WiFi
        if self._R_WIFI.search(q) and not self._R_RESUME.search(q):
            return self._reponse_wifi()

        # 3) RAM
        if self._R_RAM.search(q):
            return self._reponse_ram()

        # 4) Stockage
        if self._R_STOCKAGE.search(q):
            return self._reponse_stockage()

        # 5) Écran
        if self._R_ECRAN.search(q):
            return self._reponse_ecran()

        # 6) Mode avion
        if self._R_AVION.search(q):
            return self._reponse_avion()

        # 7) Résumé / diagnostic
        if self._R_RESUME.search(q):
            return self._reponse_resume()

        # Fallback : résumé complet
        return self._reponse_resume()

    # ===================================================================
    # RÉPONSES
    # ===================================================================

    def _reponse_batterie(self) -> str:
        b = self.core.batterie()
        n = b["niveau"]
        if n < 0:
            return "Je n'arrive pas à lire le niveau de batterie."
        etat = "en charge" if b["en_charge"] else "sur batterie"
        temp = ""
        if b["temperature"] > 0:
            temp = f", température {b['temperature']:.0f}°C"

        estimation = ""
        # Estimation autonomie (très grossière)
        if not b["en_charge"] and n >= 0:
            heures = round(n / 10, 1)  # ~10%/h en moyenne
            if heures >= 1:
                estimation = f" Environ {heures:.0f}h d'autonomie restante."

        return f"Batterie à {n}% ({etat}{temp}).{estimation}"

    def _reponse_wifi(self) -> str:
        w = self.core.wifi()
        if self.core.mode_avion():
            return "Tu es en mode avion, donc pas de connexion."
        if not w["connecte"]:
            return "Pas de connexion internet pour l'instant."
        type_reseau = w.get("type", "")
        ssid = w.get("ssid", "")
        if type_reseau == "wifi":
            if ssid:
                return f"Oui, connecté au WiFi « {ssid} »."
            return "Oui, tu es connecté en WiFi."
        if type_reseau == "cell":
            return "Oui, tu es connecté en données mobiles."
        return "Oui, tu es connecté à internet."

    def _reponse_ram(self) -> str:
        r = self.core.ram()
        if r["total_mo"] <= 0:
            return "Je n'arrive pas à lire la RAM."
        return (f"RAM : {r['libre_mo']:.0f} Mo libres sur "
                f"{r['total_mo']:.0f} Mo ({r['utilise_pct']:.0f}% utilisée).")

    def _reponse_stockage(self) -> str:
        s = self.core.stockage()
        if s["total_go"] <= 0:
            return "Je n'arrive pas à lire le stockage."
        pct = s["utilise_pct"]
        if pct > 90:
            alerte = " ⚠️ Espace très faible !"
        elif pct > 75:
            alerte = " Attention, ça se remplit."
        else:
            alerte = ""
        return (f"Stockage : {s['libre_go']:.1f} Go libres sur "
                f"{s['total_go']:.1f} Go ({pct:.0f}% utilisé).{alerte}")

    def _reponse_ecran(self) -> str:
        if self.core.ecran_allume():
            return "Oui, ton écran est allumé."
        return "Non, ton écran est éteint."

    def _reponse_avion(self) -> str:
        if self.core.mode_avion():
            return "Oui, tu es en mode avion."
        return "Non, tu n'es pas en mode avion."

    def _reponse_resume(self) -> str:
        b = self.core.batterie()
        w = self.core.wifi()
        r = self.core.ram()
        s = self.core.stockage()

        lignes = ["État du téléphone :"]
        if b["niveau"] >= 0:
            etat = "en charge" if b["en_charge"] else "sur batterie"
            lignes.append(f"• Batterie : {b['niveau']}% ({etat})")
        if w["connecte"]:
            type_reseau = w.get("type", "")
            if type_reseau == "wifi":
                ssid = w.get("ssid", "")
                label = f"WiFi{f' ({ssid})' if ssid else ''}"
            elif type_reseau == "cell":
                label = "données mobiles"
            else:
                label = "connecté"
            lignes.append(f"• Réseau : {label}")
        else:
            lignes.append("• Réseau : déconnecté")
        if r["total_mo"] > 0:
            lignes.append(f"• RAM : {r['libre_mo']:.0f} Mo libres "
                          f"({r['utilise_pct']:.0f}% utilisée)")
        if s["total_go"] > 0:
            lignes.append(f"• Stockage : {s['libre_go']:.1f} Go libres")

        return "\n".join(lignes)
