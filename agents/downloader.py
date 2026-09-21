"""agents/downloader.py — Téléchargement des modèles (reprise + progression)."""
from __future__ import annotations

import hashlib
import ssl
import logging
import os
import threading
import time
from typing import Callable, Optional
from urllib import request

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()

from .models_catalog import CATALOG, total_mo

log = logging.getLogger("jinx.dl")


class ModelDownloader:
    def __init__(self, dossier_models: str):
        self.dossier = dossier_models
        os.makedirs(dossier_models, exist_ok=True)

    def chemin(self, nom: str) -> str:
        return os.path.join(self.dossier, f"{nom}.gguf")

    def _marqueur(self, nom: str) -> str:
        return self.chemin(nom) + ".done"

    def est_present(self, nom: str) -> bool:
        """Vrai si le modèle a été téléchargé ET marqué .done."""
        # 1) Marqueur .done (source de vérité)
        if os.path.exists(self._marqueur(nom)):
            return True
        # 2) Compat : fichier .gguf > 100 Mo et pas de .part en cours
        p = self.chemin(nom)
        if not os.path.exists(p):
            return False
        if os.path.exists(p + ".part"):
            return False
        # Si gros fichier, on considère OK et on marque
        taille_mo = os.path.getsize(p) / (1024 * 1024)
        if taille_mo > 100:
            try:
                open(self._marqueur(nom), "w").close()
            except Exception:
                pass
            return True
        return False

    def manquants(self) -> list:
        return [n for n in CATALOG if not self.est_present(n)]

    def telecharger(self, nom, on_progress=None, stop_flag=None) -> bool:
        info = CATALOG.get(nom)
        if not info:
            return False
        if self.est_present(nom):
            if on_progress:
                on_progress(1.0, f"{nom} déjà présent")
            return True

        dest = self.chemin(nom)
        part = dest + ".part"
        deja = os.path.getsize(part) if os.path.exists(part) else 0

        req = request.Request(info["url"])
        if deja > 0:
            req.add_header("Range", f"bytes={deja}-")

        try:
            with request.urlopen(req, timeout=30, context=_SSL_CTX) as r:
                total = int(r.headers.get("Content-Length", 0)) + deja
                mode = "ab" if deja > 0 else "wb"
                with open(part, mode) as f:
                    lus = deja
                    t0 = time.time()
                    while True:
                        if stop_flag and stop_flag.is_set():
                            return False
                        bloc = r.read(256 * 1024)
                        if not bloc:
                            break
                        f.write(bloc)
                        lus += len(bloc)
                        if on_progress and total > 0:
                            ratio = lus / total
                            vit = lus / max(1, time.time() - t0) / (1024 * 1024)
                            reste = (total - lus) / max(1, vit * 1024 * 1024)
                            eta = f"{int(reste//60)}m{int(reste%60):02d}s"
                            on_progress(ratio,
                                f"{nom} — {ratio*100:.0f}% ({vit:.1f} Mo/s, reste {eta})")
        except Exception as e:
            log.error("DL %s échoué : %s", nom, e)
            if on_progress:
                on_progress(0.0, f"Erreur {nom} : {e}")
            return False

        sha = info.get("sha256", "").strip()
        if sha:
            h = hashlib.sha256()
            with open(part, "rb") as f:
                for b in iter(lambda: f.read(1 << 20), b""):
                    h.update(b)
            if h.hexdigest().lower() != sha.lower():
                os.remove(part)
                return False

        os.rename(part, dest)
        # Marqueur .done
        try:
            open(dest + ".done", "w").close()
        except Exception:
            pass
        return True

    def telecharger_tout(self, on_progress=None, stop_flag=None) -> bool:
        manquants = self.manquants()
        if not manquants:
            if on_progress:
                on_progress(1.0, "Tous les modèles sont prêts")
            return True

        total = total_mo()
        deja = total - sum(CATALOG[n]["taille_mo"] for n in manquants)

        for i, nom in enumerate(manquants):
            info = CATALOG[nom]

            def cb(ratio, txt, i=i, nom=nom, info=info):
                global_r = (deja + sum(CATALOG[n]["taille_mo"] for n in manquants[:i])
                            + info["taille_mo"] * ratio) / total
                if on_progress:
                    on_progress(global_r, f"[{i+1}/{len(manquants)}] {txt}")

            if not self.telecharger(nom, on_progress=cb, stop_flag=stop_flag):
                return False

        if on_progress:
            on_progress(1.0, "Installation terminée")
        return True
