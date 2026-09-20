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

VERSION = "0.3"
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
    if not (SET["voix_active"] or force):
        return
    if platform == "android":
        try:
            from jnius import autoclass
            t = tts_java()
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
    "1.5B": dict(fichier="qwen.gguf",
                 url="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
                 mini=1100000000, total=1117320736),
    "3B": dict(fichier="qwen3b.gguf",
               url="https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf",
               mini=1850000000, total=1930000000),
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
    mod = MODELES.get(SET["modele"], MODELES["1.5B"])
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
