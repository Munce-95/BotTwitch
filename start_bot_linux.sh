#!/bin/bash

# --- CONFIGURATION ---
TITLE="Bot Twitch"
# Définit le titre du terminal (si supporté)
echo -ne "\033]0;$TITLE\007"

# --- 1. VERIFICATION DU FICHIER .ENV ---
check_env() {
    if [ ! -f .env ]; then
        clear
        echo "==========================================================="
        echo "             PREMIERE INSTALLATION DETECTEE"
        echo "==========================================================="
        echo ""
        echo "  [!] Le fichier de configuration .env est manquant."
        echo ""
        echo "  1. Remplissez les identifiants dans le fichier .env"
        echo "  2. Utilisez le modele .env.example pour vous guider"
        echo "  3. Enregistrez et revenez ici"
        echo ""
        echo "==========================================================="
        echo ""
        
        if [ -f .env.example ]; then
            read -p "[SYSTEM] .env.example trouve. Le copier en .env ? (O/N) : " choice
            if [[ "$choice" =~ ^[Oo]$ ]]; then
                cp .env.example .env
                echo "[OK] Fichier .env cree. Allez le remplir maintenant."
            fi
        else
            echo "[!] .env.example introuvable. Veuillez creer votre .env manuellement."
        fi

        echo ""
        echo "[!] Appuyez sur ENTREE une fois que le .env est rempli."
        read -r
        check_env
    fi
}

check_env
echo "[OK] Fichier .env detecte."

# --- 2. CREATION ET ACTIVATION DU VENV ---
if [ ! -d "venv" ]; then
    echo "[SYSTEM] Environnement virtuel non detecte. Creation..."
    # Sur Linux, on utilise généralement python3
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERREUR] Impossible de creer le venv. Verifiez que python3-venv est installe."
        exit 1
    fi
fi

echo "[SYSTEM] Activation de l'environnement virtuel..."
source venv/bin/activate

# --- 3. MISE A JOUR DES DEPENDANCES ---
echo "[SYSTEM] Verification des dependances..."
pip install --upgrade pip --quiet

if [ -f requirements.txt ]; then
    pip install -r requirements.txt --quiet
else
    echo "[!] requirements.txt introuvable. Installation par defaut..."
    pip install spotipy python-dotenv --quiet
fi

# --- 4. BOUCLE DE LANCEMENT DU BOT ---
clear
echo "==========================================================="
echo "              BOT TWITCH EST EN LIGNE (LINUX)"
echo "==========================================================="
echo ""
echo "[INFO] Appuyez sur CTRL+C pour arreter le bot."
echo ""

while true; do
    python3 main.py
    echo ""
    echo "[!] Le bot s'est arrete inopinement."
    echo "[!] Relancement automatique dans 5 secondes..."
    sleep 5
done
