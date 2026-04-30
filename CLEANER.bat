@echo off
title Nettoyage Environnement Virtuel
cls

echo ===========================================================
echo           NETTOYAGE DE L'ENVIRONNEMENT VIRTUEL
echo ===========================================================
echo.

:: 1. Force la fermeture de Python pour debloquer le dossier
echo [1/3] Fermeture des processus Python en cours...
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: 2. Suppression du dossier venv
if exist venv (
    echo [2/3] Suppression du dossier venv en cours...
    rmdir /s /q venv
    if exist venv (
        echo [!] ERREUR : Impossible de supprimer le dossier. 
        echo     Verifie qu'aucun programme n'utilise le dossier.
        pause
        exit
    ) else (
        echo [OK] Dossier venv supprime avec succes.
    )
) else (
    echo [2/3] Aucun dossier venv detecte. Passage a la suite.
)

:: 3. Nettoyage des caches Python (optionnel mais propre)
echo [3/3] Nettoyage des caches __pycache__...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" >nul 2>&1

echo.
echo ===========================================================
echo    NETTOYAGE TERMINE : Tu peux relancer start_bot_win.bat
echo ===========================================================
echo.
pause