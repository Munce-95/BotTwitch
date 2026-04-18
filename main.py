import spotipy # type: ignore
from spotipy.oauth2 import SpotifyOAuth # type: ignore
import os, sys, time, importlib
from datetime import datetime
from dotenv import load_dotenv # type: ignore

# --- CHARGEMENT DES CONFIGURATIONS ---
load_dotenv()

TWITCH_TOKEN = os.getenv("TWITCH_TOKEN")
TWITCH_NICK = os.getenv("TWITCH_NICK")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
ARCHIVE_ID = os.getenv("ARCHIVE_ID")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-modify-public playlist-modify-private user-read-currently-playing user-modify-playback-state user-read-playback-state"

admins_raw = os.getenv("ADMINS", "")
ADMINS = [a.strip() for a in admins_raw.split(",") if a]
LIMIT_USER = int(os.getenv("LIMIT_USER", 5))
LIMIT_MODO = int(os.getenv("LIMIT_MODO", 10))

sys.path.append(os.path.join(os.path.dirname(__file__), '.scripts'))

# Imports des modules (on importe les fichiers pour pouvoir utiliser importlib.reload)
try:
    from bot_core import TwitchBase # type: ignore
    import shield  # type: ignore
    import music # type: ignore
    import commands # type: ignore
except ImportError as e:
    print(f"❌ Erreur d'importation : {e}")
    sys.exit(1)

# INITIALISATION SPOTIFY
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID, 
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI, 
    scope=SCOPE, 
    open_browser=True
))

class TwitchBot(TwitchBase):
    def __init__(self):
        super().__init__()
        self.init_modules()

    def init_modules(self):
        """Initialise ou ré-initialise les composants du bot"""
        self.shield = shield.ChatShield(db_path=".data/ad_bot_suspicion.txt", viewers_path=".data/viewer.txt")
        self.music = music.MusicManager(sp, PLAYLIST_ID, ARCHIVE_ID, ADMINS, LIMIT_USER, LIMIT_MODO)

    def get_timestamp(self):
        return datetime.now().strftime('%H:%M:%S')

    def reload_all(self):
        """Action pour le !reload all"""
        importlib.reload(shield)
        importlib.reload(music)
        importlib.reload(commands)
        
        # On arrête proprement l'ancien worker musique avant d'en créer un nouveau
        if hasattr(self, 'music'): self.music.stop_worker()
        
        self.init_modules()
        self.music.start_worker()
        return "Système complet (Shield, Music, Commands) rechargé !"

    def run(self):
        if not self.connect(): return
        
        self.music.start_worker()
        print(f"🚀 Bot v1.4.0 en ligne | Channel: {TWITCH_CHANNEL}")

        while True:
            try:
                resp = self.sock.recv(4096).decode('utf-8', 'ignore')
                if not resp: break
                
                if resp.startswith('PING'):
                    self.sock.send("PONG :tmi.twitch.tv\r\n".encode('utf-8'))
                    continue

                if "PRIVMSG" in resp:
                    user, message, tags = self.parse_irc(resp)
                    if user == TWITCH_NICK.lower(): continue
                    
                    l_msg = message.lower()
                    is_privileged = any(x in tags.get('badges', '') for x in ['broadcaster', 'moderator', 'vip']) or user in ADMINS
                    ts = self.get_timestamp()

                    # --- 1. SÉCURITÉ (Shield) ---
                    is_bad, action = self.shield.check_message(user, message, is_privileged)
                    if is_bad:
                        if action == "ACTION_BAN_PERMANENT":
                            print(f"[{ts}] 🚫 SHIELD : BAN définitif -> {user}")
                            self.ban_user(user)
                            self.send_msg("The Ban Hammer has hit another target!")
                        elif "SPAM" in action or "BOT" in action:
                            duration = 60 if action == "SPAM_LVL1" else 1
                            print(f"[{ts}] ⏳ SHIELD : {action} -> {user} ({duration}s)")
                            self.timeout_user(user, duration)
                            if "SPAM" in action: self.send_msg(f"Attention au spam @{user}")
                        continue 

                    # --- 2. GESTION DU RELOAD (v1.4.0) ---
                    if l_msg.startswith('!reload') and is_privileged:
                        parts = l_msg.split()
                        target = parts[1] if len(parts) > 1 else "all"

                        if target == "shield":
                            importlib.reload(shield)
                            self.shield = shield.ChatShield(db_path=".data/ad_bot_suspicion.txt", viewers_path=".data/viewer.txt")
                            self.send_msg("🛡️ Module Shield (Code + Data) rechargé !")
                        
                        elif target == "music":
                            self.music.stop_worker()
                            importlib.reload(music)
                            self.music = music.MusicManager(sp, PLAYLIST_ID, ARCHIVE_ID, ADMINS, LIMIT_USER, LIMIT_MODO)
                            self.music.start_worker()
                            self.send_msg("🎵 Module Musique (Code + Cache) rechargé !")

                        elif target == "commands":
                            importlib.reload(commands)
                            self.send_msg("⌨️ Module Commandes rechargé !")

                        elif target == "all":
                            msg = self.reload_all()
                            self.send_msg(f"🔄 {msg}")
                        continue

                    # --- 3. COMMANDES EXTERNALISÉES ---
                    if l_msg.startswith('!'):
                        # On délègue tout au fichier commands.py
                        commands.handle_command(self, user, message, l_msg, tags, is_privileged)

            except Exception as e:
                print(f"⚠️ Erreur loop : {e}")
                time.sleep(5) # Évite de boucler à l'infini sur une erreur
                continue

if __name__ == '__main__':
    TwitchBot().run()