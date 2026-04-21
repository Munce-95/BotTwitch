@echo off
title Bot Twitch
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
echo               PREMIERE INSTALLATION DETECTEE
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
:: On verifie si le dossier est bien un depot Git
if exist ".git" (
    :: On force le reset pour eviter les conflits si ton pote a modifie un fichier par erreur
    git reset --hard origin/main >nul 2>&1
    git pull origin main
    if errorlevel 1 (
        echo [!] Echec de la mise a jour automatique. On continue avec la version locale.
    ) else (
        echo [OK] Le bot est a jour.
    )
) else (
    echo [!] Git non detecte dans ce dossier, mise a jour auto ignoree.
)

:: ===========================================================
:: 2. CREATION ET ACTIVATION DU VENV
:: ===========================================================
if not exist venv (
    echo [SYSTEM] Environnement virtuel non detecte. Creation...
    py -m venv venv
    if errorlevel 1 python -m venv venv
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
)

:: ===========================================================
:: 4. BOUCLE DE LANCEMENT DU BOT
:: ===========================================================
cls
echo ===========================================================
echo               BOT TWITCH EST EN LIGNE (v1.4.3)
echo ===========================================================
echo.

:loop
python main.py
echo.
echo [!] Le bot s'est arrete (Crash ou Erreur).
echo [!] Relancement automatique dans 5 secondes...
timeout /t 5
goto loop
