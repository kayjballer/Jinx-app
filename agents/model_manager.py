"""agents/model_manager.py — Charge/décharge les modèles GGUF à la demande."""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from typing import Dict, Optional
from urllib import request

from .models_catalog import CATALOG

log = logging.getLogger("jinx.models")


class ModelManager:
    def __init__(self, dossier_models: str, llama_binaire: str, mode: str = "swap"):
        self.dossier = dossier_models
        self.binaire = llama_binaire
        self.mode = mode
        self.procs: Dict[str, subprocess.Popen] = {}
        self.actif: Optional[str] = None
        self._lock = threading.Lock()

    def chemin(self, nom: str) -> str:
        return os.path.join(self.dossier, f"{nom}.gguf")

    def est_present(self, nom: str) -> bool:
        return os.path.exists(self.chemin(nom))

    def url_pour(self, nom: str) -> str:
        port = CATALOG[nom]["port"]
        return f"http://127.0.0.1:{port}/v1/chat/completions"

    def _attendre_pret(self, port: int, timeout: int = 120) -> bool:
        url = f"http://127.0.0.1:{port}/health"
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                with request.urlopen(url, timeout=2) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(1.5)
        return False

    def _demarrer(self, nom: str) -> bool:
        if nom in self.procs and self.procs[nom].poll() is None:
            return True
        chemin = self.chemin(nom)
        if not os.path.exists(chemin):
            log.error("Modèle %s absent", nom)
            return False
        port = CATALOG[nom]["port"]
        cmd = [self.binaire, "-m", chemin,
               "--port", str(port), "-c", "4096", "-t", "4"]
        log.info("Démarrage %s sur port %d", nom, port)
        try:
            proc = subprocess.Popen(cmd,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                    cwd=self.dossier)
            self.procs[nom] = proc
        except Exception as e:
            log.error("Lancement %s échoué : %s", nom, e)
            return False
        return self._attendre_pret(port)

    def _arreter(self, nom: str) -> None:
        proc = self.procs.get(nom)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self.procs.pop(nom, None)

    def ensure(self, nom: str) -> Optional[str]:
        with self._lock:
            if self.mode == "multi":
                if self._demarrer(nom):
                    return self.url_pour(nom)
                return None
            if self.actif == nom and nom in self.procs \
                    and self.procs[nom].poll() is None:
                return self.url_pour(nom)
            if self.actif and self.actif != nom:
                log.info("Swap %s -> %s", self.actif, nom)
                self._arreter(self.actif)
                time.sleep(1.5)
            if self._demarrer(nom):
                self.actif = nom
                return self.url_pour(nom)
            return None

    def stop_all(self) -> None:
        with self._lock:
            for nom in list(self.procs.keys()):
                self._arreter(nom)
            self.actif = None
