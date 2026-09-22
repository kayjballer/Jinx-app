"""
agents/core.py — JinxCore : lecture des capteurs du téléphone.
Fonctionne sur Android (pyjnius) avec fallback Termux (termux-api).
Aucune permission dangereuse : lecture seule.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("julie.core")


# ===========================================================================
# JinxCore
# ===========================================================================

class JinxCore:
    """
    Accès unifié aux infos du téléphone.
    Méthodes : batterie(), wifi(), ram(), stockage(), app_active(), ecran(),
    mode_avion(), resume().
    """

    def __init__(self):
        self.android = False
        self.termux = False
        self._init_backend()

    def _init_backend(self) -> None:
        # 1) Android via pyjnius
        try:
            from jnius import autoclass, cast
            self.autoclass = autoclass
            self.cast = cast
            self.PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self.Context = autoclass("android.content.Context")
            self.android = True
            log.info("JinxCore : backend Android (pyjnius)")
            return
        except Exception as e:
            log.info("pyjnius indispo: %s", e)

        # 2) Termux
        try:
            if shutil.which("termux-battery-status"):
                self.termux = True
                log.info("JinxCore : backend Termux (termux-api)")
                return
        except Exception:
            pass

        log.warning("JinxCore : aucun backend, valeurs par défaut")

    # ===================================================================
    # BATTERIE
    # ===================================================================
    def batterie(self) -> Dict[str, Any]:
        """Retourne {niveau, en_charge, temperature}."""
        if self.android:
            return self._batterie_android()
        if self.termux:
            return self._batterie_termux()
        return {"niveau": -1, "en_charge": False, "temperature": -1}

    def _batterie_android(self) -> Dict[str, Any]:
        try:
            Intent = self.autoclass("android.content.Intent")
            IntentFilter = self.autoclass("android.content.IntentFilter")
            BatteryManager = self.autoclass("android.os.BatteryManager")

            activity = self.PythonActivity.mActivity
            intent = activity.registerReceiver(
                None, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            if not intent:
                return {"niveau": -1, "en_charge": False, "temperature": -1}

            level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, 100)
            status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
            temp = intent.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1)

            pct = int(level * 100 / scale) if scale > 0 else -1
            en_charge = status in (
                BatteryManager.BATTERY_STATUS_CHARGING,
                BatteryManager.BATTERY_STATUS_FULL,
            )
            t_c = temp / 10.0 if temp > 0 else -1
            return {"niveau": pct, "en_charge": en_charge, "temperature": t_c}
        except Exception as e:
            log.warning("batterie_android: %s", e)
            return {"niveau": -1, "en_charge": False, "temperature": -1}

    def _batterie_termux(self) -> Dict[str, Any]:
        try:
            import json
            out = subprocess.check_output(
                ["termux-battery-status"], timeout=5).decode()
            data = json.loads(out)
            return {
                "niveau": data.get("percentage", -1),
                "en_charge": data.get("status", "").upper() == "CHARGING",
                "temperature": data.get("temperature", -1),
            }
        except Exception as e:
            log.warning("batterie_termux: %s", e)
            return {"niveau": -1, "en_charge": False, "temperature": -1}

    # ===================================================================
    # WIFI
    # ===================================================================
    def wifi(self) -> Dict[str, Any]:
        """Retourne {actif, connecte, ssid}."""
        if self.android:
            return self._wifi_android()
        if self.termux:
            return self._wifi_termux()
        return {"actif": False, "connecte": False, "ssid": ""}

    def _wifi_android(self) -> Dict[str, Any]:
        try:
            WifiManager = self.autoclass("android.net.wifi.WifiManager")
            activity = self.PythonActivity.mActivity
            wm = activity.getSystemService(self.Context.WIFI_SERVICE)
            actif = wm.isWifiEnabled()
            info = wm.getConnectionInfo() if actif else None
            ssid = ""
            if info:
                ssid = info.getSSID() or ""
                ssid = ssid.strip('"')
            return {
                "actif": bool(actif),
                "connecte": bool(actif and ssid and ssid != "<unknown ssid>"),
                "ssid": ssid,
            }
        except Exception as e:
            log.warning("wifi_android: %s", e)
            return {"actif": False, "connecte": False, "ssid": ""}

    def _wifi_termux(self) -> Dict[str, Any]:
        try:
            out = subprocess.check_output(
                ["termux-wifi-connectioninfo"], timeout=5).decode()
            import json
            data = json.loads(out)
            ssid = data.get("ssid", "")
            return {"actif": bool(ssid), "connecte": bool(ssid), "ssid": ssid}
        except Exception as e:
            log.warning("wifi_termux: %s", e)
            return {"actif": False, "connecte": False, "ssid": ""}

    # ===================================================================
    # RAM
    # ===================================================================
    def ram(self) -> Dict[str, float]:
        """Retourne {total_mo, libre_mo, utilise_pct}."""
        try:
            if self.android:
                Runtime = self.autoclass("java.lang.Runtime")
                rt = Runtime.getRuntime()
                total = rt.totalMemory() / (1024 * 1024)
                libre = rt.freeMemory() / (1024 * 1024)
                # maxMemory = limite JVM
                maxi = rt.maxMemory() / (1024 * 1024)
                pct = 100 * (1 - libre / maxi) if maxi > 0 else -1
                return {"total_mo": round(maxi, 1),
                        "libre_mo": round(libre, 1),
                        "utilise_pct": round(pct, 1)}
        except Exception as e:
            log.warning("ram_android: %s", e)

        # Fallback Linux
        try:
            with open("/proc/meminfo") as f:
                lignes = f.readlines()
            info = {}
            for l in lignes:
                parts = l.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
            total = info.get("MemTotal", 0) / 1024
            dispo = info.get("MemAvailable", 0) / 1024
            pct = 100 * (1 - dispo / total) if total > 0 else -1
            return {"total_mo": round(total, 1),
                    "libre_mo": round(dispo, 1),
                    "utilise_pct": round(pct, 1)}
        except Exception as e:
            log.warning("ram_proc: %s", e)
            return {"total_mo": 0, "libre_mo": 0, "utilise_pct": -1}

    # ===================================================================
    # STOCKAGE
    # ===================================================================
    def stockage(self, chemin: str = "/data") -> Dict[str, float]:
        """Retourne {total_go, libre_go, utilise_pct}."""
        try:
            cible = chemin if os.path.exists(chemin) else "/"
            stat = os.statvfs(cible)
            total = stat.f_blocks * stat.f_frsize
            libre = stat.f_bavail * stat.f_frsize
            pct = 100 * (1 - libre / total) if total > 0 else -1
            return {
                "total_go": round(total / (1024 ** 3), 2),
                "libre_go": round(libre / (1024 ** 3), 2),
                "utilise_pct": round(pct, 1),
            }
        except Exception as e:
            log.warning("stockage: %s", e)
            return {"total_go": 0, "libre_go": 0, "utilise_pct": -1}

    # ===================================================================
    # APP ACTIVE
    # ===================================================================
    def app_active(self) -> str:
        """Nom du package de l'app au premier plan."""
        if self.android:
            try:
                activity = self.PythonActivity.mActivity
                UsageStatsManager = self.autoclass(
                    "android.app.usage.UsageStatsManager")
                usm = activity.getSystemService(
                    self.Context.USAGE_STATS_SERVICE)
                maintenant = int(time.time() * 1000)
                stats = usm.queryUsageStats(
                    UsageStatsManager.INTERVAL_DAILY,
                    maintenant - 60000, maintenant)
                if stats:
                    recent = max(stats, key=lambda s: s.getLastTimeUsed())
                    return recent.getPackageName()
            except Exception as e:
                log.debug("app_active: %s", e)
        return ""

    # ===================================================================
    # ÉCRAN
    # ===================================================================
    def ecran_allume(self) -> bool:
        if self.android:
            try:
                PowerManager = self.autoclass("android.os.PowerManager")
                activity = self.PythonActivity.mActivity
                pm = activity.getSystemService(self.Context.POWER_SERVICE)
                return pm.isInteractive()
            except Exception as e:
                log.debug("ecran: %s", e)
        return True

    # ===================================================================
    # MODE AVION
    # ===================================================================
    def mode_avion(self) -> bool:
        if self.android:
            try:
                Settings = self.autoclass("android.provider.Settings")
                Global = self.autoclass("android.provider.Settings$Global")
                activity = self.PythonActivity.mActivity
                val = Settings.Global.getInt(
                    activity.getContentResolver(),
                    Global.AIRPLANE_MODE_ON, 0)
                return val == 1
            except Exception as e:
                log.debug("avion: %s", e)
        return False

    # ===================================================================
    # RÉSUMÉ GLOBAL
    # ===================================================================
    def resume(self) -> Dict[str, Any]:
        """Retourne tout en un dict."""
        return {
            "batterie": self.batterie(),
            "wifi": self.wifi(),
            "ram": self.ram(),
            "stockage": self.stockage(),
            "app_active": self.app_active(),
            "ecran_allume": self.ecran_allume(),
            "mode_avion": self.mode_avion(),
            "ts": time.time(),
        }

    # ===================================================================
    # UTILITAIRES POUR LES AGENTS
    # ===================================================================
    def peut_acceder_internet(self) -> bool:
        """Wifi actif OU données mobiles."""
        w = self.wifi()
        if w["connecte"]:
            return True
        if self.mode_avion():
            return False
        # On suppose que sans mode avion + pas wifi = data mobile
        return True

    def resume_phrase(self) -> str:
        """Résumé lisible pour le LLM."""
        b = self.batterie()
        w = self.wifi()
        r = self.ram()
        s = self.stockage()
        parties = []
        if b["niveau"] >= 0:
            etat = "en charge" if b["en_charge"] else "sur batterie"
            parties.append(f"batterie {b['niveau']}% ({etat})")
        if w["connecte"]:
            parties.append(f"WiFi « {w['ssid']} »")
        elif w["actif"]:
            parties.append("WiFi allumé mais non connecté")
        else:
            parties.append("pas de WiFi")
        if r["total_mo"] > 0:
            parties.append(f"RAM {r['libre_mo']:.0f}/{r['total_mo']:.0f} Mo libre")
        if s["total_go"] > 0:
            parties.append(f"{s['libre_go']:.1f} Go libres")
        return " · ".join(parties)


# ===========================================================================
# Singleton (une seule instance dans l'app)
# ===========================================================================

_instance: Optional[JinxCore] = None


def get_core() -> JinxCore:
    global _instance
    if _instance is None:
        _instance = JinxCore()
    return _instance
