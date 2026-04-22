# type: ignore
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os, sys, time, importlib
from datetime import datetime
from dotenv import load_dotenv

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

# Ajout du dossier scripts au path
sys.path.append(os.path.join(os.path.dirname(__file__), '.scripts'))

# Imports des modules v1.4.4
try:
    from bot_core import TwitchBase
    import shield
    import music
    import commands 
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
        self.version = "v1.4.4 | Maîtrise des données"
        self.init_modules()

    def init_modules(self):
        """Initialise les composants avec les nouveaux chemins v1.4.4"""
        self.shield = shield.ChatShield(
            db_path=".data/database/ad_bot_suspicion.txt", 
            viewers_path=".data/database/viewers.json"
        )
        self.music = music.MusicManager(sp, PLAYLIST_ID, ARCHIVE_ID, ADMINS, LIMIT_USER, LIMIT_MODO)

    def get_timestamp(self):
        return datetime.now().strftime('%H:%M:%S')

    def reload_all(self):
        """Action pour le !reload all (v1.4.4)"""
        if hasattr(self, 'music'):
            self.music.running = False
        
        importlib.reload(shield)
        importlib.reload(music)
        importlib.reload(commands)
        
        self.init_modules()
        # On force le rechargement des fichiers txt de musique
        if hasattr(self.music, 'reload_filters'):
            self.music.reload_filters()
            
        self.music.start_worker()
        return f"Système complet {self.version} rechargé !"

    def run(self):
        if not self.connect(): return
        
        self.music.start_worker()
        print(f"🚀 Bot {self.version} en ligne | Channel: {TWITCH_CHANNEL}")

        while True:
            try:
                resp = self.sock.recv(4096).decode('utf-8', 'ignore')
                if not resp: break
                
                if resp.startswith('PING'):
                    self.sock.send("PONG :tmi.twitch.tv\r\n".encode('utf-8'))
                    continue

                # --- DETECTION DU /UNBAN ---
                if "NOTICE" in resp and "unbanned" in resp.lower():
                    try:
                        parts = resp.strip().split(" ")
                        target = parts[-1].replace(".", "").lower()
                        self.shield.unban_grace(target)
                        print(f"[{self.get_timestamp()}] 🛡️ SHIELD : Grâce accordée (Level 0) -> {target}")
                    except: pass
                    continue

                # --- GESTION DES MESSAGES (PRIVMSG) ---
                if "PRIVMSG" in resp:
                    user, message, tags = self.parse_irc(resp)
                    if user == TWITCH_NICK.lower(): continue
                    
                    l_msg = message.lower().strip()
                    is_privileged = any(x in tags.get('badges', '') for x in ['broadcaster', 'moderator', 'vip']) or user in ADMINS
                    ts = self.get_timestamp()

                    # --- A. SÉCURITÉ ---
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

                    # --- B. RELOAD ---
                    if l_msg.startswith('!reload') and is_privileged:
                        parts = l_msg.split()
                        target = parts[1] if len(parts) > 1 else "all"

                        if target == "shield":
                            importlib.reload(shield)
                            self.shield = shield.ChatShield(
                                db_path=".data/database/ad_bot_suspicion.txt", 
                                viewers_path=".data/database/viewers.json"
                            )
                            self.send_msg("🛡️ Module Shield rechargé !")
                        
                        elif target == "music":
                            self.music.running = False
                            importlib.reload(music)
                            self.music = music.MusicManager(sp, PLAYLIST_ID, ARCHIVE_ID, ADMINS, LIMIT_USER, LIMIT_MODO)
                            # Rechargement des .txt de sécurité (banwords/whitelist)
                            if hasattr(self.music, 'reload_filters'):
                                self.music.reload_filters()
                            self.music.start_worker()
                            self.send_msg("🎵 Module Musique & Listes de sécurité rechargés !")
                        
                        elif target == "commands":
                            importlib.reload(commands)
                            self.send_msg("⌨️ Module Commandes rechargé !")
                        
                        elif target == "all":
                            msg = self.reload_all()
                            self.send_msg(f"🔄 {msg}")
                        continue

                    # --- C. COMMANDES EXTERNES ---
                    if l_msg.startswith('!'):
                        commands.handle_command(self, user, message, l_msg, tags, is_privileged)

            except Exception as e:
                print(f"⚠️ Erreur loop : {e}")
                time.sleep(5)
                continue

if __name__ == '__main__':
    TwitchBot().run()