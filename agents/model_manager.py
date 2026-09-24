"""agents/model_manager.py — llama-server optimisé pour mobile ARM."""
from __future__ import annotations

import logging
import multiprocessing
import os
import subprocess
import threading
import time
from typing import Dict, Optional
from urllib import request

from .models_catalog import CATALOG

log = logging.getLogger("jinx.models")


def _nb_threads() -> int:
    """Nombre de cœurs disponibles (max 8 pour éviter la surchauffe)."""
    try:
        n = multiprocessing.cpu_count()
        return min(max(n, 2), 8)
    except Exception:
        return 4


class ModelManager:
    """
    Gère 2 modèles (rapide 0.5B + intelligent 3B).
    Optimisé mobile : threads max, flash attention, KV cache quantifié.
    """

    def __init__(self, dossier_models: str, llama_binaire: str):
        self.dossier = dossier_models
        self.binaire = llama_binaire
        self.procs: Dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()
        self._preloaded = False
        self.nb_threads = _nb_threads()
        log.info("ModelManager : %d threads disponibles", self.nb_threads)

    def chemin(self, nom: str) -> str:
        return os.path.join(self.dossier, f"{nom}.gguf")

    def est_present(self, nom: str) -> bool:
        return os.path.exists(self.chemin(nom))

    def url_pour(self, nom: str) -> str:
        port = CATALOG[nom]["port"]
        return f"http://127.0.0.1:{port}/v1/chat/completions"

    def _attendre_pret(self, port: int, timeout: int = 60) -> bool:
        url = f"http://127.0.0.1:{port}/health"
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                with request.urlopen(url, timeout=2) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(0.8)
        return False

    def _cmd_optimisee(self, nom: str, chemin: str, port: int,
                       safe_mode: bool = False) -> list:
        """
        Construit la commande llama-server.
        Mode normal = optimisé. Mode safe = uniquement les flags basiques.
        """
        threads = self.nb_threads if nom == "intelligent" else max(2, self.nb_threads // 2)
        ctx = 1024 if nom == "rapide" else 2048

        if safe_mode:
            # Mode SAFE : uniquement les flags universels
            return [
                self.binaire,
                "-m", chemin,
                "--port", str(port),
                "-c", str(ctx),
                "-t", str(threads),
                "--log-disable",
            ]

        # Mode normal : flags optimisés mais risqués
        return [
            self.binaire,
            "-m", chemin,
            "--port", str(port),
            "-c", str(ctx),
            "-t", str(threads),
            "-b", "512",
            "-ub", "512",
            "-fa",
            "--no-warmup",
            "--log-disable",
            "--temp", "0.7",
            "--top-k", "40",
            "--top-p", "0.9",
            "--repeat-penalty", "1.1",
        ]

    def _demarrer(self, nom: str) -> bool:
        if nom in self.procs and self.procs[nom].poll() is None:
            return True
        chemin = self.chemin(nom)
        if not os.path.exists(chemin):
            log.error("Modèle %s absent : %s", nom, chemin)
            return False

        port = CATALOG[nom]["port"]

        # Tentative 1 : mode optimisé
        if self._essayer_mode(nom, chemin, port, safe=False):
            return True

        # Tentative 2 : mode SAFE (si optimisé plante)
        log.warning("Mode optimisé échoué, on retente en SAFE")
        self._arreter(nom)
        return self._essayer_mode(nom, chemin, port, safe=True)

    def _essayer_mode(self, nom: str, chemin: str, port: int,
                       safe: bool) -> bool:
        cmd = self._cmd_optimisee(nom, chemin, port, safe_mode=safe)
        mode = "SAFE" if safe else "OPTIM"
        log.info("Démarrage %s [%s] : %s", nom, mode, " ".join(cmd))

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self.dossier,
            )
            self.procs[nom] = proc
        except Exception as e:
            log.error("Lancement %s échoué : %s", nom, e)
            return False

        ok = self._attendre_pret(port, timeout=90 if nom == "intelligent" else 45)
        if ok:
            log.info("Modèle %s prêt [%s] sur port %d", nom, mode, port)
        return ok

    def _arreter(self, nom: str) -> None:
        proc = self.procs.get(nom)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self.procs.pop(nom, None)

    def precharger_rapide(self) -> bool:
        """Pré-charge le 0.5B en arrière-plan."""
        if self._preloaded:
            return True
        with self._lock:
            ok = self._demarrer("rapide")
            if ok:
                self._preloaded = True
                log.info("Modèle rapide pré-chargé")
            return ok

    def ensure(self, nom: str) -> Optional[str]:
        """S'assure que le modèle est chargé. Retourne l'URL."""
        with self._lock:
            if self._demarrer(nom):
                if nom == "rapide":
                    self._preloaded = True
                return self.url_pour(nom)
            return None

    def stop_all(self) -> None:
        with self._lock:
            for nom in list(self.procs.keys()):
                self._arreter(nom)
            self._preloaded = False
