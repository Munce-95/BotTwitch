# type: ignore
# bot_core.py - v1.4.4 | Maîtrise des données

import socket
import requests
import os
from dotenv import load_dotenv

load_dotenv()

class TwitchBase:
    def __init__(self, token=None, nick=None, channel=None):
        # Configuration depuis le .env
        self.token = token or os.getenv("TWITCH_TOKEN")
        self.nick = nick or os.getenv("TWITCH_NICK")
        self.channel = (channel or os.getenv("TWITCH_CHANNEL", "")).replace("#", "").lower()
        
        self.host = "irc.chat.twitch.tv"
        self.port = 6667
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        
        self.sock = socket.socket()
        
        # Cache pour éviter les requêtes API inutiles à chaque message
        self.broadcaster_id = None
        self.bot_id = None

    # --- GESTION DU REFRESH TOKEN (AUTONOMIE) ---

    def _get_api_headers(self):
        """Génère les headers Helix avec le token actuel."""
        clean_token = self.token.replace("oauth:", "")
        return {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {clean_token}',
            'Content-Type': 'application/json'
        }

    def refresh_twitch_token(self):
        """Utilise le Refresh Token pour obtenir un nouvel Access Token sans intervention humaine."""
        refresh_token = os.getenv("TWITCH_REFRESH_TOKEN")
        
        if not refresh_token or not self.client_secret:
            print("❌ [CORE] Erreur : Refresh Token ou Secret manquant pour le renouvellement.")
            return False

        url = "https://id.twitch.tv/oauth2/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        try:
            r = requests.post(url, data=payload)
            data = r.json()

            if r.status_code == 200:
                new_access = data["access_token"]
                new_refresh = data.get("refresh_token")

                # Mise à jour en mémoire
                self.token = f"oauth:{new_access}"
                
                # Sauvegarde physique dans le .env
                self._update_env_file("TWITCH_TOKEN", self.token)
                if new_refresh:
                    self._update_env_file("TWITCH_REFRESH_TOKEN", new_refresh)
                
                print("✅ [CORE] Token Twitch renouvelé et .env mis à jour.")
                return True
            else:
                print(f"❌ [CORE] Échec du renouvellement : {data.get('message')}")
                return False
        except Exception as e:
            print(f"⚠️ [CORE] Erreur lors du refresh token : {e}")
            return False

    def _update_env_file(self, key, value):
        """Met à jour une valeur spécifique dans le fichier .env."""
        env_path = ".env"
        if not os.path.exists(env_path): return
        
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        with open(env_path, "w", encoding="utf-8") as f:
            found = False
            for line in lines:
                if line.startswith(f"{key}="):
                    f.write(f"{key}={value}\n")
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f"{key}={value}\n")

    def _ensure_ids(self):
        """Récupère l'ID de la chaîne et du bot une seule fois par session."""
        if self.broadcaster_id and self.bot_id:
            return True
        
        headers = self._get_api_headers()
        try:
            # ID du Broadcaster
            me_resp = requests.get(f'https://api.twitch.tv/helix/users?login={self.channel}', headers=headers)
            if me_resp.status_code == 401 and self.refresh_twitch_token():
                return self._ensure_ids() # Re-tentative après refresh
            
            self.broadcaster_id = me_resp.json()['data'][0]['id']

            # ID du Bot (soi-même)
            bot_resp = requests.get('https://api.twitch.tv/helix/users', headers=headers)
            self.bot_id = bot_resp.json()['data'][0]['id']
            return True
        except Exception as e:
            print(f"❌ [CORE] Erreur récupération IDs Helix : {e}")
            return False

    # --- MODÉRATION API (HELIX) ---

    def ban_user(self, target_name):
        return self._execute_moderation(target_name, action="ban")

    def timeout_user(self, target_name, duration=600):
        return self._execute_moderation(target_name, action="timeout", duration=duration)

    def unban_user(self, target_name):
        return self._execute_moderation(target_name, action="unban")

    def _execute_moderation(self, target_name, action="timeout", duration=600):
        if not self._ensure_ids(): return

        target_name = target_name.lower().replace("@", "").strip()
        headers = self._get_api_headers()

        try:
            # Récupérer l'ID de la cible
            u_resp = requests.get(f'https://api.twitch.tv/helix/users?login={target_name}', headers=headers)
            if u_resp.status_code == 401 and self.refresh_twitch_token():
                return self._execute_moderation(target_name, action, duration)
            
            u_data = u_resp.json()
            if not u_data.get('data'): return
            target_id = u_data['data'][0]['id']

            # Exécution de l'action
            if action == "unban":
                url = f'https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.broadcaster_id}&moderator_id={self.bot_id}&user_id={target_id}'
                r = requests.delete(url, headers=headers)
            else:
                url = f'https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.broadcaster_id}&moderator_id={self.bot_id}'
                reason = "🛡️ Shield : Automod v1.4.4"
                payload = {"data": {"user_id": target_id, "reason": reason}}
                if action == "timeout": payload["data"]["duration"] = duration
                r = requests.post(url, headers=headers, json=payload)
            
            if r.status_code in [200, 201, 204]:
                print(f"✓ [Helix] Action {action.upper()} réussie sur {target_name}.")
            else:
                print(f"❌ [Helix] Erreur {r.status_code} : {r.text}")

        except Exception as e:
            print(f"⚠️ [CORE] Erreur modération API : {e}")

    # --- IRC & COMMUNICATION ---

    def send_msg(self, msg):
        if not msg: return
        full_msg = f"PRIVMSG #{self.channel} :{msg}\r\n"
        self.sock.send(full_msg.encode('utf-8'))

    def parse_irc(self, data):
        tags = {}
        if data.startswith('@'):
            try:
                tag_str, rest = data[1:].split(' ', 1)
                tags = {item.split('=')[0]: item.split('=')[1] for item in tag_str.split(';') if '=' in item}
                data = rest
            except: pass
        
        user = data.split('!')[0].split(':')[-1].lower() if '!' in data else "inconnu"
        try:
            message = data.split('PRIVMSG', 1)[1].split(':', 1)[1].strip()
        except:
            message = ""
        return user, message, tags

    def connect(self):
        try:
            self.sock.connect((self.host, self.port))
            self.sock.send(f"PASS {self.token}\r\n".encode('utf-8'))
            self.sock.send(f"NICK {self.nick}\r\n".encode('utf-8'))
            self.sock.send(f"JOIN #{self.channel}\r\n".encode('utf-8'))
            self.sock.send("CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership\r\n".encode('utf-8'))
            
            # Pré-chargement des identifiants API
            self._ensure_ids()
            
            print(f"✓ {self.nick} est connecté à #{self.channel}.")
            return True
        except Exception as e:
            print(f"❌ Erreur connexion IRC : {e}")
            return False