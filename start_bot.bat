@echo off
title Bot Twitch

echo [SYSTEM] Verification de l'environnement...

:: 1. Crée le venv s'il n'existe pas (en utilisant py)
if not exist venv (
    echo [SYSTEM] Environnement virtuel non detecte. Creation en cours avec 'py'...
    py -m venv venv
    if errorlevel 1 (
        echo [ERREUR] 'py' n'est pas reconnu. Tentative avec 'python'...
        python -m venv venv
    )
)

:: 2. Active l'environnement virtuel
echo [SYSTEM] Activation de l'environnement virtuel...
call venv\Scripts\activate

:: 3. Installe/Met a jour les dependances
echo [SYSTEM] Verification des dependances...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

:: 4. Lancement du bot
echo [SYSTEM] Lancement du bot...
:loop
python main.py
echo.
echo [SYSTEM] Le bot s'est arrete. Relancement automatique dans 5 secondes...
timeout /t 5
goto loop
