"""Icone du fichier TempsPC.exe : carre vert arrondi avec une horloge blanche."""
import math
import sys
from PIL import Image, ImageDraw

N = 1024
img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
vert = (0x16, 0x82, 0x3A, 255)
blanc = (255, 255, 255, 255)
d.rounded_rectangle([0, 0, N - 1, N - 1], radius=int(N * 0.22), fill=vert)
c, r = N / 2, N * 0.34
ep = int(N * 0.07)
d.ellipse([c - r, c - r, c + r, c + r], outline=blanc, width=ep)


def aiguille(angle_deg, longueur, largeur):
    a = math.radians(angle_deg - 90)
    x, y = c + math.cos(a) * longueur, c + math.sin(a) * longueur
    d.line([c, c, x, y], fill=blanc, width=largeur)
    d.ellipse([x - largeur / 2, y - largeur / 2, x + largeur / 2, y + largeur / 2], fill=blanc)


aiguille(0, r * 0.62, int(N * 0.065))     # minutes vers 12 h
aiguille(120, r * 0.45, int(N * 0.07))    # heures vers 4 h
d.ellipse([c - N * 0.05, c - N * 0.05, c + N * 0.05, c + N * 0.05], fill=blanc)

tailles = [256, 128, 64, 48, 32, 24, 16]
img.resize((256, 256), Image.LANCZOS).save(sys.argv[1], sizes=[(t, t) for t in tailles])
img.resize((256, 256), Image.LANCZOS).save(sys.argv[1].replace(".ico", ".png"))
