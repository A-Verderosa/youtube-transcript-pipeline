#!/usr/bin/env bash
# setup_verify.sh — Vérifie tous les prérequis pour le pipeline YouTube→Notion→Obsidian
# Usage: bash setup_verify.sh

set -euo pipefail

PASS=0
FAIL=0

check() {
    local desc="$1"
    local result="$2"
    if [ "$result" = "ok" ]; then
        echo "  ✅ $desc"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $desc — $result"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "══════════════════════════════════════════════════"
echo "  YouTube Transcript Pipeline — Prérequis Check"
echo "══════════════════════════════════════════════════"
echo ""

# 1. Python
echo "── 1. Python ──────────────────────────────────────"
PYTHON=$(which python3 2>/dev/null || echo "")
if [ -n "$PYTHON" ]; then
    PV=$(python3 --version 2>&1)
    check "Python 3 trouvé ($PV)" "ok"
else
    check "Python 3" "ABSENT — Installer via: brew install python"
fi

# 2. Virtual environment
echo ""
echo "── 2. Environnement virtuel ───────────────────────"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    VENV_PY="$SCRIPT_DIR/venv/bin/python3"
    VENV_VER=$($VENV_PY --version 2>&1)
    check "venv trouvé dans $SCRIPT_DIR/venv ($VENV_VER)" "ok"
else
    check "venv (python3 -m venv venv)" "À CRÉER — cd \"$SCRIPT_DIR\" && python3 -m venv venv"
fi

# 3. yt-dlp
echo ""
echo "── 3. yt-dlp ──────────────────────────────────────"
if [ -f "$SCRIPT_DIR/venv/bin/yt-dlp" ]; then
    YT_VER=$($SCRIPT_DIR/venv/bin/yt-dlp --version 2>&1)
    check "yt-dlp installé dans venv ($YT_VER)" "ok"
else
    if command -v yt-dlp &>/dev/null; then
        YT_VER=$(yt-dlp --version 2>&1)
        PY_YT=$(which yt-dlp)
        check "yt-dlp installé système ($YT_VER at $PY_YT)" "ok"
    else
        VENV_PY="${VENV_PY:-python3}"
        check "yt-dlp" "À INSTALLER — \"$VENV_PY\" -m pip install yt-dlp"
    fi
fi

# 4. Node.js
echo ""
echo "── 4. Node.js ─────────────────────────────────────"
NODE=$(which node 2>/dev/null || echo "")
if [ -n "$NODE" ]; then
    NV=$(node --version 2>&1)
    check "Node.js trouvé ($NV at $NODE)" "ok"
    echo "     → Utilise --node-path $NODE dans la commande"
else
    check "Node.js" "ABSENT — Installer via: brew install node"
fi

# 5. bgutil POT provider
echo ""
echo "── 5. bgutil POT provider ─────────────────────────"
BGUTIL_BUILD="$SCRIPT_DIR/bgutil-ytdlp-pot-provider/server/build/generate_once.js"
if [ -f "$BGUTIL_BUILD" ]; then
    check "bgutil build trouvé ($BGUTIL_BUILD)" "ok"
else
    # Check alternative location (symlink at ~/)
    HOME_ALT="$HOME/bgutil-ytdlp-pot-provider/server/build/generate_once.js"
    if [ -f "$HOME_ALT" ]; then
        check "bgutil build trouvé via symlink ($HOME_ALT)" "ok"
    else
        check "bgutil POT provider" "À INSTALLER — voir le guide"
    fi
fi

# 6. Cookies file
echo ""
echo "── 6. Cookies YouTube ─────────────────────────────"
COOKIES="$SCRIPT_DIR/cookies.txt"
if [ -f "$COOKIES" ]; then
    HAS_LOGIN=$(grep -c LOGIN_INFO "$COOKIES" 2>/dev/null || echo 0)
    if [ "$HAS_LOGIN" -gt 0 ]; then
        check "cookies.txt trouvé avec LOGIN_INFO" "ok"
    else
        check "cookies.txt" "TROUVÉ mais LOGIN_INFO manquant — réexporte avec l'extension 'Get cookies.txt LOCALLY'"
    fi
else
    check "cookies.txt" "MANQUANT — exporte depuis Chrome dans $COOKIES"
fi

# 7. Notion API key
echo ""
echo "── 7. Notion API Key ──────────────────────────────"
if [ -n "${NOTION_API_KEY:-}" ]; then
    KEY_LEN=${#NOTION_API_KEY}
    check "NOTION_API_KEY définie ($KEY_LEN caractères)" "ok"
else
    check "NOTION_API_KEY" "MANQUANTE — exporte ta clé: export NOTION_API_KEY=\"ntn_...\""
fi

# 8. Obsidian vault (if configured)
echo ""
echo "── 8. Obsidian vault ──────────────────────────────"
if [ -n "${OBSIDIAN_VAULT:-}" ]; then
    if [ -d "$OBSIDIAN_VAULT" ]; then
        check "OBSIDIAN_VAULT=$OBSIDIAN_VAULT existe" "ok"
    else
        check "OBSIDIAN_VAULT=$OBSIDIAN_VAULT" "RÉPERTOIRE INTROUVABLE"
    fi
else
    echo "     (optionnel — définit OBSIDIAN_VAULT ou passe --obsidian-vault)"
fi

# 9. Hermes Desktop (Obsidian skill)
echo ""
echo "── 9. Hermes Desktop + Obsidian ───────────────────"
if [ -d "$HOME/Library/Application Support/Hermes" ]; then
    check "Hermes Desktop config trouvé" "ok"
else
    echo "     (vérifie que Hermes Desktop est installé)"
fi
if command -v hermes &>/dev/null; then
    check "Hermes CLI trouvé" "ok"
else
    echo "     (hermes CLI non trouvé dans PATH)"
fi

# Summary
echo ""
echo "══════════════════════════════════════════════════"
echo "  Résultat: $PASS ok, $FAIL échecs"
echo "══════════════════════════════════════════════════"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "🛠️  Résous les échecs ci-dessus, puis relance ce script."
    exit 1
else
    echo "🎉 Tous les prérequis sont satisfaits ! Tu peux lancer :"
    echo ""
    echo "    cd \"$SCRIPT_DIR\""
    echo "    source venv/bin/activate"
    echo "    python3 cron_youtube_to_facebook.py --process-today --obsidian-vault \"\$OBSIDIAN_VAULT\""
    echo ""
    exit 0
fi
