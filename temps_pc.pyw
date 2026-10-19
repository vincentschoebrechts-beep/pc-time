#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temps PC - combien de temps je passe sur mon ordinateur, jour par jour.

Lancement (Windows) : double-clic sur ce fichier.
Python 3 doit etre installe : https://www.python.org/downloads/
(pendant l'installation, cocher « Add python.exe to PATH »).

- Seul le temps ACTIF est compte : apres quelques minutes sans souris ni
  clavier, le compteur se met en pause et retire ces minutes d'inactivite.
- L'icone dans la barre des taches affiche le temps du jour, mise a jour
  chaque minute. Vert = actif, gris = en pause (icone et graphiques).
- Fermer la fenetre la reduit dans la barre des taches : le suivi continue.
  Le bouton « Quitter » arrete vraiment l'application.
- Les donnees restent sur ce PC (Windows : %APPDATA%\\TempsPC\\donnees.json).
"""
from __future__ import annotations

import csv
import ctypes
import ctypes.util
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NOM = "Temps PC"
TICK_MS = 2000        # une mesure toutes les 2 secondes
SAUVEGARDE_S = 30     # ecriture sur le disque toutes les 30 secondes
ECART_MAX_S = 30      # trou plus long entre deux mesures = veille du PC : non compte
PORT = 47615          # sert a n'avoir qu'une seule copie de l'appli ouverte
WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
JOURS_COURTS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]

POLICE = "Segoe UI" if WIN else ("Helvetica Neue" if MAC else "DejaVu Sans")

THEMES = {
    "clair": dict(fond="#fcfcfb", carte="#f1f0ec", texte="#0b0b0b", texte2="#52514e",
                  discret="#86857f", grille="#e8e7e3", axe="#c9c8c3",
                  barre_actif="#1f9d4a", passee_actif="#6fc28c",
                  barre_pause="#8a8984", passee_pause="#bdbcb6", actif="#1f9d4a",
                  bouton="#ecebe7", bouton_survol="#dfded9", bulle="#262624",
                  bulle_texte="#fcfcfb", survol_col="#f1f0ec"),
    "sombre": dict(fond="#1a1a19", carte="#252524", texte="#f0efec", texte2="#c3c2b7",
                   discret="#8f8e86", grille="#2c2c2a", axe="#4a4a47",
                   barre_actif="#34b864", passee_actif="#22703f",
                   barre_pause="#8f8e86", passee_pause="#4a4a47", actif="#34b864",
                   bouton="#2b2b29", bouton_survol="#373734", bulle="#f0efec",
                   bulle_texte="#1a1a19", survol_col="#242423"),
}


# --------------------------------------------------------------------------
# Petits utilitaires
# --------------------------------------------------------------------------
def duree(sec: float) -> str:
    """'3 h 05 min' ou '42 min'."""
    m = int(max(0, sec) // 60)
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def duree_courte(sec: float) -> str:
    """'3 h 05' ou '42 min'."""
    m = int(max(0, sec) // 60)
    h, m = divmod(m, 60)
    return f"{h} h {m:02d}" if h else f"{m} min"


def heure_txt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def dossier_donnees() -> str:
    perso = os.environ.get("TEMPS_PC_DOSSIER")
    if perso:
        return perso
    if WIN:
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "TempsPC")
    if MAC:
        return os.path.expanduser("~/Library/Application Support/TempsPC")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "temps-pc")


def ouvrir_dossier(chemin: str) -> None:
    os.makedirs(chemin, exist_ok=True)
    if WIN:
        os.startfile(chemin)  # type: ignore[attr-defined]
    elif MAC:
        subprocess.Popen(["open", chemin])
    else:
        subprocess.Popen(["xdg-open", chemin])


def theme_sombre() -> bool:
    choix = os.environ.get("TEMPS_PC_THEME")
    if choix in ("clair", "sombre"):
        return choix == "sombre"
    try:
        if WIN:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        if MAC:
            r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                               capture_output=True, text=True, timeout=2)
            return "Dark" in r.stdout
    except Exception:
        pass
    return False


def barre_titre_sombre(fenetre: tk.Misc) -> None:
    """Barre de titre sombre sous Windows 10/11 quand le theme est sombre."""
    if not WIN:
        return
    try:
        fenetre.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(fenetre.winfo_id())
        val = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (selon la version)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), 4) == 0:
                break
    except Exception:
        pass


# --------------------------------------------------------------------------
# Detection d'inactivite (temps depuis la derniere action souris/clavier)
# --------------------------------------------------------------------------
class DetecteurInactivite:
    def __init__(self) -> None:
        self.methode: str | None = None
        self._fn = None
        try:
            if WIN:
                self._init_windows()
            elif MAC:
                self._init_mac()
            else:
                self._init_linux()
        except Exception:
            self._fn = None
            self.methode = None

    def secondes(self) -> float | None:
        if not self._fn:
            return None
        try:
            return self._fn()
        except Exception:
            return None

    def _init_windows(self) -> None:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint32)]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetTickCount.restype = ctypes.c_uint32

        def lire() -> float | None:
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if not user32.GetLastInputInfo(ctypes.byref(lii)):
                return None
            return ((kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0

        self._fn, self.methode = lire, "windows"

    def _init_mac(self) -> None:
        def lire() -> float | None:
            sortie = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True,
                                    text=True, timeout=3).stdout
            m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', sortie)
            return int(m.group(1)) / 1e9 if m else None

        if lire() is not None:
            self._fn, self.methode = lire, "mac"

    def _init_linux(self) -> None:
        x11, xss = ctypes.util.find_library("X11"), ctypes.util.find_library("Xss")
        if x11 and xss and os.environ.get("DISPLAY"):
            class XScreenSaverInfo(ctypes.Structure):
                _fields_ = [("window", ctypes.c_ulong), ("state", ctypes.c_int),
                            ("kind", ctypes.c_int), ("til_or_since", ctypes.c_ulong),
                            ("idle", ctypes.c_ulong), ("eventMask", ctypes.c_ulong)]

            xlib, libxss = ctypes.cdll.LoadLibrary(x11), ctypes.cdll.LoadLibrary(xss)
            xlib.XOpenDisplay.restype = ctypes.c_void_p
            xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            xlib.XDefaultRootWindow.restype = ctypes.c_ulong
            xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            libxss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)
            libxss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                                     ctypes.POINTER(XScreenSaverInfo)]
            affichage = xlib.XOpenDisplay(None)
            if affichage:
                racine = xlib.XDefaultRootWindow(affichage)
                info = libxss.XScreenSaverAllocInfo()

                def lire() -> float | None:
                    if not libxss.XScreenSaverQueryInfo(affichage, racine, info):
                        return None
                    return info.contents.idle / 1000.0

                if lire() is not None:
                    self._fn, self.methode = lire, "x11"
                    return
        if shutil.which("xprintidle"):
            def lire2() -> float | None:
                r = subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=2)
                return int(r.stdout.strip()) / 1000.0

            self._fn, self.methode = lire2, "xprintidle"


# --------------------------------------------------------------------------
# Donnees (un fichier JSON)
# --------------------------------------------------------------------------
REGLAGES_DEFAUT = {
    "pause_si_inactif": True,
    "minutes_inactivite": 5,
    "question_demarrage_posee": False,
    "info_reduction_vue": False,
}


class Donnees:
    def __init__(self, dossier: str) -> None:
        self.dossier = dossier
        self.chemin = os.path.join(dossier, "donnees.json")
        self.avertissement: str | None = None
        self.jours: dict[str, dict] = {}
        self.reglages = dict(REGLAGES_DEFAUT)
        self._charger()

    def _charger(self) -> None:
        if not os.path.exists(self.chemin):
            return
        try:
            with open(self.chemin, encoding="utf-8") as f:
                brut = json.load(f)
            for cle, j in brut.get("jours", {}).items():
                date.fromisoformat(cle)
                heures = [float(x) for x in j.get("heures", [])][:24]
                heures += [0.0] * (24 - len(heures))
                self.jours[cle] = {"heures": heures, "premiere": j.get("premiere"),
                                   "derniere": j.get("derniere")}
            self.reglages.update(brut.get("reglages", {}))
        except Exception as e:
            self.jours = {}
            copie = self.chemin + f".illisible-{datetime.now():%Y%m%d-%H%M%S}"
            try:
                os.replace(self.chemin, copie)
            except OSError:
                copie = self.chemin
            self.avertissement = ("Le fichier de données n'a pas pu être lu "
                                  f"({e}).\n\nIl a été mis de côté ici :\n{copie}")

    def jour(self, cle: str) -> dict:
        return self.jours.setdefault(cle, {"heures": [0.0] * 24, "premiere": None, "derniere": None})

    def total(self, cle: str) -> float:
        j = self.jours.get(cle)
        return sum(j["heures"]) if j else 0.0

    def enregistrer(self) -> None:
        os.makedirs(self.dossier, exist_ok=True)
        contenu = {
            "application": APP_NOM,
            "version": 1,
            "reglages": self.reglages,
            "jours": {k: {"heures": [round(x, 1) for x in j["heures"]],
                          "premiere": j["premiere"], "derniere": j["derniere"]}
                      for k, j in sorted(self.jours.items())},
        }
        tmp = self.chemin + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(contenu, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.chemin)


# --------------------------------------------------------------------------
# Compteur : decide si le temps ecoule compte ou non
# --------------------------------------------------------------------------
class Compteur:
    def __init__(self, donnees: Donnees, detecteur: DetecteurInactivite, horloge=time.time) -> None:
        self.d = donnees
        self.det = detecteur
        self.horloge = horloge
        self.actif = True
        self.inactif_depuis = 0.0
        self.dernier_tick = horloge()
        self.segments: deque = deque()  # morceaux comptes recemment (pour pouvoir les retirer)

    def seuil(self) -> float | None:
        r = self.d.reglages
        if not r.get("pause_si_inactif", True) or self.det.methode is None:
            return None
        try:
            minutes = int(r.get("minutes_inactivite", 5))
        except (TypeError, ValueError):
            minutes = 5
        return max(1, minutes) * 60

    def tick(self) -> None:
        maintenant = self.horloge()
        dt = maintenant - self.dernier_tick
        self.dernier_tick = maintenant
        inactif = self.det.secondes()
        self.inactif_depuis = inactif or 0.0
        seuil = self.seuil()
        if seuil is not None and inactif is not None and inactif >= seuil:
            if self.actif:
                # On vient de passer en pause : on retire les minutes deja
                # comptees depuis la derniere action souris/clavier.
                self._retirer_depuis(maintenant - inactif)
                self.actif = False
        else:
            self.actif = True
            if 0 < dt <= ECART_MAX_S:
                self._ajouter(maintenant - dt, maintenant)
        limite = maintenant - (seuil or 0) - 120
        while self.segments and self.segments[0][1] < limite:
            self.segments.popleft()

    @staticmethod
    def _repartir(t0: float, t1: float):
        """Decoupe [t0, t1] par heure (et donc par jour)."""
        t = t0
        while t < t1:
            d = datetime.fromtimestamp(t)
            fin_heure = (d.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).timestamp()
            fin = min(t1, fin_heure)
            if fin <= t:  # securite (changement d'heure)
                fin = t1
            yield d.date().isoformat(), d.hour, t, fin
            t = fin

    def _ajouter(self, t0: float, t1: float) -> None:
        for cle, h, a, b in self._repartir(t0, t1):
            j = self.d.jour(cle)
            j["heures"][h] += b - a
            if not j["premiere"]:
                j["premiere"] = heure_txt(a)
            j["derniere"] = heure_txt(b)
        if self.segments and abs(self.segments[-1][1] - t0) < 1e-6:
            self.segments[-1] = (self.segments[-1][0], t1)
        else:
            self.segments.append((t0, t1))

    def _retirer_depuis(self, ts: float) -> None:
        gardes: deque = deque()
        touches = set()
        for a, b in self.segments:
            if b <= ts:
                gardes.append((a, b))
                continue
            for cle, h, x, y in self._repartir(max(a, ts), b):
                j = self.d.jour(cle)
                j["heures"][h] = max(0.0, j["heures"][h] - (y - x))
                touches.add(cle)
            if a < ts:
                gardes.append((a, ts))
        self.segments = gardes
        jour_ts = datetime.fromtimestamp(ts).date().isoformat()
        for cle in touches:
            j = self.d.jours[cle]
            if sum(j["heures"]) < 1:
                j["premiere"] = j["derniere"] = None
            elif cle == jour_ts:
                j["derniere"] = heure_txt(ts)


# --------------------------------------------------------------------------
# Lancement automatique au demarrage
# --------------------------------------------------------------------------
class Demarrage:
    CLE_WIN = r"Software\Microsoft\Windows\CurrentVersion\Run"
    NOM = "TempsPC"

    @staticmethod
    def commande() -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, "--minimise"]
        exe = sys.executable
        if WIN:
            pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
            if os.path.exists(pyw):
                exe = pyw
        return [exe, os.path.abspath(__file__), "--minimise"]

    @staticmethod
    def _plist() -> str:
        return os.path.expanduser("~/Library/LaunchAgents/be.tempspc.plist")

    @staticmethod
    def _desktop() -> str:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return os.path.join(base, "autostart", "temps-pc.desktop")

    @classmethod
    def actif(cls) -> bool:
        if WIN:
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.CLE_WIN) as k:
                    winreg.QueryValueEx(k, cls.NOM)
                return True
            except OSError:
                return False
        return os.path.exists(cls._plist() if MAC else cls._desktop())

    @classmethod
    def regler(cls, active: bool) -> None:
        cmd = cls.commande()
        if WIN:
            import winreg
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, cls.CLE_WIN, 0,
                                    winreg.KEY_SET_VALUE) as k:
                if active:
                    winreg.SetValueEx(k, cls.NOM, 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
                else:
                    try:
                        winreg.DeleteValue(k, cls.NOM)
                    except FileNotFoundError:
                        pass
        elif MAC:
            import plistlib
            chemin = cls._plist()
            if active:
                os.makedirs(os.path.dirname(chemin), exist_ok=True)
                with open(chemin, "wb") as f:
                    plistlib.dump({"Label": "be.tempspc", "ProgramArguments": cmd,
                                   "RunAtLoad": True}, f)
            elif os.path.exists(chemin):
                os.remove(chemin)
        else:
            chemin = cls._desktop()
            if active:
                def q(arg: str) -> str:
                    for c in ('\\', '"', '`', '$'):
                        arg = arg.replace(c, '\\' + c)
                    return f'"{arg}"'
                os.makedirs(os.path.dirname(chemin), exist_ok=True)
                with open(chemin, "w", encoding="utf-8") as f:
                    f.write("[Desktop Entry]\nType=Application\nName=Temps PC\n"
                            f"Exec={' '.join(q(a) for a in cmd)}\n"
                            "X-GNOME-Autostart-enabled=true\n")
            elif os.path.exists(chemin):
                os.remove(chemin)


# --------------------------------------------------------------------------
# Une seule copie ouverte : la 2e demande a la 1re de se montrer
# --------------------------------------------------------------------------
def signaler_instance_existante() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.6) as s:
            s.sendall(b"TEMPS-PC MONTRER\n")
            return s.recv(8).startswith(b"OK")
    except OSError:
        return False


def ouvrir_serveur() -> socket.socket | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if not WIN:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", PORT))
        s.listen(4)
        s.setblocking(False)
        return s
    except OSError:
        return None


# --------------------------------------------------------------------------
# Interface
# --------------------------------------------------------------------------
@dataclass
class Barre:
    valeur: float
    axe: str
    bulle: str
    couleur: str
    fort: bool = False
    etiquette: str | None = None


def rectangle_arrondi_haut(c: tk.Canvas, x0, y0, x1, y1, r, **kw):
    r = min(r, (x1 - x0) / 2, (y1 - y0))
    if r < 1:
        return c.create_rectangle(x0, y0, x1, y1, width=0, **kw)
    pts = [x0, y1, x0, y1, x0, y0 + r, x0, y0 + r, x0, y0, x0 + r, y0, x0 + r, y0,
           x1 - r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y0 + r, x1, y1, x1, y1]
    return c.create_polygon(pts, smooth=True, outline="", **kw)


class Graphique(tk.Canvas):
    def __init__(self, master, app: "Application", hauteur: int, ratio: float) -> None:
        super().__init__(master, height=app.px(hauteur), bg=app.th["fond"],
                         highlightthickness=0, bd=0)
        self.app = app
        self.ratio = ratio
        self.barres: list[Barre] = []
        self.ymax = 3600.0
        self.graduations: list[tuple[float, str]] = []
        self.zones: list[tuple[float, float, float]] = []
        self.survol: int | None = None
        self._etat = None
        self.bind("<Configure>", lambda e: self.dessiner())
        self.bind("<Motion>", self._bouge)
        self.bind("<Leave>", self._sort)

    def maj(self, barres, ymax, graduations) -> None:
        etat = (barres, ymax, graduations)
        if etat == self._etat:
            return
        self._etat = etat
        self.barres, self.ymax, self.graduations = barres, ymax, graduations
        self.dessiner()

    def dessiner(self) -> None:
        self.delete("all")
        th, px = self.app.th, self.app.px
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60 or not self.barres:
            return
        g, d, haut, bas = px(58), px(4), px(22), px(22)
        pw, ph = w - g - d, h - haut - bas
        y0 = haut + ph
        petite = (POLICE, 9)
        for v, txt in self.graduations:
            y = y0 - v / self.ymax * ph
            self.create_line(g, y, w - d, y, fill=th["grille"])
            self.create_text(g - px(8), y, text=txt, anchor="e", fill=th["discret"], font=petite)
        self.create_line(g, y0, w - d, y0, fill=th["axe"])
        pas = pw / len(self.barres)
        lb = max(2.0, pas * self.ratio)
        self.zones = []
        for i, b in enumerate(self.barres):
            xa = g + i * pas
            x0 = xa + (pas - lb) / 2
            x1 = x0 + lb
            hb = min(ph, b.valeur / self.ymax * ph)
            if b.valeur >= 30:
                hb = max(hb, px(2))
            if hb >= 1:
                rectangle_arrondi_haut(self, x0, y0 - hb, x1, y0, px(3), fill=b.couleur)
            if b.axe:
                self.create_text((x0 + x1) / 2, y0 + px(5), text=b.axe, anchor="n",
                                 fill=th["texte"] if b.fort else th["discret"],
                                 font=(POLICE, 9, "bold") if b.fort else petite)
            if b.etiquette:
                self.create_text((x0 + x1) / 2, y0 - hb - px(4), text=b.etiquette, anchor="s",
                                 fill=th["texte"], font=(POLICE, 9, "bold"))
            self.zones.append((xa, xa + pas, y0 - hb))
        self._bulle()

    def _bouge(self, e) -> None:
        i = next((k for k, (xa, xb, _) in enumerate(self.zones) if xa <= e.x < xb), None)
        if i != self.survol:
            self.survol = i
            self._bulle()

    def _sort(self, _e) -> None:
        self.survol = None
        self._bulle()

    def _bulle(self) -> None:
        self.delete("bulle")
        if self.survol is None or self.survol >= len(self.zones):
            return
        th, px = self.app.th, self.app.px
        xa, xb, yt = self.zones[self.survol]
        fond_col = self.create_rectangle(xa, px(4), xb, self.winfo_height() - px(22),
                                         fill=th["survol_col"], outline="", tags="bulle")
        self.tag_lower(fond_col)
        t = self.create_text((xa + xb) / 2, yt - px(10), text=self.barres[self.survol].bulle,
                             anchor="s", fill=th["bulle_texte"], font=(POLICE, 9), tags="bulle")
        x0, y0, x1, y1 = self.bbox(t)
        marge, w = px(7), self.winfo_width()
        dx = max(0, px(2) - (x0 - marge)) - max(0, (x1 + marge) - (w - px(2)))
        dy = max(0, px(3) - (y0 - marge // 2))
        self.move(t, dx, dy)
        x0, y0, x1, y1 = self.bbox(t)
        r = self.create_rectangle(x0 - marge, y0 - marge // 2, x1 + marge, y1 + marge // 2,
                                  fill=th["bulle"], outline="", tags="bulle")
        self.tag_lower(r, t)


class Bouton(tk.Label):
    def __init__(self, master, texte: str, commande, app: "Application") -> None:
        th = app.th
        super().__init__(master, text=texte, bg=th["bouton"], fg=th["texte"],
                         font=(POLICE, 10), padx=app.px(14), pady=app.px(6),
                         cursor="hand2", takefocus=1)
        self._th = th
        self.bind("<Enter>", lambda e: self.config(bg=th["bouton_survol"]))
        self.bind("<Leave>", lambda e: self.config(bg=th["bouton"]))
        for ev in ("<Button-1>", "<Return>", "<space>"):
            self.bind(ev, lambda e: commande())


# Police pixel (7 lignes de haut) pour ecrire le temps dans l'icone
GLYPHES = {
    "0": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "1": [".#.", "##.", ".#.", ".#.", ".#.", ".#.", "###"],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    "h": ["#...", "#...", "#.#.", "##.#", "#..#", "#..#", "#..#"],
}
FOND_ICONE_ACTIF = (0x16, 0x82, 0x3A)
FOND_ICONE_PAUSE = (0x6B, 0x6A, 0x65)


def _pixels_icone(lignes: list[str], fond: tuple, taille: int, echelle: int) -> list[list]:
    """Grille taille x taille : (r, g, b) ou None (transparent)."""
    rayon = taille * 0.2
    grille = []
    for y in range(taille):
        rang = []
        for x in range(taille):
            cx = min(max(x + 0.5, rayon), taille - rayon)
            cy = min(max(y + 0.5, rayon), taille - rayon)
            dedans = math.hypot(x + 0.5 - cx, y + 0.5 - cy) <= rayon
            rang.append(fond if dedans else None)
        grille.append(rang)
    hauteur_bloc = (7 * 2 + 1) * echelle
    y0 = (taille - hauteur_bloc) // 2
    for n, texte in enumerate(lignes):
        glyphes = [GLYPHES[c] for c in texte]
        espace = 1 if sum(len(g[0]) for g in glyphes) + len(glyphes) - 1 <= 16 else 0
        largeur = (sum(len(g[0]) for g in glyphes) + espace * (len(glyphes) - 1)) * echelle
        x = (taille - largeur) // 2
        y = y0 + n * 8 * echelle
        for g in glyphes:
            for gy, rang in enumerate(g):
                for gx, c in enumerate(rang):
                    if c == "#":
                        for dy in range(echelle):
                            for dx in range(echelle):
                                px_, py_ = x + gx * echelle + dx, y + gy * echelle + dy
                                if 0 <= px_ < taille and 0 <= py_ < taille and grille[py_][px_]:
                                    grille[py_][px_] = (255, 255, 255)
            x += (len(g[0]) + espace) * echelle
    return grille


def _reduire_moitie(grille: list[list]) -> list[list]:
    """Divise la taille par 2 en moyennant (texte lisse pour les tailles 24 px)."""
    n = len(grille) // 2
    sortie = []
    for y in range(n):
        rang = []
        for x in range(n):
            pts = [grille[2 * y + a][2 * x + b] for a in (0, 1) for b in (0, 1)]
            pleins = [p for p in pts if p]
            if len(pleins) < 2:
                rang.append(None)
            else:
                rang.append(tuple(sum(p[i] for p in pleins) // len(pleins) for i in range(3)))
        sortie.append(rang)
    return sortie


def _vers_photo(root: tk.Misc, grille: list[list]) -> tk.PhotoImage:
    n = len(grille)
    img = tk.PhotoImage(master=root, width=n, height=n)
    img.put(" ".join("{" + " ".join("#%02x%02x%02x" % (p or (0, 0, 0)) for p in rang) + "}"
                     for rang in grille))
    for y, rang in enumerate(grille):
        for x, p in enumerate(rang):
            if p is None:
                img.tk.call(img.name, "transparency", "set", x, y, 1)
    return img


def icones_temps(root: tk.Misc, secondes: float, actif: bool) -> list[tk.PhotoImage]:
    """Icones (64, 48, 32, 24, 16 px) affichant le temps : '5h' au-dessus de '28'."""
    m = int(max(0, secondes) // 60)
    h, m = divmod(m, 60)
    lignes = [f"{min(h, 99)}h", f"{m:02d}"]
    fond = FOND_ICONE_ACTIF if actif else FOND_ICONE_PAUSE
    g48 = _pixels_icone(lignes, fond, 48, 3)
    grilles = [_pixels_icone(lignes, fond, 64, 4), g48, _pixels_icone(lignes, fond, 32, 2),
               _reduire_moitie(g48), _pixels_icone(lignes, fond, 16, 1)]
    return [_vers_photo(root, g) for g in grilles]


class Application:
    def __init__(self, root: tk.Tk, donnees: Donnees, detecteur: DetecteurInactivite,
                 serveur: socket.socket | None, minimise: bool = False) -> None:
        self.root = root
        self.d = donnees
        self.det = detecteur
        self.serveur = serveur
        self.compteur = Compteur(donnees, detecteur)
        self.th = THEMES["sombre" if theme_sombre() else "clair"]
        self.echelle = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.derniere_sauvegarde = time.time()
        self.erreur_sauvegarde: str | None = None

        th = self.th
        root.title(APP_NOM)
        root.configure(bg=th["fond"])
        root.geometry(f"{self.px(520)}x{self.px(680)}")
        root.minsize(self.px(440), self.px(640))
        root.protocol("WM_DELETE_WINDOW", self.reduire)
        self._icones: list[tk.PhotoImage] = []
        self._etat_icone = None
        self._styles_ttk()
        self._construire()
        if THEMES["sombre"] is th:
            barre_titre_sombre(root)

        if Demarrage.actif():
            try:
                Demarrage.regler(True)  # remet a jour le chemin si le fichier a ete deplace
            except OSError:
                pass
        if minimise:
            root.iconify()
        root.after(50, self._tick)
        root.after(400, self._ecouter)
        if donnees.avertissement:
            root.after(300, lambda: messagebox.showwarning(APP_NOM, donnees.avertissement, parent=root))
        elif not minimise and not donnees.reglages.get("question_demarrage_posee"):
            root.after(900, self._proposer_demarrage)

    def px(self, n: float) -> int:
        return int(round(n * self.echelle))

    # ---- construction -------------------------------------------------------
    def _styles_ttk(self) -> None:
        th = self.th
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("Treeview", background=th["fond"], fieldbackground=th["fond"],
                     foreground=th["texte"], rowheight=self.px(26), borderwidth=0,
                     font=(POLICE, 10))
        st.configure("Treeview.Heading", background=th["carte"], foreground=th["texte2"],
                     relief="flat", borderwidth=0, font=(POLICE, 10, "bold"))
        st.map("Treeview", background=[("selected", th["barre_actif"])],
               foreground=[("selected", "#ffffff")])
        st.map("Treeview.Heading", background=[("active", th["bouton_survol"])])
        st.configure("Vertical.TScrollbar", background=th["bouton"], troughcolor=th["fond"],
                     bordercolor=th["fond"], arrowcolor=th["texte2"], relief="flat")

    def _construire(self) -> None:
        th, px = self.th, self.px
        cadre = tk.Frame(self.root, bg=th["fond"], padx=px(22), pady=px(18))
        cadre.pack(fill="both", expand=True)

        self.lbl_date = tk.Label(cadre, bg=th["fond"], fg=th["texte2"], font=(POLICE, 11), anchor="w")
        self.lbl_date.pack(fill="x")

        ligne = tk.Frame(cadre, bg=th["fond"])
        ligne.pack(fill="x", pady=(px(2), 0))
        self.lbl_total = tk.Label(ligne, bg=th["fond"], fg=th["texte"],
                                  font=(POLICE, 32, "bold"), anchor="w")
        self.lbl_total.pack(side="left")
        statut = tk.Frame(ligne, bg=th["fond"])
        statut.pack(side="right", anchor="s", pady=(0, px(8)))
        haut_statut = tk.Frame(statut, bg=th["fond"])
        haut_statut.pack(anchor="e")
        self.lbl_point = tk.Label(haut_statut, text="●", bg=th["fond"], font=(POLICE, 11))
        self.lbl_point.pack(side="left")
        self.lbl_statut = tk.Label(haut_statut, bg=th["fond"], fg=th["texte2"], font=(POLICE, 10))
        self.lbl_statut.pack(side="left", padx=(px(4), 0))
        self.lbl_statut2 = tk.Label(statut, bg=th["fond"], fg=th["discret"], font=(POLICE, 9))
        self.lbl_statut2.pack(anchor="e")

        self.lbl_info = tk.Label(cadre, bg=th["fond"], fg=th["texte2"], font=(POLICE, 10),
                                 anchor="w", justify="left")
        self.lbl_info.pack(fill="x")
        def ajuster(e):
            largeur = max(200, e.width - px(44))
            self.lbl_info.config(wraplength=largeur)
            self.lbl_note.config(wraplength=largeur)
        cadre.bind("<Configure>", ajuster)

        self._titre(cadre, "Aujourd'hui, heure par heure", "minutes actives")
        self.graph_heures = Graphique(cadre, self, 150, 0.7)
        self.graph_heures.pack(fill="x")

        self._titre(cadre, "Les 7 derniers jours", "survole une barre pour le détail")
        self.graph_jours = Graphique(cadre, self, 170, 0.56)
        self.graph_jours.pack(fill="x")

        bas = tk.Frame(cadre, bg=th["fond"])
        bas.pack(side="bottom", fill="x", pady=(px(16), 0))
        self.lbl_note = tk.Label(bas, bg=th["fond"], fg=th["discret"], font=(POLICE, 9),
                                 anchor="w", justify="left")
        self.lbl_note.pack(side="bottom", fill="x", pady=(px(10), 0))
        boutons = tk.Frame(bas, bg=th["fond"])
        boutons.pack(side="bottom", fill="x")
        Bouton(boutons, "Historique", self.ouvrir_historique, self).pack(side="left")
        Bouton(boutons, "Réglages", self.ouvrir_reglages, self).pack(side="left", padx=(px(8), 0))
        Bouton(boutons, "Quitter", self.quitter, self).pack(side="right")

    def _titre(self, parent, texte: str, sous_titre: str) -> None:
        th, px = self.th, self.px
        f = tk.Frame(parent, bg=th["fond"])
        f.pack(fill="x", pady=(px(18), px(2)))
        tk.Label(f, text=texte, bg=th["fond"], fg=th["texte"], font=(POLICE, 11, "bold")).pack(side="left")
        tk.Label(f, text=sous_titre, bg=th["fond"], fg=th["discret"], font=(POLICE, 9)).pack(
            side="right", anchor="s")

    # ---- boucle -------------------------------------------------------------
    def _tick(self) -> None:
        try:
            self.compteur.tick()
            if time.time() - self.derniere_sauvegarde >= SAUVEGARDE_S:
                self._sauver()
            self.rafraichir()
        finally:
            self.root.after(TICK_MS, self._tick)

    def _sauver(self) -> None:
        self.derniere_sauvegarde = time.time()
        try:
            self.d.enregistrer()
            self.erreur_sauvegarde = None
        except OSError as e:
            self.erreur_sauvegarde = f"Impossible d'enregistrer les données : {e}"

    def _ecouter(self) -> None:
        if self.serveur:
            try:
                while True:
                    conn, _ = self.serveur.accept()
                    with conn:
                        conn.settimeout(0.5)
                        try:
                            msg = conn.recv(64)
                        except OSError:
                            msg = b""
                        if msg.startswith(b"TEMPS-PC MONTRER"):
                            try:
                                conn.sendall(b"OK\n")
                            except OSError:
                                pass
                            self.montrer()
            except OSError:  # plus de connexion en attente
                pass
        self.root.after(500, self._ecouter)

    def rafraichir(self) -> None:
        th = self.th
        auj = date.today()
        cle = auj.isoformat()
        j = self.d.jours.get(cle)
        total = self.d.total(cle)

        self.lbl_date.config(text=f"Aujourd'hui · {JOURS[auj.weekday()]} {auj.day} {MOIS[auj.month - 1]}")
        self.lbl_total.config(text=duree(total))
        self._maj_icone(total)

        if self.compteur.actif:
            self.lbl_point.config(fg=th["actif"])
            self.lbl_statut.config(text="Actif")
            self.lbl_statut2.config(text="")
        else:
            self.lbl_point.config(fg=th["barre_pause"])
            self.lbl_statut.config(text="En pause")
            self.lbl_statut2.config(text=f"inactif depuis {duree(self.compteur.inactif_depuis)}")

        infos = []
        if j and j.get("premiere"):
            infos.append(f"Première activité à {j['premiere']}")
        passes = [self.d.total((auj - timedelta(days=k)).isoformat()) for k in range(1, 8)]
        passes = [v for v in passes if v >= 60]
        if passes:
            infos.append(f"moyenne des 7 jours précédents : {duree_courte(sum(passes) / len(passes))}")
        infos = [i.replace(" h ", "\u00a0h\u00a0").replace(" min", "\u00a0min").replace("à ", "à\u00a0")
                 for i in infos]
        txt = " · ".join(infos) or "Le compteur démarre : utilise ton PC normalement."
        self.lbl_info.config(text=txt[0].upper() + txt[1:])

        # Vert quand on est actif, gris quand le compteur est en pause
        etat = "actif" if self.compteur.actif else "pause"
        couleur, couleur_passee = th[f"barre_{etat}"], th[f"passee_{etat}"]

        # Heure par heure
        heures = j["heures"] if j else [0.0] * 24
        barres_h = [Barre(v, f"{h} h" if h % 6 == 0 else "",
                          f"{h} h – {h + 1} h : {duree(v)}", couleur) for h, v in enumerate(heures)]
        self.graph_heures.maj(barres_h, 3600.0, [(1800, "30 min"), (3600, "60 min")])

        # 7 derniers jours
        barres_j = []
        valeurs = []
        for k in range(6, -1, -1):
            jr = auj - timedelta(days=k)
            v = self.d.total(jr.isoformat())
            valeurs.append(v)
            nom = f"{JOURS[jr.weekday()].capitalize()} {jr.day} {MOIS[jr.month - 1]}"
            barres_j.append(Barre(
                v, "Auj." if k == 0 else f"{JOURS_COURTS[jr.weekday()]} {jr.day}",
                f"{nom} : {duree(v)}", couleur if k == 0 else couleur_passee,
                fort=(k == 0), etiquette=duree_courte(v) if k == 0 else None))
        heures_max = max(1, math.ceil(max(valeurs) / 3600 + 0.08))
        pas = 1 if heures_max <= 4 else 2 if heures_max <= 8 else 4
        heures_max = math.ceil(heures_max / pas) * pas
        grads = [(hh * 3600.0, f"{hh} h") for hh in range(pas, heures_max + 1, pas)]
        self.graph_jours.maj(barres_j, heures_max * 3600.0, grads)

        note = self.erreur_sauvegarde or (
            "Fermer la fenêtre la réduit, le suivi continue. « Quitter » arrête tout.")
        self.lbl_note.config(text=note, fg="#d03b3b" if self.erreur_sauvegarde else th["discret"])

    def _maj_icone(self, total: float) -> None:
        """Icone de la barre des taches + titre : le temps du jour, mis a jour chaque minute."""
        etat = (int(total // 60), self.compteur.actif)
        if etat == self._etat_icone:
            return
        self._etat_icone = etat
        titre = f"{duree_courte(total)} – {APP_NOM}"
        self.root.title(titre if self.compteur.actif else f"{duree_courte(total)} (en pause) – {APP_NOM}")
        try:
            icones = icones_temps(self.root, total, self.compteur.actif)
            self.root.iconphoto(True, *icones)
            self._icones = icones  # garder une reference, sinon Tk efface les images
        except tk.TclError:
            pass

    # ---- actions ------------------------------------------------------------
    def montrer(self) -> None:
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.attributes("-topmost", True)
            self.root.after(300, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except tk.TclError:
            pass

    def reduire(self) -> None:
        if not self.d.reglages.get("info_reduction_vue"):
            self.d.reglages["info_reduction_vue"] = True
            self._sauver()
            messagebox.showinfo(APP_NOM, "Temps PC continue de compter, réduit dans la barre des tâches.\n\n"
                                         "Pour l'arrêter complètement, utilise le bouton « Quitter ».",
                                parent=self.root)
        self.root.iconify()

    def quitter(self) -> None:
        if not messagebox.askyesno(APP_NOM, "Quitter Temps PC ?\n\nLe temps ne sera plus compté "
                                            "tant que l'application est fermée.", parent=self.root):
            return
        self._sauver()
        if self.serveur:
            try:
                self.serveur.close()
            except OSError:
                pass
        self.root.destroy()

    def _proposer_demarrage(self) -> None:
        self.d.reglages["question_demarrage_posee"] = True
        if messagebox.askyesno(
                APP_NOM,
                "Lancer Temps PC automatiquement à chaque démarrage de l'ordinateur ?\n\n"
                "C'est recommandé : le temps n'est compté que lorsque l'application est ouverte.\n"
                "(Tu peux changer ça plus tard dans Réglages.)", parent=self.root):
            try:
                Demarrage.regler(True)
            except OSError as e:
                messagebox.showerror(APP_NOM, f"Impossible d'activer le démarrage automatique :\n{e}",
                                     parent=self.root)
        self._sauver()

    def _fenetre(self, titre: str, l: int | None = None, h: int | None = None) -> tk.Toplevel:
        f = tk.Toplevel(self.root, bg=self.th["fond"])
        f.title(titre)
        f.transient(self.root)
        if l and h:
            f.geometry(f"{self.px(l)}x{self.px(h)}")
        if THEMES["sombre"] is self.th:
            barre_titre_sombre(f)
        return f

    def ouvrir_historique(self) -> None:
        th, px = self.th, self.px
        f = self._fenetre(f"{APP_NOM} – Historique", 560, 480)
        cadre = tk.Frame(f, bg=th["fond"], padx=px(18), pady=px(16))
        cadre.pack(fill="both", expand=True)

        jours = sorted(((k, v) for k, v in self.d.jours.items() if sum(v["heures"]) >= 1), reverse=True)
        totaux = [sum(v["heures"]) for _, v in jours]
        if totaux:
            resume = (f"{len(totaux)} jour{'s' if len(totaux) > 1 else ''} enregistré"
                      f"{'s' if len(totaux) > 1 else ''} · moyenne {duree(sum(totaux) / len(totaux))} "
                      f"par jour · total {duree(sum(totaux))}")
        else:
            resume = "Aucune donnée pour l'instant."
        tk.Label(cadre, text=resume, bg=th["fond"], fg=th["texte2"], font=(POLICE, 10),
                 anchor="w").pack(fill="x", pady=(0, px(10)))

        bas = tk.Frame(cadre, bg=th["fond"])
        bas.pack(side="bottom", fill="x", pady=(px(12), 0))
        Bouton(bas, "Exporter en CSV (Excel)…", lambda: self._exporter(f, jours), self).pack(side="left")
        Bouton(bas, "Fermer", f.destroy, self).pack(side="right")

        zone = tk.Frame(cadre, bg=th["fond"])
        zone.pack(fill="both", expand=True)
        cols = ("date", "jour", "temps", "premiere", "derniere")
        arbre = ttk.Treeview(zone, columns=cols, show="headings", selectmode="browse")
        for col, titre, larg, anc in (("date", "Date", 100, "w"), ("jour", "Jour", 90, "w"),
                                      ("temps", "Temps actif", 110, "e"),
                                      ("premiere", "Début", 70, "center"),
                                      ("derniere", "Fin", 70, "center")):
            arbre.heading(col, text=titre, anchor=anc)
            arbre.column(col, width=px(larg), anchor=anc, stretch=True)
        defil = ttk.Scrollbar(zone, orient="vertical", command=arbre.yview)
        arbre.configure(yscrollcommand=defil.set)
        defil.pack(side="right", fill="y")
        arbre.pack(side="left", fill="both", expand=True)
        for k, v in jours:
            dt = date.fromisoformat(k)
            arbre.insert("", "end", values=(dt.strftime("%d/%m/%Y"), JOURS[dt.weekday()].capitalize(),
                                            duree(sum(v["heures"])), v.get("premiere") or "–",
                                            v.get("derniere") or "–"))

    def _exporter(self, parent, jours) -> None:
        chemin = filedialog.asksaveasfilename(parent=parent, title="Exporter l'historique",
                                              defaultextension=".csv", initialfile="temps_pc.csv",
                                              filetypes=[("Fichier CSV", "*.csv")])
        if not chemin:
            return
        try:
            with open(chemin, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh, delimiter=";")
                w.writerow(["Date", "Jour", "Minutes actives", "Durée", "Première activité",
                            "Dernière activité"])
                for k, v in sorted(jours):
                    t = sum(v["heures"])
                    w.writerow([k, JOURS[date.fromisoformat(k).weekday()], round(t / 60),
                                duree_courte(t), v.get("premiere") or "", v.get("derniere") or ""])
        except OSError as e:
            messagebox.showerror(APP_NOM, f"Export impossible :\n{e}", parent=parent)
            return
        messagebox.showinfo(APP_NOM, f"Historique exporté :\n{chemin}", parent=parent)

    def ouvrir_reglages(self) -> None:
        th, px = self.th, self.px
        f = self._fenetre(f"{APP_NOM} – Réglages")
        f.resizable(False, False)
        cadre = tk.Frame(f, bg=th["fond"], padx=px(20), pady=px(18))
        cadre.pack(fill="both", expand=True)
        r = self.d.reglages
        v_pause = tk.BooleanVar(value=bool(r.get("pause_si_inactif", True)))
        v_min = tk.StringVar(value=str(r.get("minutes_inactivite", 5)))
        try:
            demarrage_avant = Demarrage.actif()
        except OSError:
            demarrage_avant = False
        v_dem = tk.BooleanVar(value=demarrage_avant)

        def case(texte, var):
            return tk.Checkbutton(cadre, text=texte, variable=var, bg=th["fond"], fg=th["texte"],
                                  activebackground=th["fond"], activeforeground=th["texte"],
                                  selectcolor=th["carte"], highlightthickness=0, bd=0,
                                  font=(POLICE, 10), anchor="w", justify="left",
                                  wraplength=px(420))

        case("Mettre le compteur en pause quand je n'utilise pas le PC", v_pause).pack(fill="x")
        ligne = tk.Frame(cadre, bg=th["fond"])
        ligne.pack(fill="x", padx=(px(26), 0), pady=(px(4), 0))
        tk.Label(ligne, text="après", bg=th["fond"], fg=th["texte2"], font=(POLICE, 10)).pack(side="left")
        tk.Spinbox(ligne, from_=1, to=120, width=4, textvariable=v_min, font=(POLICE, 10),
                   bg=th["carte"], fg=th["texte"], buttonbackground=th["bouton"],
                   insertbackground=th["texte"], relief="flat", justify="center").pack(
            side="left", padx=px(6))
        tk.Label(ligne, text="minutes sans souris ni clavier", bg=th["fond"], fg=th["texte2"],
                 font=(POLICE, 10)).pack(side="left")
        aide = ("Astuce : décoche cette option si tu veux aussi compter les films ou vidéos "
                "regardés sans toucher au PC.")
        if self.det.methode is None:
            aide = ("La détection d'inactivité n'est pas disponible sur ce système : "
                    "tout le temps où l'application est ouverte est compté.")
        tk.Label(cadre, text=aide, bg=th["fond"], fg=th["discret"], font=(POLICE, 9), anchor="w",
                 justify="left", wraplength=px(420)).pack(fill="x", padx=(px(26), 0), pady=(px(6), 0))

        case("Lancer Temps PC au démarrage de l'ordinateur", v_dem).pack(fill="x", pady=(px(18), 0))

        tk.Label(cadre, text="Données enregistrées dans :", bg=th["fond"], fg=th["texte2"],
                 font=(POLICE, 10), anchor="w").pack(fill="x", pady=(px(18), 0))
        tk.Label(cadre, text=self.d.chemin, bg=th["fond"], fg=th["discret"], font=(POLICE, 9),
                 anchor="w", justify="left", wraplength=px(420)).pack(fill="x")

        def ouvrir():
            try:
                ouvrir_dossier(self.d.dossier)
            except Exception as e:
                messagebox.showerror(APP_NOM, f"Impossible d'ouvrir le dossier :\n{e}", parent=f)

        def valider():
            try:
                minutes = int(v_min.get())
                if not 1 <= minutes <= 120:
                    raise ValueError
            except ValueError:
                messagebox.showerror(APP_NOM, "Indique un nombre de minutes entre 1 et 120.", parent=f)
                return
            r["pause_si_inactif"] = bool(v_pause.get())
            r["minutes_inactivite"] = minutes
            if bool(v_dem.get()) != demarrage_avant:
                try:
                    Demarrage.regler(bool(v_dem.get()))
                except OSError as e:
                    messagebox.showerror(APP_NOM, f"Démarrage automatique non modifié :\n{e}", parent=f)
            self._sauver()
            self.rafraichir()
            f.destroy()

        bas = tk.Frame(cadre, bg=th["fond"])
        bas.pack(side="bottom", fill="x", pady=(px(20), 0))
        Bouton(bas, "Ouvrir le dossier", ouvrir, self).pack(side="left")
        Bouton(bas, "Enregistrer", valider, self).pack(side="right")
        Bouton(bas, "Annuler", f.destroy, self).pack(side="right", padx=(0, px(8)))


# --------------------------------------------------------------------------
def main() -> None:
    minimise = "--minimise" in sys.argv
    if signaler_instance_existante():
        return  # deja ouverte : on l'a ramenee au premier plan
    serveur = ouvrir_serveur()
    if WIN:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TempsPC")
        except Exception:
            pass
    root = tk.Tk()
    Application(root, Donnees(dossier_donnees()), DetecteurInactivite(), serveur, minimise)
    root.mainloop()


if __name__ == "__main__":
    main()
