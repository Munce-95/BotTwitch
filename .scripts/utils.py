# utils.py - v1.0 | Fonctions utilitaires & Dispatcher
import re

def identify_sr_type(user_input):
    """
    Analyse l'entrée utilisateur pour déterminer la source.
    Retourne : (source_type, data)
    """
    user_input = user_input.strip()

    # 1. TEST SPOTIFY (Supporte les liens classiques et les liens internationaux /intl-fr/)
    sp_regex = r"open\.spotify\.com\/(?:intl-[a-z]{2}\/)?track\/([a-zA-Z0-9]{22})"
    sp_match = re.search(sp_regex, user_input)
    if sp_match:
        return "SPOTIFY_LINK", sp_match.group(1)

    # 2. TEST YOUTUBE (Plus strict pour éviter de capturer des IDs Spotify)
    # On vérifie que ce n'est PAS un lien spotify avant de valider youtube
    if "spotify.com" not in user_input:
        yt_regex = r"(?:v=|\/|embed\/|shorts\/|youtu\.be\/)([0-9A-Za-z_-]{11})"
        yt_match = re.search(yt_regex, user_input)
        if yt_match:
            return "YOUTUBE_LINK", yt_match.group(1)

    # 3. PAR DÉFAUT : RECHERCHE TEXTE
    return "TEXT_QUERY", user_input

def clean_string(text):
    """Nettoie une chaîne pour comparaison (minuscules, sans caractères spéciaux)."""
    if not text: return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def format_ms(ms):
    """Convertit des millisecondes en format MM:SS."""
    if not ms: return "0:00"
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000 * 60)) % 60)
    return f"{minutes}:{seconds:02d}"