import json, threading, re, time, math, random, os, subprocess, ssl, unicodedata, shutil
from urllib import request
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.graphics import Color, Mesh, Rectangle, Line, Ellipse
from kivy.graphics.texture import Texture
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.utils import platform
try:
    from kivy.graphics import Callback
    from kivy.graphics.opengl import (glBlendFunc, GL_SRC_ALPHA, GL_ONE,
                                      GL_ONE_MINUS_SRC_ALPHA)

    def _additif(*a):
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)

    def _normal(*a):
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
except Exception:
    Callback = None
try:
    import sqlite3
except Exception:
    sqlite3 = None
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()


from agents.core import get_core
from agents import build_default_director, ModelManager, ModelDownloader
from agents.splash import afficher_splash_dl
from agents.bulle2d import Bulle2D

# --- LOGGING JINX (avant tout le reste) ---
import os as _os
import sys as _sys
import traceback as _tb
import datetime as _dt

_LOG_PATH = "/sdcard/jinx_crash.log"
if not _os.path.exists("/sdcard"):
    _LOG_PATH = _os.path.join(_os.path.expanduser("~"), "jinx_crash.log")

def _log(msg):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{_dt.datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

_log("=== JINX STARTUP ===")

# Capture globale des exceptions
def _excepthook(t, v, tb):
    _log("=== CRASH ===")
    _log("".join(_tb.format_exception(t, v, tb)))
    _sys.__excepthook__(t, v, tb)

_sys.excepthook = _excepthook
# --- FIN LOGGING ---

VERSION = "0.31"
STOP_TTS = False
_TTS_SINGLETON = {"instance": None}


def _get_tts():
    """Retourne une instance TTS UNIQUE (créée si besoin)."""
    if _TTS_SINGLETON["instance"] is None:
        try:
            _TTS_SINGLETON["instance"] = tts_java()
        except Exception:
            pass
    return _TTS_SINGLETON["instance"]


def _stop_tts():
    """Arrête immédiatement la lecture vocale."""
    global STOP_TTS
    STOP_TTS = True
    t = _get_tts()
    if t:
        try:
            t.stop()
            print("TTS arrêté")
        except Exception as e:
            print("stop TTS échoué:", e)
    # Fallback plyer
    try:
        from plyer import tts as _p
        if hasattr(_p, "stop"):
            _p.stop()
    except Exception:
        pass
URL = "http://127.0.0.1:8080/v1/chat/completions"
PROC = None

DEFAUT = {
    "silence": 1.4, "langue": "fr-FR", "voix_active": True,
    "vitesse": 1.0, "hauteur": 1.0, "voix_nom": "",
    "perso": "taquine", "longueur": "moyennes", "creativite": 0.3,
    "surnom": "", "modele": "1.5B",
    "memoire": True, "historique": True,
    "theme": "or", "halo": 1.0, "eco": False, "texte": 18,
}
SET = dict(DEFAUT)


def charger_reglages(dossier):
    fichier = os.path.join(dossier, "reglages.json")
    if os.path.exists(fichier):
        try:
            with open(fichier, encoding="utf-8") as f:
                SET.update({k: v for k, v in json.load(f).items() if k in DEFAUT})
        except Exception:
            pass
    else:
        try:
            g3 = os.path.join(dossier, "qwen3b.gguf")
            if os.path.exists(g3) and os.path.getsize(g3) > 1850000000:
                SET["modele"] = "3B"
        except Exception:
            pass


def sauver_reglages(dossier):
    try:
        with open(os.path.join(dossier, "reglages.json"), "w", encoding="utf-8") as f:
            json.dump(SET, f)
    except Exception:
        pass


PERSO = {
    "taquine": "Tu es Jinx, une assistante vocale un peu taquine. ",
    "serieuse": "Tu es Jinx, une assistante vocale calme et sérieuse. ",
    "pro": "Tu es Jinx, une assistante vocale professionnelle, précise et sans blagues. ",
    "coach": "Tu es Jinx, une coach sportive motivante et pleine d'énergie. ",
}
EXEMPLES = {
    "taquine": [
        {"role": "user", "content": "Qui es-tu ?"},
        {"role": "assistant", "content": "Moi, c'est Jinx, ton assistante vocale. Un peu chipie, mais toujours là pour toi !"},
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Salut toi ! Alors, on a besoin de moi ?"}],
    "serieuse": [
        {"role": "user", "content": "Qui es-tu ?"},
        {"role": "assistant", "content": "Je suis Jinx, ton assistante vocale. Je réponds à tes questions avec calme et clarté."},
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Bonjour. Comment puis-je t'aider ?"}],
    "pro": [
        {"role": "user", "content": "Qui es-tu ?"},
        {"role": "assistant", "content": "Je suis Jinx, ton assistante vocale. Je donne des réponses claires et précises."},
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Bonjour. Que puis-je faire pour toi ?"}],
    "coach": [
        {"role": "user", "content": "Qui es-tu ?"},
        {"role": "assistant", "content": "Je suis Jinx, ta coach ! On va se dépasser ensemble !"},
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Salut champion ! Prêt à tout donner aujourd'hui ?"}],
}
LONG = {
    "courtes": (80, "Tu réponds en une seule phrase courte."),
    "moyennes": (150, "Tu réponds en une ou deux phrases courtes."),
    "longues": (320, "Tu réponds en trois à cinq phrases."),
}
STOP = set(("le la les un une des de du et ou au aux en dans sur pour par "
            "avec sans que qui quoi quel quelle est es suis sont ai as avons "
            "ont mon ma mes ton ta tes son sa ses je tu il elle nous vous ils "
            "elles me te se ce cet cette ces ne pas plus tres bien alors donc "
            "mais si comme tout tous fait faire peux peut veux veut dis dit "
            "jinx hey salut bonjour oui non cela ceci").split())
CONFIRM = {"oubli": False}


def corriger(t):
    return re.sub(r"\b(jenkins|jinks|gingks|jean x|djinx|ginx|gynx)\b",
                  "Jinx", t, flags=re.I)


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def mots(s):
    out = set()
    for w in re.findall(r"[a-z0-9]+", norm(s)):
        if len(w) < 3 or w in STOP:
            continue
        if len(w) > 3 and w[-1] in "sx":
            w = w[:-1]
        out.add(w)
    return out


def db(dossier):
    if sqlite3 is None:
        return None
    c = sqlite3.connect(os.path.join(dossier, "jinx.db"), timeout=5)
    c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, role TEXT, contenu TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS faits (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, contenu TEXT)")
    return c


def enregistrer(dossier, question, reponse):
    c = db(dossier)
    if c is None:
        return
    try:
        now = time.time()
        c.execute("INSERT INTO messages (ts, role, contenu) VALUES (?, 'user', ?)", (now, question))
        c.execute("INSERT INTO messages (ts, role, contenu) VALUES (?, 'assistant', ?)", (now, reponse))
        c.commit()
    finally:
        c.close()


def _tu(pat, new):
    def f(m):
        return new[0].upper() + new[1:] if m.group(0)[0].isupper() else new
    return (re.compile(pat, re.I), f)


TU = [_tu(r"\bje m['’]appelle\b", "tu t'appelles"),
      _tu(r"\bje suis\b", "tu es"),
      _tu(r"\bj['’]ai\b", "tu as"),
      _tu(r"\bmon\b", "ton"), _tu(r"\bma\b", "ta"), _tu(r"\bmes\b", "tes"),
      _tu(r"\bmoi\b", "toi"), _tu(r"\bm['’]", "t'")]


def en_tu(t):
    for rx, f in TU:
        t = rx.sub(f, t)
    return t


def contexte_memoire(dossier, question):
    c = db(dossier)
    if c is None:
        return "", []
    notes, souvenirs, hist = [], [], []
    try:
        cle = mots(question)
        if SET["memoire"]:
            faits = [f[0] for f in c.execute("SELECT contenu FROM faits ORDER BY id DESC LIMIT 200")]
            notes = faits[:3]
            classes = sorted(faits, key=lambda x: len(cle & mots(x)), reverse=True)
            for x in classes[:4]:
                if len(cle & mots(x)) >= 1 and x not in notes:
                    notes.append(x)
        if SET["historique"]:
            rows = c.execute("SELECT id, role, contenu FROM messages ORDER BY id DESC LIMIT 6").fetchall()
            rows.reverse()
            hist = [{"role": r[1], "content": r[2][:300]} for r in rows]
            recents = set(r[0] for r in rows)
            if SET["memoire"] and cle:
                cand = []
                for mid, txt in c.execute("SELECT id, contenu FROM messages WHERE role='user' ORDER BY id DESC LIMIT 400").fetchall():
                    if mid in recents:
                        continue
                    sc = len(cle & mots(txt))
                    if sc >= min(2, len(cle)):
                        cand.append((sc, mid, txt))
                cand.sort(reverse=True)
                for sc, mid, txt in cand[:2]:
                    r2 = c.execute("SELECT contenu FROM messages WHERE id=? AND role='assistant'", (mid + 1,)).fetchone()
                    souvenirs.append((txt, r2[0] if r2 else ""))
    finally:
        c.close()
    extra = ""
    if notes:
        extra += ("\nVoici ce que l'utilisateur t'a demandé de retenir "
                  "(tu lui parles, donc dis ta, ton, tes, tu ou toi, jamais ma ou mon) :\n"
                  + "\n".join("- " + en_tu(n) for n in notes))
    if souvenirs:
        extra += "\nSouvenirs de conversations passées :\n" + "\n".join(
            "- Il disait : %s | Tu répondais : %s" % (a[:150], b[:150])
            for a, b in souvenirs)
    if extra:
        extra += "\nUtilise ces informations seulement si elles aident à répondre."
    return extra, hist


def commande_memoire(dossier, texte):
    c = db(dossier)
    if c is None:
        return None
    try:
        base = texte.strip().rstrip(" .!?")
        t = norm(base)
        if CONFIRM["oubli"]:
            CONFIRM["oubli"] = False
            if t.startswith("oui"):
                c.execute("DELETE FROM faits")
                c.execute("DELETE FROM messages")
                c.commit()
                return "C'est fait, j'ai tout oublié. On repart de zéro."
            return "D'accord, je garde tout."
        if re.match(r"(?:jinx[ ,]*)?(?:oublie|efface)\s+(?:tout|ta memoire|toute ta memoire|tes souvenirs|tout ce que tu sais)$", t):
            CONFIRM["oubli"] = True
            return "Tu es sûr de vouloir que j'oublie tout ? Dis oui pour confirmer."
        m = re.match(r"(?:jinx[ ,]*)?(?:retiens|memorise|souviens[- ]toi|rappelle[- ]toi|n.?oublie pas)\s+(?:bien\s+)?(?:que\s+|qu.?)?(.+)$", t)
        if m:
            fait = base[m.start(1):].strip()
            if not fait:
                return None
            fait = fait[0].upper() + fait[1:]
            deja = [f[0] for f in c.execute("SELECT contenu FROM faits")]
            if any(norm(x) == norm(fait) for x in deja):
                return "Oui, je le savais déjà."
            c.execute("INSERT INTO faits (ts, contenu) VALUES (?, ?)", (time.time(), fait[:300]))
            c.commit()
            rep = "C'est noté : " + en_tu(fait) + "."
            if not SET["memoire"]:
                rep += " Mais ma mémoire est désactivée dans les paramètres."
            return rep
        if re.search(r"(qu.?est.?ce que tu (?:sais|retiens)|que sais.?tu|dis.?moi ce que tu (?:sais|retiens)|de quoi tu te souviens)", t):
            lignes = [f[0] for f in c.execute("SELECT contenu FROM faits ORDER BY id DESC LIMIT 8")]
            if not lignes:
                return "Je ne sais encore rien sur toi. Dis-moi retiens que, puis ce que tu veux que je retienne."
            return "Voici ce que je retiens : " + ". ".join(en_tu(x) for x in lignes) + "."
        if re.match(r"(?:jinx[ ,]*)?(?:annule|oublie (?:ca|cela)|efface (?:ca|cela)|oublie le dernier(?: souvenir)?)$", t):
            dern = c.execute("SELECT id FROM faits ORDER BY id DESC LIMIT 1").fetchone()
            if dern:
                c.execute("DELETE FROM faits WHERE id=?", (dern[0],))
                c.commit()
                return "C'est annulé, j'ai effacé le dernier souvenir."
            return "Je n'ai rien à annuler."
        m = re.match(r"(?:jinx[ ,]*)?(?:oublie|efface)\s+(?:que\s+|qu.?)?(.+)$", t)
        if m:
            cle = mots(m.group(1))
            if not cle:
                return "Tu veux que j'oublie quoi exactement ?"
            seuil = max(1, (len(cle) + 1) // 2)
            n = 0
            for fid, txt in c.execute("SELECT id, contenu FROM faits").fetchall():
                if len(cle & mots(txt)) >= seuil:
                    c.execute("DELETE FROM faits WHERE id=?", (fid,))
                    n += 1
            for mid, txt in c.execute("SELECT id, contenu FROM messages WHERE role='user'").fetchall():
                if len(cle & mots(txt)) >= seuil:
                    c.execute("DELETE FROM messages WHERE id=?", (mid,))
                    c.execute("DELETE FROM messages WHERE id=? AND role='assistant'", (mid + 1,))
                    n += 1
            c.commit()
            if n:
                return "C'est oublié, j'ai effacé %d souvenir%s." % (n, "s" if n > 1 else "")
            return "Je ne trouve rien à oublier là-dessus."
        return None
    finally:
        c.close()


def demander_ia(question, ctx=("", [])):
    extra, hist = ctx
    maxtok, consigne = LONG.get(SET["longueur"], LONG["moyennes"])
    systeme = (PERSO.get(SET["perso"], PERSO["taquine"])
               + "Tu parles français et tu tutoies. " + consigne
               + " Si tu ne sais pas, tu le dis.")
    if SET["surnom"]:
        systeme += " Tu appelles l'utilisateur " + SET["surnom"] + "."
    systeme += extra
    exemples = EXEMPLES.get(SET["perso"], EXEMPLES["taquine"])
    msgs = ([{"role": "system", "content": systeme}]
            + (exemples if len(hist) < 2 else [])
            + hist + [{"role": "user", "content": question}])
    data = json.dumps({"messages": msgs, "max_tokens": maxtok,
                       "temperature": float(SET["creativite"])}).encode()
    req = request.Request(URL, data=data,
                          headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=180) as r:
        rep = json.loads(r.read())
    return rep["choices"][0]["message"]["content"].strip()


_TTS = None


def tts_java():
    global _TTS
    if _TTS is None:
        from jnius import autoclass
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        cls = autoclass("android.speech.tts.TextToSpeech")
        _TTS = cls(act, None)
    return _TTS


def voix_disponibles():
    try:
        t = tts_java()
        out = []
        it = t.getVoices().iterator()
        while it.hasNext():
            v = it.next()
            if v.getLocale().toString().lower().startswith("fr"):
                out.append(v.getName())
        return sorted(out)
    except Exception:
        return []


def parler_texte(texte, force=False):
    global STOP_TTS
    STOP_TTS = False
    if not (SET["voix_active"] or force):
        return
    if platform == "android":
        try:
            from jnius import autoclass
            t = _get_tts()
            if SET["voix_nom"]:
                it = t.getVoices().iterator()
                while it.hasNext():
                    v = it.next()
                    if v.getName() == SET["voix_nom"]:
                        t.setVoice(v)
                        break
            else:
                t.setLanguage(autoclass("java.util.Locale").FRENCH)
            t.setSpeechRate(float(SET["vitesse"]))
            t.setPitch(float(SET["hauteur"]))
            if t.speak(texte, 0, None, None) == 0:
                return
        except Exception:
            pass
    try:
        from plyer import tts
        tts.speak(texte)
    except Exception:
        pass


MODELES = {
    "1.5B": {
        "fichier": "rapide.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "mini": 100000000,
        "total": 500000000,
    },
    "3B": {
        "fichier": "intelligent.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        "mini": 1800000000,
        "total": 2200000000,
    },
}


def serveur_pret():
    try:
        with request.urlopen("http://127.0.0.1:8080/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def arreter_cerveau():
    global PROC
    if PROC is not None:
        try:
            PROC.terminate()
            PROC.wait(timeout=10)
        except Exception:
            try:
                PROC.kill()
            except Exception:
                pass
        PROC = None
    for _ in range(20):
        if not serveur_pret():
            break
        time.sleep(0.5)


def supprimer_modele(dossier, cle):
    f = os.path.join(dossier, MODELES[cle]["fichier"])
    for p in (f, f + ".part"):
        try:
            os.remove(p)
        except Exception:
            pass


def espace_txt(dossier):
    def mo(p):
        try:
            return os.path.getsize(p) / 1e6
        except Exception:
            return 0.0
    m15 = mo(os.path.join(dossier, MODELES["1.5B"]["fichier"]))
    m3 = mo(os.path.join(dossier, MODELES["3B"]["fichier"]))
    bd = mo(os.path.join(dossier, "jinx.db"))
    try:
        libre = shutil.disk_usage(dossier).free / 1e9
    except Exception:
        libre = 0.0
    return "Modèle 1,5B : %d Mo · Modèle 3B : %d Mo\nBase : %.1f Mo · Libre : %.1f Go" % (m15, m3, bd, libre)


def cpu_features():
    try:
        with open("/proc/cpuinfo") as f:
            for l in f:
                if l.lower().startswith("features"):
                    return l.strip()[:300]
    except Exception as e:
        return str(e)
    return ""


def lancer_cerveau(dossier, statut):
    global PROC
    if serveur_pret():
        return True
    if platform != "android":
        statut("Pas de serveur : lance llama-server")
        return False
    from jnius import autoclass
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    binaire = act.getApplicationInfo().nativeLibraryDir + "/libllama_server.so"
    if not os.path.exists(binaire):
        statut("Serveur IA absent de l APK")
        return False
    mod = MODELES.get(SET["modele"], MODELES["3B"])
    modele = os.path.join(dossier, mod["fichier"])
    if not os.path.exists(modele) or os.path.getsize(modele) < mod["mini"]:
        tmp = modele + ".part"
        reprise = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        en_tetes = {"User-Agent": "Jinx"}
        if reprise:
            en_tetes["Range"] = "bytes=%d-" % reprise
        req = request.Request(mod["url"], headers=en_tetes)
        with request.urlopen(req, timeout=60, context=CTX) as r:
            if r.status != 206:
                reprise = 0
            total = reprise + int(r.headers.get("Content-Length") or mod["total"])
            fait = reprise
            dernier = 0
            with open(tmp, "ab" if reprise else "wb") as f:
                while True:
                    bloc = r.read(1 << 20)
                    if not bloc:
                        break
                    f.write(bloc)
                    fait += len(bloc)
                    if time.time() - dernier > 1:
                        dernier = time.time()
                        statut("Telechargement du cerveau : %d %%" % (fait * 100 // total))
        if os.path.getsize(tmp) < mod["mini"]:
            statut("Telechargement incomplet, touche la bulle pour reprendre")
            return False
        os.replace(tmp, modele)
    try:
        t = subprocess.run([binaire, "--version"], capture_output=True,
                           text=True, timeout=30)
        if t.returncode != 0:
            statut("Binaire KO, code %s\n%s" % (t.returncode, (t.stdout + t.stderr)[-300:] + " " + cpu_features()))
            return False
    except Exception as e:
        statut("Binaire impossible a lancer : %s" % e)
        return False
    log = open(os.path.join(dossier, "serveur.log"), "w")
    PROC = subprocess.Popen(
        [binaire, "-m", modele, "--host", "127.0.0.1", "--port", "8080",
         "-c", "2048", "-t", "4"],
        stdout=log, stderr=subprocess.STDOUT)
    statut("Chargement du cerveau...")
    for _ in range(180):
        if serveur_pret():
            return True
        if PROC.poll() is not None:
            try:
                with open(os.path.join(dossier, "serveur.log")) as lf:
                    fin = lf.read()[-500:]
            except Exception as e:
                fin = str(e)
            statut("Serveur arrete, code %s\n%s" % (PROC.returncode, fin))
            return False
        time.sleep(1)
    statut("Le serveur ne repond pas")
    return False


PALETTES = {
    "or": {"veille": (1.00, 0.70, 0.15), "ecoute": (1.00, 0.86, 0.38),
           "reflexion": (1.00, 0.52, 0.10), "parle": (1.00, 0.78, 0.22)},
    "bleu": {"veille": (0.15, 0.65, 1.00), "ecoute": (0.40, 0.85, 1.00),
             "reflexion": (0.55, 0.40, 1.00), "parle": (0.30, 0.75, 1.00)},
    "vert": {"veille": (0.15, 0.85, 0.40), "ecoute": (0.45, 1.00, 0.60),
             "reflexion": (0.70, 0.90, 0.20), "parle": (0.30, 0.95, 0.55)},
    "rouge": {"veille": (1.00, 0.25, 0.20), "ecoute": (1.00, 0.50, 0.40),
              "reflexion": (1.00, 0.15, 0.40), "parle": (1.00, 0.40, 0.25)},
}
ETATS = {
    "veille": dict(vit=0.22, amp=0.025, freq=1.1, halo=0.35, hamp=0.10,
                   onde=0.05, rate=0.25),
    "ecoute": dict(vit=0.50, amp=0.050, freq=3.0, halo=0.55, hamp=0.20,
                   onde=0.45, rate=0.50),
    "reflexion": dict(vit=1.50, amp=0.050, freq=5.0, halo=0.60, hamp=0.30,
                      onde=0.55, rate=0.90),
    "parle": dict(vit=0.45, amp=0.080, freq=6.0, halo=0.75, hamp=0.45,
                  onde=0.70, rate=0.70),
}


def texture_douce(n=64):
    c = (n - 1) / 2.0
    buf = bytearray()
    for y in range(n):
        for x in range(n):
            d = math.hypot(x - c, y - c) / c
            a = max(0.0, 1.0 - d)
            a = a * a * (3 - 2 * a)
            buf += bytes((255, 255, 255, int(255 * a)))
    tex = Texture.create(size=(n, n), colorfmt="rgba")
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    tex.mag_filter = "linear"
    tex.min_filter = "linear"
    return tex


def quads(m):
    return [i for q in range(m)
            for i in (4 * q, 4 * q + 1, 4 * q + 2, 4 * q, 4 * q + 2, 4 * q + 3)]


def unit(v):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / l, v[1] / l, v[2] / l)


def alea3():
    return unit([random.gauss(0, 1) for _ in range(3)])


class Bulle(Widget):
    def __init__(self, on_tap, **kw):
        super().__init__(**kw)
        self.on_tap = on_tap
        self.etat = "veille"
        self.theme = "or"
        self.halo_mult = 1.0
        self.t = 0.0
        self.ay = 0.0
        self.ax = 0.35
        self.ph_onde = 0.0
        self._ev = None
        self.p = dict(vit=0.22, amp=0.025, halo=0.35, hamp=0.10, onde=0.05,
                      rate=0.25, r=1.0, g=0.70, b=0.15)
        random.seed(11)
        tex = texture_douce()
        n0 = 150
        gold = math.pi * (3 - math.sqrt(5))
        self.pts = []
        self.tai = []
        for i in range(n0):
            y = 1 - 2 * (i + 0.5) / n0
            r = math.sqrt(1 - y * y)
            th = gold * i
            k = random.uniform(0.80, 1.06)
            self.pts.append((math.cos(th) * r * k, y * k, math.sin(th) * r * k))
            self.tai.append(random.uniform(0.6, 1.3))
        for i in range(40):
            u = alea3()
            k = random.uniform(1.10, 1.40)
            self.pts.append((u[0] * k, u[1] * k, u[2] * k))
            self.tai.append(random.uniform(0.35, 0.70))
        self.n0 = n0
        self.n = len(self.pts)
        self.ph = [random.uniform(0, 6.28) for _ in range(self.n)]
        idx = []
        for i in range(n0):
            for j in range(i + 1, n0):
                dx = self.pts[i][0] - self.pts[j][0]
                dy = self.pts[i][1] - self.pts[j][1]
                dz = self.pts[i][2] - self.pts[j][2]
                if dx * dx + dy * dy + dz * dz < 0.15:
                    idx += [i, j]
        self.bok = []
        self.bokt = []
        for i in range(9):
            u = alea3()
            k = random.uniform(0.45, 1.15)
            self.bok.append((u[0] * k, u[1] * k, u[2] * k))
            self.bokt.append(random.uniform(0.8, 1.6))
        self.stk = []
        for i in range(30):
            u = alea3()
            k = random.uniform(0.75, 1.30)
            a = (u[0] * k, u[1] * k, u[2] * k)
            w = [random.gauss(0, 1) for _ in range(3)]
            d = w[0] * u[0] + w[1] * u[1] + w[2] * u[2]
            tg = unit([w[0] - u[0] * d, w[1] - u[1] * d, w[2] - u[2] * d])
            ln = random.uniform(0.10, 0.28)
            self.stk.append((a, (a[0] + tg[0] * ln, a[1] + tg[1] * ln,
                                 a[2] + tg[2] * ln)))
        self.anneaux = []
        self.vit_an = (1.0, -0.7, 0.55)
        for (tx, tz, rr) in ((0.0, 0.0, 1.0), (1.05, 0.5, 1.12),
                             (-0.8, 1.1, 0.92)):
            base = []
            for q in range(72):
                a = 2 * math.pi * q / 72
                x, y, z = math.cos(a) * rr, 0.0, math.sin(a) * rr
                y1 = y * math.cos(tx) - z * math.sin(tx)
                z1 = y * math.sin(tx) + z * math.cos(tx)
                x2 = x * math.cos(tz) - y1 * math.sin(tz)
                y2 = x * math.sin(tz) + y1 * math.cos(tz)
                base.append((x2, y2, z1))
            self.anneaux.append(base)
        ns = len(self.stk)
        with self.canvas:
            if Callback:
                Callback(_additif)
            self.c_halo = Color(1, 0.7, 0.15, 0.35)
            self.r_halo = Rectangle(texture=tex, pos=(0, 0), size=(1, 1))
            self.c_ondes = []
            self.l_ondes = []
            for i in range(3):
                self.c_ondes.append(Color(1, 0.7, 0.15, 0))
                self.l_ondes.append(Line(circle=(0, 0, 1), width=dp(1.2)))
            self.c_res = Color(1, 0.7, 0.15, 0.14)
            self.m_res = Mesh(vertices=[0, 0, 0, 0] * n0, indices=idx,
                              mode="lines")
            self.c_an = Color(1, 0.7, 0.15, 0.6)
            self.l_an = [Line(points=[0, 0, 0, 0], width=dp(1.1))
                         for _ in self.anneaux]
            self.c_stk = Color(1, 0.8, 0.3, 0.6)
            self.m_stk = Mesh(vertices=[0, 0, 0, 0] * (2 * ns),
                              indices=list(range(2 * ns)), mode="lines")
            self.c_bok = Color(1, 0.7, 0.15, 0.12)
            self.m_bok = Mesh(vertices=[0, 0, 0, 0] * 36, indices=quads(9),
                              mode="triangles", texture=tex)
            self.c_p = Color(1, 0.9, 0.5, 0.95)
            self.m_p = Mesh(vertices=[0, 0, 0, 0] * (4 * self.n),
                            indices=quads(self.n), mode="triangles",
                            texture=tex)
            self.c_noy = Color(1, 0.9, 0.5, 0.6)
            self.r_noy = Rectangle(texture=tex, pos=(0, 0), size=(1, 1))
            self.c_arcs = Color(1, 0.9, 0.5, 0.85)
            self.l_arcs = [Line(circle=(0, 0, 1, 0, 90), width=dp(1.4))
                           for _ in range(3)]
            if Callback:
                Callback(_normal)
        self.set_fps(20)

    def set_fps(self, fps):
        if self._ev is not None:
            self._ev.cancel()
        self._ev = Clock.schedule_interval(self.maj, 1.0 / fps)

    def set_etat(self, e):
        self.etat = e

    def rayon(self):
        return min(self.width, self.height) * 0.36

    def maj(self, dt):
        self.t += dt
        t = self.t
        e = ETATS[self.etat]
        p = self.p
        k = min(1.0, dt * 3)
        for c in ("vit", "amp", "halo", "hamp", "onde", "rate"):
            p[c] += (e[c] - p[c]) * k
        pal = PALETTES.get(self.theme, PALETTES["or"])
        for c, v in zip("rgb", pal[self.etat]):
            p[c] += (v - p[c]) * k
        r, g, b = p["r"], p["g"], p["b"]
        hm = self.halo_mult
        self.ay += p["vit"] * dt
        self.ph_onde += p["rate"] * dt
        cx, cy = self.center_x, self.center_y
        base = self.rayon()
        if self.etat == "parle":
            env = abs(math.sin(t * 7.3) * math.sin(t * 3.1 + 1.0) * 0.6
                      + math.sin(t * 11.7) * 0.4) * 1.4
            env = min(1.0, env)
        else:
            env = 0.5 + 0.5 * math.sin(t * e["freq"])
        R = base * (1 + p["amp"] * (2 * env - 1))
        hs = base * (2.4 + 2.2 * p["hamp"] * env)
        self.c_halo.rgba = (r, g * 0.92, b * 0.85,
                            min(1.0, p["halo"] * hm * (0.55 + 0.45 * env)))
        self.r_halo.pos = (cx - hs, cy - hs)
        self.r_halo.size = (2 * hs, 2 * hs)
        for i in range(3):
            ph = (self.ph_onde + i / 3.0) % 1.0
            self.c_ondes[i].rgba = (r, g, b, min(1.0, p["onde"] * hm * (1 - ph) ** 1.6))
            self.l_ondes[i].circle = (cx, cy, R * (1.05 + 1.1 * ph))
        cay, say = math.cos(self.ay), math.sin(self.ay)
        cax, sax = math.cos(self.ax), math.sin(self.ax)

        def proj(x, y, z):
            x1 = x * cay + z * say
            z1 = -x * say + z * cay
            y2 = y * cax - z1 * sax
            z2 = y * sax + z1 * cax
            s = 1 + z2 * 0.2
            return cx + x1 * R * s, cy + y2 * R * s, z2

        u1 = dp(6)
        vs = []
        res = []
        for i in range(self.n):
            x, y, z = self.pts[i]
            px, py, z2 = proj(x, y, z)
            h = (u1 * self.tai[i] * max(0.3, 0.7 + 0.35 * z2)
                 * (0.85 + 0.15 * math.sin(t * 2.5 + self.ph[i])))
            vs += [px - h, py - h, 0, 0, px + h, py - h, 1, 0,
                   px + h, py + h, 1, 1, px - h, py + h, 0, 1]
            if i < self.n0:
                res += [px, py, 0, 0]
        self.m_p.vertices = vs
        self.m_res.vertices = res
        bv = []
        for i in range(9):
            x, y, z = self.bok[i]
            px, py, z2 = proj(x, y, z)
            h = R * 0.08 * self.bokt[i]
            bv += [px - h, py - h, 0, 0, px + h, py - h, 1, 0,
                   px + h, py + h, 1, 1, px - h, py + h, 0, 1]
        self.m_bok.vertices = bv
        sv = []
        for (pa, pb) in self.stk:
            ax_, ay_, _ = proj(*pa)
            bx_, by_, _ = proj(*pb)
            sv += [ax_, ay_, 0, 0, bx_, by_, 0, 0]
        self.m_stk.vertices = sv
        for j in range(3):
            pts = self.anneaux[j]
            st = int(t * self.vit_an[j] * 12) % 72
            lst = []
            for q in range(46):
                x, y, z = pts[(st + q) % 72]
                px, py, _ = proj(x, y, z)
                lst += [px, py]
            self.l_an[j].points = lst
        self.c_res.rgba = (r, g, b, 0.14)
        self.c_an.rgba = (r, g, b, 0.6)
        self.c_stk.rgba = (r, min(1, g + 0.12), min(1, b + 0.15),
                           0.3 + 0.35 * (0.5 + 0.5 * math.sin(t * 9)))
        self.c_bok.rgba = (r, g * 0.9, b, 0.10 + 0.06 * env)
        self.c_p.rgba = (min(1, r + 0.05), min(1, g + 0.15),
                         min(1, b + 0.3), 0.95)
        ch = R * (0.32 + 0.10 * env)
        self.c_noy.rgba = (min(1, r + 0.05), min(1, g + 0.2),
                           min(1, b + 0.35), 0.5 + 0.4 * env)
        self.r_noy.pos = (cx - ch, cy - ch)
        self.r_noy.size = (2 * ch, 2 * ch)
        self.c_arcs.rgba = (min(1, r + 0.05), min(1, g + 0.2),
                            min(1, b + 0.35), 0.85)
        for j, (rad, span, sp_) in enumerate(((0.10, 250, 1.0),
                                              (0.17, 200, -1.4),
                                              (0.25, 300, 0.7))):
            a0 = (t * sp_ * 60 * (1 + p["vit"])) % 360
            self.l_arcs[j].circle = (cx, cy, R * rad, a0, a0 + span)

    def on_touch_down(self, touch):
        dx = touch.x - self.center_x
        dy = touch.y - self.center_y
        if dx * dx + dy * dy < (self.rayon() * 1.3) ** 2:
            self.on_tap()
            return True
        return super().on_touch_down(touch)


class BoutonPoints(Widget):
    def __init__(self, action, **kw):
        super().__init__(**kw)
        self.action = action
        self.couleur = (1, 0.75, 0.25, 0.9)
        self.bind(pos=self.dessiner, size=self.dessiner)
        self.dessiner()

    def dessiner(self, *a):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        r = dp(4)
        with self.canvas:
            Color(*self.couleur)
            for k in (-1, 0, 1):
                Ellipse(pos=(cx - r, cy + k * dp(13) - r), size=(2 * r, 2 * r))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.action()
            return True
        return super().on_touch_down(touch)


def trouver_llama_server(dossier):
    """Trouve llama-server : user_data, nativeLibraryDir ou PATH.
    Copie dans user_data/llama-server avec chmod +x si nécessaire."""
    import shutil, stat
    cible = os.path.join(dossier, "llama-server")

    # 1) Déjà dans user_data ?
    if os.path.exists(cible) and os.access(cible, os.X_OK):
        return cible

    # 2) Dossier natif Android (libllama_server.so packagé par Buildozer)
    candidats = []
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        info = PythonActivity.mActivity.getApplicationInfo()
        natif = info.nativeLibraryDir
        candidats.append(os.path.join(natif, "libllama_server.so"))
    except Exception as e:
        print("nativeLibraryDir indispo:", e)

    # 3) Autres chemins possibles
    candidats += [
        "/data/data/org.jinx.jinx/files/llama-server",
        "/data/data/com.jinx/files/llama-server",
        os.path.join(dossier, "lib", "libllama_server.so"),
    ]

    for c in candidats:
        if os.path.exists(c):
            try:
                shutil.copy2(c, cible)
                os.chmod(cible, 0o755)
                print("llama-server copié depuis", c)
                return cible
            except Exception as e:
                print("copie impossible (%s): %s" % (c, e))
                # Fallback : exécuter directement depuis le chemin source
                if os.access(c, os.X_OK):
                    return c

    # 4) Dans le PATH ?
    p = shutil.which("llama-server")
    if p:
        return p

    print("llama-server introuvable")
    return None


def marges_systeme():
    if platform != "android":
        return 0, 0
    try:
        from jnius import autoclass
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        try:
            ins = act.getWindow().getDecorView().getRootWindowInsets()
            haut = ins.getSystemWindowInsetTop()
            bas = ins.getSystemWindowInsetBottom()
        except Exception:
            res = act.getResources()
            i1 = res.getIdentifier("status_bar_height", "dimen", "android")
            i2 = res.getIdentifier("navigation_bar_height", "dimen", "android")
            haut = res.getDimensionPixelSize(i1) if i1 > 0 else 0
            bas = res.getDimensionPixelSize(i2) if i2 > 0 else 0
        Point = autoclass("android.graphics.Point")
        p = Point()
        act.getWindowManager().getDefaultDisplay().getRealSize(p)
        if Window.height >= p.y - 4:
            return int(haut), int(bas)
        return 0, 0
    except Exception:
        return 0, 0


class JinxApp(App):
    def build(self):
        Window.clearcolor = (0.02, 0.015, 0.01, 1)
        try:
            charger_reglages(self.user_data_dir)
        except Exception:
            pass
        self.occupe = False
        self.stop_requested = False
        self.pret = False
        self.col = col = BoxLayout(orientation="vertical", padding=dp(12),
                                   spacing=dp(6))
        self.titre = Label(text="J.I.N.X", font_size="22sp", bold=True,
                           color=(1, 0.75, 0.25, 1), size_hint=(1, .07))
        self.titre.bind(on_touch_down=self.touche_titre)
        self.bulle = Bulle(self.ecouter, size_hint=(1, .56))
        self.etat_lbl = Label(text="Touche la bulle pour parler",
                              font_size="14sp", color=(0.85, 0.65, 0.30, 1),
                              size_hint=(1, .07))
        self.lbl = Label(text="", font_size="18sp", halign="center",
                         valign="top", size_hint=(1, .30))
        self.lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.lbl.color = (1, 0.93, 0.78, 1)
        for w in (self.titre, self.bulle, self.etat_lbl):
            col.add_widget(w)
        # --- Zone de texte (hauteur FIXE, pas de binding dynamique) ---
        self.scroll_texte = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(2),
            bar_color=(1, 0.9, 0.7, 0.4),
            size_hint_y=None,
            height=dp(200),
        )
        self.lbl.size_hint = (1, None)
        self.lbl.height = dp(200)
        self.lbl.text_size = (Window.width - dp(40), None)
        self.scroll_texte.add_widget(self.lbl)
        col.add_widget(self.scroll_texte)

        # Mettre à jour la largeur UNIQUEMENT quand la fenêtre change
        def _on_window_resize(win, taille):
            try:
                self.lbl.text_size = (taille[0] - dp(40), None)
            except Exception:
                pass
        Window.bind(size=_on_window_resize)

        fl = FloatLayout()
        fl.add_widget(col)
        # --- Bouton Clavier ---
        self.bt_clavier = Button(
            text="⌨",
            font_size="24sp",
            size_hint=(None, None),
            size=(dp(52), dp(52)),
            background_normal="",
            background_color=(1, 1, 1, 0.1),
            color=(1, 0.93, 0.78, 1),
        )
        self.bt_clavier.bind(on_release=self._ouvrir_clavier)
        fl.add_widget(self.bt_clavier)

        # --- Bouton STOP (caché par défaut) ---
        self.bt_stop = Button(
            text="■",
            font_size="24sp",
            size_hint=(None, None),
            size=(dp(52), dp(52)),
            background_normal="",
            background_color=(1, 1, 1, 0.1),
            color=(1, 0.55, 0.35, 1),
            opacity=0,
        )
        self.bt_stop.bind(on_release=self._stopper_reflexion)
        fl.add_widget(self.bt_stop)

        # --- Positionner les boutons (bas droite, empilés) ---
        self.bt_clavier.pos_hint = {"x": 0.03, "y": 0.04}
        self.bt_stop.pos_hint = {"x": 0.03, "y": 0.14}

        self.points = BoutonPoints(self.ouvrir_reglages, size_hint=(None, None),
                                   size=(dp(72), dp(72)),
                                   pos_hint={"right": 1, "y": 0.02})
        fl.add_widget(self.points)
        self.appliquer_reglages()
        return fl

    def appliquer_reglages(self):
        pal = PALETTES.get(SET["theme"], PALETTES["or"])
        r, g, b = pal["veille"]
        self.bulle.theme = SET["theme"]
        self.bulle.halo_mult = float(SET["halo"])
        self.bulle.set_fps(15 if SET["eco"] else 25)
        self.titre.color = (r, g, b, 1)
        self.etat_lbl.color = (r * 0.9, g * 0.9, b * 0.7, 1)
        self.points.couleur = (r, g, b, 0.9)
        self.points.dessiner()
        self.lbl.font_size = sp(int(SET["texte"]))

        # Couleur des boutons selon thème
        if hasattr(self, "bt_clavier"):
            self.bt_clavier.color = (r, g, b, 1)
            self.bt_clavier.background_color = (r * 0.2, g * 0.2, b * 0.2, 0.6)
        if hasattr(self, "bt_stop"):
            # Rouge doux pour rester visible quel que soit le thème
            self.bt_stop.color = (1, 0.5, 0.4, 1)
            self.bt_stop.background_color = (0.4, 0.1, 0.05, 0.7)

        # Couleur du texte selon le thème
        self.lbl.color = (min(1, r * 0.95 + 0.1),
                          min(1, g * 0.95 + 0.1),
                          min(1, b * 0.95 + 0.1), 1)

    def on_start(self):
        if platform == "android":
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO])
            try:
                tts_java()
            except Exception:
                pass
        self.demarrer_cerveau()
        Clock.schedule_once(self._init_modeles, 2.0)
        Clock.schedule_once(self.ajuster_marges, 0.6)
        Window.bind(size=lambda *a: Clock.schedule_once(self.ajuster_marges, 0.3))


    # --------------------------------------------------------- modeles IA
    def _init_modeles(self, *a):
        try:
            self._init_modeles_impl(*a)
        except Exception as e:
            import traceback
            _log("=== CRASH _init_modeles ===")
            _log(traceback.format_exc())
            self.lbl.text = "Erreur init : " + str(e)[:80]

    def _init_modeles_impl(self, *a):
        dossier = self.user_data_dir
        dossier_models = os.path.join(dossier, "models")
        self.downloader = ModelDownloader(dossier_models)
        manquants = self.downloader.manquants()

        if manquants:
            self.lbl.text = ("Premier lancement : telechargement de %d "
                             "modele(s) IA..." % len(manquants))
            afficher_splash_dl(
                self.downloader,
                on_done=self._modeles_prets,
                on_error=lambda: setattr(
                    self.lbl, "text",
                    "Telechargement incomplet. Relance Jinx pour reprendre."),
            )
        else:
            self._modeles_prets()

    def _modeles_prets(self, *a):
        try:
            self._modeles_prets_impl(*a)
        except Exception as e:
            import traceback
            _log("=== CRASH _modeles_prets ===")
            _log(traceback.format_exc())
            self.lbl.text = "Erreur : " + str(e)[:80]

    def _modeles_prets_impl(self, *a):
        dossier = self.user_data_dir
        dossier_models = os.path.join(dossier, "models")
        llama_binaire = trouver_llama_server(dossier)
        if not llama_binaire:
            self.lbl.text = "Erreur : llama-server introuvable dans l'APK."
            return
        print("llama-server :", llama_binaire)

        self.model_manager = ModelManager(
            dossier_models=dossier_models,
            llama_binaire=llama_binaire,
            mode="swap",
        )
        self.director = build_default_director(
            dossier=dossier,
            model_manager=self.model_manager,
        )
        self.director.set_core(get_core())
        self.lbl.text = "Pret ! Touche la bulle pour parler."


    def _telecharger_manuel(self, *a):
        dossier = self.user_data_dir
        dossier_models = os.path.join(dossier, "models")
        if not hasattr(self, "downloader"):
            self.downloader = ModelDownloader(dossier_models)
        manquants = self.downloader.manquants()
        if not manquants:
            self.lbl.text = "Tous les modeles sont deja installes."
            self._modeles_prets()
            return
        self.lbl.text = "Telechargement de %d modele(s)..." % len(manquants)
        afficher_splash_dl(
            self.downloader,
            on_done=self._modeles_prets,
            on_error=lambda: setattr(
                self.lbl, "text",
                "Erreur pendant le telechargement. Relance Jinx."),
        )


    def _stopper_reflexion(self, *a):
        """Annule la requête ET arrête la lecture vocale."""
        global STOP_TTS
        STOP_TTS = True
        self.stop_requested = True
        # Arrêter le TTS via le singleton
        _stop_tts()
        self.bulle.set_etat("veille")
        self.etat_lbl.text = "Touche la bulle pour parler"
        self.lbl.text = "Arrêté."
        self.occupe = False
        try:
            if hasattr(self, "director") and self.director:
                # Force la fin du thread
                pass
        except Exception:
            pass

    # ---------------------------------------------------------- Clavier
    def _ouvrir_clavier(self, *a):
        """Ouvre une modale pour taper du texte."""
        from kivy.uix.modalview import ModalView
        from kivy.uix.textinput import TextInput
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button

        mv = ModalView(size_hint=(0.95, 0.35),
                       background_color=(0.05, 0.04, 0.02, 0.98),
                       auto_dismiss=True)
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        champ = TextInput(
            hint_text="Tape ton message...",
            multiline=False,
            size_hint_y=None, height=dp(50),
            font_size="15sp",
            background_color=(0.15, 0.12, 0.08, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(0.95, 0.75, 0.35, 1),
        )
        root.add_widget(champ)

        btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))

        def envoyer(*a):
            texte = champ.text.strip()
            if texte:
                mv.dismiss()
                self.envoyer(texte)

        bt_envoi = Button(text="Envoyer", background_color=(0.4, 0.3, 0.1, 1))
        bt_fermer = Button(text="Annuler", background_color=(0.25, 0.2, 0.15, 1))
        bt_envoi.bind(on_release=envoyer)
        bt_fermer.bind(on_release=lambda *a: mv.dismiss())

        btns.add_widget(bt_envoi)
        btns.add_widget(bt_fermer)
        root.add_widget(btns)

        mv.add_widget(root)
        mv.open()
        # Focus auto sur le champ + clavier
        Clock.schedule_once(lambda d: setattr(champ, "focus", True), 0.2)


    def notifier(self, titre, message):
        """Affiche une notification Android."""
        try:
            if platform == "android":
                from jnius import autoclass, cast
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                Context = autoclass("android.content.Context")
                NotificationManager = autoclass("android.app.NotificationManager")
                NotificationChannel = autoclass("android.app.NotificationChannel")
                Notification = autoclass("android.app.Notification")
                NotificationBuilder = autoclass("android.app.Notification$Builder")
                Build = autoclass("android.os.Build")

                activity = PythonActivity.mActivity
                canal_id = "jinx_channel"

                # Créer un canal (Android 8+)
                if Build.VERSION.SDK_INT >= 26:
                    channel = NotificationChannel(
                        canal_id, "Jinx", NotificationManager.IMPORTANCE_DEFAULT)
                    nm = cast(NotificationManager,
                              activity.getSystemService(Context.NOTIFICATION_SERVICE))
                    nm.createNotificationChannel(channel)

                # Icone (utilise l'icône de l'app)
                icon = activity.getApplicationInfo().icon
                builder = NotificationBuilder(activity, canal_id)
                builder.setContentTitle(titre)
                builder.setContentText(message)
                builder.setSmallIcon(icon)
                builder.setAutoCancel(True)

                nm = cast(NotificationManager,
                          activity.getSystemService(Context.NOTIFICATION_SERVICE))
                nm.notify(1, builder.build())
                print(f"Notification envoyée : {titre} - {message}")
                return True
        except Exception as e:
            print(f"Notification échouée : {e}")

        # Fallback plyer
        try:
            from plyer import notification
            notification.notify(title=titre, message=message, timeout=5)
            return True
        except Exception as e:
            print(f"Fallback notif échoué : {e}")
        return False


    def _demander_confirmation(self, agent, query, message):
        """Affiche une modale pour confirmer une action critique."""
        from kivy.uix.modalview import ModalView
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button

        mv = ModalView(size_hint=(0.9, 0.4),
                       background_color=(0.05, 0.04, 0.02, 0.98),
                       auto_dismiss=False)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))

        root.add_widget(Label(
            text="[b]Confirmation requise[/b]\n\n" + message,
            markup=True, font_size="14sp",
            halign="center", valign="middle"))
        root.add_widget(Label(
            text="« %s »" % query[:80],
            font_size="12sp", color=(0.9, 0.75, 0.3, 1),
            halign="center"))

        btns = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))

        def autoriser(*a):
            mv.dismiss()
            self.bulle.set_etat("reflexion")
            self.etat_lbl.text = "Julie réfléchit..."
            def _run():
                rep = self.director.confirmer_action(agent, query)
                def _aff(d):
                    self.repondre(query, rep)
                Clock.schedule_once(_aff, 0)
            import threading
            threading.Thread(target=_run, daemon=True).start()

        def refuser(*a):
            mv.dismiss()
            self.repondre(query, "Action annulée.")

        bt_oui = Button(text="Autoriser",
                        background_color=(0.2, 0.55, 0.25, 1))
        bt_non = Button(text="Refuser",
                        background_color=(0.6, 0.2, 0.15, 1))
        bt_oui.bind(on_release=autoriser)
        bt_non.bind(on_release=refuser)
        btns.add_widget(bt_oui)
        btns.add_widget(bt_non)
        root.add_widget(btns)

        mv.add_widget(root)
        mv.open()


    def touche_titre(self, w, touch):
        if w.collide_point(*touch.pos):
            self.ouvrir_reglages()
            return True
        return False

    def ajuster_marges(self, *a):
        haut, bas = marges_systeme()
        self.col.padding = [dp(12), dp(12) + haut, dp(12), dp(12) + bas]
        self.points.pos_hint = {"right": 1}
        self.points.y = bas + dp(16)


    def on_stop(self):
        if PROC is not None:
            try:
                PROC.terminate()
            except Exception:
                pass

    def demarrer_cerveau(self, avant=None):
        self.occupe = True
        self.pret = False
        self.bulle.set_etat("reflexion")
        self.etat_lbl.text = "Preparation du cerveau..."
        self.lbl.text = ""

        def statut(t):
            Clock.schedule_once(lambda d: setattr(self.lbl, "text", t))

        def tache():
            try:
                if avant:
                    avant()
                ok = lancer_cerveau(self.user_data_dir, statut)
            except Exception as e:
                ok = False
                statut("Erreur cerveau : %s" % e)
            Clock.schedule_once(lambda d: self.cerveau_pret(ok))
        threading.Thread(target=tache, daemon=True).start()

    def cerveau_pret(self, ok):
        self.pret = ok
        self.occupe = False
        self.bulle.set_etat("veille")
        if ok:
            self.lbl.text = ""
            self.etat_lbl.text = "Touche la bulle pour parler"
        else:
            self.etat_lbl.text = "Touche la bulle pour reessayer"

    def ecouter(self):
        if self.occupe:
            return
        if not self.pret:
            self.demarrer_cerveau()
            return
        self.occupe = True
        self.bulle.set_etat("ecoute")
        self.etat_lbl.text = "J'ecoute..."
        self.lbl.text = ""
        try:
            from plyer import stt
            stt.results = []
            stt.errors = []
            stt.partial_results = []
            stt.language = SET["langue"]
            stt.start()
            self.t0 = time.time()
            self.tchange = self.t0
            self.sig = None
            Clock.schedule_interval(self.surveiller, 0.3)
        except Exception as e:
            self.repos("Erreur STT: %s" % e)

    def texte_courant(self, stt):
        part = getattr(stt, "partial_results", None) or []
        if stt.results:
            return stt.results[-1]
        if part:
            return part[-1]
        return ""

    def surveiller(self, dt):
        from plyer import stt
        now = time.time()
        texte = self.texte_courant(stt)
        sig = (len(stt.results), texte)
        if sig != self.sig:
            self.sig = sig
            self.tchange = now
            if texte:
                self.lbl.text = texte
        fini = False
        if texte and now - self.tchange > float(SET["silence"]):
            fini = True
        elif not texte and (stt.errors or now - self.t0 > 7):
            fini = True
        elif now - self.t0 > 14:
            fini = True
        if not fini:
            return
        Clock.unschedule(self.surveiller)
        erreurs = stt.errors
        try:
            stt.stop()
        except Exception:
            pass
        texte = corriger(texte).strip()
        if not texte:
            self.repos("Rien compris %s" % (erreurs,))
            return
        self.envoyer(texte)

    def envoyer(self, texte):
        if hasattr(self, "bt_stop"):
            self.bt_stop.opacity = 1
        self.bulle.set_etat("reflexion")
        self.etat_lbl.text = "Je reflechis..."
        self.lbl.text = "Toi : %s" % texte
        threading.Thread(target=self.penser, args=(texte,),
                         daemon=True).start()

    def penser(self, texte):
        self.stop_requested = False
        dossier = self.user_data_dir

        # 1) Commandes memoire locales rapides
        try:
            rep = commande_memoire(dossier, texte)
        except Exception:
            rep = None
        if rep is not None:
            Clock.schedule_once(lambda d: self.repondre(texte, rep))
            return

        # 2) Contexte memoire + exemples
        try:
            ctx_mem, exemples = contexte_memoire(dossier, texte)
        except Exception:
            ctx_mem, exemples = "", []

        # 3) Callback final
        def _reponse(rep):
            if self.stop_requested:
                self.stop_requested = False
                return
            # Confirmation requise ?
            if isinstance(rep, str) and rep.startswith("[JINX_CONFIRM]"):
                try:
                    contenu = rep.replace("[JINX_CONFIRM]", "", 1)
                    agent, query, msg = contenu.split("|||", 2)
                    Clock.schedule_once(
                        lambda d: self._demander_confirmation(agent, query, msg),
                        0)
                except Exception as e:
                    print("Erreur parsing CONFIRM:", e)
                return
            if SET.get("historique"):
                try:
                    enregistrer(dossier, texte, rep)
                except Exception:
                    pass
            self.repondre(texte, rep)

        # 4) Directeur pret ?
        if not getattr(self, "director", None):
            Clock.schedule_once(lambda d: self.repondre(
                texte, "Patientez, l'installation n'est pas terminee."))
            return

        # 5) Lancer le directeur
        self.director.handle_async(
            texte,
            callback=_reponse,
            context={"memoire": ctx_mem, "exemples": exemples,
                     "temperature": SET.get("creativite", 0.3),
                     "max_tokens": 400,
                     "llm_fn": lambda q, c: demander_ia(
                         q, (c.get("memoire", ""), c.get("exemples", [])))},
        )


    def repondre(self, texte, rep):
        if hasattr(self, "bt_stop"):
            self.bt_stop.opacity = 0
        self.bulle.set_etat("parle")
        self.etat_lbl.text = "Jinx parle..."
        self.lbl.text = "Toi : %s\n\nJinx : %s" % (texte, rep)
        parler_texte(rep)
        if SET["voix_active"]:
            delai = 1.0 + len(rep) * 0.075 / max(0.5, float(SET["vitesse"]))
        else:
            delai = 0.8
        Clock.schedule_once(lambda d: self.repos(), delai)

    def repos(self, msg=None):
        self.bulle.set_etat("veille")
        self.etat_lbl.text = "Touche la bulle pour parler"
        if msg:
            self.lbl.text = msg
        self.occupe = False

    # ------------------------------------------------------------ paramètres
    def ouvrir_reglages(self):
        try:
            self.panneau()
        except Exception as e:
            self.lbl.text = "Erreur parametres : %s" % e

    def panneau(self):
        pal = PALETTES.get(SET["theme"], PALETTES["or"])
        r, g, b = pal["veille"]
        OR = (r, g, b, 1)
        BL = (1, 0.93, 0.78, 1)
        ON = (r * 0.6, g * 0.6, b * 0.2, 1)
        OFF = (0.22, 0.22, 0.22, 1)
        BT = (0.28, 0.21, 0.07, 1)
        dossier = self.user_data_dir

        def sauver():
            sauver_reglages(dossier)

        mv = ModalView(size_hint=(0.94, 0.84), background="",
                       background_color=(0.04, 0.03, 0.02, 0.98),
                       auto_dismiss=True)
        col = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        liste = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(6), padding=(0, dp(4)))
        liste.bind(minimum_height=liste.setter("height"))

        def mk(texte, action=None, coul=BT, largeur=None):
            bt = Button(text=texte, background_normal="", background_color=coul,
                        color=BL, font_size="14sp")
            if largeur:
                bt.size_hint_x = None
                bt.width = largeur
            if action:
                bt.bind(on_release=lambda *a: action())
            return bt

        def section(t):
            l = Label(text=t, color=OR, bold=True, font_size="16sp",
                      size_hint_y=None, height=dp(36), halign="left",
                      valign="middle")
            l.bind(size=lambda w, s: setattr(w, "text_size", s))
            liste.add_widget(l)

        def note(texte, hauteur=34):
            l = Label(text=texte, color=BL, font_size="13sp",
                      size_hint_y=None, height=dp(hauteur), halign="left",
                      valign="middle")
            l.bind(size=lambda w, s: setattr(w, "text_size", s))
            liste.add_widget(l)
            return l

        def ligne(texte, widget, hauteur=48):
            row = BoxLayout(size_hint_y=None, height=dp(hauteur), spacing=dp(8))
            lab = Label(text=texte, color=BL, font_size="14sp", halign="left",
                        valign="middle", size_hint_x=.5)
            lab.bind(size=lambda w, s: setattr(w, "text_size", s))
            row.add_widget(lab)
            row.add_widget(widget)
            liste.add_widget(row)

        def pleine(texte, action):
            bt = mk(texte, action)
            bt.size_hint_y = None
            bt.height = dp(44)
            liste.add_widget(bt)

        def interrupteur(texte, cle, apres=None):
            bt = mk("OUI" if SET[cle] else "NON",
                    coul=ON if SET[cle] else OFF)

            def basculer(*a):
                SET[cle] = not SET[cle]
                bt.text = "OUI" if SET[cle] else "NON"
                bt.background_color = ON if SET[cle] else OFF
                sauver()
                if apres:
                    apres()
            bt.bind(on_release=basculer)
            ligne(texte, bt)

        def choix(texte, cle, options, etiquettes=None, apres=None):
            def lab(v):
                return (etiquettes or {}).get(v, str(v))
            bt = mk(lab(SET[cle]))

            def suivant(*a):
                try:
                    i = options.index(SET[cle])
                except ValueError:
                    i = -1
                SET[cle] = options[(i + 1) % len(options)]
                bt.text = lab(SET[cle])
                sauver()
                if apres:
                    apres()
            bt.bind(on_release=suivant)
            ligne(texte, bt)

        def curseur(texte, cle, mini, maxi, pas, fmt, apres=None, entier=False):
            box = BoxLayout(orientation="vertical")
            val = Label(text=fmt(SET[cle]), color=OR, font_size="13sp",
                        size_hint_y=.4)
            sl = Slider(min=mini, max=maxi, value=float(SET[cle]), step=pas,
                        value_track=True, value_track_color=OR, size_hint_y=.6)

            def change(inst, v):
                SET[cle] = int(round(v)) if entier else round(float(v), 2)
                val.text = fmt(SET[cle])

            def fin(*a):
                sauver()
                if apres:
                    apres()
            sl.bind(value=change, on_touch_up=fin)
            box.add_widget(val)
            box.add_widget(sl)
            ligne(texte, box, 62)

        def nom_change(inst, v):
            SET["surnom"] = v.strip()[:30]
            sauver()
        ti.bind(text=nom_change)
        ligne("Comment t'appeler", ti)
        choix("Modèle IA (puis redémarrer le cerveau)", "modele",
              ["1.5B", "3B"],
              {"1.5B": "0.5B rapide", "3B": "3B intelligent"})

        section("Mémoire")
        interrupteur("Utiliser la mémoire", "memoire")
        interrupteur("Enregistrer l'historique", "historique")
        pleine("Voir mes souvenirs", self.voir_souvenirs)
        pleine("Tout effacer (souvenirs et historique)",
               lambda: self.confirmer("Tout effacer ?\nSouvenirs et historique.",
                                      self.efface_tout))
        pleine("Sauvegarder (partager en texte)", self.partager_base)

        section("Apparence")
        choix("Couleur du thème", "theme", ["or", "bleu", "vert", "rouge"],
              {"or": "Or", "bleu": "Bleu", "vert": "Vert", "rouge": "Rouge"},
              apres=self.appliquer_reglages)
        curseur("Intensité du halo", "halo", 0.3, 1.5, 0.1,
                lambda v: "%d %%" % round(v * 100),
                apres=self.appliquer_reglages)
        curseur("Taille du texte", "texte", 14, 26, 1, lambda v: "%d" % v,
                apres=self.appliquer_reglages, entier=True)

        section("Système")
        etat = "prêt" if serveur_pret() else "arrêté"
        note("Cerveau : Qwen 3B")
        pleine("Redémarrer le cerveau",
               lambda: (mv.dismiss(),
                        self.demarrer_cerveau(avant=arreter_cerveau)))
        pleine("Journal du serveur", self.voir_journal)
        note(espace_txt(dossier), 50)
        pleine("Supprimer le modèle inutilisé",
               lambda: self.confirmer("Supprimer le modèle que tu n'utilises pas ?",
                                      self.supprimer_inutilises))
        pleine("Retélécharger le modèle",
               lambda: self.confirmer("Supprimer puis retélécharger le modèle actuel ?",
                                      lambda: (mv.dismiss(), self.retelecharger())))
        note("Jinx version %s · marges %s" % (VERSION, marges_systeme()))
        mv.open()

    def confirmer(self, message, action):
        contenu = BoxLayout(orientation="vertical", spacing=dp(10),
                            padding=dp(10))
        lab = Label(text=message, halign="center", valign="middle")
        lab.bind(size=lambda w, s: setattr(w, "text_size", s))
        contenu.add_widget(lab)
        rangee = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        pop = Popup(title="Confirmer", content=contenu, size_hint=(.85, .38))
        non = Button(text="Non")
        oui = Button(text="Oui")
        non.bind(on_release=lambda *a: pop.dismiss())
        oui.bind(on_release=lambda *a: (pop.dismiss(), action()))
        rangee.add_widget(non)
        rangee.add_widget(oui)
        contenu.add_widget(rangee)
        pop.open()

    def popup_texte(self, titre, texte):
        sv = ScrollView(do_scroll_x=False)
        lab = Label(text=texte, font_size="11sp", size_hint_y=None,
                    halign="left", valign="top")
        lab.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
        lab.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        sv.add_widget(lab)
        Popup(title=titre, content=sv, size_hint=(.94, .8)).open()

    def voir_journal(self):
        chemin = os.path.join(self.user_data_dir, "serveur.log")
        try:
            with open(chemin, encoding="utf-8", errors="replace") as f:
                txt = f.read()[-3000:]
        except Exception as e:
            txt = "Pas de journal : %s" % e
        self.popup_texte("Journal du serveur", txt or "(vide)")

    def voir_souvenirs(self):
        dossier = self.user_data_dir
        contenu = BoxLayout(orientation="vertical", spacing=dp(6))
        sv = ScrollView(do_scroll_x=False)
        lst = BoxLayout(orientation="vertical", size_hint_y=None,
                        spacing=dp(6))
        lst.bind(minimum_height=lst.setter("height"))
        sv.add_widget(lst)
        contenu.add_widget(sv)
        pop = Popup(title="Mes souvenirs", content=contenu, size_hint=(.94, .8))
        fermer = Button(text="Fermer", size_hint_y=None, height=dp(44))
        fermer.bind(on_release=lambda *a: pop.dismiss())
        contenu.add_widget(fermer)

        def supprimer(fid):
            c = db(dossier)
            if c is None:
                return
            try:
                c.execute("DELETE FROM faits WHERE id=?", (fid,))
                c.commit()
            finally:
                c.close()
            remplir()

        def remplir():
            lst.clear_widgets()
            c = db(dossier)
            if c is None:
                lst.add_widget(Label(text="Base indisponible",
                                     size_hint_y=None, height=dp(40)))
                return
            try:
                faits = c.execute("SELECT id, contenu FROM faits ORDER BY id DESC LIMIT 100").fetchall()
                nb = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            finally:
                c.close()
            lst.add_widget(Label(
                text="%d souvenir(s) · %d message(s) enregistré(s)" % (len(faits), nb),
                size_hint_y=None, height=dp(34)))
            for fid, txt in faits:
                row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(6))
                lab = Label(text=en_tu(txt), halign="left", valign="middle")
                lab.bind(size=lambda w, s: setattr(w, "text_size", s))
                bt = Button(text="X", size_hint_x=None, width=dp(44))
                bt.bind(on_release=lambda inst, fid=fid: supprimer(fid))
                row.add_widget(lab)
                row.add_widget(bt)
                lst.add_widget(row)
        remplir()
        pop.open()

    def efface_tout(self):
        c = db(self.user_data_dir)
        if c is None:
            return
        try:
            c.execute("DELETE FROM faits")
            c.execute("DELETE FROM messages")
            c.commit()
        finally:
            c.close()
        self.lbl.text = "Mémoire effacée."

    def partager_base(self):
        c = db(self.user_data_dir)
        if c is None:
            return
        try:
            faits = [f[0] for f in c.execute("SELECT contenu FROM faits ORDER BY id")]
            msgs = c.execute("SELECT ts, role, contenu FROM messages ORDER BY id DESC LIMIT 300").fetchall()
        finally:
            c.close()
        msgs.reverse()
        txt = ("JINX - sauvegarde\n\nSOUVENIRS\n"
               + "\n".join("- " + f for f in faits)
               + "\n\nHISTORIQUE\n"
               + "\n".join("%s [%s] %s" % (
                   time.strftime("%d/%m %H:%M", time.localtime(t)), rl, x)
                   for t, rl, x in msgs))[:200000]
        if platform == "android":
            try:
                from jnius import autoclass, cast
                Intent = autoclass("android.content.Intent")
                String = autoclass("java.lang.String")
                act = autoclass("org.kivy.android.PythonActivity").mActivity
                it = Intent(Intent.ACTION_SEND)
                it.setType("text/plain")
                it.putExtra(Intent.EXTRA_TEXT,
                            cast("java.lang.CharSequence", String(txt)))
                act.startActivity(Intent.createChooser(
                    it, cast("java.lang.CharSequence", String("Sauvegarder Jinx"))))
            except Exception as e:
                self.lbl.text = "Partage impossible : %s" % e

    def supprimer_inutilises(self):
        for k in MODELES:
            if k != SET["modele"]:
                supprimer_modele(self.user_data_dir, k)
        self.lbl.text = "Modèle inutilisé supprimé."

    def retelecharger(self):
        d = self.user_data_dir

        def avant():
            arreter_cerveau()
            supprimer_modele(d, SET["modele"])
        self.demarrer_cerveau(avant=avant)


JinxApp().run()
