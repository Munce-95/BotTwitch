import spotipy # type: ignore
from spotipy.oauth2 import SpotifyOAuth # type: ignore
import os, sys
from datetime import datetime
from dotenv import load_dotenv # type: ignore

# --- CHARGEMENT DES CONFIGURATIONS (.env) ---
load_dotenv()

# Variables Twitch
TWITCH_TOKEN = os.getenv("TWITCH_TOKEN")
TWITCH_NICK = os.getenv("TWITCH_NICK")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")

# Variables Spotify
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
ARCHIVE_ID = os.getenv("ARCHIVE_ID")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-modify-public playlist-modify-private user-read-currently-playing user-modify-playback-state user-read-playback-state"

# Paramètres du bot
admins_raw = os.getenv("ADMINS", "")
ADMINS = [a.strip() for a in admins_raw.split(",") if a]
LIMIT_USER = int(os.getenv("LIMIT_USER", 5))
LIMIT_MODO = int(os.getenv("LIMIT_MODO", 10))

# 1. PRÉPARATION DU CHEMIN (Accès aux dossiers cachés)
sys.path.append(os.path.join(os.path.dirname(__file__), '.scripts'))

# 2. IMPORTS DES MODULES CUSTOM
try:
    from bot_core import TwitchBase # type: ignore
    from shield import ChatShield # type: ignore
    from music import MusicManager # type: ignore
except ImportError as e:
    print(f"❌ Erreur d'importation : {e}")
    sys.exit(1)

# 3. INITIALISATION SPOTIFY
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID, 
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI, 
    scope=SCOPE, 
    open_browser=True
))


class TwitchBot(TwitchBase):
    def __init__(self):
        # TwitchBase utilise ses propres os.getenv ou les arguments
        super().__init__()
        
        # Initialisation du bouclier anti-bot et du gestionnaire de musique
        self.shield = ChatShield(db_path=".data/ad_bot_suspicion.txt", viewers_path=".data/viewer.txt")
        self.music = MusicManager(sp, PLAYLIST_ID, ARCHIVE_ID, ADMINS, LIMIT_USER, LIMIT_MODO)
        self.music.start_worker()

    def run(self):
        """Lancement du bot et de la boucle de réception IRC"""
        if not self.connect(): 
            return
        
        # Lance le nettoyeur de playlist en arrière-plan
        self.music.start_worker()

        print(f"🚀 Bot prêt et connecté sur le channel : {TWITCH_CHANNEL}")

        while True:
            try:
                resp = self.sock.recv(4096).decode('utf-8', 'ignore')
                if not resp: break
                
                # Répondre au PING de Twitch
                if resp.startswith('PING'):
                    self.sock.send("PONG :tmi.twitch.tv\r\n".encode('utf-8'))
                    continue

                if "PRIVMSG" in resp:
                    user, message, tags = self.parse_irc(resp)
                    
                    # Ignorer le bot lui-même
                    if user == TWITCH_NICK.lower(): 
                        continue
                    
                    l_msg = message.lower()
                    
                    # Vérification des droits
                    is_privileged = any(x in tags.get('badges', '') for x in ['broadcaster', 'moderator', 'vip']) or user in ADMINS
                    timestamp = datetime.now().strftime('%H:%M:%S')

                    # --- ÉTAPE 1 : SÉCURITÉ (Shield) ---
                    is_bad, action = self.shield.check_message(user, message, is_privileged)
                    
                    if is_bad:
                        if action == "ACTION_BAN_PERMANENT":
                            print(f"[{timestamp}] 🚫 SHIELD : BAN définitif pour {user}")
                            self.ban_user(user)
                            self.send_msg("The Ban Hammer has hit another target!")
                        elif action == "SPAM_LVL2":
                            print(f"[{timestamp}] ⏳ SHIELD : Spam Habitué (1s) pour {user}")
                            self.timeout_user(user, 1)
                            self.send_msg(f"Attention au spam @{user}")
                        elif action == "SPAM_LVL1":
                            print(f"[{timestamp}] ⏳ SHIELD : Spam Lambda (60s) pour {user}")
                            self.timeout_user(user, 60)
                            self.send_msg(f"Attention au spam @{user}")
                        elif action == "BOT_TO_1S":
                            print(f"[{timestamp}] 🛡️ SHIELD : Botting suspect (1s) pour {user}")
                            self.timeout_user(user, 1)
                        elif action == "BOT_TO_2S":
                            print(f"[{timestamp}] 🛡️ SHIELD : Sommation Botting (2s) pour {user}")
                            self.timeout_user(user, 2)
                        continue 

                    # --- ÉTAPE 2 : COMMANDES (!) ---
                    if l_msg.startswith('!'):
                        if l_msg == '!shield reload' and is_privileged:
                            nb = self.shield.reload_database()
                            print(f"[{timestamp}] ⚙️ SYSTEM : Base Shield rechargée ({nb} patterns).")
                            self.send_msg(f"🛡️ Shield synchronisé ({nb} patterns).")
                        
                        else:
                            # Note : on a retiré config.PLAYLIST_ID ici car géré dans MusicManager
                            print(f"[{timestamp}] 🎵 MUSIC : {user} -> {message}")
                            self.music.process_command(user, message, l_msg, tags, is_privileged, self.send_msg)
                        
                        continue

            except Exception as e:
                print(f"⚠️ Erreur loop : {e}")
                continue

if __name__ == '__main__':
    TwitchBot().run()
