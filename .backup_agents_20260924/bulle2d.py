"""
agents/bulle2d.py — Bulle 3D réseau sphérique (version SAFE).
Utilise uniquement Line + Ellipse : 100% compatible Android.
"""
from __future__ import annotations

import math
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line
from kivy.uix.widget import Widget


class Bulle2D(Widget):
    NB_POINTS = 50
    NB_VOISINS = 4

    def __init__(self, on_tap=None, **kw):
        super().__init__(**kw)
        self.on_tap = on_tap
        self.etat = "veille"
        self.couleur = (1, 0.6, 0.2, 1)
        self.halo = 1.0
        self.t = 0.0
        self._event = None

        # Points sur sphère (Fibonacci)
        self.points_3d = []
        phi = math.pi * (3 - math.sqrt(5))
        for i in range(self.NB_POINTS):
            y = 1 - (i / float(self.NB_POINTS - 1)) * 2
            r = math.sqrt(max(0.0, 1 - y * y))
            theta = phi * i
            self.points_3d.append((math.cos(theta) * r, y, math.sin(theta) * r))

        # Connexions (voisins)
        self.connexions = []
        for i in range(self.NB_POINTS):
            p1 = self.points_3d[i]
            dist = []
            for j in range(self.NB_POINTS):
                if i == j:
                    continue
                p2 = self.points_3d[j]
                d = (p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2
                dist.append((d, j))
            dist.sort()
            for k in range(min(self.NB_VOISINS, len(dist))):
                j = dist[k][1]
                paire = (min(i, j), max(i, j))
                if paire not in self.connexions:
                    self.connexions.append(paire)

        self.angle_x = 0.0
        self.angle_y = 0.0
        self.angle_z = 0.0

        self._construire()
        self.set_fps(20)

    def _construire(self):
        self.canvas.clear()
        self.g_colors = []

        with self.canvas:
            # Halos
            self.g_halos = []
            for i in range(3):
                c = Color(1, 0.5, 0.15, 0.05)
                self.g_colors.append(c)
                e = Ellipse(pos=(0, 0), size=(1, 1))
                self.g_halos.append(e)

            # Disque accrétion
            self.g_disk = []
            for i in range(3):
                c = Color(1, 0.7, 0.3, 0.85)
                self.g_colors.append(c)
                arc = Line(circle=(0, 0, 1, 0, 130), width=2 + i * 1.5)
                self.g_disk.append(arc)

            # Anneau photon
            c = Color(1, 0.95, 0.6, 1)
            self.g_colors.append(c)
            self.g_ring = Line(circle=(0, 0, 1), width=1.5)

            # LIGNES du réseau (chaque connexion = 1 Line)
            self.g_lignes = []
            for _ in self.connexions:
                c = Color(1, 0.6, 0.2, 0.7)
                self.g_colors.append(c)
                line = Line(points=[0, 0, 0, 0], width=1.2)
                self.g_lignes.append(line)

            # POINTS (chaque point = 1 Ellipse)
            self.g_points = []
            for _ in range(self.NB_POINTS):
                c = Color(1, 0.9, 0.6, 1)
                self.g_colors.append(c)
                e = Ellipse(pos=(0, 0), size=(2, 2))
                self.g_points.append(e)

            # Trou noir
            c = Color(0, 0, 0, 1)
            self.g_colors.append(c)
            self.g_black = Ellipse(pos=(0, 0), size=(1, 1))

            # Coeur
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
        return min(self.width, self.height) / 2.0 * 0.88

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

    def _rotation(self, p, ax, ay, az):
        x, y, z = p
        cz, sz = math.cos(az), math.sin(az)
        x, y = x * cz - y * sz, x * sz + y * cz
        cx, sx = math.cos(ax), math.sin(ax)
        y, z = y * cx - z * sx, y * sx + z * cx
        cy, sy = math.cos(ay), math.sin(ay)
        x, z = x * cy + z * sy, -x * sy + z * cy
        return x, y, z

    def _update(self, dt):
        cx, cy = self.center_x, self.center_y
        R = self.rayon()
        if R <= 2:
            return

        e = self.etat
        if e == "veille":
            vitesse, intensite, alpha_lignes = 0.35, 0.55, 0.45
        elif e == "ecoute":
            vitesse, intensite, alpha_lignes = 0.9, 1.0, 0.75
        elif e == "reflexion":
            vitesse, intensite, alpha_lignes = 1.6, 1.0, 0.85
        elif e == "parle":
            vitesse, intensite, alpha_lignes = 0.7, 1.0, 0.65
        else:
            vitesse, intensite, alpha_lignes = 0.5, 1.0, 0.6

        self.angle_x = (self.angle_x + vitesse * dt * 0.8) % (2 * math.pi)
        self.angle_y = (self.angle_y + vitesse * dt * 1.2) % (2 * math.pi)
        self.angle_z = (self.t * 0.25 * vitesse) % (2 * math.pi)

        puls = 1.0 + math.sin(self.t * 2.0) * 0.03

        # Calculer les points projetés
        proj = []
        for i in range(self.NB_POINTS):
            p3 = self._rotation(self.points_3d[i],
                                self.angle_x, self.angle_y, self.angle_z)
            x, y, z = p3
            scale = 1.0 / (1.6 - z * 0.4)
            proj.append((x * R * scale * puls, y * R * scale * puls, z))

        # Mettre à jour les lignes
        for k, (a, b) in enumerate(self.connexions):
            x1, y1, _ = proj[a]
            x2, y2, _ = proj[b]
            self.g_lignes[k].points = [cx + x1, cy + y1, cx + x2, cy + y2]

        # Mettre à jour les points
        for i, (px, py, pz) in enumerate(proj):
            taille = 2.0 + (pz + 1) * 1.5
            e = self.g_points[i]
            e.size = (taille * 2, taille * 2)
            e.pos = (cx + px - taille, cy + py - taille)

        # Couleurs
        r0, g0, b0, _ = self.couleur
        halo_f = max(0.0, min(2.0, float(self.halo)))
        ci = 0

        # Halos
        for i, ell in enumerate(self.g_halos):
            hr = R * (0.5 + i * 0.12) * puls
            ell.size = (hr * 2, hr * 2)
            ell.pos = (cx - hr, cy - hr)
            self.g_colors[ci].rgba = (r0, g0 * 0.9, b0 * 0.8,
                                      (0.10 - i * 0.02) * intensite * halo_f)
            ci += 1

        # Disque
        disk_r = R * 0.30 * puls
        for i, arc in enumerate(self.g_disk):
            offset = (self.t * (30 + i * 20) * vitesse) % 360
            arc.circle = (cx, cy, disk_r + i * 2, offset, offset + 130)
            self.g_colors[ci].rgba = (1, 0.75, 0.35, (0.9 - i * 0.15) * intensite)
            ci += 1

        # Anneau photon
        ring_r = R * 0.24 * puls
        self.g_ring.circle = (cx, cy, ring_r)
        self.g_colors[ci].rgba = (1, 0.95, 0.6, intensite)
        ci += 1

        # Lignes
        for _ in self.connexions:
            self.g_colors[ci].rgba = (r0, g0, b0, alpha_lignes * intensite * halo_f)
            ci += 1

        # Points
        for _ in range(self.NB_POINTS):
            self.g_colors[ci].rgba = (1, 0.95, 0.75, min(1.0, intensite * 1.1))
            ci += 1

        # Trou noir
        black_r = R * 0.20 * puls
        self.g_black.size = (black_r * 2, black_r * 2)
        self.g_black.pos = (cx - black_r, cy - black_r)
        self.g_colors[ci].rgba = (0, 0, 0, 1)
        ci += 1

        # Coeur
        core_r = R * 0.02 * puls
        self.g_core.size = (core_r * 2, core_r * 2)
        self.g_core.pos = (cx - core_r, cy - core_r)
        self.g_colors[ci].rgba = (1, 0.95, 0.7, intensite * 0.9)
