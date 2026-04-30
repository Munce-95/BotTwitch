@echo off
title Bot Twitch - v1.5 (Supabase Ready)
setlocal enabledelayedexpansion

:: ===========================================================
:: 1. VERIFICATION DU FICHIER .ENV
:: ===========================================================
:check_env
cls
echo [DEBUG] Verification des fichiers...

if exist ".env" (
    echo [OK] .env trouve.
    goto env_ok
)

echo ===========================================================
echo                PREMIERE INSTALLATION DETECTEE
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
    echo [!] ERREUR : .env.example est introuvable.
    echo [ACTION] Creation d'un fichier .env vide...
    echo # Identifiants Twitch > .env
    echo TWITCH_TOKEN=oauth: >> .env
    echo TWITCH_NICK= >> .env
)

echo.
pause
goto check_env

:env_ok
echo [SYSTEM] Configuration prete.

:: ===========================================================
:: 1b. MISE A JOUR AUTOMATIQUE (GIT PULL)
:: ===========================================================
echo [SYSTEM] Verification des mises a jour sur GitHub...
if exist ".git" (
    git pull origin main >nul 2>&1
    if errorlevel 1 (
        echo [!] Echec de la mise a jour automatique.
    ) else (
        echo [OK] Le bot est a jour.
    )
)

:: ===========================================================
:: 2. CREATION DU VENV SI NECESSAIRE (Priorité 'py')
:: ===========================================================
if not exist venv (
    echo [SYSTEM] Environnement virtuel non detecte. Creation...
    py -m venv venv || python -m venv venv
    if errorlevel 1 (
        echo [!] ERREUR CRITIQUE : Python n'est pas installe.
        pause
        exit
    )
)

:: ===========================================================
:: 3. MISE A JOUR DES DEPENDANCES (DOUBLE INSTALLATION)
:: ===========================================================
echo [SYSTEM] Verification des dependances (Quiet mode)...
:: Chemin direct pour eviter tout conflit
set PYTHON_EXE="%~dp0venv\Scripts\python.exe"

:: Mise a jour de pip
%PYTHON_EXE% -m pip install --upgrade pip --quiet

:: Installation 1 : Le requirements complet
if exist requirements.txt (
    echo [SYSTEM] Installation via requirements.txt...
    %PYTHON_EXE% -m pip install -r requirements.txt --quiet
)

:: Installation 2 : FORCE MODE pour Spotipy (et les essentiels)
echo [SYSTEM] Securite : Installation forcee de spotipy...
%PYTHON_EXE% -m pip install spotipy twitchio python-dotenv supabase --quiet

:: ===========================================================
:: 4. BOUCLE DE LANCEMENT DU BOT
:: ===========================================================
cls
echo ===========================================================
echo                BOT TWITCH EST EN LIGNE (v1.5)
echo ===========================================================
echo.

:loop
:: Lancement via le chemin physique direct defini plus haut
%PYTHON_EXE% main.py

echo.
echo [!] Le bot s'est arrete (Crash ou Erreur).
echo [!] Relancement automatique dans 5 secondes...
timeout /t 5
goto loop