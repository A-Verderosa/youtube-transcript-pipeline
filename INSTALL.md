# YouTube Transcript Pipeline — Guide d'installation complet A→Z

> **Machine cible :** MacBook Pro M3 (macOS)
> **Version du pipeline :** 1.0
> **Dernière mise à jour :** 12 août 2026

Ce guide installe de zéro le pipeline de transcription YouTube :  
**YouTube → Notion + Obsidian (vault OBSIDIAN/REDPILL)**  
Sans IA, sans LLM, sans token. Un simple cron quotidien.

---

## 📋 Table des matières

1. [Prérequis système](#1-prérequis-système)
2. [Cloner le dépôt](#2-cloner-le-dépôt)
3. [Environnement Python et yt-dlp](#3-environnement-python-et-yt-dlp)
4. [Node.js et bgutil POT provider](#4-nodejs-et-bgutil-pot-provider)
5. [Cookies YouTube](#5-cookies-youtube)
6. [Clé API Notion](#6-clé-api-notion)
7. [Vérification complète](#7-vérification-complète)
8. [Test rapide](#8-test-rapide)
9. [Pipeline complet (Notion + Obsidian)](#9-pipeline-complet-notion--obsidian)
10. [Cron automatique (launchd)](#10-cron-automatique-launchd)
11. [Structure Obsidian et Graph View](#11-structure-obsidian-et-graph-view)
12. [Dépannage](#12-dépannage)
13. [Mise à jour](#13-mise-à-jour)

---

## 1. Prérequis système

Vérifie que ta machine a :

```bash
# Python 3 (déjà présent sur macOS)
python3 --version
# → Python 3.14.0 ou supérieur

# Homebrew (pour installer Node.js)
brew --version
# Si absent : /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Installe Node.js :

```bash
brew install node
```

> ⚠️ **Piège évité :** Sur Mac, `pip install` système est bloqué par SIP (PEP 668).  
> On utilisera un environnement virtuel Python. Ne pas forcer avec `--break-system-packages`.

---

## 2. Cloner le dépôt

```bash
git clone https://github.com/A-Verderosa/youtube-transcript-pipeline.git /Users/wafer/Hermes_youtube
cd /Users/wafer/Hermes_youtube
```

Vérifie :

```bash
ls cron_youtube_to_facebook.py setup_verify.sh
```

---

## 3. Environnement Python et yt-dlp

```bash
# Crée l'environnement virtuel (une seule fois)
python3 -m venv venv

# Active-le
source venv/bin/activate
```

Ton invite doit passer en `(venv) wafer@MacBook-Pro...`.  
Si tu vois `(venv)`, c'est bon.

```bash
# Installe yt-dlp DANS le venv (pas système)
pip install yt-dlp

# Vérifie
python3 -m yt_dlp --version
# → stable@2026.07.04
```

> ⚠️ **Piège évité :** `pip` sans venv → erreur *"externally-managed-environment"*.  
> Toujours faire `source venv/bin/activate` avant d'utiliser le script.

---

## 4. Node.js et bgutil POT provider

Le POT provider permet à yt-dlp de générer les tokens anti-bot YouTube.  
**Deux composants sont nécessaires :** le plugin Python ET le serveur Node.js.

### 4.1 — Télécharger le plugin yt-dlp

```bash
cd /Users/wafer/Hermes_youtube

curl -L -o bgutil.zip \
  https://github.com/Brainicism/bgutil-ytdlp-pot-provider/releases/download/1.3.1/bgutil-ytdlp-pot-provider.zip

# Extrait (cela crée un dossier yt_dlp_plugins/)
unzip -o bgutil.zip
rm bgutil.zip
```

### 4.2 — Télécharger et compiler le serveur Node.js

```bash
# Le zip ci-dessus ne contient que le plugin Python (8 Ko).
# Il faut aussi le code source du serveur :

curl -L -o bgutil-server.tar.gz \
  https://github.com/Brainicism/bgutil-ytdlp-pot-provider/archive/refs/tags/1.3.1.tar.gz

# Extrait
tar -xzf bgutil-server.tar.gz
rm bgutil-server.tar.gz

# Renomme
rm -rf bgutil-ytdlp-pot-provider  # supprime l'ancien dossier vide
mv bgutil-ytdlp-pot-provider-1.3.1 bgutil-ytdlp-pot-provider
```

### 4.3 — Compiler le TypeScript

```bash
cd bgutil-ytdlp-pot-provider/server
npm install
npx tsc

# Vérifie que le build est présent
ls build/generate_once.js
# → build/generate_once.js  ✅
```

### 4.4 — Créer le symlink

> ⚠️ **Piège critique :** Le plugin yt-dlp cherche le serveur POT par défaut dans  
> `~/bgutil-ytdlp-pot-provider/server/` (dans le HOME, PAS dans Hermes_youtube).  
> Il faut créer un lien symbolique.

```bash
cd /Users/wafer/Hermes_youtube

# Supprime si déjà existant
rm -f /Users/wafer/bgutil-ytdlp-pot-provider

# Crée le symlink
ln -s /Users/wafer/Hermes_youtube/bgutil-ytdlp-pot-provider /Users/wafer/

# Vérifie
ls -la /Users/wafer/bgutil-ytdlp-pot-provider
# → lrwxr-xr-x ... -> /Users/wafer/Hermes_youtube/bgutil-ytdlp-pot-provider
```

---

## 5. Cookies YouTube

### 5.1 — Exporter les cookies

1. Installe l'extension Chrome **"Get cookies.txt LOCALLY"**  
   https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc

2. Va sur **youtube.com** et connecte-toi à ton compte Google.

3. Clique sur l'icône de l'extension → **"Export"**  
   → **Ne filtre pas par domaine** — exporte **tous les cookies** (pas seulement YouTube).

> ⚠️ **Piège critique :** Le cookie HTTP-only `LOGIN_INFO` est indispensable.  
> Si tu exportes seulement les cookies YouTube, `LOGIN_INFO` ne sera PAS exporté.  
> Il faut exporter **tous les cookies** du navigateur.

Le fichier est sauvegardé dans `~/Downloads/cookies.txt`.

### 5.2 — Copier dans le projet

```bash
cp ~/Downloads/cookies.txt /Users/wafer/Hermes_youtube/cookies.txt
```

### 5.3 — Vérifier LOGIN_INFO

```bash
grep LOGIN_INFO /Users/wafer/Hermes_youtube/cookies.txt
```

Tu dois voir une ligne contenant `LOGIN_INFO` suivie d'une longue chaîne de caractères.  
Si tu ne vois rien, réexporte avec l'extension en exportant **tous les cookies** (pas YouTube seulement).

---

## 6. Clé API Notion

### 6.1 — Obtenir la clé

Va sur https://www.notion.so/my-integrations → crée une intégration → copie la clé `ntn_...`.

### 6.2 — Définir dans l'environnement

```bash
export NOTION_API_KEY="ntn_votre_clé_ici"
```

### 6.3 — Rendre permanente (optionnel mais recommandé)

```bash
echo 'export NOTION_API_KEY="ntn_votre_clé_ici"' >> ~/.zshrc
```

---

## 7. Vérification complète

```bash
cd /Users/wafer/Hermes_youtube
bash setup_verify.sh
```

Résultat attendu (9/9) :

```
── 1. Python ────────────── ✅ Python 3 trouvé (Python 3.14.0)
── 2. venv ──────────────── ✅ venv trouvé dans /Users/wafer/Hermes_youtube/venv
── 3. yt-dlp ────────────── ✅ yt-dlp installé dans venv (2026.07.04)
── 4. Node.js ───────────── ✅ Node.js trouvé (v22.22.3 at /Users/wafer/.local/bin/node)
── 5. bgutil POT ────────── ✅ bgutil build trouvé
── 6. Cookies ───────────── ✅ cookies.txt trouvé avec LOGIN_INFO
── 7. Notion API ────────── ✅ NOTION_API_KEY définie
── 8. Obsidian vault ────── (optionnel)
── 9. Hermes Desktop ────── ✅ Hermes Desktop config trouvé

Résultat: 9 ok, 0 échecs  🎉
```

Si un test est rouge, résous-le avant de continuer.

---

## 8. Test rapide

### 8.1 — Toujours activer le venv d'abord

```bash
cd /Users/wafer/Hermes_youtube
source venv/bin/activate
```

Tu dois voir `(venv)` dans ton invite.

### 8.2 — Tester avec Rick Astley (vidéo sans auth)

```bash
python3 cron_youtube_to_facebook.py \
  --fetch-transcript dQw4w9WgXcQ \
  --node-path /Users/wafer/.local/bin/node
```

Résultat attendu :

```json
{"success": true, "video_id": "dQw4w9WgXcQ", "language": "en", "text": "...", "length": 1446}
```

### 8.3 — Tester avec Despacito (vidéo avec auth + POT)

```bash
python3 cron_youtube_to_facebook.py \
  --fetch-transcript kJQP7kiw5Fk \
  --node-path /Users/wafer/.local/bin/node
```

Résultat attendu :

```json
{"success": true, "video_id": "kJQP7kiw5Fk", "language": "en", "text": "...", "length": ...}
```

> ⚠️ **Piège évité :** Sur le VPS, cette vidéo échouait car l'IP cloud était bloquée.  
> Depuis ton MacBook (IP domestique), ça fonctionne — même raison que de regarder la vidéo dans ton navigateur.

---

## 9. Pipeline complet (Notion + Obsidian)

```bash
cd /Users/wafer/Hermes_youtube
source venv/bin/activate

python3 cron_youtube_to_facebook.py \
  --process-today \
  --max-videos 5 \
  --node-path /Users/wafer/.local/bin/node \
  --obsidian-vault "/Users/wafer/Documents/Obsidian/OBSIDIAN/REDPILL"
```

Le script va :
1. Interroger la base Notion "YouTube notes"
2. Trouver les vidéos créées aujourd'hui sans transcription
3. Télécharger chaque transcription
4. L'écrire dans le corps de la page Notion
5. L'écrire dans le vault Obsidian OBSIDIAN/REDPILL

Vérifie dans Obsidian :
- Ouvre le vault **OBSIDIAN/REDPILL**
- Dossier **YouTube Transcripts/** créé
- Fichier **YouTube Transcripts.md** (index MOC)

---

## 10. Cron automatique (launchd)

Sur macOS, on utilise `launchd` (pas `crontab`) pour les tâches planifiées.

### 10.1 — Créer le dossier de logs

```bash
mkdir -p /Users/wafer/Hermes_youtube/logs
```

### 10.2 — Copier et éditer le plist

```bash
cp /Users/wafer/Hermes_youtube/com.wafer.youtube-transcript-pipeline.plist \
   ~/Library/LaunchAgents/
```

Édite le fichier avec ta vraie clé Notion :

```bash
nano ~/Library/LaunchAgents/com.wafer.youtube-transcript-pipeline.plist
```

Remplace `ntn_votre_clé_ici` par ta vraie clé dans la balise `<key>NOTION_API_KEY</key>`.

### 10.3 — Charger le service

```bash
launchctl load ~/Library/LaunchAgents/com.wafer.youtube-transcript-pipeline.plist
```

Le script tournera **tous les jours à 9h00**.

### 10.4 — Tester immédiatement

```bash
launchctl start com.wafer.youtube-transcript-pipeline
```

Voir le résultat :

```bash
cat /Users/wafer/Hermes_youtube/logs/cron.log
```

### 10.5 — Commandes utiles

| Action | Commande |
|--------|----------|
| Démarrer | `launchctl load ~/Library/LaunchAgents/com.wafer.youtube-transcript-pipeline.plist` |
| Arrêter | `launchctl unload ~/Library/LaunchAgents/com.wafer.youtube-transcript-pipeline.plist` |
| Exécuter manuellement | `launchctl start com.wafer.youtube-transcript-pipeline` |
| Voir les logs | `tail -20 /Users/wafer/Hermes_youtube/logs/cron.log` |
| Voir les erreurs | `tail -20 /Users/wafer/Hermes_youtube/logs/cron-error.log` |

---

## 11. Structure Obsidian et Graph View

### 11.1 — Fichiers créés

```
/Users/wafer/Documents/Obsidian/OBSIDIAN/REDPILL/
└── YouTube Transcripts/
    ├── YouTube Transcripts.md          ← MOC (Map of Content) — index
    ├── Luis Fonsi - Despacito ft. Daddy Yankee.md
    ├── Rick Astley - Never Gonna Give You Up.md
    └── ...
```

### 11.2 — Contenu d'une note

Chaque note contient :

```yaml
---
title: "Luis Fonsi - Despacito ft. Daddy Yankee"
created: 2026-08-12
source: YouTube
video_id: kJQP7kiw5Fk
language: en
channel: "LuisFonsiVEVO"
url: "https://www.youtube.com/watch?v=kJQP7kiw5Fk"
tags:
  - youtube/transcript
  - youtube/en
aliases:
  - "Luis Fonsi - Despacito ft. Daddy Yankee"
---
```

### 11.3 — Graph View

Le **Graph View** d'Obsidian relie automatiquement :

```
[Chaîne A] ←──→ [Vidéo 1] ←──→ [YouTube Transcripts]
[Chaîne A] ←──→ [Vidéo 2] ←──→ [YouTube Transcripts]
[Chaîne B] ←──→ [Vidéo 3] ←──→ [YouTube Transcripts]
```

Chaque wikilink `[[Nom de la Chaîne]]` crée un nœud dans le graph.

---

## 12. Dépannage

### 12.1 — Erreurs fréquentes et solutions

| Problème | Cause racine | Solution |
|----------|-------------|----------|
| `Authentication required` | Cookies périmés ou LOGIN_INFO manquant | Réexporte les cookies avec l'extension Chrome (tous les domaines) |
| `yt-dlp is not installed` | Tu es en dehors du venv | `source venv/bin/activate` puis réessaie |
| `No supported JavaScript runtime` | Node.js non trouvé ou mauvais chemin | Passe `--node-path $(which node)` |
| `Script path doesn't exist` | Symlink bgutil manquant ou cassé | Vérifie : `ls -la ~/bgutil-ytdlp-pot-provider` |
| `NOTION_API_KEY not set` | Clé API pas dans l'environnement | `export NOTION_API_KEY="ntn_..."` |
| `zsh: command not found: #` | Copier-coller avec commentaires `#` | Copie seulement les commandes, pas les `#` |
| `quote>` en invite | Une quote non fermée dans la commande | Ctrl+C puis recommence sans les `#` |
| `externally-managed-environment` | `pip` sans venv sur macOS | Active d'abord le venv |
| `ModuleNotFoundError: yt_dlp` | yt-dlp installé système, pas dans le venv | `pip install yt-dlp` (dans le venv) |
| `The page needs to be reloaded` | POT token manquant ou invalide | Vérifie le build bgutil et le symlink |

### 12.2 — Logs

```bash
# Voir la dernière exécution du cron
tail -20 /Users/wafer/Hermes_youtube/logs/cron.log

# Voir les erreurs
tail -20 /Users/wafer/Hermes_youtube/logs/cron-error.log

# Exécution manuelle détaillée
cd /Users/wafer/Hermes_youtube
source venv/bin/activate
python3 cron_youtube_to_facebook.py --process-today --max-videos 1
```

### 12.3 — Réexporter les cookies

Quand YouTube invalide les cookies (généralement toutes les 2-4 semaines) :

```bash
# 1. Ouvre Chrome → youtube.com
# 2. Extension Get cookies.txt LOCALLY → Export (tous les cookies)
# 3. Copie
cp ~/Downloads/cookies.txt /Users/wafer/Hermes_youtube/cookies.txt

# 4. Vérifie
grep LOGIN_INFO /Users/wafer/Hermes_youtube/cookies.txt
```

---

## 13. Mise à jour

```bash
cd /Users/wafer/Hermes_youtube
git pull
source venv/bin/activate
pip install -U yt-dlp
```

---

## Annexe A — Résumé des chemins

| Élément | Chemin |
|---------|--------|
| Projet | `/Users/wafer/Hermes_youtube` |
| Script principal | `/Users/wafer/Hermes_youtube/cron_youtube_to_facebook.py` |
| Vérification | `/Users/wafer/Hermes_youtube/setup_verify.sh` |
| Venv Python | `/Users/wafer/Hermes_youtube/venv/` |
| Cookies | `/Users/wafer/Hermes_youtube/cookies.txt` |
| bgutil plugin | `/Users/wafer/Hermes_youtube/yt_dlp_plugins/` |
| bgutil serveur | `/Users/wafer/Hermes_youtube/bgutil-ytdlp-pot-provider/` |
| Symlink bgutil | `/Users/wafer/bgutil-ytdlp-pot-provider` → `.../Hermes_youtube/...` |
| Plist launchd | `~/Library/LaunchAgents/com.wafer.youtube-transcript-pipeline.plist` |
| Logs cron | `/Users/wafer/Hermes_youtube/logs/` |
| Obsidian vault | `/Users/wafer/Documents/Obsidian/OBSIDIAN/REDPILL/YouTube Transcripts/` |

## Annexe B — Commandes utiles (copier-coller sans erreurs)

```bash
# Aller dans le projet
cd /Users/wafer/Hermes_youtube

# Activer le venv
source venv/bin/activate

# Vérification
bash setup_verify.sh

# Une vidéo précise
python3 cron_youtube_to_facebook.py --fetch-transcript dQw4w9WgXcQ --node-path /Users/wafer/.local/bin/node

# Pipeline complet aujourd'hui
python3 cron_youtube_to_facebook.py --process-today --max-videos 5 --node-path /Users/wafer/.local/bin/node --obsidian-vault "/Users/wafer/Documents/Obsidian/OBSIDIAN/REDPILL"

# Logs
tail -20 /Users/wafer/Hermes_youtube/logs/cron.log
```
