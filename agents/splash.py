"""agents/splash.py — Ecran de telechargement au 1er lancement."""
from __future__ import annotations

import threading

from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.metrics import dp, sp
from kivy.clock import Clock


def afficher_splash_dl(downloader, on_done, on_error=None):
    mv = ModalView(size_hint=(0.92, 0.55), auto_dismiss=False,
                   background_color=(0.04, 0.03, 0.02, 0.98))
    root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))

    titre = Label(text="[b]Installation de Jinx[/b]", markup=True,
                  font_size=sp(22), size_hint_y=None, height=dp(40),
                  color=(0.95, 0.75, 0.35, 1))
    root.add_widget(titre)

    sous = Label(text="Jinx telecharge les modeles IA.\n"
                      "Cette operation n'a lieu qu'une seule fois.",
                 font_size=sp(13), size_hint_y=None, height=dp(60),
                 halign="center", valign="middle")
    sous.bind(size=sous.setter("text_size"))
    root.add_widget(sous)

    bar = ProgressBar(max=1.0, value=0.0, size_hint_y=None, height=dp(24))
    root.add_widget(bar)

    statut = Label(text="Preparation...", font_size=sp(12),
                   size_hint_y=None, height=dp(60),
                   halign="center", valign="middle", color=(1, 1, 1, 0.8))
    statut.bind(size=statut.setter("text_size"))
    root.add_widget(statut)

    mv.add_widget(root)
    mv.open()

    def on_progress(ratio, txt):
        def _ui(*_):
            bar.value = ratio
            statut.text = txt
        Clock.schedule_once(_ui, 0)

    def work():
        ok = downloader.telecharger_tout(on_progress=on_progress)
        def _fin(*_):
            mv.dismiss()
            if ok:
                on_done()
            elif on_error:
                on_error()
        Clock.schedule_once(_fin, 0)

    threading.Thread(target=work, daemon=True).start()
    return mv
