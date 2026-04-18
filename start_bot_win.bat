@echo off
title Bot Twitch
setlocal enabledelayedexpansion

:: ===========================================================
:: 1. VERIFICATION DU FICHIER .ENV
:: ===========================================================
:check_env
cls
echo [DEBUG] Verification des fichiers...

:: On teste directement l'existence sans se soucier des attributs
if exist ".env" (
    echo [OK] .env trouve.
    goto env_ok
)

:: Si on est ici, le .env n'existe pas. On cherche l'exemple.
echo ===========================================================
echo             PREMIERE INSTALLATION DETECTEE
echo ===========================================================
echo.

if exist ".env.example" (
    echo [SYSTEM] .env.example detecte.
    echo [ACTION] Copie en cours...
    copy /y ".env.example" ".env" >nul
    echo.
    echo [!] Le fichier .env a ete cree a partir du modele.
    echo [!] REMPLISSEZ-LE MAINTENANT, enregistrez, puis revenez ici.
) else (
    echo [!] ERREUR : .env.example est introuvable dans :
    echo     %cd%
    echo.
    echo [ACTION] Creation d'un fichier .env vide pour vous aider...
    echo # Identifiants Twitch > .env
    echo TWITCH_TOKEN=oauth: >> .env
    echo TWITCH_NICK= >> .env
    echo.
    echo [!] Un fichier .env vierge a ete cree. Allez le remplir.
)

echo.
echo ===========================================================
echo [ATTENTE] Appuyez sur une touche UNE FOIS le .env rempli...
pause > nul
goto check_env

:env_ok
echo [SYSTEM] Configuration prete.
:: ===========================================================
:: 2. CREATION ET ACTIVATION DU VENV
:: ===========================================================
if not exist venv (
    echo [SYSTEM] Environnement virtuel non detecte. Creation avec 'py'...
    py -m venv venv
    if errorlevel 1 (
        echo [ERREUR] 'py' a echoue. Tentative avec 'python'...
        python -m venv venv
    )
)

echo [SYSTEM] Activation de l'environnement virtuel...
call venv\Scripts\activate

:: ===========================================================
:: 3. MISE A JOUR DES DEPENDANCES
:: ===========================================================
echo [SYSTEM] Verification des dependances...
python -m pip install --upgrade pip --quiet
if exist requirements.txt (
    pip install -r requirements.txt --quiet
) else (
    echo [!] requirements.txt introuvable. Installation par defaut...
    pip install spotipy python-dotenv --quiet
)

:: ===========================================================
:: 4. BOUCLE DE LANCEMENT DU BOT
:: ===========================================================
cls
echo ===========================================================
echo              BOT TWITCH EST EN LIGNE
echo ===========================================================
echo.
echo [INFO] Fermez cette fenetre pour arreter le bot.
echo.

:loop
python main.py
echo.
echo [!] Le bot s'est arrete inopinement (Crash ou Erreur).
echo [!] Relancement automatique dans 5 secondes...
echo [!] Appuyez sur CTRL+C pour annuler.
timeout /t 5
goto loop
