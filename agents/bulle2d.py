"""
agents/bulle2d.py — Bulle Jarvis "trou noir" : plasma fluide tourbillonnant.
Inspiré de Interstellar + Arc reactor.
"""
from __future__ import annotations

import math
import random
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line
from kivy.uix.widget import Widget


class Bulle2D(Widget):
    """Trou noir central + plasma doré fluide. 4 états."""

    def __init__(self, on_tap=None, **kw):
        super().__init__(**kw)
        self.on_tap = on_tap
        self.etat = "veille"
        self.couleur = (1, 0.55, 0.15, 1)
        self.halo = 1.0
        self.t = 0.0
        self._event = None

        # Particules organisées en 6 bras spiraux fluides
        self.particules = []
        NB_BRAS = 6
        NB_PAR_BRAS = 16
        for b in range(NB_BRAS):
            angle_bras = (b / NB_BRAS) * 2 * math.pi
            for j in range(NB_PAR_BRAS):
                t_param = j / (NB_PAR_BRAS - 1)  # 0=intérieur, 1=extérieur
                r_base = 0.24 + t_param * 0.75
                self.particules.append({
                    "angle": angle_bras + t_param * 1.3,
                    "r": r_base,
                    "vit": 0.6 + (1.0 - t_param) * 2.2,
                    "taille": 1.8 + (1.0 - t_param) * 3.8,
                    "alpha_base": 0.25 + (1.0 - t_param) * 0.75,
                    "phase": random.uniform(0, 2 * math.pi),
                    "pulse": random.uniform(0.8, 2.5),
                    "wobble": random.uniform(0.015, 0.04),
                })

        self._construire()
        self.set_fps(30)

    def _construire(self):
        self.canvas.clear()
        self.g_colors = []
        self.g_halos = []
        self.g_particules = []
        self.g_disk = []
        self.g_black = None
        self.g_ring = None
        self.g_core = None

        with self.canvas:
            # Halos extérieurs (grands flous)
            for i in range(4):
                c = Color(1, 0.5, 0.15, 0.05)
                self.g_colors.append(c)
                e = Ellipse(pos=(0, 0), size=(1, 1))
                self.g_halos.append(e)

            # Plasma fluide (particules)
            for _ in self.particules:
                c = Color(1, 0.5, 0.15, 0.5)
                self.g_colors.append(c)
                e = Ellipse(pos=(0, 0), size=(2, 2))
                self.g_particules.append(e)

            # Disque d'accrétion (3 arcs épais)
            for i in range(3):
                c = Color(1, 0.6, 0.2, 0.9)
                self.g_colors.append(c)
                arc = Line(circle=(0, 0, 1, 0, 120), width=3 + i * 2)
                self.g_disk.append(arc)

            # Anneau de photon (fin, très lumineux)
            c = Color(1, 0.9, 0.5, 1)
            self.g_colors.append(c)
            self.g_ring = Line(circle=(0, 0, 1), width=2)

            # Trou noir (cercle noir)
            c = Color(0, 0, 0, 1)
            self.g_colors.append(c)
            self.g_black = Ellipse(pos=(0, 0), size=(1, 1))

            # Cœur ultra-brillant
            c = Color(1, 0.95, 0.7, 0.9)
            self.g_colors.append(c)
            self.g_core = Ellipse(pos=(0, 0), size=(2, 2))

    def set_fps(self, fps: int):
        if self._event:
            self._event.cancel()
        self._event = Clock.schedule_interval(self.maj, 1.0 / max(1, fps))

    def set_etat(self, e: str):
        self.etat = e

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
            vitesse, intensite = 0.4, 0.55
            puls = 1.0 + math.sin(self.t * 1.2) * 0.04
        elif e == "ecoute":
            vitesse, intensite = 1.8, 1.0
            puls = 1.0 + math.sin(self.t * 4.0) * 0.06
        elif e == "reflexion":
            vitesse, intensite = 3.0, 1.0
            puls = 1.0 + math.sin(self.t * 7.0) * 0.04
        elif e == "parle":
            vitesse, intensite = 1.2, 1.0
            puls = 1.0 + math.sin(self.t * 9.0) * 0.10
        else:
            vitesse, intensite = 1.0, 1.0
            puls = 1.0

        r0, g0, b0, _ = self.couleur
        halo_f = max(0.0, min(2.0, float(self.halo)))
        ci = 0

        # ===== HALOS =====
        for i, ell in enumerate(self.g_halos):
            hr = R * (0.55 + i * 0.13) * puls
            ell.size = (hr * 2, hr * 2)
            ell.pos = (cx - hr, cy - hr)
            self.g_colors[ci].rgba = (
                r0, g0 * 0.9, b0 * 0.8, (0.11 - i * 0.02) * intensite * halo_f)
            ci += 1

        # ===== PLASMA (particules fluides) =====
        for i, p in enumerate(self.particules):
            p["angle"] = (p["angle"] + p["vit"] * dt * vitesse * 0.6) % (2 * math.pi)
            wobble = math.sin(self.t * 1.5 + p["phase"]) * p["wobble"]
            r_eff = max(0.05, p["r"] + wobble)
            px = cx + math.cos(p["angle"]) * R * r_eff * puls
            py = cy + math.sin(p["angle"]) * R * r_eff * puls
            taille = p["taille"] * (0.85 + math.sin(self.t * p["pulse"] + p["phase"]) * 0.15)
            g = self.g_particules[i]
            g.size = (taille * 2, taille * 2)
            g.pos = (px - taille, py - taille)
            alpha = p["alpha_base"] * intensite * halo_f
            if p["r"] < 0.4:
                alpha = min(1.0, alpha * 1.6)
            self.g_colors[ci].rgba = (
                min(1.0, r0 * 1.1), g0 * 0.85, b0 * 0.7, alpha)
            ci += 1

        # ===== DISQUE D'ACCRÉTION =====
        disk_radius = R * 0.28 * puls
        for i, arc in enumerate(self.g_disk):
            offset = (self.t * (1.5 + i * 0.3) * vitesse * 40) % 360
            arc.circle = (cx, cy, disk_radius + i * 3, offset, offset + 120)
            self.g_colors[ci].rgba = (1, 0.75, 0.35, (0.9 - i * 0.15) * intensite)
            ci += 1

        # ===== ANNEAU DE PHOTON =====
        ring_r = R * 0.22 * puls
        self.g_ring.circle = (cx, cy, ring_r)
        self.g_colors[ci].rgba = (1, 0.95, 0.6, intensite)
        ci += 1

        # ===== TROU NOIR =====
        black_r = R * 0.18 * puls
        self.g_black.size = (black_r * 2, black_r * 2)
        self.g_black.pos = (cx - black_r, cy - black_r)
        self.g_colors[ci].rgba = (0, 0, 0, 1)
        ci += 1

        # ===== CŒUR =====
        core_r = R * 0.015 * puls
        self.g_core.size = (core_r * 2, core_r * 2)
        self.g_core.pos = (cx - core_r, cy - core_r)
        self.g_colors[ci].rgba = (1, 0.95, 0.7, intensite * 0.8)
