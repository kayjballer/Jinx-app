"""agents/core.py — JinxCore : lecture des capteurs du téléphone."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from typing import Any, Dict, Optional

log = logging.getLogger("jinx.core")


class JinxCore:
    def __init__(self):
        self.android = False
        self.termux = False
        self._init_backend()

    def _init_backend(self) -> None:
        try:
            from jnius import autoclass, cast
            self.autoclass = autoclass
            self.cast = cast
            self.PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self.Context = autoclass("android.content.Context")
            self.android = True
            log.info("Backend Android")
            return
        except Exception:
            pass
        try:
            if shutil.which("termux-battery-status"):
                self.termux = True
                log.info("Backend Termux")
                return
        except Exception:
            pass
        log.warning("Aucun backend")

    def batterie(self) -> Dict[str, Any]:
        if self.android:
            return self._batt_android()
        if self.termux:
            return self._batt_termux()
        return {"niveau": -1, "en_charge": False, "temperature": -1}

    def _batt_android(self) -> Dict[str, Any]:
        try:
            Intent = self.autoclass("android.content.Intent")
            IntentFilter = self.autoclass("android.content.IntentFilter")
            BatteryManager = self.autoclass("android.os.BatteryManager")
            activity = self.PythonActivity.mActivity
            intent = activity.registerReceiver(None, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            if not intent:
                return {"niveau": -1, "en_charge": False, "temperature": -1}
            level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, 100)
            status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
            temp = intent.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1)
            pct = int(level * 100 / scale) if scale > 0 else -1
            en_charge = status in (BatteryManager.BATTERY_STATUS_CHARGING,
                                   BatteryManager.BATTERY_STATUS_FULL)
            t_c = temp / 10.0 if temp > 0 else -1
            return {"niveau": pct, "en_charge": en_charge, "temperature": t_c}
        except Exception as e:
            log.warning("batt_android: %s", e)
            return {"niveau": -1, "en_charge": False, "temperature": -1}

    def _batt_termux(self) -> Dict[str, Any]:
        try:
            import json
            out = subprocess.check_output(["termux-battery-status"], timeout=5).decode()
            data = json.loads(out)
            return {"niveau": data.get("percentage", -1),
                    "en_charge": data.get("status", "").upper() == "CHARGING",
                    "temperature": data.get("temperature", -1)}
        except Exception:
            return {"niveau": -1, "en_charge": False, "temperature": -1}

    def wifi(self) -> Dict[str, Any]:
        if self.android:
            return self._wifi_android()
        if self.termux:
            return self._wifi_termux()
        return {"actif": False, "connecte": False, "ssid": ""}

    def _wifi_android(self) -> Dict[str, Any]:
        try:
            ConnectivityManager = self.autoclass("android.net.ConnectivityManager")
            NetworkCapabilities = self.autoclass("android.net.NetworkCapabilities")
            activity = self.PythonActivity.mActivity
            cm = activity.getSystemService(self.Context.CONNECTIVITY_SERVICE)
            network = cm.getActiveNetwork()
            if not network:
                return {"actif": False, "connecte": False, "ssid": ""}
            caps = cm.getNetworkCapabilities(network)
            if not caps:
                return {"actif": False, "connecte": False, "ssid": ""}
            connected = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            is_wifi = caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
            is_cell = caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)
            ssid = ""
            try:
                WifiManager = self.autoclass("android.net.wifi.WifiManager")
                wm = activity.getSystemService(self.Context.WIFI_SERVICE)
                info = wm.getConnectionInfo()
                if info:
                    ssid = (info.getSSID() or "").strip('"')
                    if ssid == "<unknown ssid>":
                        ssid = ""
            except Exception:
                pass
            return {"actif": bool(is_wifi or is_cell), "connecte": bool(connected),
                    "ssid": ssid, "type": "wifi" if is_wifi else ("cell" if is_cell else "autre")}
        except Exception as e:
            log.warning("wifi_android: %s", e)
            return {"actif": False, "connecte": False, "ssid": ""}

    def _wifi_termux(self) -> Dict[str, Any]:
        try:
            import json
            out = subprocess.check_output(["termux-wifi-connectioninfo"], timeout=5).decode()
            data = json.loads(out)
            ssid = data.get("ssid", "")
            return {"actif": bool(ssid), "connecte": bool(ssid), "ssid": ssid}
        except Exception:
            return {"actif": False, "connecte": False, "ssid": ""}

    def ram(self) -> Dict[str, float]:
        try:
            if self.android:
                ActivityManager = self.autoclass("android.app.ActivityManager")
                MemoryInfo = self.autoclass("android.app.ActivityManager$MemoryInfo")
                activity = self.PythonActivity.mActivity
                am = activity.getSystemService(self.Context.ACTIVITY_SERVICE)
                mi = MemoryInfo()
                am.getMemoryInfo(mi)
                total = mi.totalMem / (1024 * 1024)
                libre = mi.availMem / (1024 * 1024)
                pct = 100 * (1 - libre / total) if total > 0 else -1
                return {"total_mo": round(total, 1), "libre_mo": round(libre, 1),
                        "utilise_pct": round(pct, 1)}
        except Exception as e:
            log.warning("ram_android: %s", e)
        try:
            with open("/proc/meminfo") as f:
                info = {}
                for l in f:
                    parts = l.split()
                    if len(parts) >= 2:
                        info[parts[0].rstrip(":")] = int(parts[1])
            total = info.get("MemTotal", 0) / 1024
            dispo = info.get("MemAvailable", 0) / 1024
            pct = 100 * (1 - dispo / total) if total > 0 else -1
            return {"total_mo": round(total, 1), "libre_mo": round(dispo, 1),
                    "utilise_pct": round(pct, 1)}
        except Exception:
            return {"total_mo": 0, "libre_mo": 0, "utilise_pct": -1}

    def stockage(self, chemin: str = "/data") -> Dict[str, float]:
        try:
            cible = chemin if os.path.exists(chemin) else "/"
            stat = os.statvfs(cible)
            total = stat.f_blocks * stat.f_frsize
            libre = stat.f_bavail * stat.f_frsize
            pct = 100 * (1 - libre / total) if total > 0 else -1
            return {"total_go": round(total / (1024 ** 3), 2),
                    "libre_go": round(libre / (1024 ** 3), 2),
                    "utilise_pct": round(pct, 1)}
        except Exception:
            return {"total_go": 0, "libre_go": 0, "utilise_pct": -1}

    def mode_avion(self) -> bool:
        if self.android:
            try:
                Settings = self.autoclass("android.provider.Settings")
                Global = self.autoclass("android.provider.Settings$Global")
                activity = self.PythonActivity.mActivity
                val = Settings.Global.getInt(activity.getContentResolver(),
                                              Global.AIRPLANE_MODE_ON, 0)
                return val == 1
            except Exception:
                pass
        return False

    def resume(self) -> Dict[str, Any]:
        return {"batterie": self.batterie(), "wifi": self.wifi(),
                "ram": self.ram(), "stockage": self.stockage(),
                "mode_avion": self.mode_avion(), "ts": time.time()}


_instance: Optional[JinxCore] = None


def get_core() -> JinxCore:
    global _instance
    if _instance is None:
        _instance = JinxCore()
    return _instance
