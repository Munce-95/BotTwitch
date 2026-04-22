@echo off
title Bot Twitch - v1.4.4
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
    git reset --hard origin/main >nul 2>&1
    git pull origin main
    if errorlevel 1 (
        echo [!] Echec de la mise a jour automatique.
    ) else (
        echo [OK] Le bot est a jour.
    )
)

:: ===========================================================
:: 2. CREATION DU VENV SI NECESSAIRE
:: ===========================================================
if not exist venv (
    echo [SYSTEM] Environnement virtuel non detecte. Creation...
    :: On essaie 'py' puis 'python' pour la creation initiale
    py -m venv venv || python -m venv venv
    if errorlevel 1 (
        echo [!] ERREUR CRITIQUE : Python n'est pas installe sur ce systeme.
        pause
        exit
    )
)

:: ===========================================================
:: 3. MISE A JOUR DES DEPENDANCES (VIA CHEMIN DIRECT)
:: ===========================================================
echo [SYSTEM] Verification des dependances...
:: On utilise le chemin direct pour eviter l'erreur "python non reconnu"
venv\Scripts\python.exe -m pip install --upgrade pip --quiet
if exist requirements.txt (
    venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
)

:: ===========================================================
:: 4. BOUCLE DE LANCEMENT DU BOT
:: ===========================================================
cls
echo ===========================================================
echo                BOT TWITCH EST EN LIGNE (v1.4.4)
echo ===========================================================
echo.

:loop
:: L'appel direct qui sauve la mise
venv\Scripts\python.exe main.py

echo.
echo [!] Le bot s'est arrete (Crash ou Erreur).
echo [!] Relancement automatique dans 5 secondes...
timeout /t 5
goto loop