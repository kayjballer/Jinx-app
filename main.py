import json, threading, re, time
from urllib import request
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.utils import platform

URL = "http://127.0.0.1:8080/v1/chat/completions"
SYSTEM = ("Tu es Jinx, une assistante vocale au caractere vif, moqueur et un peu chaotique. "
          "Tu tutoies toujours, jamais de vouvoiement. Ne dis jamais comment puis-je vous aider. "
          "Reponds toujours en francais, en 1 ou 2 phrases courtes.")

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

class JinxApp(App):
    def build(self):
        self.mode = "off"
        self.t0 = 0
        self.lbl = Label(text="Jinx dort", font_size="20sp",
                         halign="center", valign="middle")
        self.lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.btn = Button(text="Activer Jinx", size_hint=(1, .2))
        self.btn.bind(on_release=self.basculer)
        root = BoxLayout(orientation="vertical")
        root.add_widget(self.lbl)
        root.add_widget(self.btn)
        return root

    def on_start(self):
        if platform == "android":
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO])

    def basculer(self, *a):
        if self.mode == "off":
            self.mode = "veille"
            self.btn.text = "Arreter Jinx"
            self.lbl.text = "Dis 'Jinx'..."
            self.demarrer()
        else:
            self.mode = "off"
            self.btn.text = "Activer Jinx"
            self.lbl.text = "Jinx dort"
            Clock.unschedule(self.surveiller)
            try:
                from plyer import stt
                stt.stop()
            except Exception:
                pass

    def demarrer(self, *a):
        if self.mode == "off":
            return
        try:
            from plyer import stt
            stt.results = []
            stt.errors = []
            stt.partial_results = []
            stt.language = "fr-FR"
            stt.start()
            self.t0 = time.time()
            Clock.unschedule(self.surveiller)
            Clock.schedule_interval(self.surveiller, 0.4)
        except Exception as e:
            self.lbl.text = "Erreur STT: %s" % e
            Clock.schedule_once(self.demarrer, 3)

    def surveiller(self, dt):
        from plyer import stt
        limite = 8 if self.mode == "veille" else 15
        if not (stt.results or stt.errors or time.time() - self.t0 > limite):
            return
        Clock.unschedule(self.surveiller)
        texte = ""
        if stt.results:
            texte = stt.results[-1]
        elif stt.partial_results:
            texte = stt.partial_results[-1]
        try:
            stt.stop()
        except Exception:
            pass
        Clock.schedule_once(lambda d: self.traiter(texte), 0.3)

    def traiter(self, texte):
        if self.mode == "off":
            return
        texte = corriger(texte).strip()
        if self.mode == "veille":
            if re.search(r"\bjinx\b", texte, re.I):
                cmd = re.sub(r"^.*?\bjinx\b[\s,!.?]*", "", texte,
                             count=1, flags=re.I).strip()
                if cmd:
                    self.envoyer(cmd)
                else:
                    self.mode = "actif"
                    self.lbl.text = "Oui ? Je t'ecoute..."
                    self.parler("Oui ?")
                    Clock.schedule_once(self.demarrer, 1.2)
            else:
                self.demarrer()
        else:
            if texte:
                self.envoyer(texte)
            else:
                self.mode = "veille"
                self.lbl.text = "Dis 'Jinx'..."
                self.demarrer()

    def envoyer(self, texte):
        self.lbl.text = "Toi : %s\nJinx reflechit..." % texte
        threading.Thread(target=self.penser, args=(texte,),
                         daemon=True).start()

    def penser(self, texte):
        try:
            rep = demander_ia(texte)
        except Exception:
            rep = "Je n'arrive pas a joindre mon cerveau. Lance le serveur dans Termux."
        Clock.schedule_once(lambda d: self.repondre(texte, rep))

    def repondre(self, texte, rep):
        if self.mode == "off":
            return
        self.lbl.text = "Toi : %s\nJinx : %s" % (texte, rep)
        self.parler(rep)
        self.mode = "veille"
        Clock.schedule_once(self.demarrer, 1.5 + len(rep) * 0.075)

    def parler(self, texte):
        try:
            from plyer import tts
            tts.speak(texte)
        except Exception as e:
            self.lbl.text += "\nErreur voix: %s" % e

JinxApp().run()
