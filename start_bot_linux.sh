#!/bin/bash

# Nom du bot pour l'affichage
APP_NAME="Bot Twitch"
echo -e "\033]0;$APP_NAME\007"

# ===========================================================
# 1. VERIFICATION DU FICHIER .ENV
# ===========================================================
check_env() {
    clear
    echo "[DEBUG] Verification des fichiers..."

    if [ -f ".env" ]; then
        echo "[OK] .env trouve."
    else
        echo "==========================================================="
        echo "               PREMIERE INSTALLATION DETECTEE"
        echo "==========================================================="
        echo ""

        if [ -f ".env.example" ]; then
            echo "[SYSTEM] .env.example detecte."
            echo "[ACTION] Copie en cours..."
            cp ".env.example" ".env"
            echo ""
            echo "[!] Le fichier .env a ete cree a partir du modele."
            echo "[!] REMPLISSEZ-LE MAINTENANT, enregistrez, puis revenez ici."
        else
            echo "[!] ERREUR : .env.example est introuvable."
            echo "[ACTION] Creation d'un fichier .env vide..."
            echo "# Identifiants Twitch" > .env
            echo "TWITCH_TOKEN=oauth:" >> .env
            echo "TWITCH_NICK=" >> .env
        fi

        echo ""
        read -p "[ATTENTE] Appuyez sur Entree UNE FOIS le .env rempli..."
        check_env
    fi
}

check_env

# ===========================================================
# 1b. MISE A JOUR AUTOMATIQUE (GIT PULL)
# ===========================================================
echo "[SYSTEM] Verification des mises a jour sur GitHub..."
if [ -d ".git" ]; then
    # On force le reset pour eviter les conflits
    git reset --hard origin/main > /dev/null 2>&1
    git pull origin main
    if [ $? -eq 0 ]; then
        echo "[OK] Le bot est a jour."
    else
        echo "[!] Echec de la mise a jour automatique. On continue en local."
    fi
else
    echo "[!] Git non detecte, mise a jour auto ignoree."
fi

# ===========================================================
# 2. CREATION ET ACTIVATION DU VENV
# ===========================================================
if [ ! -d "venv" ]; then
    echo "[SYSTEM] Environnement virtuel non detecte. Creation..."
    python3 -m venv venv
fi

echo "[SYSTEM] Activation de l'environnement virtuel..."
source venv/bin/activate

# ===========================================================
# 3. MISE A JOUR DES DEPENDANCES
# ===========================================================
echo "[SYSTEM] Verification des dependances..."
python3 -m pip install --upgrade pip --quiet
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
fi

# ===========================================================
# 4. BOUCLE DE LANCEMENT DU BOT
# ===========================================================
clear
echo "==========================================================="
echo "               BOT TWITCH EST EN LIGNE (v1.4.3)"
echo "==========================================================="
echo ""
echo "[INFO] Appuyez sur CTRL+C pour arreter le bot."
echo ""

while true
do
    python3 main.py
    echo ""
    echo "[!] Le bot s'est arrete (Crash ou Erreur)."
    echo "[!] Relancement automatique dans 5 secondes..."
    sleep 5
done