import socket
import requests
import os
from dotenv import load_dotenv

# On charge le .env au cas où ce fichier est testé isolément
load_dotenv()

class TwitchBase:
    def __init__(self, token=None, nick=None, channel=None):
        # On récupère les infos soit des arguments, soit du .env
        self.token = token or os.getenv("TWITCH_TOKEN")
        self.nick = nick or os.getenv("TWITCH_NICK")
        self.channel = channel or os.getenv("TWITCH_CHANNEL")
        
        # Paramètres fixes
        self.host = "irc.chat.twitch.tv"
        self.port = 6667
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        
        self.sock = socket.socket()

    def send_msg(self, msg):
        if not msg: return
        full_msg = f"PRIVMSG #{self.channel} :{msg}\r\n"
        self.sock.send(full_msg.encode('utf-8'))

    def ban_user(self, target_name):
        """Bannit définitivement un utilisateur (Niveau -1)"""
        return self._execute_moderation(target_name, action="ban")

    def timeout_user(self, target_name, duration=600):
        """Exclut temporairement un utilisateur (Niveau 0)"""
        return self._execute_moderation(target_name, action="timeout", duration=duration)

    def _execute_moderation(self, target_name, action="timeout", duration=600):
        """Fonction privée qui gère l'appel API pour Ban et Timeout via Helix"""
        try:
            # 1. Nettoyage du nom et du token
            target_name = target_name.lower().replace(":", "").replace("@", "").strip()
            clean_token = self.token.replace("oauth:", "")
            
            headers = {
                'Client-ID': self.client_id,
                'Authorization': f'Bearer {clean_token}',
                'Content-Type': 'application/json'
            }

            # 2. Récupérer l'ID de la cible
            u_resp = requests.get(f'https://api.twitch.tv/helix/users?login={target_name}', headers=headers)
            u_data = u_resp.json()
            if not u_data.get('data'):
                print(f"⚠️ API : Utilisateur '{target_name}' introuvable.")
                return
            target_id = u_data['data'][0]['id']

            # 3. Récupérer l'ID du Broadcaster et du Bot
            my_channel = self.channel.replace("#", "").lower()
            me_resp = requests.get(f'https://api.twitch.tv/helix/users?login={my_channel}', headers=headers)
            broadcaster_id = me_resp.json()['data'][0]['id']

            bot_resp = requests.get('https://api.twitch.tv/helix/users', headers=headers)
            bot_id = bot_resp.json()['data'][0]['id']

            # 4. Préparation de la requête
            url = f'https://api.twitch.tv/helix/moderation/bans?broadcaster_id={broadcaster_id}&moderator_id={bot_id}'
            
            data_payload = {"user_id": target_id}
            
            if action == "timeout":
                data_payload["duration"] = duration
                reason = "🛡️ Shield : Sommation (Niveau 0)"
            else:
                reason = "🛡️ Shield : Automod anti-bot (Niveau -1)"
            
            data_payload["reason"] = reason
            payload = {"data": data_payload}

            # 5. Envoi
            r = requests.post(url, headers=headers, json=payload)
            
            if r.status_code in [200, 201]:
                emoji = "⏳" if action == "timeout" else "🚫"
                print(f"{emoji} [API Helix] {action.upper()} réussi sur {target_name}.")
            else:
                error_msg = r.json().get('message', r.text)
                print(f"❌ [API Helix] Erreur {r.status_code} : {error_msg}")

        except Exception as e:
            print(f"⚠️ Erreur lors de la modération API : {e}")

    def parse_irc(self, data):
        tags = {}
        if data.startswith('@'):
            try:
                tag_str, rest = data[1:].split(' ', 1)
                tags = dict(item.split('=') for item in tag_str.split(';') if '=' in item)
                data = rest
            except: pass
            
        user = data.split('!')[0].split(':')[-1].lower() if '!' in data else "inconnu"
        message = data.split('PRIVMSG', 1)[1].split(':', 1)[1].strip() if 'PRIVMSG' in data else ""
        return user, message, tags

    def connect(self):
        try:
            self.sock.connect((self.host, self.port))
            self.sock.send(f"PASS {self.token}\r\n".encode('utf-8'))
            self.sock.send(f"NICK {self.nick}\r\n".encode('utf-8'))
            self.sock.send(f"JOIN #{self.channel}\r\n".encode('utf-8'))
            self.sock.send("CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership\r\n".encode('utf-8'))
            print(f"✓ {self.nick} en ligne.")
            return True
        except Exception as e:
            print(f"❌ Erreur connexion : {e}")
            return False