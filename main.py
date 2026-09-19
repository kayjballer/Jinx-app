import json, threading, re, time, math, random, os, subprocess, ssl
from urllib import request
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Point, Mesh
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.utils import platform

URL = "http://127.0.0.1:8080/v1/chat/completions"
SYSTEM = ("Tu es Jinx, une assistante vocale au caractere vif, moqueur et un peu chaotique. "
          "Tu tutoies toujours, jamais de vouvoiement. Ne dis jamais comment puis-je vous aider. "
          "Reponds toujours en francais, en 1 ou 2 phrases courtes.")

# vitesse de rotation, amplitude du pouls, frequence du pouls, couleur
ETATS = {
    "veille":    (0.25, 0.03, 1.2, (0.10, 0.80, 1.00)),
    "ecoute":    (0.70, 0.10, 4.0, (0.20, 1.00, 0.70)),
    "reflexion": (1.60, 0.06, 6.0, (0.80, 0.40, 1.00)),
    "parle":     (0.50, 0.12, 7.0, (1.00, 0.65, 0.20)),
}

def corriger(t):
    return re.sub(r"\b(jenkins|jinks|gingks|jean x|djinx|ginx|gynx)\b",
                  "Jinx", t, flags=re.I)

def demander_ia(question):
    data = json.dumps({
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question}],
        "max_tokens": 120, "temperature": 0.7}).encode()
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
            statut("Binaire KO, code %s\n%s" % (t.returncode, (t.stdout + t.stderr)[-400:]))
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


class Bulle(Widget):
    def __init__(self, on_tap, **kw):
        super().__init__(**kw)
        self.on_tap = on_tap
        self.etat = "veille"
        self.t = 0.0
        self.ay = 0.0
        self.ax = 0.35
        self.vit = 0.25
        self.amp = 0.03
        random.seed(7)
        n = 170
        gold = math.pi * (3 - math.sqrt(5))
        self.pts = []
        for i in range(n):
            y = 1 - 2 * (i + 0.5) / n
            r = math.sqrt(1 - y * y)
            th = gold * i
            k = random.uniform(0.82, 1.08)
            self.pts.append((math.cos(th) * r * k, y * k, math.sin(th) * r * k))
        idx = []
        for i in range(n):
            for j in range(i + 1, n):
                dx = self.pts[i][0] - self.pts[j][0]
                dy = self.pts[i][1] - self.pts[j][1]
                dz = self.pts[i][2] - self.pts[j][2]
                if dx * dx + dy * dy + dz * dz < 0.13:
                    idx += [i, j]
        with self.canvas:
            self.c_lignes = Color(0.1, 0.8, 1, 0.30)
            self.mesh = Mesh(vertices=[0, 0, 0, 0] * n, indices=idx,
                             mode="lines")
            self.c_pts = []
            self.groupes = []
            for taille in (dp(1.2), dp(2.0), dp(3.0)):
                self.c_pts.append(Color(0.4, 0.9, 1, 1))
                self.groupes.append(Point(points=[0, 0], pointsize=taille))
        self.set_etat("veille")
        Clock.schedule_interval(self.maj, 1 / 30.0)

    def set_etat(self, e):
        self.etat = e
        r, g, b = ETATS[e][3]
        self.c_lignes.rgba = (r, g, b, 0.30)
        for c, al in zip(self.c_pts, (0.35, 0.70, 1.0)):
            c.rgba = (min(1, r + 0.3), min(1, g + 0.2), min(1, b + 0.1), al)

    def rayon(self):
        return min(self.width, self.height) * 0.42

    def maj(self, dt):
        self.t += dt
        v, a, f, _ = ETATS[self.etat]
        k = min(1.0, dt * 3)
        self.vit += (v - self.vit) * k
        self.amp += (a - self.amp) * k
        self.ay += self.vit * dt
        cx, cy = self.center_x, self.center_y
        R = self.rayon() * (1 + self.amp * math.sin(self.t * f))
        cay, say = math.cos(self.ay), math.sin(self.ay)
        cax, sax = math.cos(self.ax), math.sin(self.ax)
        verts = []
        g = [[], [], []]
        for (x, y, z) in self.pts:
            x1 = x * cay + z * say
            z1 = -x * say + z * cay
            y2 = y * cax - z1 * sax
            z2 = y * sax + z1 * cax
            s = 1 + z2 * 0.2
            px = cx + x1 * R * s
            py = cy + y2 * R * s
            verts += [px, py, 0, 0]
            b = 0 if z2 < -0.33 else (1 if z2 < 0.33 else 2)
            g[b] += [px, py]
        self.mesh.vertices = verts
        for i in range(3):
            self.groupes[i].points = g[i] if g[i] else [0, 0]

    def on_touch_down(self, touch):
        dx = touch.x - self.center_x
        dy = touch.y - self.center_y
        if dx * dx + dy * dy < (self.rayon() * 1.15) ** 2:
            self.on_tap()
            return True
        return super().on_touch_down(touch)


class JinxApp(App):
    def build(self):
        Window.clearcolor = (0.02, 0.03, 0.06, 1)
        self.occupe = False
        self.pret = False
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        titre = Label(text="J.I.N.X", font_size="22sp", bold=True,
                      color=(0.2, 0.9, 1, 1), size_hint=(1, .07))
        self.bulle = Bulle(self.ecouter, size_hint=(1, .50))
        self.etat_lbl = Label(text="Touche la bulle pour parler",
                              font_size="14sp", color=(0.3, 0.7, 0.85, 1),
                              size_hint=(1, .07))
        self.lbl = Label(text="", font_size="18sp", halign="center",
                         valign="top", size_hint=(1, .36))
        self.lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
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
        try:
            rep = demander_ia(texte)
        except Exception:
            rep = "Je n'arrive pas a joindre mon cerveau. Lance le serveur dans Termux."
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
