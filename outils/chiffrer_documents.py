#!/usr/bin/env python3
"""
Chiffre les documents d'un dossier pour la page protégée https://greenserver.be/files/

Utilisation (depuis n'importe où) :
    pip install cryptography
    python outils/chiffrer_documents.py "C:\\Users\\Vincent\\Documents\\a_publier"

Ensuite : git add docs/files && git commit -m "Documents" && git push

Fonctionnement
- Le script demande le mot de passe (deux fois) et chiffre chaque fichier du dossier
  en AES-256-GCM, avec une clé dérivée du mot de passe (PBKDF2-SHA256, 600 000 tours).
- Il reconstruit entièrement docs/files/data/ : le dossier source est la référence.
  Pour ajouter ou retirer un document, ou changer le mot de passe, relancez-le.
- Les noms des fichiers sont chiffrés aussi (dans manifest.bin) ; seuls leur nombre et
  leur taille approximative restent visibles.
- Les originaux ne sont jamais copiés dans le dépôt, qui est public.

Pour lancer sans saisie (automatisation), le mot de passe peut être passé dans la
variable d'environnement GREENSERVER_FILES_PASSWORD.
"""
import argparse
import base64
import getpass
import json
import mimetypes
import os
import secrets
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    sys.exit("Module manquant : lancez d'abord  pip install cryptography")

ITERATIONS = 600_000
LONGUEUR_MIN = 12
ALERTE_TAILLE = 50 * 1024 * 1024     # GitHub avertit au-delà de 50 Mo
TAILLE_MAX = 95 * 1024 * 1024        # et refuse les fichiers de plus de 100 Mo
IGNORES = {"desktop.ini", "thumbs.db", ".ds_store"}

DEPOT = Path(__file__).resolve().parent.parent
SORTIE_DEFAUT = DEPOT / "docs" / "files"


def taille_lisible(n):
    for unite in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unite == "Go":
            return f"{n:.0f} {unite}" if unite == "o" else f"{n:.1f} {unite}"
        n /= 1024


def lire_mot_de_passe():
    env = os.environ.get("GREENSERVER_FILES_PASSWORD")
    if env:
        mdp = env
    else:
        mdp = getpass.getpass("Mot de passe : ")
        if getpass.getpass("Confirmez le mot de passe : ") != mdp:
            sys.exit("Les deux mots de passe ne correspondent pas.")
    mdp = unicodedata.normalize("NFC", mdp)
    if len(mdp) < LONGUEUR_MIN:
        sys.exit(f"Mot de passe trop court : {LONGUEUR_MIN} caractères minimum "
                 "(une phrase de 4 ou 5 mots est idéale).")
    return mdp


def chiffrer(aes, donnees, aad):
    iv = secrets.token_bytes(12)
    return iv + aes.encrypt(iv, donnees, aad.encode())


def main():
    p = argparse.ArgumentParser(description="Chiffre un dossier de documents pour greenserver.be/files/")
    p.add_argument("source", type=Path, help="dossier contenant les documents à publier")
    p.add_argument("--sortie", type=Path, default=SORTIE_DEFAUT,
                   help=f"dossier de la page (défaut : {SORTIE_DEFAUT})")
    args = p.parse_args()

    source = args.source.resolve()
    sortie = args.sortie.resolve()
    if not source.is_dir():
        sys.exit(f"Dossier introuvable : {source}")
    if source == DEPOT or DEPOT in source.parents:
        sys.exit("Le dossier source est dans le dépôt Git, qui est public : les originaux "
                 "risqueraient d'être publiés. Placez-les dans un dossier hors du dépôt.")
    if not (sortie / "index.html").is_file():
        sys.exit(f"Page introuvable : {sortie / 'index.html'}")

    fichiers = sorted(
        (f for f in source.iterdir()
         if f.is_file() and not f.name.startswith(".") and f.name.lower() not in IGNORES),
        key=lambda f: f.name.lower(),
    )
    if not fichiers:
        sys.exit(f"Aucun document dans {source}")
    for f in fichiers:
        t = f.stat().st_size
        if t > TAILLE_MAX:
            sys.exit(f"{f.name} fait {taille_lisible(t)} : GitHub refuse les fichiers de plus de 100 Mo.")
        if t > ALERTE_TAILLE:
            print(f"Attention : {f.name} fait {taille_lisible(t)} (lent à ouvrir sur téléphone).")

    mdp = lire_mot_de_passe()
    sel = secrets.token_bytes(16)
    print("Dérivation de la clé…")
    cle = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sel,
                     iterations=ITERATIONS).derive(mdp.encode("utf-8"))
    aes = AESGCM(cle)

    data = sortie / "data"
    data.mkdir(parents=True, exist_ok=True)
    for ancien in data.glob("*.bin"):
        ancien.unlink()

    liste = []
    for f in fichiers:
        ident = secrets.token_hex(8)
        contenu = f.read_bytes()
        (data / f"{ident}.bin").write_bytes(chiffrer(aes, contenu, ident))
        type_mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        liste.append({"id": ident, "name": f.name, "size": len(contenu), "type": type_mime})
        print(f"  chiffré : {f.name} ({taille_lisible(len(contenu))})")

    manifeste = {
        "v": 1,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "files": liste,
    }
    (data / "manifest.bin").write_bytes(
        chiffrer(aes, json.dumps(manifeste, ensure_ascii=False).encode("utf-8"), "manifest"))

    coffre = {
        "v": 1,
        "kdf": "PBKDF2-SHA256",
        "iterations": ITERATIONS,
        "salt": base64.b64encode(sel).decode(),
        "cipher": "AES-256-GCM",
    }
    (sortie / "vault.json").write_text(json.dumps(coffre, indent=2) + "\n", encoding="utf-8")

    print(f"\n{len(liste)} document(s) chiffré(s) dans {sortie}")
    print("Publiez avec :  git add docs/files  puis  git commit  et  git push")


if __name__ == "__main__":
    main()
