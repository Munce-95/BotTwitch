import re
import os
import time
from datetime import datetime, timedelta

class ChatShield:
    def __init__(self, db_path=".data/ad_bot_suspicion.txt", viewers_path=".data/viewer.txt"):
        self.db_path = db_path
        self.viewers_path = viewers_path
        self.blacklist = []
        self.viewers_data = {} 
        self.spam_tracker = {}
        
        # Domaines autorisés (Whitelist)
        self.safe_domains = [
            "twitch.tv", "youtube.com", "youtu.be", "spotify.link",
            "googleusercontent.com", "spotify.com" # Simplifié pour couvrir tous les liens Spotify
        ]
        
        # Liste d'immunité : si ces mots sont présents, on est plus indulgent
        self.art_keywords = [
            "artist", "designer", "portfolio", "illustration", 
            "commissions", "behance", "artstation", "overlay", "rebrand"
        ]
        
        # Création du dossier .data si absent
        os.makedirs(".data", exist_ok=True)
        
        self.load_database()
        self.load_viewers()
        self.purge_old_viewers(days=30)

    def load_viewers(self):
        if os.path.exists(self.viewers_path):
            with open(self.viewers_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().lower().split(":")
                    if len(parts) >= 3:
                        user = parts[0]
                        try:
                            score = int(parts[1])
                            count = int(parts[2])
                            last_date = parts[3] if len(parts) == 4 else datetime.now().strftime("%Y-%m-%d")
                            self.viewers_data[user] = [score, count, last_date]
                        except ValueError: continue

    def save_data(self):
        # On s'assure que le dossier existe avant d'écrire
        os.makedirs(os.path.dirname(self.viewers_path), exist_ok=True)
        with open(self.viewers_path, "w", encoding="utf-8") as f:
            for user, data in self.viewers_data.items():
                f.write(f"{user}:{data[0]}:{data[1]}:{data[2]}\n")

    def purge_old_viewers(self, days=30):
        limit_date = datetime.now() - timedelta(days=days)
        to_delete = []
        for user, data in self.viewers_data.items():
            if data[0] <= 1: 
                try:
                    last_seen = datetime.strptime(data[2], "%Y-%m-%d")
                    if last_seen < limit_date: to_delete.append(user)
                except: continue
        for user in to_delete: del self.viewers_data[user]
        if to_delete: self.save_data()

    def update_user(self, user, is_privileged=False, new_score=None):
        user = user.lower()
        today = datetime.now().strftime("%Y-%m-%d")
        if user not in self.viewers_data:
            self.viewers_data[user] = [1, 0, today] 

        if new_score is not None:
            self.viewers_data[user][0] = new_score
            self.viewers_data[user][2] = today
            self.save_data()
            return

        self.viewers_data[user][2] = today
        score_actuel = self.viewers_data[user][0]
        
        # Un utilisateur privilégié (Modo/VIP) passe/reste au score 3 (Confiance totale)
        if is_privileged:
            self.viewers_data[user][0] = 3
        elif score_actuel == 3:
            # Si un ancien modo redevient viewer normal, on garde un score élevé s'il a beaucoup parlé
            self.viewers_data[user][0] = 2 if self.viewers_data[user][1] >= 50 else 1

        self.viewers_data[user][1] += 1
        count = self.viewers_data[user][1]
        
        # Évolution naturelle du score
        if self.viewers_data[user][0] == 0 and count % 3 == 0:
            self.viewers_data[user][0] = 1
        if self.viewers_data[user][0] == 1 and count >= 50:
            self.viewers_data[user][0] = 2
        self.save_data()

    def load_database(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, "r", encoding="utf-8") as f:
                self.blacklist = [l.strip().lower() for l in f if l.strip() and not l.startswith("#")]
                
    def reload_database(self):
        self.blacklist = [] 
        self.load_database()
        return len(self.blacklist)

    def check_message(self, user, message, is_privileged=False):
        user = user.lower()
        if user not in self.viewers_data:
            self.viewers_data[user] = [1, 0, datetime.now().strftime("%Y-%m-%d")]
        
        score, count, last_date = self.viewers_data[user]
        if score == -1: return True, "ACTION_BAN_PERMANENT"

        now = time.time()
        msg_raw = message.lower()

        # --- 1. GESTION DU SPAM ---
        if user not in self.spam_tracker:
            self.spam_tracker[user] = {"time": now, "count": 0, "last_msg": ""}
        
        tracker = self.spam_tracker[user]
        has_consonant_streak = re.search(r'[^aeiouy0-9 ]{6,}', msg_raw)
        is_long_no_space = len(msg_raw) > 12 and " " not in msg_raw
        is_repeat = (msg_raw == tracker["last_msg"])
        
        if (is_repeat or has_consonant_streak or is_long_no_space) and (now - tracker["time"] < 300):
            tracker["count"] += 1
        else:
            tracker["count"] = 1
        
        tracker["last_msg"] = msg_raw
        tracker["time"] = now

        if is_privileged or score == 3:
            self.update_user(user, is_privileged)
            return False, None

        if score == 2 and tracker["count"] >= 7:
            tracker["count"] = 0
            return True, "SPAM_LVL2"
        if score <= 1 and tracker["count"] >= 3:
            tracker["count"] = 0
            return True, "SPAM_LVL1"

        # --- 2. LOGIQUE DE SÉCURITÉ (WHITELIST & IMMUNITÉ ART) ---
        is_botting = False
        is_safe_link = False
        
        # A. Priorité Whitelist Liens
        if any(ext in msg_raw for ext in ["http", ".com", ".net", ".ru", "t.me", "youtu.be"]):
            for domain in self.safe_domains:
                if domain.lower() in msg_raw:
                    is_safe_link = True
                    break
        
        # B. Priorité Immunité Art
        is_art_talk = any(art in msg_raw for art in self.art_keywords)
        if is_art_talk and (score >= 2 or count > 5):
            is_botting = False 
        elif not is_safe_link:
            # C. Check Blacklist
            msg_clean = msg_raw.replace(" ", "").replace("-", "").replace("_", "").replace(".", "")
            for pattern in self.blacklist:
                if not pattern.strip(): continue
                
                if len(pattern) < 4:
                    if not re.search(rf'\b{re.escape(pattern)}\b', msg_raw):
                        continue
                
                p_ns = pattern.replace(" ", "")
                if pattern in msg_raw or (len(p_ns) > 4 and p_ns in msg_clean):
                    if any(art in pattern for art in self.art_keywords) and (score >= 2 or count > 5):
                        continue
                    is_botting = True
                    break
        
        # D. Liens inconnus pour les bas scores
        if not is_botting and not is_safe_link and score <= 1:
            if any(ext in msg_raw for ext in ["http", ".com", ".net", ".ru", "t.me", "youtu.be"]):
                is_botting = True

        # --- 3. ACTIONS ---
        if is_botting:
            if score == 2:
                self.update_user(user, new_score=1)
                return True, "BOT_TO_1S"
            if score == 1:
                self.update_user(user, new_score=0)
                return True, "BOT_TO_2S"
            if score == 0:
                self.update_user(user, new_score=-1)
                return True, "ACTION_BAN_PERMANENT"

        self.update_user(user, is_privileged)
        return False, None