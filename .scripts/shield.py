# type: ignore
import re
import os
import time
import json
from datetime import datetime, timedelta

class ChatShield:
    def __init__(self, db_path=".data/database/ad_bot_suspicion.txt", viewers_path=".data/database/viewers.json"):
        # --- Chemins v1.4.4 (Rétablis) ---
        self.db_path = db_path
        self.viewers_path = viewers_path
        
        self.blacklist = []
        self.viewers_data = {} 
        self.spam_tracker = {}
        
        # Whitelist & Mots-clés
        self.safe_domains = [
            "twitch.tv", "youtube.com", "youtu.be", "spotify.link", 
            "googleusercontent.com", "spotify.com"
        ]
        
        self.art_keywords = [
            "artist", "designer", "portfolio", "illustration", 
            "commissions", "behance", "artstation", "overlay", "rebrand"
        ]
        
        # Initialisation des répertoires
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.viewers_path), exist_ok=True)
        
        self.load_database()
        self.load_viewers()
        self.purge_old_viewers(days=30)

    # --- GESTION DU JSON ---
    def load_viewers(self):
        """Charge les données structurées des viewers."""
        if os.path.exists(self.viewers_path):
            try:
                with open(self.viewers_path, "r", encoding="utf-8") as f:
                    self.viewers_data = json.load(f)
            except:
                self.viewers_data = {}
        else:
            self.viewers_data = {}

    def save_data(self):
        """Sauvegarde propre au format JSON dictionnaire."""
        try:
            with open(self.viewers_path, "w", encoding="utf-8") as f:
                json.dump(self.viewers_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[SHIELD] Erreur sauvegarde : {e}")

    # --- LOGIQUE DE PURGE ---
    def purge_old_viewers(self, days=30):
        """Supprime uniquement les scores 0 et 1 inactifs (préserve -1, 2, 3)."""
        limit_date = datetime.now() - timedelta(days=days)
        to_delete = []
        
        for user, data in self.viewers_data.items():
            # Sécurité : on ne purge QUE les éphémères (0 et 1)
            if data.get("level") in [0, 1]: 
                try:
                    last_seen = datetime.strptime(data["last_seen"], "%Y-%m-%d")
                    if last_seen < limit_date:
                        to_delete.append(user)
                except: continue
                
        if to_delete:
            for user in to_delete:
                del self.viewers_data[user]
            self.save_data()
            print(f"[SHIELD] Purge effectuée : {len(to_delete)} entrées supprimées.")

    # --- MISES À JOUR DES SCORES ---
    def update_user(self, user, is_privileged=False, new_score=None):
        """Gestionnaire central de l'état d'un viewer."""
        user = user.lower()
        today = datetime.now().strftime("%Y-%m-%d")
        
        if user not in self.viewers_data:
            self.viewers_data[user] = {
                "level": 1,
                "messages": 0,
                "last_seen": today,
                "is_banned": False,
                "safe_messages_count": 0
            }

        data = self.viewers_data[user]
        data["last_seen"] = today

        # 1. Forçage via commande admin
        if new_score is not None:
            data["level"] = new_score
            data["is_banned"] = (new_score == -1)
            if new_score >= 1:
                data["safe_messages_count"] = 0
            self.save_data()
            return

        # 2. Gestion de la Grâce (Level 0)
        if data["level"] == 0:
            if data.get("safe_messages_count", 0) > 0:
                data["safe_messages_count"] -= 1
            
            if data["safe_messages_count"] <= 0:
                data["level"] = 1
                print(f"[SHIELD] @{user} a fini sa probation (Level 1).")

        # 3. Évolution classique
        data["messages"] += 1
        
        if is_privileged:
            data["level"] = 3
            data["is_banned"] = False
            data["safe_messages_count"] = 0
        elif data["level"] == 1 and data["messages"] >= 50:
            data["level"] = 2

        self.save_data()

    def unban_grace(self, user, required_safe=10):
        """Place un utilisateur en probation Level 0."""
        user = user.lower()
        self.viewers_data[user] = {
            "level": 0,
            "messages": 0,
            "last_seen": datetime.now().strftime("%Y-%m-%d"),
            "is_banned": False,
            "safe_messages_count": required_safe
        }
        self.save_data()
        return True

    # --- ANALYSE ---
    def load_database(self):
        """Charge les patterns de bots."""
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w", encoding="utf-8") as f:
                f.write("# Patterns AD-BOT\n")
        with open(self.db_path, "r", encoding="utf-8") as f:
            self.blacklist = [l.strip().lower() for l in f if l.strip() and not l.startswith("#")]

    def check_message(self, user, message, is_privileged=False):
        user = user.lower()
        if user not in self.viewers_data:
            self.update_user(user, is_privileged)
        
        u_data = self.viewers_data[user]
        if u_data.get("is_banned") or u_data.get("level") == -1:
            return True, "ACTION_BAN_PERMANENT"

        now = time.time()
        msg_raw = message.lower()

        # --- Détection Spam ---
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

        if is_privileged or u_data["level"] == 3:
            self.update_user(user, is_privileged)
            return False, None

        if u_data["level"] == 2 and tracker["count"] >= 7: return True, "SPAM_LVL2"
        if u_data["level"] <= 1 and tracker["count"] >= 3: return True, "SPAM_LVL1"

        # --- Détection Patterns Bot ---
        is_botting = False
        is_safe_link = any(domain in msg_raw for domain in self.safe_domains)
        
        if not is_safe_link:
            msg_clean = msg_raw.replace(" ", "").replace(".", "").replace("-", "")
            for pattern in self.blacklist:
                if pattern in msg_raw or (len(pattern) > 4 and pattern.replace(" ","") in msg_clean):
                    is_botting = True
                    break
            
            # Liens suspects pour scores faibles
            if not is_botting and u_data["level"] <= 1:
                if any(ext in msg_raw for ext in ["http", ".com", ".net", ".ru"]):
                    is_botting = True

        if is_botting:
            lvl = u_data["level"]
            if lvl == 2:
                self.update_user(user, new_score=1)
                return True, "BOT_TO_1S"
            if lvl == 1:
                self.update_user(user, new_score=0)
                return True, "BOT_TO_2S"
            if lvl == 0:
                u_data["is_banned"] = True
                self.update_user(user, new_score=-1)
                return True, "ACTION_BAN_PERMANENT"

        self.update_user(user, is_privileged)
        return False, None