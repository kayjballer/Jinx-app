"""
agents/permissions.py — Système de permissions par agent.
3 niveaux : PASSIF (lecture), ACTIF (action), CRITIQUE (confirmation).
"""
from __future__ import annotations

import json
import logging
import os
from enum import Enum
from typing import Dict, Optional

log = logging.getLogger("jinx.perms")


class Niveau(str, Enum):
    PASSIF = "passif"       # 🟢 lecture seule
    ACTIF = "actif"         # 🟡 action, annoncée
    CRITIQUE = "critique"   # 🔴 action, demande confirmation


# Niveaux par défaut selon le nom de l'agent
DEFAUTS = {
    # Agents passifs (lecture)
    "time": Niveau.PASSIF,
    "math": Niveau.PASSIF,
    "dictionnaire": Niveau.PASSIF,
    "memory": Niveau.PASSIF,          # écrit dans sa propre DB, pas critique
    "code": Niveau.PASSIF,
    "conversations": Niveau.PASSIF,
    "researcher": Niveau.PASSIF,
    "system": Niveau.PASSIF,
    "echo": Niveau.PASSIF,

    # Agents actifs (modifient le tél)
    "alarm": Niveau.ACTIF,
    "media": Niveau.ACTIF,
    "calendar": Niveau.ACTIF,
    "system_control": Niveau.ACTIF,   # wifi, bluetooth, luminosité

    # Agents critiques (sensibles)
    "sms": Niveau.CRITIQUE,
    "call": Niveau.CRITIQUE,
    "location": Niveau.CRITIQUE,
}


class PermissionManager:
    """Gère les permissions par agent, persistées en JSON."""

    def __init__(self, dossier: str):
        self.dossier = dossier
        self.fichier = os.path.join(dossier, "permissions.json")
        self.niveaux: Dict[str, Niveau] = {}
        self.charger()

    def charger(self) -> None:
        """Charge depuis le JSON ou initialise avec les défauts."""
        try:
            if os.path.exists(self.fichier):
                with open(self.fichier, encoding="utf-8") as f:
                    data = json.load(f)
                for nom, val in data.items():
                    try:
                        self.niveaux[nom] = Niveau(val)
                    except ValueError:
                        log.warning("Niveau inconnu pour %s : %s", nom, val)
            # Compléter avec les défauts manquants
            for nom, niv in DEFAUTS.items():
                if nom not in self.niveaux:
                    self.niveaux[nom] = niv
        except Exception as e:
            log.error("charger: %s", e)
            self.niveaux = dict(DEFAUTS)

    def sauver(self) -> None:
        try:
            data = {nom: niv.value for nom, niv in self.niveaux.items()}
            with open(self.fichier, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error("sauver: %s", e)

    def niveau(self, agent: str) -> Niveau:
        """Retourne le niveau d'un agent."""
        return self.niveaux.get(agent, DEFAUTS.get(agent, Niveau.PASSIF))

    def set_niveau(self, agent: str, niveau: Niveau) -> None:
        self.niveaux[agent] = niveau
        self.sauver()

    def peut_executer(self, agent: str) -> tuple:
        """
        Retourne (peut_executer, besoin_confirmation, niveau).
        - PASSIF : (True, False, PASSIF)
        - ACTIF  : (True, False, ACTIF)   → annoncé
        - CRITIQUE : (False, True, CRITIQUE) → demande confirmation
        """
        niv = self.niveau(agent)
        if niv == Niveau.CRITIQUE:
            return False, True, niv
        return True, False, niv

    def liste_agents(self) -> Dict[str, str]:
        """Retourne {nom: niveau} pour l'affichage."""
        return {nom: niv.value for nom, niv in sorted(self.niveaux.items())}


# ===========================================================================
# Singleton
# ===========================================================================

_instance: Optional[PermissionManager] = None


def get_perms(dossier: str = None) -> PermissionManager:
    global _instance
    if _instance is None:
        if dossier is None:
            raise ValueError("dossier requis pour init PermissionManager")
        _instance = PermissionManager(dossier)
    return _instance
