#!/bin/bash
# WaziScope Extractor — démarrage rapide
cd "$(dirname "$0")"

if [ ! -f "venv/bin/activate" ]; then
    echo "Création du venv..."
    python3 -m venv venv
fi

source venv/bin/activate

# Réinstaller seulement si requirements.txt a changé
REQ_HASH_FILE="venv/.req_hash"
REQ_HASH="$(md5sum requirements.txt 2>/dev/null | cut -d' ' -f1)"
SAVED_HASH="$(cat "$REQ_HASH_FILE" 2>/dev/null || echo '')"

if [ "$REQ_HASH" != "$SAVED_HASH" ]; then
    echo "Mise à jour des dépendances Python..."
    pip install -q -r requirements.txt
    echo "$REQ_HASH" > "$REQ_HASH_FILE"
fi

echo "✓ Extractor démarré sur http://localhost:8032"
python main.py
