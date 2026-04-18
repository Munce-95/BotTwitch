@echo off
:: Change le titre de la fenêtre
title Bot Twitch

echo [SYSTEM] Verification de l'environnement...

:: 1. Crée le venv s'il n'existe pas
if not exist venv (
    echo [SYSTEM] Environnement virtuel non detecte. Creation en cours...
    python -m venv venv
    echo [SYSTEM] Environnement cree avec succes.
)

:: 2. Active l'environnement virtuel
echo [SYSTEM] Activation de l'environnement virtuel...
call venv\Scripts\activate

:: 3. Installe/Met à jour les dépendances
echo [SYSTEM] Verification des dependances (spotipy, python-dotenv)...
pip install -r requirements.txt --quiet

:: 4. Lancement du bot avec boucle de redémarrage
echo [SYSTEM] Lancement du bot...
:loop
python main.py
echo.
echo [SYSTEM] Le bot s'est arrete. Relancement automatique dans 5 secondes...
timeout /t 5
goto loop
