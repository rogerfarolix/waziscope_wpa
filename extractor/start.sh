#!/bin/bash
# WaziScope Extractor — démarrage rapide
cd "$(dirname "$0")"

if [ ! -f "venv/bin/activate" ]; then
    echo "Création du venv..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt
echo "✓ Extractor démarré sur http://localhost:8032"
python main.py
