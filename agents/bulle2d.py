"""
agents/bulle2d.py — Bulle 3D "réseau sphérique" style Jarvis.
Optimisée : Mesh unique, rotation matricielle, 50 points, 20 FPS.
"""
from __future__ import annotations

import math
import random
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Mesh, PointSize
from kivy.uix.widget import Widget

# Numpy optionnel (accélère beaucoup)
try:
    import numpy as _np
    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False


class Bulle2D(Widget):
    """Réseau sphérique 3D rotatif + trou noir central."""

    NB_POINTS = 50
    NB_VOISINS = 4  # connexions par point

    def __init__(self, on_tap=None, **kw):
        super().__init__(**kw)
        self.on_tap = on_tap
        self.etat = "veille"
        self.couleur = (1, 0.6, 0.2, 1)
        self.halo = 1.0
        self.t = 0.0
        self._event = None

        # --- Générer les points sur une sphère (Fibonacci) ---
        self.points_3d = []
        phi = math.pi * (3 - math.sqrt(5))  # angle d'or
        for i in range(self.NB_POINTS):
            y = 1 - (i / float(self.NB_POINTS - 1)) * 2
            r = math.sqrt(max(0.0, 1 - y * y))
            theta = phi * i
            x = math.cos(theta) * r
            z = math.sin(theta) * r
            self.points_3d.append((x, y, z))

        # --- Précalculer les connexions (voisins les plus proches) ---
        self.connexions = set()
        for i in range(self.NB_POINTS):
            p1 = self.points_3d[i]
            distances = []
            for j in range(self.NB_POINTS):
                if i == j:
                    continue
                p2 = self.points_3d[j]
                d = ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)
                distances.append((d, j))
            distances.sort()
            for k in range(min(self.NB_VOISINS, len(distances))):
                j = distances[k][1]
                self.connexions.add((min(i, j), max(i, j)))
        self.connexions = list(self.connexions)

        # --- Buffers Mesh ---
        # Chaque connexion = 2 vertices × 2 coords = 4 floats
        self.vertices_lignes = [0.0] * (len(self.connexions) * 4)
        # Chaque point = 2 coords
        self.vertices_points = [0.0] * (self.NB_POINTS * 2)

        # --- Angle de rotation ---
        self.angle_x = 0.0
        self.angle_y = 0.0

        self._construire()
        self.set_fps(30)

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

            # Disque d'accrétion (3 arcs)
            self.g_disk = []
            for i in range(3):
                c = Color(1, 0.7, 0.3, 0.9)
                self.g_colors.append(c)
                arc = Line(circle=(0, 0, 1, 0, 130), width=2.5 + i * 1.5)
                self.g_disk.append(arc)

            # Anneau photon
            c = Color(1, 0.95, 0.6, 1)
            self.g_colors.append(c)
            self.g_ring = Line(circle=(0, 0, 1), width=1.5)

            # LIGNES (Mesh unique)
            c = Color(1, 0.6, 0.2, 0.7)
            self.g_colors.append(c)
            self.g_mesh_lignes = Mesh(
                vertices=self.vertices_lignes,
                indices=list(range(len(self.vertices_lignes) // 2)),
                mode="lines",
            )

            # POINTS (Mesh unique)
            c = Color(1, 0.9, 0.6, 1)
            self.g_colors.append(c)
            self.g_mesh_points = Mesh(
                vertices=self.vertices_points,
                indices=list(range(self.NB_POINTS)),
                mode="points",
            )

            # Trou noir
            c = Color(0, 0, 0, 1)
            self.g_colors.append(c)
            self.g_black = Ellipse(pos=(0, 0), size=(1, 1))

            # Cœur brillant
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
        """Applique 3 rotations (X, Y, Z) à un point."""
        x, y, z = p
        # Rot Z
        cz, sz = math.cos(az), math.sin(az)
        x, y = x * cz - y * sz, x * sz + y * cz
        # Rot X
        cx, sx = math.cos(ax), math.sin(ax)
        y, z = y * cx - z * sx, y * sx + z * cx
        # Rot Y
        cy, sy = math.cos(ay), math.sin(ay)
        x, z = x * cy + z * sy, -x * sy + z * cy
        return x, y, z

    def _projection(self, p, R):
        """Projection perspective simple."""
        x, y, z = p
        # Perspective : plus proche = plus grand
        scale = 1.0 / (1.6 - z * 0.4)
        return x * R * scale, y * R * scale, z

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

        # Rotation continue
        self.angle_x = (self.angle_x + vitesse * dt * 0.8) % (2 * math.pi)
        self.angle_y = (self.angle_y + vitesse * dt * 1.2) % (2 * math.pi)
        self.angle_z = (self.t * 0.25 * vitesse) % (2 * math.pi)

        # Pulsation légère du rayon
        puls = 1.0 + math.sin(self.t * 2.0 * (0.5 + vitesse)) * 0.03

        # --- Calculer les 50 points projetés ---
        proj = []
        for i in range(self.NB_POINTS):
            p3 = self._rotation(self.points_3d[i],
                                self.angle_x, self.angle_y, self.angle_z)
            px, py, pz = self._projection(p3, R * puls)
            proj.append((px, py, pz))

        # --- Mettre à jour le mesh des lignes ---
        vl = self.vertices_lignes
        i = 0
        for (a, b) in self.connexions:
            x1, y1, z1 = proj[a]
            x2, y2, z2 = proj[b]
            vl[i]   = cx + x1
            vl[i+1] = cy + y1
            vl[i+2] = cx + x2
            vl[i+3] = cy + y2
            i += 4
        self.g_mesh_lignes.vertices = vl

        # --- Mettre à jour le mesh des points ---
        vp = self.vertices_points
        for idx, (px, py, pz) in enumerate(proj):
            vp[idx*2]   = cx + px
            vp[idx*2+1] = cy + py
        self.g_mesh_points.vertices = vp

        # --- Couleurs ---
        r0, g0, b0, _ = self.couleur
        halo_f = max(0.0, min(2.0, float(self.halo)))
        ci = 0

        # Halos
        for i, ell in enumerate(self.g_halos):
            hr = R * (0.5 + i * 0.12) * puls
            ell.size = (hr * 2, hr * 2)
            ell.pos = (cx - hr, cy - hr)
            self.g_colors[ci].rgba = (
                r0, g0 * 0.9, b0 * 0.8, (0.10 - i * 0.02) * intensite * halo_f)
            ci += 1

        # Disque
        disk_r = R * 0.30 * puls
        for i, arc in enumerate(self.g_disk):
            offset = (self.t * (30 + i * 20) * vitesse) % 360
            arc.circle = (cx, cy, disk_r + i * 2, offset, offset + 130)
            self.g_colors[ci].rgba = (1, 0.75, 0.35,
                                      (0.9 - i * 0.15) * intensite)
            ci += 1

        # Anneau photon
        ring_r = R * 0.24 * puls
        self.g_ring.circle = (cx, cy, ring_r)
        self.g_colors[ci].rgba = (1, 0.95, 0.6, intensite)
        ci += 1

        # Lignes (couleur thème)
        self.g_colors[ci].rgba = (r0, g0, b0, alpha_lignes * intensite * halo_f)
        ci += 1

        # Points (blancs chauds)
        self.g_colors[ci].rgba = (1, 0.95, 0.75, min(1.0, intensite * 1.1))
        ci += 1

        # Trou noir
        black_r = R * 0.20 * puls
        self.g_black.size = (black_r * 2, black_r * 2)
        self.g_black.pos = (cx - black_r, cy - black_r)
        self.g_colors[ci].rgba = (0, 0, 0, 1)
        ci += 1

        # Cœur
        core_r = R * 0.02 * puls
        self.g_core.size = (core_r * 2, core_r * 2)
        self.g_core.pos = (cx - core_r, cy - core_r)
        self.g_colors[ci].rgba = (1, 0.95, 0.7, intensite * 0.9)
