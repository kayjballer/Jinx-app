"""agents/panel.py — Panneau d'affichage des agents du directeur."""
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp, sp


def ouvrir_panneau_agents(director):
    vue = ModalView(size_hint=(0.92, 0.82), background_color=(0, 0, 0, 0.75))
    root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

    infos = director.get_agents_info()

    titre = Label(
        text="[b]Agent Directeur[/b]\n%d agent(s) sous sa direction" % len(infos),
        markup=True, size_hint_y=None, height=dp(64), font_size=sp(18))
    root.add_widget(titre)

    scroll = ScrollView()
    liste = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
    liste.bind(minimum_height=liste.setter("height"))

    for info in infos:
        card = BoxLayout(orientation="vertical", size_hint_y=None,
                         height=dp(120), padding=dp(10), spacing=dp(2))

        nom = Label(text="[b]%s[/b]" % info["name"], markup=True,
                    size_hint_y=None, height=dp(22),
                    halign="left", valign="middle")
        nom.bind(size=nom.setter("text_size"))

        desc = Label(text=info["description"], size_hint_y=None,
                     height=dp(40), halign="left", valign="top",
                     font_size=sp(13))
        desc.bind(size=desc.setter("text_size"))

        mots = info["keywords"] or ["(fallback)"]
        kw = Label(text="Mots-cles : %s" % ", ".join(mots),
                   font_size=sp(11), size_hint_y=None, height=dp(20),
                   halign="left", valign="middle")
        kw.bind(size=kw.setter("text_size"))

        db_txt = info["db"] or "aucune"
        db_line = "BDD : %s (%.1f Mo)" % (db_txt, info["db_mo"])
        modele = info["model"] or "aucun"
        meta = Label(text="%s  -  Modele : %s" % (db_line, modele),
                     font_size=sp(10), size_hint_y=None, height=dp(20),
                     halign="left", valign="middle",
                     color=(0.9, 0.7, 0.3, 1))
        meta.bind(size=meta.setter("text_size"))

        card.add_widget(nom)
        card.add_widget(desc)
        card.add_widget(kw)
        card.add_widget(meta)
        liste.add_widget(card)

    scroll.add_widget(liste)
    root.add_widget(scroll)

    fermer = Button(text="Fermer", size_hint_y=None, height=dp(48))
    fermer.bind(on_release=lambda *_: vue.dismiss())
    root.add_widget(fermer)

    vue.add_widget(root)
    vue.open()
    return vue
