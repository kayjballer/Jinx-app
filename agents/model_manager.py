"""agents/model_manager.py — llama-server minimal (sans flags risqués)."""
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
    try:
        return min(max(multiprocessing.cpu_count(), 2), 8)
    except Exception:
        return 4


class ModelManager:
    def __init__(self, dossier_models: str, llama_binaire: str):
        self.dossier = dossier_models
        self.binaire = llama_binaire
        self.procs: Dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()
        self._preloaded = False
        self.nb_threads = _nb_threads()
        log.info("ModelManager : %d threads", self.nb_threads)

    def chemin(self, nom: str) -> str:
        return os.path.join(self.dossier, f"{nom}.gguf")

    def est_present(self, nom: str) -> bool:
        return os.path.exists(self.chemin(nom))

    def url_pour(self, nom: str) -> str:
        port = CATALOG[nom]["port"]
        return f"http://127.0.0.1:{port}/v1/chat/completions"

    def _attendre_pret(self, port: int, timeout: int = 90) -> bool:
        url = f"http://127.0.0.1:{port}/health"
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                req = request.Request(url)
                req.add_header("User-Agent", "Jinx/1.0")
                with request.urlopen(req, timeout=2) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(1.0)
        return False

    def _cmd(self, nom: str, chemin: str, port: int) -> list:
        """Commande MINIMALE — aucun flag exotique."""
        return [
            self.binaire,
            "-m", chemin,
            "--port", str(port),
            "-c", "2048",
            "-t", str(self.nb_threads),
        ]

    def _demarrer(self, nom: str) -> bool:
        if nom in self.procs and self.procs[nom].poll() is None:
            return True
        chemin = self.chemin(nom)
        if not os.path.exists(chemin):
            log.error("Modèle %s absent : %s", nom, chemin)
            return False

        port = CATALOG[nom]["port"]
        cmd = self._cmd(nom, chemin, port)
        log.info("Démarrage %s : %s", nom, " ".join(cmd))

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.dossier,
            )
            self.procs[nom] = proc
        except Exception as e:
            log.error("Lancement %s échoué : %s", nom, e)
            return False

        ok = self._attendre_pret(port, timeout=120)
        if ok:
            log.info("Modèle %s prêt sur port %d", nom, port)
        else:
            log.error("Modèle %s timeout", nom)
            # Récupérer les logs du process mort
            try:
                out, err = proc.communicate(timeout=2)
                log.error("STDERR llama-server : %s", err.decode()[:500])
            except Exception:
                pass
        return ok

    def ensure(self, nom: str = "default") -> Optional[str]:
        with self._lock:
            if self._demarrer(nom):
                self._preloaded = True
                return self.url_pour(nom)
            return None

    def precharger(self) -> bool:
        return self.ensure("default") is not None

    def stop_all(self) -> None:
        with self._lock:
            for nom, proc in list(self.procs.items()):
                try:
                    proc.terminate()
                    proc.wait(timeout=8)
                except Exception:
                    try: proc.kill()
                    except Exception: pass
                self.procs.pop(nom, None)
            self._preloaded = False
