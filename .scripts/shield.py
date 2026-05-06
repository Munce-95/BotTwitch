# type: ignore
# shield.py - v1.5 | Database Integrated
import re
import os
import time
from datetime import datetime, timedelta

class ChatShield:
    def __init__(self, db_manager):
        self.db = db_manager
        self.spam_tracker = {}
        
        # Whitelist & Mots-clés
        self.safe_domains = [
            "twitch.tv", "youtube.com", "youtu.be", "spotify.link", 
            "googleusercontent.com", "spotify.com"
        ]
        
        # Patterns AD-BOT (On garde un petit fichier local pour les regex perso)
        self.db_path = ".data/database/ad_bot_suspicion.txt"
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.load_blacklist()

    def load_blacklist(self):
        """Charge les patterns de bots depuis le fichier local."""
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w", encoding="utf-8") as f:
                f.write("# Patterns AD-BOT\n")
        with open(self.db_path, "r", encoding="utf-8") as f:
            self.blacklist = [l.strip().lower() for l in f if l.strip() and not l.startswith("#")]

    # --- LOGIQUE DATABASE (SUPABASE) ---
    def get_user_data(self, username):
        """Récupère les infos d'un viewer en DB."""
        try:
            res = self.db.supabase.table(self.db.viewer_table).select("*").eq("username", username.lower()).execute()
            return res.data[0] if res.data else None
        except: return None

    def update_user(self, user, is_privileged=False, new_score=None):
        """Gestionnaire centralisé des viewers en base de données."""
        user = user.lower()
        if not user: return # Sécurité supplémentaire
        
        today = datetime.now().strftime("%Y-%m-%d")
        current = self.get_user_data(user)
        
        # Initialisation du dictionnaire avec le username TOUJOURS présent
        data = {"username": user} 
        
        if not current:
            # Création du nouveau viewer
            data.update({
                "level": 3 if is_privileged else 1,
                "messages": 1,
                "last_seen": today,
                "is_banned": False,
                "safe_messages_count": 0
            })
        else:
            # Mise à jour
            data.update({
                "last_seen": today,
                "messages": current["messages"] + 1
            })
            
            if new_score is not None:
                data["level"] = new_score
                data["is_banned"] = (new_score == -1)
                data["safe_messages_count"] = 0
            elif is_privileged:
                data["level"] = 3
            elif current["level"] == 0:
                # Gestion de la probation
                safe_count = current.get("safe_messages_count", 0) - 1
                if safe_count <= 0:
                    data["level"] = 1
                    data["safe_messages_count"] = 0
                else:
                    data["safe_messages_count"] = safe_count
            elif current["level"] == 1 and (current["messages"] + 1) >= 50:
                data["level"] = 2

        try:
            # L'upsert se basera sur le username pour savoir s'il doit update ou insert
            self.db.supabase.table(self.db.viewer_table).upsert(data, on_conflict="username").execute()
        except Exception as e:
            print(f"[SHIELD DB ERROR] {e}")

    # --- ANALYSE DU MESSAGE ---
    def check_message(self, user, message, is_privileged=False):
        user = user.lower()
        u_data = self.get_user_data(user)
        
        # Si le mec est banni en DB, on ne cherche même pas
        if u_data and (u_data.get("is_banned") or u_data.get("level") == -1):
            return True, "ACTION_BAN_PERMANENT"

        now = time.time()
        msg_raw = message.lower()

        # --- Détection Spam (Mémoire vive uniquement) ---
        if user not in self.spam_tracker:
            self.spam_tracker[user] = {"time": now, "count": 0, "last_msg": ""}
        
        tracker = self.spam_tracker[user]
        is_repeat = (msg_raw == tracker["last_msg"])
        
        if is_repeat and (now - tracker["time"] < 300):
            tracker["count"] += 1
        else:
            tracker["count"] = 1
        
        tracker["last_msg"] = msg_raw
        tracker["time"] = now

        # Skip pour les VIP/Modos/Streamer
        if is_privileged or (u_data and u_data["level"] == 3):
            self.update_user(user, is_privileged)
            return False, None

        # Sanctions Spam
        user_lvl = u_data["level"] if u_data else 1
        if user_lvl == 2 and tracker["count"] >= 7: return True, "SPAM_LVL2"
        if user_lvl <= 1 and tracker["count"] >= 3: return True, "SPAM_LVL1"

        # --- Détection Patterns Bot ---
        is_botting = False
        is_safe_link = any(domain in msg_raw for domain in self.safe_domains)
        
        if not is_safe_link:
            msg_clean = msg_raw.replace(" ", "").replace(".", "").replace("-", "")
            for pattern in self.blacklist:
                if pattern in msg_raw or (len(pattern) > 4 and pattern.replace(" ","") in msg_clean):
                    is_botting = True
                    break
            
            # Liens suspects pour nouveaux (Level 1 ou moins)
            if not is_botting and user_lvl <= 1:
                if any(ext in msg_raw for ext in ["http", ".com", ".net", ".ru"]):
                    is_botting = True

        if is_botting:
            if user_lvl == 2:
                self.update_user(user, new_score=1)
                return True, "BOT_TO_1S"
            if user_lvl == 1:
                self.update_user(user, new_score=0)
                return True, "BOT_TO_2S"
            if user_lvl == 0:
                self.update_user(user, new_score=-1)
                return True, "ACTION_BAN_PERMANENT"

        self.update_user(user, is_privileged)
        return False, None