"""
agents/jarvis_agents.py — Agents Jarvis (alarm, calendar, media, system).
Utilise pyjnius sur Android, termux-api en fallback.
"""
from __future__ import annotations

import logging
import re
import subprocess
import time
from typing import Any, Dict, Optional

from .base import Agent, sans_accents

log = logging.getLogger("jinx.jarvis")


def _jnius():
    try:
        from jnius import autoclass
        return autoclass
    except Exception:
        return None


def _est_android() -> bool:
    try:
        from jnius import autoclass
        return True
    except Exception:
        return False


# ===========================================================================
# ALARM AGENT
# ===========================================================================
class AlarmAgent(Agent):
    name = "alarm"
    description = "Réveils, minuteurs, rappels."
    keywords = ["réveil", "reveil", "réveille", "minuteur", "minuterie",
                "rappel", "rappelle-moi", "alarme", "alarm"]
    requires_model = None

    _R = re.compile(
        r"\b(r[ée]veil|r[ée]veille[- ]moi|mets?\s+un\s+r[ée]veil|"
        r"minuteur|minuterie|chronom[èe]tre|"
        r"rappelle[- ]moi\s+(dans|à)|rappel\s+(dans|à)|"
        r"alarme|annule\s+(le\s+)?r[ée]veil|liste\s+mes\s+r[ée]veils?)\b",
        re.IGNORECASE)

    def match(self, query):
        return 0.93 if self._R.search(sans_accents(query)) else 0.0

    def _parse_heure(self, q: str) -> Optional[str]:
        """Détecte une heure : 7h, 7:30, 14h15."""
        m = re.search(r"\b(\d{1,2})\s*[h:]\s*(\d{2})?\b", q)
        if m:
            h = int(m.group(1))
            mn = int(m.group(2)) if m.group(2) else 0
            if 0 <= h <= 23 and 0 <= mn <= 59:
                return f"{h:02d}:{mn:02d}"
        return None

    def _parse_delai(self, q: str) -> Optional[int]:
        """Détecte une durée : dans 20 minutes, dans 2 heures."""
        m = re.search(
            r"dans\s+(\d+)\s*(seconde|minute|heure|sec|min|h)s?\b", q)
        if not m:
            return None
        val = int(m.group(1))
        unite = m.group(2).lower()
        if unite in ("seconde", "sec"):
            return val
        if unite in ("minute", "min"):
            return val * 60
        if unite in ("heure", "h"):
            return val * 3600
        return None

    def run(self, query, context):
        q = sans_accents(query).lower()

        # Annuler
        if "annule" in q:
            return self._annuler_tout()

        # Lister
        if "liste" in q or "quels" in q or "mes reveils" in q:
            return self._lister()

        # Délai (dans 20 minutes)
        delai = self._parse_delai(q)
        if delai:
            label = query.strip()
            ok = self._creer_minuteur(delai, label)
            if ok:
                if delai < 60:
                    return f"⏱ Minuteur de {delai}s lancé."
                if delai < 3600:
                    return f"⏱ Minuteur de {delai//60} minute(s) lancé."
                return f"⏱ Minuteur de {delai//3600}h lancé."

        # Heure fixe (réveil à 7h)
        heure = self._parse_heure(q)
        if heure:
            ok = self._creer_reveil(heure)
            if ok:
                return f"⏰ Réveil programmé à {heure}."

        return ("Dis-moi : « réveil à 7h », « rappelle-moi dans 20 minutes » "
                "ou « annule mes réveils ».")

    def _creer_reveil(self, heure: str) -> bool:
        if _est_android():
            try:
                A = _jnius()
                PythonActivity = A("org.kivy.android.PythonActivity")
                Context = A("android.content.Context")
                Intent = A("android.content.Intent")
                AlarmManager = A("android.app.AlarmManager")
                Calendar = A("java.util.Calendar")

                act = PythonActivity.mActivity
                h, m = map(int, heure.split(":"))
                cal = Calendar.getInstance()
                cal.set(Calendar.HOUR_OF_DAY, h)
                cal.set(Calendar.MINUTE, m)
                cal.set(Calendar.SECOND, 0)
                now = Calendar.getInstance()
                if cal.before(now):
                    cal.add(Calendar.DAY_OF_YEAR, 1)

                intent = Intent(Context.ALARM_SERVICE)
                pending = A("android.app.PendingIntent").getBroadcast(
                    act, 0, intent, 0)
                am = act.getSystemService(Context.ALARM_SERVICE)
                am.set(AlarmManager.RTC_WAKEUP, cal.getTimeInMillis(), pending)
                return True
            except Exception as e:
                log.error("creer_reveil: %s", e)
        # Termux fallback
        try:
            subprocess.run(["termux-notification",
                            "--title", "Réveil",
                            "--content", f"Réveil à {heure}"],
                           timeout=5)
            return True
        except Exception:
            return False

    def _creer_minuteur(self, secondes: int, label: str) -> bool:
        if _est_android():
            try:
                A = _jnius()
                PythonActivity = A("org.kivy.android.PythonActivity")
                Context = A("android.content.Context")
                Intent = A("android.content.Intent")
                AlarmManager = A("android.app.AlarmManager")

                act = PythonActivity.mActivity
                intent = Intent(Context.ALARM_SERVICE)
                pending = A("android.app.PendingIntent").getBroadcast(
                    act, 0, intent, 0)
                am = act.getSystemService(Context.ALARM_SERVICE)
                quand = int(time.time() * 1000) + secondes * 1000
                am.set(AlarmManager.RTC_WAKEUP, quand, pending)
                return True
            except Exception as e:
                log.error("creer_minuteur: %s", e)
        try:
            subprocess.Popen(["sleep", str(secondes), "&&",
                              "termux-notification",
                              "--title", "Minuteur",
                              "--content", "Terminé"])
            return True
        except Exception:
            return False

    def _annuler_tout(self) -> str:
        if _est_android():
            try:
                A = _jnius()
                PythonActivity = A("org.kivy.android.PythonActivity")
                Context = A("android.content.Context")
                Intent = A("android.content.Intent")
                act = PythonActivity.mActivity
                intent = Intent(Context.ALARM_SERVICE)
                pending = A("android.app.PendingIntent").getBroadcast(
                    act, 0, intent, 0)
                am = act.getSystemService(Context.ALARM_SERVICE)
                am.cancel(pending)
                return "✅ Réveils et minuteurs annulés."
            except Exception as e:
                log.error("annuler: %s", e)
        return "Impossible d'annuler sur cette plateforme."

    def _lister(self) -> str:
        return ("Je ne peux pas encore lister les alarmes système "
                "(nécessite une permission spéciale). Dis-moi "
                "« annule les réveils » pour les supprimer.")


# ===========================================================================
# CALENDAR AGENT
# ===========================================================================
class CalendarAgent(Agent):
    name = "calendar"
    description = "Crée et lit des événements (agenda)."
    keywords = ["événement", "evenement", "rendez-vous", "rdv", "agenda",
                "ajoute", "calendrier", "réunion", "anniversaire"]
    requires_model = None

    _R = re.compile(
        r"\b(ajoute\s+(un\s+)?(rendez[- ]vous|r[ée]v|r[ée]union|"
        r"[ée]v[ée]nement)|cr[ée]e\s+(un\s+)?(r[ée]v|[ée]v[ée]nement)|"
        r"note\s+(un\s+)?(rendez[- ]vous|r[ée]v)|"
        r"quel\s+est\s+mon\s+agenda|mon\s+agenda|"
        r"j'?ai\s+quoi\s+(aujourd'?hui|demain)|"
        r"calendrier|anniversaire)\b",
        re.IGNORECASE)

    def match(self, query):
        return 0.90 if self._R.search(sans_accents(query)) else 0.0

    def run(self, query, context):
        # Pas d'API standard sans permission WRITE_CALENDAR
        # On utilise une base locale "calendar.db"
        import os
        import sqlite3
        db = os.path.join(self.dossier, "calendar.db")
        try:
            con = sqlite3.connect(db)
            cur = con.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS events("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "titre TEXT, date TEXT, cree_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            # Extraction simple : "ajoute un rdv dentiste demain"
            titre = re.sub(
                r"(ajoute|cr[ée]e|note|un|une|le|la|rendez[- ]vous|r[ée]v|"
                r"[ée]v[ée]nement|agenda)", "", query, flags=re.IGNORECASE).strip()
            if titre:
                cur.execute("INSERT INTO events(titre, date) VALUES (?, ?)",
                            (titre[:80], "à préciser"))
                con.commit()
                con.close()
                return f"📅 Noté dans l'agenda : « {titre[:60]} »"
            con.close()
        except Exception as e:
            return f"Erreur agenda : {e}"
        return "Dis-moi : « ajoute un rendez-vous dentiste demain »."


# ===========================================================================
# MEDIA AGENT
# ===========================================================================
class MediaAgent(Agent):
    name = "media"
    description = "Contrôle le volume et la musique."
    keywords = ["volume", "musique", "son", "plus fort", "moins fort",
                "coupe", "pause", "joue"]
    requires_model = None

    _R = re.compile(
        r"\b(volume|musique|son|plus\s+fort|moins\s+fort|"
        r"monte\s+le\s+son|baisse\s+le\s+son|coupe\s+(le\s+)?(son|la\s+musique)|"
        r"mets?\s+(la\s+)?musique|pause|joue|play|met\s+la\s+musique)\b",
        re.IGNORECASE)

    def match(self, query):
        return 0.88 if self._R.search(sans_accents(query)) else 0.0

    def run(self, query, context):
        q = sans_accents(query).lower()

        if _est_android():
            try:
                A = _jnius()
                PythonActivity = A("org.kivy.android.PythonActivity")
                Context = A("android.content.Context")
                AudioManager = A("android.media.AudioManager")
                act = PythonActivity.mActivity
                am = act.getSystemService(Context.AUDIO_SERVICE)

                max_vol = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                cur_vol = am.getStreamVolume(AudioManager.STREAM_MUSIC)

                if "coupe" in q or "pause" in q:
                    am.setStreamVolume(AudioManager.STREAM_MUSIC, 0, 0)
                    return "🔇 Son coupé."
                if "plus fort" in q or "monte" in q:
                    new = min(max_vol, cur_vol + 2)
                    am.setStreamVolume(AudioManager.STREAM_MUSIC, new, 0)
                    return f"🔊 Volume augmenté ({new}/{max_vol})."
                if "moins fort" in q or "baisse" in q:
                    new = max(0, cur_vol - 2)
                    am.setStreamVolume(AudioManager.STREAM_MUSIC, new, 0)
                    return f"🔉 Volume baissé ({new}/{max_vol})."
                if "volume" in q:
                    return f"🔊 Volume actuel : {cur_vol}/{max_vol}."
                if "musique" in q or "joue" in q:
                    Intent = A("android.content.Intent")
                    ComponentName = A("android.content.ComponentName")
                    intent = Intent()
                    intent.setAction(Intent.ACTION_MAIN)
                    intent.addCategory(Intent.CATEGORY_APP_MUSIC)
                    act.startActivity(intent)
                    return "🎵 Ouverture du lecteur musique."
            except Exception as e:
                log.error("media: %s", e)
                return f"Erreur média : {e}"
        return "Le contrôle média n'est disponible que sur Android."


# ===========================================================================
# SYSTEM CONTROL AGENT
# ===========================================================================
class SystemControlAgent(Agent):
    name = "system_control"
    description = "Contrôle WiFi, Bluetooth, luminosité."
    keywords = ["wifi", "bluetooth", "luminosité", "éteins", "allume",
                "active", "désactive"]
    requires_model = None

    _R = re.compile(
        r"\b(active|d[ée]sactive|[ée]teins|allume|coupe)\s+"
        r"(le\s+|la\s+)?(wifi|wi[- ]fi|bluetooth|luminosit[ée]|"
        r"[ée]cran|mode\s+avion)\b|"
        r"\b(baisse|monte|augmente|diminue)\s+(la\s+)?luminosit[ée]\b|"
        r"\b(mode\s+avion)\b",
        re.IGNORECASE)

    def match(self, query):
        return 0.88 if self._R.search(sans_accents(query)) else 0.0

    def run(self, query, context):
        q = sans_accents(query).lower()

        if _est_android():
            try:
                A = _jnius()
                PythonActivity = A("org.kivy.android.PythonActivity")
                Context = A("android.content.Context")
                act = PythonActivity.mActivity

                # Luminosité
                if "luminosite" in q:
                    Settings = A("android.provider.Settings")
                    SettingsSystem = A("android.provider.Settings$System")
                    cur = Settings.System.getInt(
                        act.getContentResolver(),
                        SettingsSystem.SCREEN_BRIGHTNESS, 128)
                    if "baisse" in q or "diminue" in q:
                        new = max(0, cur - 60)
                    elif "monte" in q or "augmente" in q:
                        new = min(255, cur + 60)
                    else:
                        new = 128
                    Settings.System.putInt(
                        act.getContentResolver(),
                        SettingsSystem.SCREEN_BRIGHTNESS, new)
                    return f"☀️ Luminosité ajustée ({new}/255)."

                # WiFi (Android 10+ nécessite ACTION_WIFI_SETTINGS)
                if "wifi" in q or "wi-fi" in q:
                    if "désactive" in q or "eteins" in q or "coupe" in q:
                        Intent = A("android.content.Intent")
                        Intent2 = A("android.provider.Settings")
                        intent = Intent(Intent2.ACTION_WIFI_SETTINGS)
                        act.startActivity(intent)
                        return "Paramètres WiFi ouverts (Android restreint l'extinction directe)."
                    if "active" in q or "allume" in q:
                        Intent = A("android.content.Intent")
                        Intent2 = A("android.provider.Settings")
                        intent = Intent(Intent2.ACTION_WIFI_SETTINGS)
                        act.startActivity(intent)
                        return "Paramètres WiFi ouverts."

                # Bluetooth
                if "bluetooth" in q:
                    Intent = A("android.content.Intent")
                    Intent2 = A("android.provider.Settings")
                    intent = Intent(Intent2.ACTION_BLUETOOTH_SETTINGS)
                    act.startActivity(intent)
                    return "Paramètres Bluetooth ouverts."

                # Mode avion
                if "avion" in q:
                    Intent = A("android.content.Intent")
                    Intent2 = A("android.provider.Settings")
                    intent = Intent(Intent2.ACTION_AIRPLANE_MODE_SETTINGS)
                    act.startActivity(intent)
                    return "Paramètres mode avion ouverts."

            except Exception as e:
                log.error("system_control: %s", e)
                return f"Erreur contrôle système : {e}"
        return "Le contrôle système n'est disponible que sur Android."


# ===========================================================================
# FABRIQUE
# ===========================================================================
def tous_les_agents():
    return [AlarmAgent, CalendarAgent, MediaAgent, SystemControlAgent]
