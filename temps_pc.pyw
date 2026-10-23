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
- Historique : histogramme des 12 derniers mois et du mois jour par jour.
- En francais ou en anglais (langue de Windows, ou au choix dans Reglages).
- Les donnees restent sur ce PC (Windows : %APPDATA%\\TempsPC\\donnees.json),
  avec une copie de securite automatique chaque jour (dossier « sauvegardes »).
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

import calendar
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NOM = "Temps PC"
APP_VERSION = "1.3"
COPYRIGHT = "© 2026 V. Schoebrechts"
PAYPAL = "https://paypal.me/VSC1973"
TICK_MS = 2000        # une mesure toutes les 2 secondes
SAUVEGARDE_S = 30     # ecriture sur le disque toutes les 30 secondes
ECART_MAX_S = 30      # trou plus long entre deux mesures = veille du PC : non compte
PORT = 47615          # sert a n'avoir qu'une seule copie de l'appli ouverte
WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"

SAUVEGARDES_GARDEES = 14

# --------------------------------------------------------------------------
# Textes en francais et en anglais
# --------------------------------------------------------------------------
TEXTES: dict[str, dict] = {
    "fr": {
        "jours": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "jours_courts": ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"],
        "mois": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                 "août", "septembre", "octobre", "novembre", "décembre"],
        "mois_courts": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.",
                        "oct.", "nov.", "déc."],
        "date_longue": "{jour} {n} {mois}",
        "mois_annee": "{mois} {a}",
        "date_tableau": "%d/%m/%Y",
        "deux_points": " : ",
        "axe_jour": "{jc} {n}",
        "duree_hm": "{h} h {m:02d} min",
        "duree_m": "{m} min",
        "duree_courte_hm": "{h} h {m:02d}",
        "grad_min": "{n} min",
        "grad_h": "{n} h",
        "langue": "Langue",
        "aujourdhui_date": "Aujourd'hui · {date}",
        "actif": "Actif",
        "en_pause": "En pause",
        "inactif_depuis": "inactif depuis {d}",
        "premiere_activite": "Première activité à {h}",
        "moyenne_7": "moyenne des 7 jours précédents : {d}",
        "demarre": "Le compteur démarre : utilise ton PC normalement.",
        "titre_heures": "Aujourd'hui, heure par heure",
        "sous_heures": "minutes actives",
        "titre_7j": "Les 7 derniers jours",
        "sous_7j": "survole une barre pour le détail",
        "auj_court": "Auj.",
        "axe_heure": "{h} h",
        "bulle_heure": "{h} h – {h2} h : {d}",
        "historique": "Historique",
        "reglages": "Réglages",
        "quitter": "Quitter",
        "note": "Fermer la fenêtre la réduit, le suivi continue. « Quitter » arrête tout.",
        "cafe": "☕ Offre-moi un café via PayPal",
        "erreur_sauvegarde": "Impossible d'enregistrer les données : {e}",
        "titre_pause": "{d} (en pause)",
        "fichier_illisible": "Le fichier de données n'a pas pu être lu ({e}).\n\nIl a été mis de côté ici :\n{copie}",
        "info_reduction": "Temps PC continue de compter, réduit dans la barre des tâches.\n\n"
                          "Pour l'arrêter complètement, utilise le bouton « Quitter ».",
        "confirmer_quitter": "Quitter Temps PC ?\n\nLe temps ne sera plus compté tant que l'application est fermée.",
        "proposer_demarrage": "Lancer Temps PC automatiquement à chaque démarrage de l'ordinateur ?\n\n"
                              "C'est recommandé : le temps n'est compté que lorsque l'application est ouverte.\n"
                              "(Tu peux changer ça plus tard dans Réglages.)",
        "erreur_demarrage": "Impossible d'activer le démarrage automatique :\n{e}",
        "export_titre": "Exporter l'historique",
        "export_type": "Fichier CSV",
        "export_colonnes": ["Date", "Jour", "Minutes actives", "Durée", "Première activité", "Dernière activité"],
        "export_separateur": ";",
        "export_erreur": "Export impossible :\n{e}",
        "export_ok": "Historique exporté :\n{chemin}",
        "titre_reglages": "Réglages",
        "case_pause": "Mettre le compteur en pause quand je n'utilise pas le PC",
        "apres": "après",
        "minutes_sans": "minutes sans souris ni clavier",
        "astuce": "Astuce : décoche cette option si tu veux aussi compter les films ou vidéos regardés "
                  "sans toucher au PC.",
        "pas_detection": "La détection d'inactivité n'est pas disponible sur ce système : "
                         "tout le temps où l'application est ouverte est compté.",
        "case_demarrage": "Lancer Temps PC au démarrage de l'ordinateur",
        "langue_auto": "Automatique ({nom})",
        "donnees_dans": "Données enregistrées dans :",
        "ouvrir_dossier": "Ouvrir le dossier",
        "enregistrer": "Enregistrer",
        "annuler": "Annuler",
        "erreur_dossier": "Impossible d'ouvrir le dossier :\n{e}",
        "erreur_minutes": "Indique un nombre de minutes entre 1 et 120.",
        "erreur_demarrage_modif": "Démarrage automatique non modifié :\n{e}",
        "titre_historique": "Historique",
        "jours_enregistres_1": "{n} jour enregistré",
        "jours_enregistres_n": "{n} jours enregistrés",
        "resume": "{jours} · moyenne {m} par jour · total {t}",
        "aucune_donnee": "Aucune donnée pour l'instant.",
        "titre_12m": "Les 12 derniers mois",
        "sous_12m": "clique sur un mois pour le détail",
        "nb_jours_1": "{n} jour",
        "nb_jours_n": "{n} jours",
        "bulle_mois_detail": " · {jours} · moy. {m}/jour",
        "titre_jpj": "Jour par jour",
        "sous_jpj": "temps actif",
        "exporter_tout": "Exporter tout en CSV (Excel)…",
        "fermer": "Fermer",
        "col_date": "Date", "col_jour": "Jour", "col_temps": "Temps actif", "col_debut": "Début", "col_fin": "Fin",
        "jours_utilises_1": "{n} jour utilisé",
        "jours_utilises_n": "{n} jours utilisés",
        "detail1": "{t} au total · {jours} · moyenne {m} par jour",
        "detail2": "Jour record : {date}, {d}",
        "aucune_donnee_mois": "Aucune donnée pour ce mois.",
    },
    "en": {
        "jours": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "jours_courts": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "mois": ["January", "February", "March", "April", "May", "June", "July",
                 "August", "September", "October", "November", "December"],
        "mois_courts": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "date_longue": "{jour}, {mois} {n}",
        "mois_annee": "{mois} {a}",
        "date_tableau": "%Y-%m-%d",
        "deux_points": ": ",
        "axe_jour": "{jc} {n}",
        "duree_hm": "{h} h {m:02d} min",
        "duree_m": "{m} min",
        "duree_courte_hm": "{h} h {m:02d}",
        "grad_min": "{n} min",
        "grad_h": "{n} h",
        "langue": "Language",
        "aujourdhui_date": "Today · {date}",
        "actif": "Active",
        "en_pause": "Paused",
        "inactif_depuis": "idle for {d}",
        "premiere_activite": "First activity at {h}",
        "moyenne_7": "average over the previous 7 days: {d}",
        "demarre": "The counter is starting: just use your PC as usual.",
        "titre_heures": "Today, hour by hour",
        "sous_heures": "active minutes",
        "titre_7j": "The last 7 days",
        "sous_7j": "hover over a bar for details",
        "auj_court": "Today",
        "axe_heure": "{h}h",
        "bulle_heure": "{h}:00 – {h2}:00: {d}",
        "historique": "History",
        "reglages": "Settings",
        "quitter": "Quit",
        "note": "Closing the window just minimizes it. “Quit” stops tracking.",
        "cafe": "☕ Buy me a coffee via PayPal",
        "erreur_sauvegarde": "Could not save the data: {e}",
        "titre_pause": "{d} (paused)",
        "fichier_illisible": "The data file could not be read ({e}).\n\nIt has been set aside here:\n{copie}",
        "info_reduction": "Temps PC keeps counting, minimized to the taskbar.\n\n"
                          "To stop it completely, use the “Quit” button.",
        "confirmer_quitter": "Quit Temps PC?\n\nTime will not be counted while the app is closed.",
        "proposer_demarrage": "Start Temps PC automatically every time the computer starts?\n\n"
                              "Recommended: time is only counted while the app is open.\n"
                              "(You can change this later in Settings.)",
        "erreur_demarrage": "Could not enable automatic startup:\n{e}",
        "export_titre": "Export history",
        "export_type": "CSV file",
        "export_colonnes": ["Date", "Day", "Active minutes", "Duration", "First activity", "Last activity"],
        "export_separateur": ",",
        "export_erreur": "Export failed:\n{e}",
        "export_ok": "History exported:\n{chemin}",
        "titre_reglages": "Settings",
        "case_pause": "Pause the counter when I'm not using the PC",
        "apres": "after",
        "minutes_sans": "minutes without mouse or keyboard",
        "astuce": "Tip: uncheck this if you also want to count movies or videos watched without "
                  "touching the PC.",
        "pas_detection": "Idle detection is not available on this system: "
                         "all the time the app is open is counted.",
        "case_demarrage": "Start Temps PC when the computer starts",
        "langue_auto": "Automatic ({nom})",
        "donnees_dans": "Data saved in:",
        "ouvrir_dossier": "Open folder",
        "enregistrer": "Save",
        "annuler": "Cancel",
        "erreur_dossier": "Could not open the folder:\n{e}",
        "erreur_minutes": "Enter a number of minutes between 1 and 120.",
        "erreur_demarrage_modif": "Automatic startup not changed:\n{e}",
        "titre_historique": "History",
        "jours_enregistres_1": "{n} day recorded",
        "jours_enregistres_n": "{n} days recorded",
        "resume": "{jours} · average {m} per day · total {t}",
        "aucune_donnee": "No data yet.",
        "titre_12m": "The last 12 months",
        "sous_12m": "click a month for details",
        "nb_jours_1": "{n} day",
        "nb_jours_n": "{n} days",
        "bulle_mois_detail": " · {jours} · avg {m}/day",
        "titre_jpj": "Day by day",
        "sous_jpj": "active time",
        "exporter_tout": "Export all to CSV (Excel)…",
        "fermer": "Close",
        "col_date": "Date", "col_jour": "Day", "col_temps": "Active time", "col_debut": "Start", "col_fin": "End",
        "jours_utilises_1": "{n} day used",
        "jours_utilises_n": "{n} days used",
        "detail1": "{t} in total · {jours} · average {m} per day",
        "detail2": "Record day: {date}, {d}",
        "aucune_donnee_mois": "No data for this month.",
    },
    "es": {
        "jours": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
        "jours_courts": ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"],
        "mois": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                 "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
        "mois_courts": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"],
        "date_longue": "{jour}, {n} de {mois}",
        "mois_annee": "{mois} de {a}",
        "date_tableau": "%d/%m/%Y",
        "deux_points": ": ",
        "axe_jour": "{jc} {n}",
        "duree_hm": "{h} h {m:02d} min",
        "duree_m": "{m} min",
        "duree_courte_hm": "{h} h {m:02d}",
        "grad_min": "{n} min",
        "grad_h": "{n} h",
        "langue": "Idioma",
        "aujourdhui_date": "Hoy · {date}",
        "actif": "Activo",
        "en_pause": "En pausa",
        "inactif_depuis": "inactivo desde hace {d}",
        "premiere_activite": "Primera actividad a las {h}",
        "moyenne_7": "media de los 7 días anteriores: {d}",
        "demarre": "El contador está empezando: usa tu PC con normalidad.",
        "titre_heures": "Hoy, hora por hora",
        "sous_heures": "minutos activos",
        "titre_7j": "Los últimos 7 días",
        "sous_7j": "pasa el ratón sobre una barra",
        "auj_court": "Hoy",
        "axe_heure": "{h} h",
        "bulle_heure": "{h}:00 – {h2}:00: {d}",
        "historique": "Historial",
        "reglages": "Ajustes",
        "quitter": "Salir",
        "note": "Cerrar la ventana solo la minimiza. «Salir» detiene el seguimiento.",
        "cafe": "☕ Invítame a un café con PayPal",
        "erreur_sauvegarde": "No se pudieron guardar los datos: {e}",
        "titre_pause": "{d} (en pausa)",
        "fichier_illisible": "No se pudo leer el archivo de datos ({e}).\n\nSe ha guardado aparte aquí:\n{copie}",
        "info_reduction": "Temps PC sigue contando, minimizado en la barra de tareas.\n\n"
                          "Para detenerlo por completo, usa el botón «Salir».",
        "confirmer_quitter": "¿Salir de Temps PC?\n\nEl tiempo no se contará mientras la aplicación esté cerrada.",
        "proposer_demarrage": "¿Iniciar Temps PC automáticamente cada vez que se encienda el ordenador?\n\n"
                              "Recomendado: el tiempo solo se cuenta mientras la aplicación está abierta.\n"
                              "(Puedes cambiarlo más tarde en Ajustes.)",
        "erreur_demarrage": "No se pudo activar el inicio automático:\n{e}",
        "export_titre": "Exportar el historial",
        "export_type": "Archivo CSV",
        "export_colonnes": ["Fecha", "Día", "Minutos activos", "Duración", "Primera actividad", "Última actividad"],
        "export_separateur": ";",
        "export_erreur": "No se pudo exportar:\n{e}",
        "export_ok": "Historial exportado:\n{chemin}",
        "titre_reglages": "Ajustes",
        "case_pause": "Pausar el contador cuando no uso el PC",
        "apres": "tras",
        "minutes_sans": "minutos sin ratón ni teclado",
        "astuce": "Consejo: desmarca esta opción si también quieres contar las películas o vídeos que ves "
                  "sin tocar el PC.",
        "pas_detection": "La detección de inactividad no está disponible en este sistema: se cuenta todo el "
                         "tiempo que la aplicación está abierta.",
        "case_demarrage": "Iniciar Temps PC al encender el ordenador",
        "langue_auto": "Automático ({nom})",
        "donnees_dans": "Datos guardados en:",
        "ouvrir_dossier": "Abrir la carpeta",
        "enregistrer": "Guardar",
        "annuler": "Cancelar",
        "erreur_dossier": "No se pudo abrir la carpeta:\n{e}",
        "erreur_minutes": "Indica un número de minutos entre 1 y 120.",
        "erreur_demarrage_modif": "Inicio automático sin cambios:\n{e}",
        "titre_historique": "Historial",
        "jours_enregistres_1": "{n} día registrado",
        "jours_enregistres_n": "{n} días registrados",
        "resume": "{jours} · media {m} por día · total {t}",
        "aucune_donnee": "Todavía no hay datos.",
        "titre_12m": "Los últimos 12 meses",
        "sous_12m": "haz clic en un mes para ver el detalle",
        "nb_jours_1": "{n} día",
        "nb_jours_n": "{n} días",
        "bulle_mois_detail": " · {jours} · media {m}/día",
        "titre_jpj": "Día a día",
        "sous_jpj": "tiempo activo",
        "exporter_tout": "Exportar todo a CSV (Excel)…",
        "fermer": "Cerrar",
        "col_date": "Fecha", "col_jour": "Día", "col_temps": "Tiempo activo", "col_debut": "Inicio", "col_fin": "Fin",
        "jours_utilises_1": "{n} día de uso",
        "jours_utilises_n": "{n} días de uso",
        "detail1": "{t} en total · {jours} · media {m} por día",
        "detail2": "Día récord: {date}, {d}",
        "aucune_donnee_mois": "No hay datos para este mes.",
    },
    "zh": {
        "jours": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"],
        "jours_courts": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
        "mois": ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
        "mois_courts": ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
        "date_longue": "{mois}{n}日 {jour}",
        "mois_annee": "{a}年{mois}",
        "date_tableau": "%Y-%m-%d",
        "deux_points": "：",
        "axe_jour": "{jc} {n}",
        "duree_hm": "{h} 小时 {m} 分钟",
        "duree_m": "{m} 分钟",
        "duree_courte_hm": "{h} 小时 {m} 分",
        "grad_min": "{n} 分钟",
        "grad_h": "{n} 小时",
        "langue": "语言",
        "aujourdhui_date": "今天 · {date}",
        "actif": "使用中",
        "en_pause": "已暂停",
        "inactif_depuis": "已空闲 {d}",
        "premiere_activite": "首次活动 {h}",
        "moyenne_7": "前 7 天平均：{d}",
        "demarre": "计时器正在启动：照常使用电脑即可。",
        "titre_heures": "今天（按小时）",
        "sous_heures": "活跃分钟数",
        "titre_7j": "最近 7 天",
        "sous_7j": "将鼠标悬停在柱形上查看详情",
        "auj_court": "今天",
        "axe_heure": "{h}时",
        "bulle_heure": "{h}:00–{h2}:00：{d}",
        "historique": "历史记录",
        "reglages": "设置",
        "quitter": "退出",
        "note": "关闭窗口只会将其最小化。点击“退出”才会停止计时。",
        "cafe": "☕ 通过 PayPal 请我喝杯咖啡",
        "erreur_sauvegarde": "无法保存数据：{e}",
        "titre_pause": "{d}（已暂停）",
        "fichier_illisible": "无法读取数据文件（{e}）。\n\n该文件已另存到：\n{copie}",
        "info_reduction": "Temps PC 会继续计时，已最小化到任务栏。\n\n如需完全停止，请点击“退出”按钮。",
        "confirmer_quitter": "退出 Temps PC？\n\n应用关闭期间不会计时。",
        "proposer_demarrage": "每次开机时自动启动 Temps PC？\n\n推荐：只有在应用打开时才会计时。\n"
                              "（以后可以在“设置”中更改。）",
        "erreur_demarrage": "无法启用开机自动启动：\n{e}",
        "export_titre": "导出历史记录",
        "export_type": "CSV 文件",
        "export_colonnes": ["日期", "星期", "活跃分钟数", "时长", "首次活动", "最后活动"],
        "export_separateur": ",",
        "export_erreur": "导出失败：\n{e}",
        "export_ok": "历史记录已导出：\n{chemin}",
        "titre_reglages": "设置",
        "case_pause": "不使用电脑时暂停计时",
        "apres": "在",
        "minutes_sans": "分钟无鼠标或键盘操作后",
        "astuce": "提示：如果你也想统计不碰电脑观看电影或视频的时间，请取消勾选此项。",
        "pas_detection": "此系统不支持空闲检测：应用打开期间的所有时间都会被计入。",
        "case_demarrage": "开机时启动 Temps PC",
        "langue_auto": "自动（{nom}）",
        "donnees_dans": "数据保存位置：",
        "ouvrir_dossier": "打开文件夹",
        "enregistrer": "保存",
        "annuler": "取消",
        "erreur_dossier": "无法打开文件夹：\n{e}",
        "erreur_minutes": "请输入 1 到 120 之间的分钟数。",
        "erreur_demarrage_modif": "开机自动启动未更改：\n{e}",
        "titre_historique": "历史记录",
        "jours_enregistres_1": "已记录 {n} 天",
        "jours_enregistres_n": "已记录 {n} 天",
        "resume": "{jours} · 平均每天 {m} · 合计 {t}",
        "aucune_donnee": "暂无数据。",
        "titre_12m": "最近 12 个月",
        "sous_12m": "点击月份查看详情",
        "nb_jours_1": "{n} 天",
        "nb_jours_n": "{n} 天",
        "bulle_mois_detail": " · {jours} · 平均 {m}/天",
        "titre_jpj": "每日",
        "sous_jpj": "活跃时间",
        "exporter_tout": "全部导出为 CSV（Excel）…",
        "fermer": "关闭",
        "col_date": "日期", "col_jour": "星期", "col_temps": "活跃时间", "col_debut": "开始", "col_fin": "结束",
        "jours_utilises_1": "使用 {n} 天",
        "jours_utilises_n": "使用 {n} 天",
        "detail1": "合计 {t} · {jours} · 平均每天 {m}",
        "detail2": "最高纪录：{date}，{d}",
        "aucune_donnee_mois": "本月暂无数据。",
    },
    "hi": {
        "jours": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
        "jours_courts": ["सोम", "मंगल", "बुध", "गुरु", "शुक्र", "शनि", "रवि"],
        "mois": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई",
                 "अगस्त", "सितंबर", "अक्तूबर", "नवंबर", "दिसंबर"],
        "mois_courts": ["जन॰", "फ़र॰", "मार्च", "अप्रैल", "मई", "जून", "जुल॰", "अग॰", "सित॰", "अक्तू॰", "नव॰", "दिस॰"],
        "date_longue": "{jour}, {n} {mois}",
        "mois_annee": "{mois} {a}",
        "date_tableau": "%d/%m/%Y",
        "deux_points": ": ",
        "axe_jour": "{jc} {n}",
        "duree_hm": "{h} घंटे {m} मिनट",
        "duree_hm_1": "{h} घंटा {m} मिनट",
        "duree_m": "{m} मिनट",
        "duree_courte_hm": "{h} घं {m:02d} मि",
        "grad_min": "{n} मि",
        "grad_h": "{n} घं",
        "langue": "भाषा",
        "aujourdhui_date": "आज · {date}",
        "actif": "सक्रिय",
        "en_pause": "रुका हुआ",
        "inactif_depuis": "{d} से निष्क्रिय",
        "premiere_activite": "पहली गतिविधि {h} बजे",
        "moyenne_7": "पिछले 7 दिनों का औसत: {d}",
        "demarre": "काउंटर शुरू हो रहा है: अपना पीसी सामान्य रूप से इस्तेमाल करें।",
        "titre_heures": "आज, घंटे के हिसाब से",
        "sous_heures": "सक्रिय मिनट",
        "titre_7j": "पिछले 7 दिन",
        "sous_7j": "विवरण के लिए बार पर माउस ले जाएँ",
        "auj_court": "आज",
        "axe_heure": "{h}:00",
        "bulle_heure": "{h}:00 – {h2}:00: {d}",
        "historique": "इतिहास",
        "reglages": "सेटिंग्स",
        "quitter": "बाहर निकलें",
        "note": "विंडो बंद करने पर वह सिर्फ़ छोटी हो जाती है। “बाहर निकलें” से गिनती रुकती है।",
        "cafe": "☕ PayPal से मुझे एक कॉफ़ी पिलाएँ",
        "erreur_sauvegarde": "डेटा सहेजा नहीं जा सका: {e}",
        "titre_pause": "{d} (रुका हुआ)",
        "fichier_illisible": "डेटा फ़ाइल पढ़ी नहीं जा सकी ({e})।\n\nउसे यहाँ अलग रख दिया गया है:\n{copie}",
        "info_reduction": "Temps PC टास्कबार में छोटा होकर गिनती जारी रखता है।\n\n"
                          "इसे पूरी तरह रोकने के लिए “बाहर निकलें” बटन का इस्तेमाल करें।",
        "confirmer_quitter": "Temps PC से बाहर निकलें?\n\nऐप बंद रहने तक समय नहीं गिना जाएगा।",
        "proposer_demarrage": "क्या हर बार कंप्यूटर चालू होने पर Temps PC अपने-आप शुरू हो?\n\n"
                              "सुझाया गया: समय सिर्फ़ तभी गिना जाता है जब ऐप खुला हो।\n"
                              "(आप इसे बाद में सेटिंग्स में बदल सकते हैं।)",
        "erreur_demarrage": "अपने-आप शुरू होना चालू नहीं किया जा सका:\n{e}",
        "export_titre": "इतिहास निर्यात करें",
        "export_type": "CSV फ़ाइल",
        "export_colonnes": ["तारीख", "दिन", "सक्रिय मिनट", "अवधि", "पहली गतिविधि", "आख़िरी गतिविधि"],
        "export_separateur": ",",
        "export_erreur": "निर्यात नहीं हो सका:\n{e}",
        "export_ok": "इतिहास निर्यात हो गया:\n{chemin}",
        "titre_reglages": "सेटिंग्स",
        "case_pause": "जब मैं पीसी इस्तेमाल नहीं कर रहा हूँ, तब काउंटर रोकें",
        "apres": "माउस या कीबोर्ड के बिना",
        "minutes_sans": "मिनट के बाद",
        "astuce": "सुझाव: अगर आप पीसी को छुए बिना देखी गई फ़िल्में या वीडियो भी गिनना चाहते हैं, "
                  "तो इसे अनचेक करें।",
        "pas_detection": "इस सिस्टम पर निष्क्रियता पहचान उपलब्ध नहीं है: ऐप खुले रहने का पूरा समय गिना जाता है।",
        "case_demarrage": "कंप्यूटर चालू होने पर Temps PC शुरू करें",
        "langue_auto": "स्वचालित ({nom})",
        "donnees_dans": "डेटा यहाँ सहेजा गया है:",
        "ouvrir_dossier": "फ़ोल्डर खोलें",
        "enregistrer": "सहेजें",
        "annuler": "रद्द करें",
        "erreur_dossier": "फ़ोल्डर खोला नहीं जा सका:\n{e}",
        "erreur_minutes": "1 से 120 के बीच मिनटों की संख्या डालें।",
        "erreur_demarrage_modif": "अपने-आप शुरू होने की सेटिंग नहीं बदली:\n{e}",
        "titre_historique": "इतिहास",
        "jours_enregistres_1": "{n} दिन दर्ज",
        "jours_enregistres_n": "{n} दिन दर्ज",
        "resume": "{jours} · रोज़ाना औसत {m} · कुल {t}",
        "aucune_donnee": "अभी तक कोई डेटा नहीं।",
        "titre_12m": "पिछले 12 महीने",
        "sous_12m": "विवरण के लिए किसी महीने पर क्लिक करें",
        "nb_jours_1": "{n} दिन",
        "nb_jours_n": "{n} दिन",
        "bulle_mois_detail": " · {jours} · औसत {m}/दिन",
        "titre_jpj": "दिन-ब-दिन",
        "sous_jpj": "सक्रिय समय",
        "exporter_tout": "सब कुछ CSV (Excel) में निर्यात करें…",
        "fermer": "बंद करें",
        "col_date": "तारीख", "col_jour": "दिन", "col_temps": "सक्रिय समय", "col_debut": "शुरुआत", "col_fin": "अंत",
        "jours_utilises_1": "{n} दिन इस्तेमाल",
        "jours_utilises_n": "{n} दिन इस्तेमाल",
        "detail1": "कुल {t} · {jours} · रोज़ाना औसत {m}",
        "detail2": "सबसे ज़्यादा: {date}, {d}",
        "aucune_donnee_mois": "इस महीने का कोई डेटा नहीं।",
    },
    "ar": {
        "jours": ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"],
        "jours_courts": ["إثنين", "ثلاثاء", "أربعاء", "خميس", "جمعة", "سبت", "أحد"],
        "mois": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
                 "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
        "mois_courts": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
                        "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
        "date_longue": "{jour}، {n} {mois}",
        "mois_annee": "{mois} {a}",
        "date_tableau": "%d/%m/%Y",
        "deux_points": ": ",
        "axe_jour": "{jc}",
        "duree_hm": "{h} س {m:02d} د",
        "duree_m": "{m} د",
        "duree_courte_hm": "{h} س {m:02d}",
        "grad_min": "{n} د",
        "grad_h": "{n} س",
        "langue": "اللغة",
        "aujourdhui_date": "اليوم · {date}",
        "actif": "نشط",
        "en_pause": "متوقف مؤقتًا",
        "inactif_depuis": "خامل منذ {d}",
        "premiere_activite": "أول نشاط عند {h}",
        "moyenne_7": "متوسط الأيام السبعة السابقة: {d}",
        "demarre": "العداد يبدأ: استخدم حاسوبك كالمعتاد.",
        "titre_heures": "اليوم، ساعة بساعة",
        "sous_heures": "دقائق النشاط",
        "titre_7j": "آخر 7 أيام",
        "sous_7j": "مرّر الماوس فوق عمود لرؤية التفاصيل",
        "auj_court": "اليوم",
        "axe_heure": "{h}:00",
        "bulle_heure": "{h}:00 – {h2}:00: {d}",
        "historique": "السجل",
        "reglages": "الإعدادات",
        "quitter": "خروج",
        "note": "إغلاق النافذة يصغّرها فقط. «خروج» يوقف العدّ.",
        "cafe": "ادعمني بفنجان قهوة عبر باي بال ☕",
        "erreur_sauvegarde": "تعذّر حفظ البيانات: {e}",
        "titre_pause": "{d} (متوقف مؤقتًا)",
        "fichier_illisible": "تعذّرت قراءة ملف البيانات ({e}).\n\nتم وضعه جانبًا هنا:\n{copie}",
        "info_reduction": "يواصل التطبيق العدّ وهو مصغّر في شريط المهام.\n\nلإيقافه تمامًا، استخدم زر «خروج».",
        "confirmer_quitter": "هل تريد الخروج من التطبيق؟\n\nلن يُحتسب الوقت ما دام التطبيق مغلقًا.",
        "proposer_demarrage": "هل تريد تشغيل التطبيق تلقائيًا في كل مرة يبدأ فيها الحاسوب؟\n\n"
                              "يُنصح بذلك: لا يُحتسب الوقت إلا عندما يكون التطبيق مفتوحًا.\n"
                              "(يمكنك تغيير ذلك لاحقًا من الإعدادات.)",
        "erreur_demarrage": "تعذّر تفعيل التشغيل التلقائي:\n{e}",
        "export_titre": "تصدير السجل",
        "export_type": "ملف CSV",
        "export_colonnes": ["التاريخ", "اليوم", "دقائق النشاط", "المدة", "أول نشاط", "آخر نشاط"],
        "export_separateur": ",",
        "export_erreur": "تعذّر التصدير:\n{e}",
        "export_ok": "تم تصدير السجل:\n{chemin}",
        "titre_reglages": "الإعدادات",
        "case_pause": "إيقاف العداد مؤقتًا عندما لا أستخدم الحاسوب",
        "apres": "بعد",
        "minutes_sans": "دقائق دون استخدام الماوس أو لوحة المفاتيح",
        "astuce": "نصيحة: ألغِ تحديد هذا الخيار إذا أردت أيضًا احتساب الأفلام أو مقاطع الفيديو التي تشاهدها "
                  "دون لمس الحاسوب.",
        "pas_detection": "اكتشاف الخمول غير متاح على هذا النظام: يُحتسب كل الوقت الذي يكون فيه التطبيق مفتوحًا.",
        "case_demarrage": "تشغيل التطبيق عند بدء تشغيل الحاسوب",
        "langue_auto": "تلقائي ({nom})",
        "donnees_dans": "البيانات محفوظة في:",
        "ouvrir_dossier": "فتح المجلد",
        "enregistrer": "حفظ",
        "annuler": "إلغاء",
        "erreur_dossier": "تعذّر فتح المجلد:\n{e}",
        "erreur_minutes": "أدخل عدد دقائق بين 1 و120.",
        "erreur_demarrage_modif": "لم يتغيّر التشغيل التلقائي:\n{e}",
        "titre_historique": "السجل",
        "jours_enregistres_1": "الأيام المسجّلة: {n}",
        "jours_enregistres_n": "الأيام المسجّلة: {n}",
        "resume": "{jours} · المتوسط {m} يوميًا · المجموع {t}",
        "aucune_donnee": "لا توجد بيانات بعد.",
        "titre_12m": "آخر 12 شهرًا",
        "sous_12m": "انقر على شهر لرؤية التفاصيل",
        "nb_jours_1": "الأيام: {n}",
        "nb_jours_n": "الأيام: {n}",
        "bulle_mois_detail": " · {jours} · المتوسط {m} يوميًا",
        "titre_jpj": "يومًا بيوم",
        "sous_jpj": "وقت النشاط",
        "exporter_tout": "تصدير الكل إلى ملف إكسل…",
        "fermer": "إغلاق",
        "col_date": "التاريخ", "col_jour": "اليوم", "col_temps": "وقت النشاط", "col_debut": "البداية",
        "col_fin": "النهاية",
        "jours_utilises_1": "أيام الاستخدام: {n}",
        "jours_utilises_n": "أيام الاستخدام: {n}",
        "detail1": "المجموع {t} · {jours} · المتوسط {m} يوميًا",
        "detail2": "اليوم القياسي: {date}، {d}",
        "aucune_donnee_mois": "لا توجد بيانات لهذا الشهر.",
    },
}
# Ordre d'affichage : l'anglais d'abord, puis les langues les plus parlees, et le francais
ORDRE_LANGUES = ["en", "zh", "hi", "es", "ar", "fr"]
NOMS_LANGUES = {"en": "English", "zh": "中文（简体）", "hi": "हिन्दी", "es": "Español", "ar": "العربية",
                "fr": "Français"}
LANGUES_RTL = {"ar"}
# Identifiants de langue Windows (LANG_xxx) et prefixes de locale
LANGUES_WINDOWS = {0x09: "en", 0x04: "zh", 0x39: "hi", 0x0A: "es", 0x01: "ar", 0x0C: "fr"}
# Polices Windows qui contiennent ces ecritures
POLICES_WINDOWS = {"zh": "Microsoft YaHei UI", "hi": "Nirmala UI"}
LANGUE = "en"


def langue_systeme() -> str:
    """Langue de Windows (ou du systeme) si elle est disponible, sinon l'anglais."""
    try:
        if WIN:
            return LANGUES_WINDOWS.get(ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF, "en")
        import locale
        loc = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") \
            or (locale.getlocale()[0] or "")
        return next((code for code in ORDRE_LANGUES if loc.lower().startswith(code)), "en")
    except Exception:
        return "en"


def definir_langue(langue: str) -> None:
    global LANGUE, POLICE
    LANGUE = langue if langue in TEXTES else "en"
    if WIN and not os.environ.get("TEMPS_PC_POLICE"):
        POLICE = POLICES_WINDOWS.get(LANGUE, "Segoe UI")


def rtl() -> bool:
    """Arabe : l'interface se lit de droite a gauche."""
    return LANGUE in LANGUES_RTL


def debut() -> str:
    return "right" if rtl() else "left"


def fin() -> str:
    return "left" if rtl() else "right"


def ancre_debut() -> str:
    return "e" if rtl() else "w"


def ancre_fin() -> str:
    return "w" if rtl() else "e"


def justif() -> str:
    return "right" if rtl() else "left"


def marge(avant: int, apres: int) -> tuple[int, int]:
    return (apres, avant) if rtl() else (avant, apres)


MONTANTS_DON = (2.5, 5, 10)


def lien_paypal(montant: float | None = None) -> str:
    if not montant:
        return PAYPAL
    texte = f"{montant:.2f}" if montant != int(montant) else str(int(montant))
    return f"{PAYPAL}/{texte}EUR"


def libelle_montant(montant: float) -> str:
    """« 2,50 € » en francais et en espagnol, « €2.50 » ailleurs."""
    v = f"{montant:.2f}" if montant != int(montant) else str(int(montant))
    return f"{v.replace('.', ',')} €" if LANGUE in ("fr", "es") else f"€{v}"


def ouvrir_paypal(montant: float | None = None) -> None:
    """Page PayPal.me (dans le navigateur), avec le montant deja rempli si on l'a choisi."""
    try:
        webbrowser.open(lien_paypal(montant))
    except Exception:
        pass


def choisir_langue(reglage: str | None) -> str:
    force = os.environ.get("TEMPS_PC_LANGUE")
    if force in TEXTES:
        return force
    return reglage if reglage in TEXTES else langue_systeme()


CHIFFRES_ARABES = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
NON_TRADUITS = ("chemin", "copie", "e")  # chemins de fichiers et messages d'erreur : tels quels


def nombre(texte) -> str:
    """En arabe, chiffres arabes orientaux : Windows les place alors dans le bon sens de lecture."""
    texte = str(texte)
    return texte.translate(CHIFFRES_ARABES) if LANGUE == "ar" else texte


def t(cle: str, **kw):
    val = TEXTES[LANGUE].get(cle, TEXTES["en"].get(cle, cle))
    if not isinstance(val, str):
        return val
    if LANGUE != "ar":
        return val.format(**kw) if kw else val
    gardes = {k: str(v) for k, v in kw.items() if k in NON_TRADUITS}
    texte = val.format(**{k: (f"\x00{k}\x00" if k in gardes else v) for k, v in kw.items()}) if kw else val
    texte = nombre(texte)
    for k, v in gardes.items():
        texte = texte.replace(f"\x00{k}\x00", v)
    return texte


def pluriel(n: int, cle: str) -> str:
    return t(f"{cle}_{'1' if n == 1 else 'n'}", n=n)


def majuscule(texte: str) -> str:
    return texte[:1].upper() + texte[1:]


def nom_jour(dt: date) -> str:
    return t("jours")[dt.weekday()]


def nom_mois(m: int) -> str:
    return t("mois")[m - 1]


def date_longue(dt: date, maj: bool = False) -> str:
    texte = t("date_longue", jour=nom_jour(dt), n=dt.day, mois=nom_mois(dt.month))
    return majuscule(texte) if maj else texte


def mois_annee(a: int, m: int) -> str:
    return t("mois_annee", mois=majuscule(nom_mois(m)), a=a)


def insecables(texte: str) -> str:
    """Evite de couper « 5 h 28 » ou « 12 min » en fin de ligne."""
    texte = texte.replace(" h ", "\u00a0h\u00a0").replace(" min", "\u00a0min").replace("à ", "à\u00a0")
    return re.sub(r"(\d) ", "\\1\u00a0", texte)

POLICE = "Segoe UI" if WIN else ("Helvetica Neue" if MAC else "DejaVu Sans")
POLICE_FORCEE = os.environ.get("TEMPS_PC_POLICE")  # pour les essais uniquement
if POLICE_FORCEE:
    POLICE = POLICE_FORCEE

THEMES = {
    "clair": dict(fond="#fcfcfb", carte="#f1f0ec", texte="#0b0b0b", texte2="#52514e",
                  discret="#86857f", grille="#e8e7e3", axe="#c9c8c3",
                  barre_actif="#1f9d4a", passee_actif="#6fc28c",
                  barre_pause="#8a8984", passee_pause="#bdbcb6", actif="#1f9d4a",
                  bouton="#ecebe7", bouton_survol="#dfded9", bulle="#262624",
                  bulle_texte="#fcfcfb", survol_col="#f1f0ec", copyright="#c9c8c2"),
    "sombre": dict(fond="#1a1a19", carte="#252524", texte="#f0efec", texte2="#c3c2b7",
                   discret="#8f8e86", grille="#2c2c2a", axe="#4a4a47",
                   barre_actif="#34b864", passee_actif="#22703f",
                   barre_pause="#8f8e86", passee_pause="#4a4a47", actif="#34b864",
                   bouton="#2b2b29", bouton_survol="#373734", bulle="#f0efec",
                   bulle_texte="#1a1a19", survol_col="#242423", copyright="#4a4a46"),
}


# --------------------------------------------------------------------------
# Petits utilitaires
# --------------------------------------------------------------------------
def duree(sec: float) -> str:
    """'3 h 05 min' ou '42 min' (dans la langue choisie)."""
    m = int(max(0, sec) // 60)
    h, m = divmod(m, 60)
    if not h:
        return t("duree_m", m=m)
    return t("duree_hm_1" if h == 1 and "duree_hm_1" in TEXTES[LANGUE] else "duree_hm", h=h, m=m)


def duree_courte(sec: float) -> str:
    """'3 h 05' ou '42 min'."""
    m = int(max(0, sec) // 60)
    h, m = divmod(m, 60)
    return t("duree_courte_hm", h=h, m=m) if h else t("duree_m", m=m)


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


def copier_fichier(source: str, cible: str) -> None:
    """Copie simple et sure (pas de shutil.copy2 : CopyFile2 absent de certains systemes)."""
    tmp = cible + ".tmp"
    with open(source, "rb") as fs, open(tmp, "wb") as fc:
        fc.write(fs.read())
        fc.flush()
        os.fsync(fc.fileno())
    os.replace(tmp, cible)


class Donnees:
    def __init__(self, dossier: str) -> None:
        self.dossier = dossier
        self.chemin = os.path.join(dossier, "donnees.json")
        self.erreur_lecture: tuple[str, str] | None = None
        self.jours: dict[str, dict] = {}
        self.reglages = dict(REGLAGES_DEFAUT)
        self._sauvegarde_faite: str | None = None
        self._charger()
        if not self.avertissement:
            self.sauvegarde_du_jour()

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
            self.erreur_lecture = (str(e), copie)

    @property
    def avertissement(self) -> str | None:
        if not self.erreur_lecture:
            return None
        return t("fichier_illisible", e=self.erreur_lecture[0], copie=self.erreur_lecture[1])

    def sauvegarde_du_jour(self) -> None:
        """Copie de securite de donnees.json, avant toute ecriture : une par jour (les
        14 dernieres sont gardees) + une copie permanente a la 1re ouverture d'une version."""
        auj = date.today().isoformat()
        if self._sauvegarde_faite == auj or not os.path.exists(self.chemin):
            return
        self._sauvegarde_faite = auj
        dossier = os.path.join(self.dossier, "sauvegardes")
        try:
            os.makedirs(dossier, exist_ok=True)
            for nom in (f"donnees-{auj}.json", f"donnees-avant-version-{APP_VERSION}.json"):
                cible = os.path.join(dossier, nom)
                if not os.path.exists(cible):
                    copier_fichier(self.chemin, cible)
            quotidiennes = sorted(n for n in os.listdir(dossier)
                                  if re.fullmatch(r"donnees-\d{4}-\d\d-\d\d\.json", n))
            for nom in quotidiennes[:-SAUVEGARDES_GARDEES]:
                os.remove(os.path.join(dossier, nom))
        except OSError:
            pass

    def jour(self, cle: str) -> dict:
        return self.jours.setdefault(cle, {"heures": [0.0] * 24, "premiere": None, "derniere": None})

    def total(self, cle: str) -> float:
        j = self.jours.get(cle)
        return sum(j["heures"]) if j else 0.0

    def enregistrer(self) -> None:
        os.makedirs(self.dossier, exist_ok=True)
        self.sauvegarde_du_jour()
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


def echelle_heures(max_sec: float, graduations_max: int = 4) -> tuple[float, list[tuple[float, str]]]:
    """Haut de l'axe et graduations pour des durees en heures."""
    hmax = max(1.0, max_sec / 3600 + 0.08)
    for pas in (1, 2, 4, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if math.ceil(hmax / pas) <= graduations_max:
            break
    n = max(1, math.ceil(hmax / pas))
    return n * pas * 3600.0, [(k * pas * 3600.0, t("grad_h", n=k * pas)) for k in range(1, n + 1)]


def mois_decale(an: int, mois: int, delta: int) -> tuple[int, int]:
    n = an * 12 + (mois - 1) + delta
    return n // 12, n % 12 + 1


def rectangle_arrondi_haut(c: tk.Canvas, x0, y0, x1, y1, r, **kw):
    r = min(r, (x1 - x0) / 2, (y1 - y0))
    if r < 1:
        return c.create_rectangle(x0, y0, x1, y1, width=0, **kw)
    pts = [x0, y1, x0, y1, x0, y0 + r, x0, y0 + r, x0, y0, x0 + r, y0, x0 + r, y0,
           x1 - r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y0 + r, x1, y1, x1, y1]
    return c.create_polygon(pts, smooth=True, outline="", **kw)


class Graphique(tk.Canvas):
    def __init__(self, master, app: "Application", hauteur: int, ratio: float, au_clic=None) -> None:
        super().__init__(master, height=app.px(hauteur), bg=app.th["fond"],
                         highlightthickness=0, bd=0)
        self.app = app
        self.au_clic = au_clic
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
        if au_clic:
            self.bind("<Button-1>", self._clic)

    def _index(self, x: float) -> int | None:
        return next((k for k, (xa, xb, _) in enumerate(self.zones) if xa <= x < xb), None)

    def _clic(self, e) -> None:
        i = self._index(e.x)
        if i is not None:
            self.au_clic(i)

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
                et = self.create_text((x0 + x1) / 2, y0 - hb - px(4), text=b.etiquette, anchor="s",
                                      fill=th["texte"], font=(POLICE, 9, "bold"))
                ex0, _, ex1, _ = self.bbox(et)
                self.move(et, max(0, px(2) - ex0) - max(0, ex1 - (w - px(2))), 0)
            self.zones.append((xa, xa + pas, y0 - hb))
        self._bulle()

    def _bouge(self, e) -> None:
        i = self._index(e.x)
        if i != self.survol:
            if self.au_clic:
                self.config(cursor="hand2" if i is not None else "")
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
        self.actif = True
        self.bind("<Enter>", lambda e: self.config(bg=th["bouton_survol"]) if self.actif else None)
        self.bind("<Leave>", lambda e: self.config(bg=th["bouton"]))
        for ev in ("<Button-1>", "<Return>", "<space>"):
            self.bind(ev, lambda e: commande() if self.actif else None)

    def activer(self, oui: bool) -> None:
        if oui != self.actif:
            self.actif = oui
            self.config(fg=self._th["texte"] if oui else self._th["discret"],
                        cursor="hand2" if oui else "", bg=self._th["bouton"])


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


class BoutonCafe(tk.Label):
    """Petit bouton jaune « 2 € » qui ouvre PayPal avec ce montant."""
    JAUNE, JAUNE_SURVOL = "#facc15", "#eab308"

    def __init__(self, master, montant: float, app: "Application") -> None:
        super().__init__(master, text=libelle_montant(montant), bg=self.JAUNE, fg="#1a1a19",
                         font=(POLICE, 9, "bold"), padx=app.px(8), pady=app.px(1), cursor="hand2")
        self.bind("<Enter>", lambda e: self.config(bg=self.JAUNE_SURVOL))
        self.bind("<Leave>", lambda e: self.config(bg=self.JAUNE))
        self.bind("<Button-1>", lambda e: ouvrir_paypal(montant))


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
        definir_langue(choisir_langue(donnees.reglages.get("langue")))
        self.th = THEMES["sombre" if theme_sombre() else "clair"]
        self.echelle = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.derniere_sauvegarde = time.time()
        self.erreur_sauvegarde: str | None = None

        th = self.th
        root.title(APP_NOM)
        root.configure(bg=th["fond"])
        self._dimensionner(root, 520, 712, 440, 670)
        root.protocol("WM_DELETE_WINDOW", self.reduire)
        self._icones: list[tk.PhotoImage] = []
        self._etat_icone = None
        self.historique: FenetreHistorique | None = None
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

    def _dimensionner(self, fen: tk.Misc, l: int, h: int, lmin: int, hmin: int) -> None:
        """Taille voulue, sans depasser l'ecran (petits portables, zoom Windows a 125-150 %)."""
        w = min(self.px(l), fen.winfo_screenwidth() - self.px(40))
        hh = min(self.px(h), fen.winfo_screenheight() - self.px(90))
        fen.geometry(f"{w}x{hh}")
        fen.minsize(min(self.px(lmin), w), min(self.px(hmin), hh))

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
        st.configure("TCombobox", fieldbackground=th["carte"], background=th["bouton"],
                     foreground=th["texte"], arrowcolor=th["texte2"], bordercolor=th["axe"],
                     lightcolor=th["carte"], darkcolor=th["carte"], padding=self.px(3))
        st.map("TCombobox", fieldbackground=[("readonly", th["carte"])],
               foreground=[("readonly", th["texte"])], selectbackground=[("readonly", th["carte"])],
               selectforeground=[("readonly", th["texte"])])
        self.root.option_add("*TCombobox*Listbox.background", th["carte"])
        self.root.option_add("*TCombobox*Listbox.foreground", th["texte"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", th["barre_actif"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    def _construire(self) -> None:
        th, px = self.th, self.px
        cadre = tk.Frame(self.root, bg=th["fond"], padx=px(22), pady=px(18))
        cadre.pack(fill="both", expand=True)

        self.lbl_date = tk.Label(cadre, bg=th["fond"], fg=th["texte2"], font=(POLICE, 11), anchor=ancre_debut())
        self.lbl_date.pack(fill="x")

        ligne = tk.Frame(cadre, bg=th["fond"])
        ligne.pack(fill="x", pady=(px(2), 0))
        self.lbl_total = tk.Label(ligne, bg=th["fond"], fg=th["texte"],
                                  font=(POLICE, 32, "bold"), anchor=ancre_debut())
        self.lbl_total.pack(side=debut())
        statut = tk.Frame(ligne, bg=th["fond"])
        statut.pack(side=fin(), anchor="s", pady=(0, px(8)))
        haut_statut = tk.Frame(statut, bg=th["fond"])
        haut_statut.pack(anchor=ancre_fin())
        self.lbl_point = tk.Label(haut_statut, text="●", bg=th["fond"], font=(POLICE, 11))
        self.lbl_point.pack(side=debut())
        self.lbl_statut = tk.Label(haut_statut, bg=th["fond"], fg=th["texte2"], font=(POLICE, 10))
        self.lbl_statut.pack(side=debut(), padx=marge(px(4), 0))
        self.lbl_statut2 = tk.Label(statut, bg=th["fond"], fg=th["discret"], font=(POLICE, 9))
        self.lbl_statut2.pack(anchor=ancre_fin())

        self.lbl_info = tk.Label(cadre, bg=th["fond"], fg=th["texte2"], font=(POLICE, 10),
                                 anchor=ancre_debut(), justify=justif())
        self.lbl_info.pack(fill="x")
        def ajuster(e):
            largeur = max(200, e.width - px(44))
            self.lbl_info.config(wraplength=largeur)
            self.lbl_note.config(wraplength=largeur)
        cadre.bind("<Configure>", ajuster)

        self._titre(cadre, t("titre_heures"), t("sous_heures"))
        self.graph_heures = Graphique(cadre, self, 150, 0.7)
        self.graph_heures.pack(fill="x")

        self._titre(cadre, t("titre_7j"), t("sous_7j"))
        self.graph_jours = Graphique(cadre, self, 170, 0.56)
        self.graph_jours.pack(fill="x")

        bas = tk.Frame(cadre, bg=th["fond"])
        bas.pack(side="bottom", fill="x", pady=(px(16), 0))
        # Derniere ligne : « offre-moi un cafe » (PayPal) et le copyright, tout petit
        pied = tk.Frame(bas, bg=th["fond"])
        pied.pack(side="bottom", fill="x", pady=(px(12), 0))
        cafe = tk.Label(pied, text=t("cafe"), bg=th["fond"], fg=th["texte2"], font=(POLICE, 9),
                        cursor="hand2")
        cafe.pack(side=debut())
        cafe.bind("<Button-1>", lambda e: ouvrir_paypal())
        for montant in MONTANTS_DON:
            BoutonCafe(pied, montant, self).pack(side=debut(), padx=marge(px(6), 0))
        tk.Label(pied, text=COPYRIGHT, bg=th["fond"], fg=th["copyright"], font=(POLICE, 7)).pack(
            side=fin(), anchor="s")
        self.lbl_note = tk.Label(bas, bg=th["fond"], fg=th["discret"], font=(POLICE, 9),
                                 anchor=ancre_debut(), justify=justif())
        self.lbl_note.pack(side="bottom", fill="x", pady=(px(10), 0))
        boutons = tk.Frame(bas, bg=th["fond"])
        boutons.pack(side="bottom", fill="x")
        Bouton(boutons, t("historique"), self.ouvrir_historique, self).pack(side=debut())
        Bouton(boutons, t("reglages"), self.ouvrir_reglages, self).pack(side=debut(), padx=marge(px(8), 0))
        Bouton(boutons, t("quitter"), self.quitter, self).pack(side=fin())

    def _titre(self, parent, texte: str, sous_titre: str) -> None:
        th, px = self.th, self.px
        f = tk.Frame(parent, bg=th["fond"])
        f.pack(fill="x", pady=(px(18), px(2)))
        tk.Label(f, text=texte, bg=th["fond"], fg=th["texte"], font=(POLICE, 11, "bold")).pack(side=debut())
        tk.Label(f, text=sous_titre, bg=th["fond"], fg=th["discret"], font=(POLICE, 9)).pack(
            side=fin(), anchor="s")

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
            self.erreur_sauvegarde = t("erreur_sauvegarde", e=e)

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

        self.lbl_date.config(text=t("aujourdhui_date", date=date_longue(auj)))
        self.lbl_total.config(text=duree(total))
        self._maj_icone(total)

        if self.compteur.actif:
            self.lbl_point.config(fg=th["actif"])
            self.lbl_statut.config(text=t("actif"))
            self.lbl_statut2.config(text="")
        else:
            self.lbl_point.config(fg=th["barre_pause"])
            self.lbl_statut.config(text=t("en_pause"))
            self.lbl_statut2.config(text=t("inactif_depuis", d=duree(self.compteur.inactif_depuis)))

        infos = []
        if j and j.get("premiere"):
            infos.append(t("premiere_activite", h=j["premiere"]))
        passes = [self.d.total((auj - timedelta(days=k)).isoformat()) for k in range(1, 8)]
        passes = [v for v in passes if v >= 60]
        if passes:
            infos.append(t("moyenne_7", d=duree_courte(sum(passes) / len(passes))))
        txt = " · ".join(insecables(i) for i in infos) or t("demarre")
        self.lbl_info.config(text=majuscule(txt))

        # Vert quand on est actif, gris quand le compteur est en pause
        etat = "actif" if self.compteur.actif else "pause"
        couleur, couleur_passee = th[f"barre_{etat}"], th[f"passee_{etat}"]

        # Heure par heure
        heures = j["heures"] if j else [0.0] * 24
        barres_h = [Barre(v, t("axe_heure", h=h) if h % 6 == 0 else "",
                          t("bulle_heure", h=h, h2=h + 1, d=duree(v)), couleur) for h, v in enumerate(heures)]
        self.graph_heures.maj(barres_h, 3600.0, [(1800, t("grad_min", n=30)), (3600, t("grad_min", n=60))])

        # 7 derniers jours
        barres_j = []
        valeurs = []
        for k in range(6, -1, -1):
            jr = auj - timedelta(days=k)
            v = self.d.total(jr.isoformat())
            valeurs.append(v)
            barres_j.append(Barre(
                v, t("auj_court") if k == 0 else t("axe_jour", jc=t("jours_courts")[jr.weekday()], n=jr.day),
                date_longue(jr, True) + t("deux_points") + duree(v), couleur if k == 0 else couleur_passee,
                fort=(k == 0), etiquette=duree_courte(v) if k == 0 else None))
        self.graph_jours.maj(barres_j, *echelle_heures(max(valeurs)))

        note = self.erreur_sauvegarde or t("note")
        self.lbl_note.config(text=note, fg="#d03b3b" if self.erreur_sauvegarde else th["discret"])

        if self.historique:
            try:
                self.historique.maj()
            except tk.TclError:  # fenetre fermee entre-temps
                self.historique = None

    def _maj_icone(self, total: float) -> None:
        """Icone de la barre des taches + titre : le temps du jour, mis a jour chaque minute."""
        etat = (int(total // 60), self.compteur.actif)
        if etat == self._etat_icone:
            return
        self._etat_icone = etat
        temps = duree_courte(total) if self.compteur.actif else t("titre_pause", d=duree_courte(total))
        self.root.title(f"{APP_NOM} – {temps}" if rtl() else f"{temps} – {APP_NOM}")
        try:
            icones = icones_temps(self.root, total, self.compteur.actif)
            self.root.iconphoto(True, *icones)
            self._icones = icones  # garder une reference, sinon Tk efface les images
        except tk.TclError:
            pass

    def reconstruire(self) -> None:
        """Refait l'interface dans la nouvelle langue (les donnees ne bougent pas)."""
        historique_ouvert = bool(self.historique and self.historique.f.winfo_exists())
        if historique_ouvert:
            self.historique.f.destroy()
            self.historique = None
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        self._construire()
        self._etat_icone = None
        self.rafraichir()
        if historique_ouvert:
            self.ouvrir_historique()

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
            messagebox.showinfo(APP_NOM, t("info_reduction"), parent=self.root)
        self.root.iconify()

    def quitter(self) -> None:
        if not messagebox.askyesno(APP_NOM, t("confirmer_quitter"), parent=self.root):
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
        if messagebox.askyesno(APP_NOM, t("proposer_demarrage"), parent=self.root):
            try:
                Demarrage.regler(True)
            except OSError as e:
                messagebox.showerror(APP_NOM, t("erreur_demarrage", e=e), parent=self.root)
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
        if self.historique and self.historique.f.winfo_exists():
            self.historique.f.deiconify()
            self.historique.f.lift()
            return
        self.historique = FenetreHistorique(self)

    def _exporter(self, parent, jours) -> None:
        chemin = filedialog.asksaveasfilename(parent=parent, title=t("export_titre"),
                                              defaultextension=".csv", initialfile="temps_pc.csv",
                                              filetypes=[(t("export_type"), "*.csv")])
        if not chemin:
            return
        try:
            with open(chemin, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh, delimiter=t("export_separateur"))
                w.writerow(t("export_colonnes"))
                for k, v in sorted(jours):
                    tot = sum(v["heures"])
                    w.writerow([k, nom_jour(date.fromisoformat(k)), round(tot / 60),
                                duree_courte(tot), v.get("premiere") or "", v.get("derniere") or ""])
        except OSError as e:
            messagebox.showerror(APP_NOM, t("export_erreur", e=e), parent=parent)
            return
        messagebox.showinfo(APP_NOM, t("export_ok", chemin=chemin), parent=parent)

    def ouvrir_reglages(self) -> None:
        th, px = self.th, self.px
        f = self._fenetre(f"{APP_NOM} – {t('titre_reglages')}")
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
        langue_avant = r.get("langue") if r.get("langue") in TEXTES else "auto"
        codes_langue = ["auto"] + ORDRE_LANGUES
        libelles_langue = [t("langue_auto", nom=NOMS_LANGUES[langue_systeme()])] + \
                          [NOMS_LANGUES[c] for c in ORDRE_LANGUES]

        def case(texte, var):
            return tk.Checkbutton(cadre, text=texte, variable=var, bg=th["fond"], fg=th["texte"],
                                  activebackground=th["fond"], activeforeground=th["texte"],
                                  selectcolor=th["carte"], highlightthickness=0, bd=0,
                                  font=(POLICE, 10), anchor=ancre_debut(), justify=justif(),
                                  wraplength=px(420))

        case(t("case_pause"), v_pause).pack(fill="x")
        ligne = tk.Frame(cadre, bg=th["fond"])
        ligne.pack(fill="x", padx=marge(px(26), 0), pady=(px(4), 0))
        tk.Label(ligne, text=t("apres"), bg=th["fond"], fg=th["texte2"], font=(POLICE, 10)).pack(side=debut())
        tk.Spinbox(ligne, from_=1, to=120, width=4, textvariable=v_min, font=(POLICE, 10),
                   bg=th["carte"], fg=th["texte"], buttonbackground=th["bouton"],
                   insertbackground=th["texte"], relief="flat", justify="center").pack(
            side=debut(), padx=px(6))
        tk.Label(ligne, text=t("minutes_sans"), bg=th["fond"], fg=th["texte2"],
                 font=(POLICE, 10)).pack(side=debut())
        aide = t("astuce") if self.det.methode is not None else t("pas_detection")
        tk.Label(cadre, text=aide, bg=th["fond"], fg=th["discret"], font=(POLICE, 9), anchor=ancre_debut(),
                 justify=justif(), wraplength=px(420)).pack(fill="x", padx=marge(px(26), 0), pady=(px(6), 0))

        case(t("case_demarrage"), v_dem).pack(fill="x", pady=(px(18), 0))

        # Langue (toujours aussi ecrit en anglais, pour s'y retrouver)
        titre_langue = t("langue") if LANGUE == "en" else f"{t('langue')} / Language"
        tk.Label(cadre, text=titre_langue, bg=th["fond"], fg=th["texte2"], font=(POLICE, 10),
                 anchor=ancre_debut()).pack(fill="x", pady=(px(18), 0))
        self.choix_langue = choix_langue = ttk.Combobox(cadre, values=libelles_langue, state="readonly",
                                                         font=(POLICE, 10), width=24)
        choix_langue.current(codes_langue.index(langue_avant))
        choix_langue.pack(anchor=ancre_debut(), padx=marge(px(20), 0), pady=(px(4), 0))

        tk.Label(cadre, text=t("donnees_dans"), bg=th["fond"], fg=th["texte2"],
                 font=(POLICE, 10), anchor=ancre_debut()).pack(fill="x", pady=(px(18), 0))
        tk.Label(cadre, text=self.d.chemin, bg=th["fond"], fg=th["discret"], font=(POLICE, 9),
                 anchor=ancre_debut(), justify="left", wraplength=px(420)).pack(fill="x")

        def ouvrir():
            try:
                ouvrir_dossier(self.d.dossier)
            except Exception as e:
                messagebox.showerror(APP_NOM, t("erreur_dossier", e=e), parent=f)

        def valider():
            try:
                minutes = int(v_min.get())
                if not 1 <= minutes <= 120:
                    raise ValueError
            except ValueError:
                messagebox.showerror(APP_NOM, t("erreur_minutes"), parent=f)
                return
            r["pause_si_inactif"] = bool(v_pause.get())
            r["minutes_inactivite"] = minutes
            if bool(v_dem.get()) != demarrage_avant:
                try:
                    Demarrage.regler(bool(v_dem.get()))
                except OSError as e:
                    messagebox.showerror(APP_NOM, t("erreur_demarrage_modif", e=e), parent=f)
            nouvelle = codes_langue[max(0, choix_langue.current())]
            if nouvelle == "auto":
                r.pop("langue", None)
            else:
                r["langue"] = nouvelle
            self._sauver()
            f.destroy()
            if choisir_langue(r.get("langue")) != LANGUE:
                definir_langue(choisir_langue(r.get("langue")))
                self.reconstruire()
            else:
                self.rafraichir()

        bas = tk.Frame(cadre, bg=th["fond"])
        bas.pack(side="bottom", fill="x", pady=(px(20), 0))
        Bouton(bas, t("ouvrir_dossier"), ouvrir, self).pack(side=debut())
        Bouton(bas, t("enregistrer"), valider, self).pack(side=fin())
        Bouton(bas, t("annuler"), f.destroy, self).pack(side=fin(), padx=marge(0, px(8)))


# --------------------------------------------------------------------------
# Fenetre Historique : 12 derniers mois + mois choisi jour par jour
# --------------------------------------------------------------------------
class FenetreHistorique:
    def __init__(self, app: Application) -> None:
        self.app = app
        th, px = app.th, app.px
        auj = date.today()
        self.mois = (auj.year, auj.month)
        self.bornes = (self.mois, self.mois)
        self.mois_affiches: list[tuple[int, int]] = []
        self._sig_table = None

        self.f = f = app._fenetre(f"{APP_NOM} – {t('titre_historique')}")
        app._dimensionner(f, 600, 780, 500, 560)
        f.bind("<Destroy>", self._ferme, add="+")
        f.bind("<Left>", lambda e: self.changer(-1))
        f.bind("<Right>", lambda e: self.changer(1))
        petit = f.winfo_screenheight() < px(860)

        cadre = tk.Frame(f, bg=th["fond"], padx=px(20), pady=px(14))
        cadre.pack(fill="both", expand=True)
        self.lbl_resume = tk.Label(cadre, bg=th["fond"], fg=th["texte2"], font=(POLICE, 10), anchor=ancre_debut())
        self.lbl_resume.pack(fill="x")

        app._titre(cadre, t("titre_12m"), t("sous_12m"))
        self.g_mois = Graphique(cadre, app, 112 if petit else 132, 0.56, au_clic=self._clic_mois)
        self.g_mois.pack(fill="x")

        nav = tk.Frame(cadre, bg=th["fond"])
        nav.pack(fill="x", pady=(px(14), 0))
        self.b_prec = Bouton(nav, "‹", lambda: self.changer(-1), app)
        self.b_prec.pack(side="left")
        self.lbl_mois = tk.Label(nav, bg=th["fond"], fg=th["texte"], font=(POLICE, 13, "bold"))
        self.lbl_mois.pack(side="left", padx=px(12))
        self.b_suiv = Bouton(nav, "›", lambda: self.changer(1), app)
        self.b_suiv.pack(side="left")
        self.lbl_detail = tk.Label(cadre, bg=th["fond"], fg=th["texte2"], font=(POLICE, 10),
                                   anchor=ancre_debut(), justify=justif())
        self.lbl_detail.pack(fill="x", pady=(px(6), 0))
        cadre.bind("<Configure>", lambda e: self.lbl_detail.config(wraplength=max(200, e.width - px(40))),
                   add="+")

        app._titre(cadre, t("titre_jpj"), t("sous_jpj"))
        self.g_jours = Graphique(cadre, app, 118 if petit else 150, 0.62, au_clic=self._clic_jour)
        self.g_jours.pack(fill="x")

        bas = tk.Frame(cadre, bg=th["fond"])
        bas.pack(side="bottom", fill="x", pady=(px(12), 0))
        Bouton(bas, t("exporter_tout"), self._exporter, app).pack(side=debut())
        Bouton(bas, t("fermer"), f.destroy, app).pack(side=fin())

        zone = tk.Frame(cadre, bg=th["fond"])
        zone.pack(fill="both", expand=True, pady=(px(14), 0))
        cols = ("date", "jour", "temps", "premiere", "derniere")
        self.arbre = ttk.Treeview(zone, columns=cols, show="headings", selectmode="browse", height=4)
        for col, titre, larg, anc in (("date", t("col_date"), 100, "w"), ("jour", t("col_jour"), 90, "w"),
                                      ("temps", t("col_temps"), 110, "e"),
                                      ("premiere", t("col_debut"), 70, "center"),
                                      ("derniere", t("col_fin"), 70, "center")):
            self.arbre.heading(col, text=titre, anchor=anc)
            self.arbre.column(col, width=px(larg), anchor=anc, stretch=True)
        defil = ttk.Scrollbar(zone, orient="vertical", command=self.arbre.yview)
        self.arbre.configure(yscrollcommand=defil.set)
        defil.pack(side="right", fill="y")
        self.arbre.pack(side="left", fill="both", expand=True)
        self.maj()
        f.focus_set()

    # ---- donnees ------------------------------------------------------------
    def _par_mois(self) -> dict[tuple[int, int], list]:
        """{(annee, mois): [temps total, nombre de jours utilises]}"""
        res: dict[tuple[int, int], list] = {}
        for cle, j in self.app.d.jours.items():
            tot = sum(j["heures"])
            if tot < 1:
                continue
            dt = date.fromisoformat(cle)
            m = res.setdefault((dt.year, dt.month), [0.0, 0])
            m[0] += tot
            if tot >= 60:
                m[1] += 1
        return res

    def maj(self) -> None:
        app, th = self.app, self.app.th
        jours = app.d.jours
        etat = "actif" if app.compteur.actif else "pause"
        couleur, couleur_legere = th[f"barre_{etat}"], th[f"passee_{etat}"]
        if etat != getattr(self, "_etat_style", None):
            self._etat_style = etat
            ttk.Style(self.f).map("Treeview", background=[("selected", couleur)],
                                  foreground=[("selected", "#ffffff")])
        auj = date.today()
        courant = (auj.year, auj.month)
        par_mois = self._par_mois()
        premier = min([courant, *par_mois])
        dernier = max([courant, *par_mois])
        self.bornes = (premier, dernier)
        self.mois = min(max(self.mois, premier), dernier)
        sel = self.mois
        a, m = sel

        # Resume global
        totaux = [sum(j["heures"]) for j in jours.values() if sum(j["heures"]) >= 1]
        if totaux:
            n = len(totaux)
            self.lbl_resume.config(text=t("resume", jours=pluriel(n, "jours_enregistres"),
                                          m=duree(sum(totaux) / n), t=duree(sum(totaux))))
        else:
            self.lbl_resume.config(text=t("aucune_donnee"))

        # 12 mois : se termine au mois courant, ou suit le mois choisi s'il est hors de la fenetre
        debut = mois_decale(*courant, -11)
        if sel < debut:
            debut = sel
        elif sel > courant:
            debut = mois_decale(*sel, -11)
        self.mois_affiches = [mois_decale(*debut, k) for k in range(12)]
        barres_m, valeurs_m = [], []
        for i, am in enumerate(self.mois_affiches):
            tot, nb = par_mois.get(am, (0.0, 0))
            valeurs_m.append(tot)
            choisi = am == sel
            bulle = mois_annee(*am) + t("deux_points") + duree(tot)
            if nb:
                bulle += t("bulle_mois_detail", jours=pluriel(nb, "nb_jours"), m=duree_courte(tot / nb))
            etiquette = None
            if choisi and tot >= 60:
                etiquette = t("grad_h", n=int(tot // 3600)) if tot >= 3600 else duree_courte(tot)
            # en arabe, les noms de mois sont longs : un sur deux (et le mois choisi)
            axe = t("mois_courts")[am[1] - 1] if (not rtl() or choisi or i % 2 == 1) else ""
            barres_m.append(Barre(tot, axe, bulle,
                                  couleur if choisi else couleur_legere, fort=choisi, etiquette=etiquette))
        self.g_mois.maj(barres_m, *echelle_heures(max(valeurs_m), 3))

        # Navigation
        self.lbl_mois.config(text=mois_annee(a, m))
        self.b_prec.activer(sel > premier)
        self.b_suiv.activer(sel < dernier)

        # Mois choisi, jour par jour
        nb_jours = calendar.monthrange(a, m)[1]
        jour_auj = auj.day if sel == courant else None
        barres_j, valeurs_j, lignes = [], [], []
        for jour in range(1, nb_jours + 1):
            dt = date(a, m, jour)
            j = jours.get(dt.isoformat())
            v = sum(j["heures"]) if j else 0.0
            valeurs_j.append(v)
            if jour_auj and abs(jour - jour_auj) == 1:
                axe = ""  # laisse la place au numero d'aujourd'hui
            elif jour == jour_auj or jour == 1 or jour % 5 == 0:
                axe = nombre(jour)
            else:
                axe = ""
            bulle = date_longue(dt, True) + t("deux_points") + duree(v)
            if j and v >= 60 and j.get("premiere") and j.get("derniere"):
                bulle += nombre(f" ({j['premiere']} – {j['derniere']})")
            barres_j.append(Barre(v, axe, bulle, couleur, fort=(jour == jour_auj)))
            if v >= 1:
                lignes.append((dt.isoformat(), (nombre(dt.strftime(t("date_tableau"))), majuscule(nom_jour(dt)),
                                                duree(v), nombre((j or {}).get("premiere") or "–"),
                                                nombre((j or {}).get("derniere") or "–"))))
        self.g_jours.maj(barres_j, *echelle_heures(max(valeurs_j)))

        tot, nb = par_mois.get(sel, (0.0, 0))
        if tot >= 60 and nb:
            i_max = max(range(nb_jours), key=lambda k: valeurs_j[k])
            d_max = date(a, m, i_max + 1)
            ligne1 = t("detail1", t=duree(tot), jours=pluriel(nb, "jours_utilises"), m=duree_courte(tot / nb))
            ligne2 = t("detail2", date=date_longue(d_max), d=duree(valeurs_j[i_max]))
            detail = insecables(ligne1) + "\n" + insecables(ligne2)
        else:
            detail = t("aucune_donnee_mois")
        self.lbl_detail.config(text=detail)

        # Tableau du mois (reconstruit seulement s'il a change)
        sig = (sel, tuple(lignes))
        if sig != self._sig_table:
            self._sig_table = sig
            choix = self.arbre.selection()
            self.arbre.delete(*self.arbre.get_children())
            for iid, valeurs in lignes:
                self.arbre.insert("", "end", iid=iid, values=valeurs)
            garde = [i for i in choix if self.arbre.exists(i)]
            if garde:
                self.arbre.selection_set(garde)

    # ---- actions ------------------------------------------------------------
    def changer(self, delta: int) -> None:
        nouveau = mois_decale(*self.mois, delta)
        if self.bornes[0] <= nouveau <= self.bornes[1]:
            self.mois = nouveau
            self.maj()

    def _clic_mois(self, i: int) -> None:
        if i < len(self.mois_affiches):
            self.mois = self.mois_affiches[i]
            self.maj()

    def _clic_jour(self, i: int) -> None:
        iid = date(self.mois[0], self.mois[1], i + 1).isoformat()
        if self.arbre.exists(iid):
            self.arbre.selection_set(iid)
            enfants = self.arbre.get_children()
            self.arbre.yview_moveto(max(0, enfants.index(iid) - 2) / max(1, len(enfants)))
            self.arbre.see(iid)

    def _exporter(self) -> None:
        jours = [(k, v) for k, v in self.app.d.jours.items() if sum(v["heures"]) >= 1]
        self.app._exporter(self.f, jours)

    def _ferme(self, e) -> None:
        if e.widget is self.f and self.app.historique is self:
            self.app.historique = None


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
