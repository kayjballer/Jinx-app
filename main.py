import json, threading, re, time, math, random, os, subprocess, ssl, unicodedata
from urllib import request
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Mesh, Rectangle, Line
from kivy.graphics.texture import Texture
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
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.utils import platform

URL = "http://127.0.0.1:8080/v1/chat/completions"
SYSTEM = ("Tu es Jinx, une assistante vocale un peu taquine. "
          "Tu parles français et tu tutoies. Tu réponds en une ou deux phrases courtes. "
          "Si tu ne sais pas, tu le dis.")
EXEMPLES = [
    {"role": "user", "content": "Qui es-tu ?"},
    {"role": "assistant", "content": "Moi, c'est Jinx, ton assistante vocale. Un peu chipie, mais toujours là pour toi !"},
    {"role": "user", "content": "Bonjour"},
    {"role": "assistant", "content": "Salut toi ! Alors, on a besoin de moi ?"},
]

# vitesse de rotation, amplitude du pouls, frequence du pouls, couleur
ETATS = {
    "veille":    (0.25, 0.03, 1.2, (0.10, 0.80, 1.00)),
    "ecoute":    (0.70, 0.10, 4.0, (0.20, 1.00, 0.70)),
    "reflexion": (1.60, 0.06, 6.0, (0.80, 0.40, 1.00)),
    "parle":     (0.50, 0.12, 7.0, (1.00, 0.65, 0.20)),
}

try:
    import sqlite3
except Exception:
    sqlite3 = None


def corriger(t):
    return re.sub(r"\b(jenkins|jinks|gingks|jean x|djinx|ginx|gynx)\b",
                  "Jinx", t, flags=re.I)

STOP = set(("le la les un une des de du et ou au aux en dans sur pour par "
            "avec sans que qui quoi quel quelle est es suis sont ai as avons "
            "ont mon ma mes ton ta tes son sa ses je tu il elle nous vous ils "
            "elles me te se ce cet cette ces ne pas plus tres bien alors donc "
            "mais si comme tout tous fait faire peux peut veux veut dis dit "
            "jinx hey salut bonjour oui non cela ceci").split())
CONFIRM = {"oubli": False}
SYSTEM_BASE = ("Tu es Jinx, une assistante vocale un peu taquine. "
               "Tu parles français et tu tutoies. Tu réponds en une ou deux phrases courtes. "
               "Si tu ne sais pas, tu le dis.")
EXEMPLES_JINX = [
    {"role": "user", "content": "Qui es-tu ?"},
    {"role": "assistant", "content": "Moi, c'est Jinx, ton assistante vocale. Un peu chipie, mais toujours là pour toi !"},
    {"role": "user", "content": "Bonjour"},
    {"role": "assistant", "content": "Salut toi ! Alors, on a besoin de moi ?"},
]


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


def contexte_memoire(dossier, question):
    c = db(dossier)
    if c is None:
        return "", []
    try:
        cle = mots(question)
        faits = [f[0] for f in c.execute("SELECT contenu FROM faits ORDER BY id DESC LIMIT 200")]
        notes = faits[:3]
        classes = sorted(faits, key=lambda x: len(cle & mots(x)), reverse=True)
        for x in classes[:4]:
            if len(cle & mots(x)) >= 1 and x not in notes:
                notes.append(x)
        rows = c.execute("SELECT id, role, contenu FROM messages ORDER BY id DESC LIMIT 6").fetchall()
        rows.reverse()
        hist = [{"role": r[1], "content": r[2][:300]} for r in rows]
        recents = set(r[0] for r in rows)
        souvenirs = []
        if cle:
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
                  "(ce sont ses propres mots, il parle de lui) :\n"
                  + "\n".join("- " + n for n in notes))
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
            return "C'est noté, je m'en souviendrai."
        if re.search(r"(qu.?est.?ce que tu (?:sais|retiens)|que sais.?tu|dis.?moi ce que tu (?:sais|retiens)|de quoi tu te souviens)", t):
            lignes = [f[0] for f in c.execute("SELECT contenu FROM faits ORDER BY id DESC LIMIT 8")]
            if not lignes:
                return "Je ne sais encore rien sur toi. Dis-moi retiens que, puis ce que tu veux que je retienne."
            return "Voici ce que je retiens : " + ". ".join(lignes) + "."
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
    msgs = ([{"role": "system", "content": SYSTEM_BASE + extra}]
            + (EXEMPLES_JINX if len(hist) < 2 else [])
            + hist + [{"role": "user", "content": question}])
    data = json.dumps({"messages": msgs, "max_tokens": 150,
                       "temperature": 0.3}).encode()
    req = request.Request(URL, data=data,
                          headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=120) as r:
        rep = json.loads(r.read())
    return rep["choices"][0]["message"]["content"].strip()


MODELE_URL = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
PROC = None
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl.create_default_context()

def serveur_pret():
    try:
        with request.urlopen("http://127.0.0.1:8080/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False

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
    modele = os.path.join(dossier, "qwen.gguf")
    if not os.path.exists(modele) or os.path.getsize(modele) < 1100000000:
        tmp = modele + ".part"
        reprise = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        en_tetes = {"User-Agent": "Jinx"}
        if reprise:
            en_tetes["Range"] = "bytes=%d-" % reprise
        req = request.Request(MODELE_URL, headers=en_tetes)
        with request.urlopen(req, timeout=60, context=CTX) as r:
            if r.status != 206:
                reprise = 0
            total = reprise + int(r.headers.get("Content-Length") or 1117320736)
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
        if os.path.getsize(tmp) < 1100000000:
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


ETATS = {
    "veille": dict(vit=0.22, amp=0.025, freq=1.1, halo=0.35, hamp=0.10,
                   onde=0.05, rate=0.25, c=(1.00, 0.70, 0.15)),
    "ecoute": dict(vit=0.50, amp=0.050, freq=3.0, halo=0.55, hamp=0.20,
                   onde=0.45, rate=0.50, c=(1.00, 0.86, 0.38)),
    "reflexion": dict(vit=1.50, amp=0.050, freq=5.0, halo=0.60, hamp=0.30,
                      onde=0.55, rate=0.90, c=(1.00, 0.52, 0.10)),
    "parle": dict(vit=0.45, amp=0.080, freq=6.0, halo=0.75, hamp=0.45,
                  onde=0.70, rate=0.70, c=(1.00, 0.78, 0.22)),
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
        self.t = 0.0
        self.ay = 0.0
        self.ax = 0.35
        self.ph_onde = 0.0
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
        Clock.schedule_interval(self.maj, 1 / 30.0)

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
        for c, v in zip("rgb", e["c"]):
            p[c] += (v - p[c]) * k
        r, g, b = p["r"], p["g"], p["b"]
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
                            p["halo"] * (0.55 + 0.45 * env))
        self.r_halo.pos = (cx - hs, cy - hs)
        self.r_halo.size = (2 * hs, 2 * hs)
        for i in range(3):
            ph = (self.ph_onde + i / 3.0) % 1.0
            self.c_ondes[i].rgba = (r, g, b, p["onde"] * (1 - ph) ** 1.6)
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
        for j, (rad, span, sp) in enumerate(((0.10, 250, 1.0),
                                             (0.17, 200, -1.4),
                                             (0.25, 300, 0.7))):
            a0 = (t * sp * 60 * (1 + p["vit"])) % 360
            self.l_arcs[j].circle = (cx, cy, R * rad, a0, a0 + span)

    def on_touch_down(self, touch):
        dx = touch.x - self.center_x
        dy = touch.y - self.center_y
        if dx * dx + dy * dy < (self.rayon() * 1.3) ** 2:
            self.on_tap()
            return True
        return super().on_touch_down(touch)


class JinxApp(App):
    def build(self):
        Window.clearcolor = (0.02, 0.015, 0.01, 1)
        self.occupe = False
        self.pret = False
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        titre = Label(text="J.I.N.X", font_size="22sp", bold=True,
                      color=(1, 0.75, 0.25, 1), size_hint=(1, .07))
        self.bulle = Bulle(self.ecouter, size_hint=(1, .56))
        self.etat_lbl = Label(text="Touche la bulle pour parler",
                              font_size="14sp", color=(0.85, 0.65, 0.30, 1),
                              size_hint=(1, .07))
        self.lbl = Label(text="", font_size="18sp", halign="center",
                         valign="top", size_hint=(1, .30))
        self.lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.lbl.color = (1, 0.93, 0.78, 1)
        for w in (titre, self.bulle, self.etat_lbl, self.lbl):
            root.add_widget(w)
        return root

    def on_start(self):
        if platform == "android":
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO])
        self.demarrer_cerveau()

    def on_stop(self):
        if PROC is not None:
            try:
                PROC.terminate()
            except Exception:
                pass

    def demarrer_cerveau(self):
        self.occupe = True
        self.pret = False
        self.bulle.set_etat("reflexion")
        self.etat_lbl.text = "Preparation du cerveau..."
        self.lbl.text = ""

        def statut(t):
            Clock.schedule_once(lambda d: setattr(self.lbl, "text", t))

        def tache():
            try:
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
            stt.language = "fr-FR"
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
        if texte and now - self.tchange > 1.4:
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
        self.bulle.set_etat("reflexion")
        self.etat_lbl.text = "Je reflechis..."
        self.lbl.text = "Toi : %s" % texte
        threading.Thread(target=self.penser, args=(texte,),
                         daemon=True).start()

    def penser(self, texte):
        dossier = self.user_data_dir
        log = False
        try:
            rep = commande_memoire(dossier, texte)
        except Exception:
            rep = None
        if rep is None:
            try:
                ctx = contexte_memoire(dossier, texte)
            except Exception:
                ctx = ("", [])
            try:
                rep = demander_ia(texte, ctx)
                log = True
            except Exception:
                rep = "Je n'arrive pas a joindre mon cerveau. Lance le serveur dans Termux."
        if log:
            try:
                enregistrer(dossier, texte, rep)
            except Exception:
                pass
        Clock.schedule_once(lambda d: self.repondre(texte, rep))

    def repondre(self, texte, rep):
        self.bulle.set_etat("parle")
        self.etat_lbl.text = "Jinx parle..."
        self.lbl.text = "Toi : %s\n\nJinx : %s" % (texte, rep)
        try:
            from plyer import tts
            tts.speak(rep)
        except Exception as e:
            self.lbl.text += "\nErreur voix: %s" % e
        Clock.schedule_once(lambda d: self.repos(), 1.0 + len(rep) * 0.075)

    def repos(self, msg=None):
        self.bulle.set_etat("veille")
        self.etat_lbl.text = "Touche la bulle pour parler"
        if msg:
            self.lbl.text = msg
        self.occupe = False

JinxApp().run()
