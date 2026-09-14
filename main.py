from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

class JinxApp(App):
    def build(self):
        layout = BoxLayout(orientation='vertical')
        self.label = Label(text="Salut, je suis Jinx.", font_size=24)
        bouton = Button(text="Parler a Jinx", font_size=24, size_hint=(1, 0.3))
        bouton.bind(on_press=self.parler)
        layout.add_widget(self.label)
        layout.add_widget(bouton)
        return layout

    def parler(self, instance):
        self.label.text = "Jinx t'ecoute..."

if __name__ == "__main__":
    JinxApp().run()
