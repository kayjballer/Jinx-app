import json, threading
from urllib import request
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.utils import platform

URL = "http://127.0.0.1:8080/v1/chat/completions"
SYSTEM = ("Tu es Jinx, une assistante vocale au caractere vif et taquin. "
          "Reponds toujours en francais, en 1 ou 2 phrases courtes.")

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
        self.lbl = Label(text="Jinx est prete", font_size="20sp",
                         halign="center", valign="middle")
        self.lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        btn = Button(text="Parler a Jinx", size_hint=(1, .25))
        btn.bind(on_release=self.ecouter)
        root = BoxLayout(orientation="vertical")
        root.add_widget(self.lbl)
        root.add_widget(btn)
        return root

    def on_start(self):
        if platform == "android":
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO])

    def ecouter(self, *a):
        try:
            from plyer import stt
            self.lbl.text = "J'ecoute..."
            stt.language = "fr-FR"
            stt.start()
            Clock.schedule_once(self.fin, 6)
        except Exception as e:
            self.lbl.text = "Erreur STT: %s" % e

    def fin(self, dt):
        try:
            from plyer import stt
            stt.stop()
            texte = stt.results[-1] if stt.results else ""
            if not texte:
                self.lbl.text = "Rien compris: %s" % (stt.errors,)
                return
            self.lbl.text = "Toi : %s\nJinx reflechit..." % texte
            threading.Thread(target=self.penser, args=(texte,),
                             daemon=True).start()
        except Exception as e:
            self.lbl.text = "Erreur: %s" % e

    def penser(self, texte):
        try:
            rep = demander_ia(texte)
        except Exception:
            rep = "Je n'arrive pas a joindre mon cerveau. Lance le serveur dans Termux."
        Clock.schedule_once(lambda dt: self.repondre(texte, rep))

    def repondre(self, texte, rep):
        from plyer import tts
        self.lbl.text = "Toi : %s\nJinx : %s" % (texte, rep)
        try:
            tts.speak(rep)
        except Exception as e:
            self.lbl.text += "\nErreur voix: %s" % e

JinxApp().run()
