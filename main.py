from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.utils import platform

class JinxApp(App):
    def build(self):
        self.lbl = Label(text="Jinx est prete", font_size="20sp", halign="center", valign="middle")
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
            from plyer import stt, tts
            stt.stop()
            texte = stt.results[-1] if stt.results else ""
            if texte:
                self.lbl.text = texte
                tts.speak(texte)
            else:
                self.lbl.text = "Rien compris: %s" % (stt.errors,)
        except Exception as e:
            self.lbl.text = "Erreur: %s" % e

JinxApp().run()
