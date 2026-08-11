# YouTube Transcript Pipeline

Pipeline automatisé de transcription YouTube → Notion. Utilisé par Hermes Agent (Nous Research) pour alimenter une base Notion en transcriptions vidéo.

## Prérequis

- Python 3.13+
- yt-dlp 2026.07.04+
- Node.js 22+ (pour la génération POT bgutil)

## Installation

```bash
# Installer yt-dlp
pip install yt-dlp

# Installer le bgutil POT provider
git clone https://github.com/BiologicalRecord/bgutil-ytdlp-pot-provider.git
cd bgutil-ytdlp-pot-provider/server
npm install
npm run build
```

## Configuration

### Cookies YouTube

1. Installe une extension d'export cookies avec support HTTP-only :
   - Chrome : [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Va sur youtube.com, connecté à ton compte
3. Exporte les cookies → `~/Downloads/cookies.txt`

> ⚠️ **Important :** Le cookie `LOGIN_INFO` doit être présent. Sans lui, YouTube refuse l'authentification.
> ⚠️ Les cookies sont rotés par YouTube si l'IP change — exécute le script depuis la même IP que le navigateur.

## Utilisation

```bash
# 1. Clone
git clone https://github.com/A-Verderosa/youtube-transcript-pipeline.git /Users/wafer/Hermes_youtube
cd /Users/wafer/Hermes_youtube

# 2. Copie les cookies (optionnel, sinon utilise --cookies)
cp ~/Downloads/cookies.txt ./cookies.txt

# 3. Test : transcrit Rick Astley
python3 cron_youtube_to_facebook.py --fetch-transcript dQw4w9WgXcQ

# 4. Avec Node.js personnalisé
python3 cron_youtube_to_facebook.py --fetch-transcript dQw4w9WgXcQ --node-path /usr/local/bin/node

# 5. Batch Notion complet
export NOTION_API_KEY="nttn_..."
python3 cron_youtube_to_facebook.py
```

## Structure

```
├── cron_youtube_to_facebook.py   # Pipeline principal
├── requirements.txt              # Dépendances Python
└── README.md                     # Ce fichier
```

## Fonctionnement

1. **Stratégie 1 :** Client Android (pas de cookies) — fonctionne pour les vidéos ne nécessitant pas d'auth
2. **Stratégie 2 :** Cookies + Node.js POT — fonctionne avec des cookies valides depuis la même IP
3. Les transcriptions sont poussées vers Notion via l'API Notion

## Dépannage

- **"Sign in to confirm you're not a bot"** → Les cookies sont rotés, ré-exporter depuis le navigateur
- **"Failed to generate integrity token"** → Vérifier que Node.js est installé et que le bgutil provider est à jour
- **Aucune transcription** → La vidéo peut être image-only (pas de piste audio)
