# YouTube Transcript Pipeline

Pipeline automatisé de transcription YouTube → Notion + Obsidian.
Zéro IA, zéro LLM. Juste Python + yt-dlp + Node.js.

## Architecture

```
┌───────────────────────────────────────────────────┐
│  cron ou launchd (tous les jours à 9h)            │
│                                                     │
│  cron_youtube_to_facebook.py --process-today        │
│       │                                             │
│       ├─ 1. Interroge la base Notion "YouTube notes"│
│       │    (vidéos créées aujourd'hui)              │
│       ├─ 2. Pour chaque vidéo :                     │
│       │    ├─ Télécharge la transcription (yt-dlp)  │
│       │    ├─ Écrit dans le corps de la page Notion │
│       │    └─ Écrit dans le vault Obsidian          │
│       └─ 3. Résumé JSON en sortie                   │
└───────────────────────────────────────────────────┘
```

---

## Guide d'installation complet (MacBook Pro M3)

### 📦 Prérequis système

Avant de commencer, vérifie que ton Mac a :

```bash
# 1. Python 3 (déjà présent sur macOS)
python3 --version

# 2. Node.js (nécessaire pour le POT provider YouTube)
brew install node
```

---

### 🚀 Installation pas à pas

#### Étape 1 : Cloner le dépôt

```bash
git clone https://github.com/A-Verderosa/youtube-transcript-pipeline.git /Users/wafer/Hermes_youtube
cd /Users/wafer/Hermes_youtube
```

#### Étape 2 : Créer l'environnement virtuel Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install yt-dlp
```

> 💡 Après `source venv/bin/activate`, ton invite affiche `(venv)` — c'est normal.

#### Étape 3 : Installer le bgutil POT provider

Le POT provider permet à yt-dlp de contourner les protections YouTube.

```bash
cd /Users/wafer/Hermes_youtube

# Télécharge la release officielle (pas de compilation TypeScript nécessaire)
curl -L -o bgutil.zip \
  https://github.com/Brainicism/bgutil-ytdlp-pot-provider/releases/download/1.3.1/bgutil-ytdlp-pot-provider.zip

unzip bgutil.zip   # Extrait le dossier yt_dlp_plugins/ + le serveur
rm bgutil.zip

# Symlink pour que yt-dlp trouve le POT provider
ln -s /Users/wafer/Hermes_youtube/bgutil-ytdlp-pot-provider /Users/wafer/
```

> ⚠️ Le symlink est nécessaire car le plugin yt-dlp cherche le dossier par défaut dans `~/bgutil-ytdlp-pot-provider/`.

#### Étape 4 : Exporter les cookies YouTube

1. Installe l'extension Chrome **"Get cookies.txt LOCALLY"** : [Lien Chrome Web Store](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Va sur [youtube.com](https://www.youtube.com) et **connecte-toi** à ton compte
3. Clique sur l'icône de l'extension → **"Export all cookies"** (pas seulement YouTube)
4. Copie le fichier dans le projet :

```bash
cp ~/Downloads/cookies.txt /Users/wafer/Hermes_youtube/cookies.txt
```

#### Étape 5 : Configurer la clé API Notion

```bash
export NOTION_API_KEY="ntn_votre_clé_ici"
```

> Pour la rendre permanente, ajoute cette ligne dans `~/.zshrc` :
> ```bash
> echo 'export NOTION_API_KEY="ntn_votre_clé_ici"' >> ~/.zshrc
> ```

#### Étape 6 : Vérifier l'installation

```bash
cd /Users/wafer/Hermes_youtube
bash setup_verify.sh
```

Le script vérifie : Python, venv, yt-dlp, Node.js, bgutil POT, cookies, Notion API key.

---

### 🧪 Test rapide

```bash
cd /Users/wafer/Hermes_youtube
source venv/bin/activate

# Test avec Rick Astley (vidéo qui ne nécessite pas d'auth)
python3 cron_youtube_to_facebook.py --fetch-transcript dQw4w9WgXcQ

# Test avec Despacito (nécessite auth + cookies + POT)
python3 cron_youtube_to_facebook.py --fetch-transcript kJQP7kiw5Fk
```

Résultat attendu pour Rick Astley :
```json
{"success": true, "video_id": "dQw4w9WgXcQ", "language": "en", "text": "...", "length": 1446}
```

---

### 🔄 Exécution complète (Notion + Obsidian)

```bash
cd /Users/wafer/Hermes_youtube
source venv/bin/activate

export NOTION_API_KEY="ntn_votre_clé_ici"

python3 cron_youtube_to_facebook.py \
  --process-today \
  --max-videos 5 \
  --node-path /Users/wafer/.local/bin/node \
  --obsidian-vault "/Users/wafer/Obsidian/VotreVault"
```

> ⚙️ Pour connaître ton chemin Node : `which node`

---

### ⏰ Automatisation quotidienne (launchd)

Sur macOS, on utilise `launchd` au lieu de cron.

#### 1. Créer le dossier de logs

```bash
mkdir -p /Users/wafer/Hermes_youtube/logs
```

#### 2. Copier et configurer le plist

```bash
cp /Users/wafer/Hermes_youtube/com.wafer.youtube-transcript-pipeline.plist ~/Library/LaunchAgents/
```

Édite le fichier pour :
- Mettre ta vraie clé Notion API dans `<key>NOTION_API_KEY</key>`
- Mettre ton vrai chemin Obsidian vault

```bash
nano ~/Library/LaunchAgents/com.wafer.youtube-transcript-pipeline.plist
```

#### 3. Charger le service

```bash
launchctl load ~/Library/LaunchAgents/com.wafer.youtube-transcript-pipeline.plist
```

Le script tournera **tous les jours à 9h00** automatiquement.

#### 4. Tester immédiatement

```bash
launchctl start com.wafer.youtube-transcript-pipeline
```

Voir les logs :

```bash
cat /Users/wafer/Hermes_youtube/logs/cron.log
cat /Users/wafer/Hermes_youtube/logs/cron-error.log
```

#### 5. Désactiver le cron (si besoin)

```bash
launchctl unload ~/Library/LaunchAgents/com.wafer.youtube-transcript-pipeline.plist
```

---

### 📁 Structure des fichiers Obsidian

Les transcriptions sont écrites dans :
```
/Users/wafer/Obsidian/VotreVault/
└── YouTube Transcripts/
    ├── Luis Fonsi - Despacito ft. Daddy Yankee.md
    ├── Rick Astley - Never Gonna Give You Up.md
    └── ...
```

Chaque note contient : métadonnées YAML (date, vidéo ID, langue, chaîne, URL) + transcription complète.

---

### 📋 Lignes de commande (référence)

| Commande | Description |
|----------|-------------|
| `--fetch-transcript VIDEO_ID` | Télécharge la transcription d'une vidéo |
| `--process-today` | Pipeline complet : Notion → transcript → Notion + Obsidian |
| `--max-videos N` | Limite le nombre de vidéos traitées |
| `--cookies PATH` | Chemin vers le fichier cookies (défaut: ./cookies.txt) |
| `--node-path PATH` | Chemin vers Node.js (défaut: node, utilise le PATH) |
| `--obsidian-vault PATH` | Chemin du vault Obsidian pour écrire les transcriptions |
| `--write-body PAGE_ID TITLE CHANNEL URL THUMBNAIL` | Écrire les métadonnées dans une page Notion |
| `--create-transcript-child PARENT_ID TEXT LANG TITLE` | Créer une sous-page avec transcription |

---

### 🔧 Dépannage

| Problème | Cause | Solution |
|----------|-------|----------|
| `Authentication required` | Cookies périmés ou IP bloquée | Réexporte les cookies frais depuis Chrome |
| `yt-dlp is not installed` | Pas dans le venv | `source venv/bin/activate` puis `pip install yt-dlp` |
| `No JS runtime` | Node.js non trouvé | Passe `--node-path $(which node)` |
| `Script path doesn't exist` | bgutil non installé | Vérifie le symlink : `ls -la ~/bgutil-ytdlp-pot-provider` |
| `NOTION_API_KEY not set` | Clé manquante | `export NOTION_API_KEY="ntn_..."` |

---

### 📝 Logs

Les logs du cron sont dans `/Users/wafer/Hermes_youtube/logs/` :
- `cron.log` — sortie normale
- `cron-error.log` — erreurs

Pour voir le dernier run :
```bash
tail -20 /Users/wafer/Hermes_youtube/logs/cron.log
```

### 🧹 Mise à jour

```bash
cd /Users/wafer/Hermes_youtube
git pull
source venv/bin/activate
pip install -U yt-dlp
```
