<img src="captures/icone.png" width="64" align="right" alt="">

# Temps PC

**Français** · [English](#english)

Petite application Windows gratuite qui compte le temps passé **chaque jour** sur l'ordinateur, comme le « temps d'écran » d'un téléphone.

Seul le temps **actif** est compté : après quelques minutes sans souris ni clavier, le compteur se met en pause et retire ces minutes d'inactivité. La veille du PC n'est pas comptée non plus.

<p>
  <img src="captures/fenetre_fr.png" width="380" alt="Fenêtre principale">
  <img src="captures/historique_fr.png" width="420" alt="Fenêtre Historique">
</p>

## Ce qu'elle fait

- Temps du jour en grand, graphique **heure par heure** et graphique des **7 derniers jours**. Survole une barre pour voir le détail.
- **Vert** quand tu utilises le PC, **gris** quand le compteur est en pause.
- L'icône dans la barre des tâches **affiche le temps du jour** (ex. « 5h » au-dessus de « 28 »), mise à jour chaque minute.
- **Historique** : histogramme des 12 derniers mois (clic sur un mois pour le détail), le mois choisi jour par jour, tableau des jours et export CSV pour Excel.
- En **français ou en anglais** : la langue de Windows, ou au choix dans Réglages.
- Démarrage automatique avec Windows (proposé au premier lancement, modifiable dans Réglages).
- Fermer la fenêtre la réduit, le suivi continue. Le bouton **Quitter** arrête tout.
- Gratuite. Le bouton « Offre-moi un café » (PayPal) permet de soutenir le projet.

<img src="captures/icones_barre_des_taches.png" width="320" alt="Icône de la barre des tâches qui affiche le temps">

## Installation

1. **[Télécharge TempsPC.zip](https://github.com/vincentschoebrechts-beep/temps-pc/raw/main/telechargement/TempsPC.zip)** (Windows 10/11, 64 bits, environ 10 Mo).
2. Clic droit sur le zip → **Extraire tout…**, puis place le dossier `TempsPC` là où il restera (par ex. Documents).
3. Double-clique sur `TempsPC.exe`. Rien d'autre à installer.

L'exe n'est pas signé : Windows peut afficher « Windows a protégé votre ordinateur ». Clique sur **Informations complémentaires**, puis **Exécuter quand même**.

**Mise à jour :** dans Temps PC, clique sur **Quitter**, remplace l'ancien `TempsPC.exe` par le nouveau **au même endroit** (pour garder le démarrage automatique), puis relance-le. Les données sont conservées.

## Données et vie privée

Tout reste sur le PC, dans `%APPDATA%\TempsPC\donnees.json` (bouton « Ouvrir le dossier » dans Réglages). Rien n'est envoyé sur Internet, et aucun compte n'est nécessaire.

Copies de sécurité automatiques dans `%APPDATA%\TempsPC\sauvegardes` : une par jour (les 14 dernières sont gardées) et une copie permanente avant chaque nouvelle version.

## Versions

- **1.2** : français / anglais, bouton « Offre-moi un café ».
- **1.1** : Historique avec histogrammes (12 derniers mois et mois jour par jour), copies de sécurité automatiques, fenêtres adaptées aux petits écrans.
- **1.0** : première version.

---

<a name="english"></a>

## English

Small free Windows app that counts the time you spend on your computer **each day**, like the “screen time” of a phone.

Only **active** time counts: after a few minutes without mouse or keyboard, the counter pauses and removes those idle minutes. Sleep time is not counted either.

<p>
  <img src="captures/fenetre_en.png" width="380" alt="Main window">
  <img src="captures/historique_en.png" width="420" alt="History window">
</p>

### Features

- Today's time in large type, an **hour-by-hour** chart and a **last 7 days** chart. Hover over a bar for details.
- **Green** while you use the PC, **grey** when the counter is paused.
- The taskbar icon **shows today's time** (e.g. “5h” above “28”), updated every minute.
- **History**: last 12 months as a bar chart (click a month for details), the chosen month day by day, a table of days and CSV export for Excel.
- **English or French**: same as Windows, or choose in Settings.
- Starts with Windows (offered on first launch, can be changed in Settings).
- Closing the window just minimizes it; tracking continues. **Quit** stops everything.
- Free. The “Buy me a coffee” button (PayPal) lets you support the project.

### Install

1. **[Download TempsPC.zip](https://github.com/vincentschoebrechts-beep/temps-pc/raw/main/telechargement/TempsPC.zip)** (Windows 10/11, 64-bit, about 10 MB).
2. Right-click the zip → **Extract All…**, then put the `TempsPC` folder where it will stay (e.g. Documents).
3. Double-click `TempsPC.exe`. Nothing else to install.

The exe is not signed: Windows may show “Windows protected your PC”. Click **More info**, then **Run anyway**.

**Update:** in Temps PC, click **Quit**, replace the old `TempsPC.exe` with the new one **in the same place** (to keep automatic startup), then start it again. Your data is kept.

### Data and privacy

Everything stays on the PC, in `%APPDATA%\TempsPC\donnees.json` (“Open folder” button in Settings). Nothing is sent over the Internet, and no account is needed.

Automatic backups in `%APPDATA%\TempsPC\sauvegardes`: one per day (the last 14 are kept) and a permanent copy before each new version.

---

## Code source / Source code

Avec / with [Python 3](https://www.python.org/downloads/) : double-clic sur / double-click `temps_pc.pyw`. Aucun module à installer / no extra module needed. Fonctionne aussi sur / also runs on macOS and Linux.

Construire l'exe / build the exe (Windows, Python installé / installed) :

```bat
construction\construire.bat
```

Résultat / output : `dist\TempsPC.exe` (PyInstaller, un seul fichier / single file).
