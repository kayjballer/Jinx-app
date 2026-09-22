
"""
agents/bulle2d.py — Bulle Jarvis 2D (radar animé ultra-léger).
API identique à l'ancienne Bulle 3D : set_etat, set_fps, rayon, couleur, halo.
"""
from __future__ import annotations

import math
import random
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line
from kivy.uix.widget import Widget


class Bulle2D(Widget):
    """Radar Jarvis : 3 anneaux + particules + ondes. ~5% CPU."""

    def __init__(self, on_tap=None, **kw):
        super().__init__(**kw)
        self.on_tap = on_tap
        self.etat = "veille"
        self.couleur = (1, 0.6, 0.2, 1)
        self.halo = 1.0
        self.theme = "or"
        self.t = 0.0
        self.fps_cible = 30
        self._event = None

        self.anneaux_cfg = [
            {"r": 0.46, "vit":  0.35, "nb": 3, "ep": 2.5, "alpha": 0.85},
            {"r": 0.34, "vit": -0.55, "nb": 4, "ep": 2.0, "alpha": 0.65},
            {"r": 0.22, "vit":  0.90, "nb": 2, "ep": 1.8, "alpha": 0.55},
        ]

        self.particules = [{
            "angle": random.uniform(0, 360),
            "r":     random.uniform(0.40, 0.48),
            "vit":   random.uniform(0.4, 1.5) * random.choice([-1, 1]),
            "taille": random.uniform(1.5, 3.0),
        } for _ in range(18)]

        self.ondes = []
        self._event = None
        self._construire()
        self.set_fps(30)

    def _construire(self):
        self.canvas.clear()
        self.g_colors = []
        self.g_halo = []
        self.g_anneaux = []
        self.g_particules = []
        self.g_ondes = []
        self.g_coeur = None
        self.g_bright = None

        with self.canvas:
            for i in range(3):
                c = Color(1, 0.6, 0.2, 0.06)
                self.g_colors.append(c)
                e = Ellipse(pos=(0, 0), size=(1, 1))
                self.g_halo.append(e)

            for cfg in self.anneaux_cfg:
                arcs = []
                for _ in range(cfg["nb"]):
                    c = Color(1, 0.6, 0.2, cfg["alpha"])
                    self.g_colors.append(c)
                    line = Line(circle=(0, 0, 1, 0, 60), width=cfg["ep"])
                    arcs.append(line)
                self.g_anneaux.append(arcs)

            for _ in self.particules:
                c = Color(1, 1, 1, 0.9)
                self.g_colors.append(c)
                e = Ellipse(pos=(0, 0), size=(2, 2))
                self.g_particules.append(e)

            for _ in range(6):
                c = Color(1, 1, 1, 0)
                self.g_colors.append(c)
                line = Line(circle=(0, 0, 1), width=1.5)
                self.g_ondes.append(line)

            c = Color(1, 0.6, 0.2, 1)
            self.g_colors.append(c)
            self.g_coeur = Ellipse(pos=(0, 0), size=(10, 10))

            c = Color(1, 1, 1, 0.95)
            self.g_colors.append(c)
            self.g_bright = Ellipse(pos=(0, 0), size=(5, 5))

    def set_fps(self, fps: int):
        self.fps_cible = fps
        if self._event:
            self._event.cancel()
        self._event = Clock.schedule_interval(self.maj, 1.0 / max(1, fps))

    def set_etat(self, e: str):
        if e == self.etat:
            return
        self.etat = e
        if e == "parle":
            self.ondes.append({"r": 0.15, "alpha": 0.9})

    def rayon(self) -> float:
        return min(self.width, self.height) / 2.0 * 0.92

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.on_tap:
                self.on_tap(touch)
            return True
        return super().on_touch_down(touch)

    def maj(self, dt):
        self.t += dt
        try:
            self._update(dt)
        except Exception:
            pass

    def _update(self, dt):
        cx, cy = self.center_x, self.center_y
        R = self.rayon()
        if R <= 2:
            return

        e = self.etat
        if e == "veille":
            vitesse, intensite = 0.5, 0.6
            puls = 1.0 + math.sin(self.t * 1.5) * 0.03
        elif e == "ecoute":
            vitesse, intensite = 1.6, 1.0
            puls = 1.0 + math.sin(self.t * 4.5) * 0.08
        elif e == "reflexion":
            vitesse, intensite = 2.6, 1.0
            puls = 1.0 + math.sin(self.t * 6.0) * 0.05
        elif e == "parle":
            vitesse, intensite = 1.1, 1.0
            puls = 1.0 + math.sin(self.t * 8.0) * 0.12
        else:
            vitesse, intensite = 1.0, 1.0
            puls = 1.0

        r0, g0, b0, a0 = self.couleur
        halo_f = max(0.0, min(2.0, float(self.halo)))

        for i, ell in enumerate(self.g_halo):
            hr = R * (0.35 + i * 0.18) * puls
            ell.size = (hr * 2, hr * 2)
            ell.pos = (cx - hr, cy - hr)
        for i in range(3):
            base_a = 0.08 - i * 0.022
            self.g_colors[i].rgba = (r0, g0, b0, base_a * intensite * halo_f)

        color_idx = 3
        for idx, cfg in enumerate(self.anneaux_cfg):
            r_anneau = R * cfg["r"] * puls
            angle_base = (self.t * cfg["vit"] * 60 * vitesse) % 360
            for j, arc in enumerate(self.g_anneaux[idx]):
                start = angle_base + j * (360.0 / cfg["nb"])
                end = start + 70.0
                arc.circle = (cx, cy, r_anneau, start, end)
                self.g_colors[color_idx].rgba = (
                    r0, g0, b0, cfg["alpha"] * intensite * halo_f)
                color_idx += 1

        for i, p in enumerate(self.particules):
            p["angle"] = (p["angle"] + p["vit"] * 60 * dt * vitesse) % 360
            rad = math.radians(p["angle"])
            px = cx + math.cos(rad) * R * p["r"] * puls
            py = cy + math.sin(rad) * R * p["r"] * puls
            tt = p["taille"]
            g = self.g_particules[i]
            g.size = (tt * 2, tt * 2)
            g.pos = (px - tt, py - tt)
            self.g_colors[color_idx].rgba = (1, 1, 1, 0.9 * intensite)
            color_idx += 1

        if e == "parle" and random.random() < 0.10:
            self.ondes.append({"r": 0.15, "alpha": 0.9})

        vivantes = []
        for ond in self.ondes:
            ond["r"] += dt * 0.7
            ond["alpha"] -= dt * 1.1
            if ond["alpha"] > 0.02 and ond["r"] < 0.95:
                vivantes.append(ond)
        self.ondes = vivantes

        for i, line in enumerate(self.g_ondes):
            if i < len(self.ondes):
                ond = self.ondes[i]
                rr = R * ond["r"]
                line.circle = (cx, cy, rr)
                self.g_colors[color_idx].rgba = (r0, g0, b0, ond["alpha"])
            else:
                line.circle = (cx, cy, 1)
                self.g_colors[color_idx].rgba = (r0, g0, b0, 0)
            color_idx += 1

        coeur_r = R * 0.13 * puls
        self.g_coeur.size = (coeur_r * 2, coeur_r * 2)
        self.g_coeur.pos = (cx - coeur_r, cy - coeur_r)
        self.g_colors[color_idx].rgba = (r0, g0, b0, intensite)
        color_idx += 1

        bright_r = R * 0.06 * puls
        self.g_bright.size = (bright_r * 2, bright_r * 2)
        self.g_bright.pos = (cx - bright_r, cy - bright_r)
        self.g_colors[color_idx].rgba = (1, 1, 1, 0.95 * intensite)
