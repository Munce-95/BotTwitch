@echo off
title Bot Twitch
setlocal enabledelayedexpansion

:: ===========================================================
:: 1. VERIFICATION DU FICHIER .ENV
:: ===========================================================
:check_env
if not exist .env (
    cls
    echo ===========================================================
    echo             PREMIERE INSTALLATION DETECTEE
    echo ===========================================================
    echo.
    echo  [!] Le fichier de configuration .env est manquant.
    echo.
    echo  1. Remplissez les identifiants dans le fichier .env
    echo  2. Utilisez le modele .env.example pour vous guider
    echo  3. Enregistrez et revenez ici
    echo.
    echo ===========================================================
    echo.
    
    if exist .env.example (
        echo [SYSTEM] .env.example trouve. Voulez-vous le copier en .env ? (O/N)
        set /p choice=^> 
        if /i "!choice!"=="O" (
            copy .env.example .env
            echo [OK] Fichier .env cree. Allez le remplir maintenant.
        )
    ) else (
        echo [!] .env.example introuvable. Veuillez creer votre .env manuellement.
    )

    echo.
    echo [!] Appuyez sur une touche UNE FOIS que le .env est rempli et enregistre.
    pause > nul
    goto check_env
)

echo [OK] Fichier .env detecte.

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
