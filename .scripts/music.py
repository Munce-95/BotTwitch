import re
import os
import time
import threading
from difflib import SequenceMatcher

class MusicManager:
    def __init__(self, sp, playlist_id, admin_list, limit_user, limit_modo):
        self.sp = sp
        self.playlist_id = playlist_id
        self.admins = admin_list
        self.limit_user = limit_user
        self.limit_modo = limit_modo
        self.user_queues = {}
        self.last_track_uri = None
        
        # Chemins vers les fichiers de données
        self.banwords_file = ".data/banwords.txt"
        self.whitelist_file = ".data/whitelist.txt"

    def start_cleaner(self):
        """Lance le thread de nettoyage automatique des queues utilisateurs."""
        threading.Thread(target=self._music_cleaner_loop, daemon=True).start()
        print("🎶 MusicCleaner démarré.")

    def _music_cleaner_loop(self):
        """Boucle interne qui surveille la lecture Spotify pour libérer les slots des viewers."""
        while True:
            try:
                curr = self.sp.current_playback()
                if curr and curr['is_playing'] and curr['item']:
                    uri = curr['item']['uri']
                    if uri != self.last_track_uri:
                        self.last_track_uri = uri
                        for u in list(self.user_queues.keys()):
                            if uri in self.user_queues[u]:
                                self.user_queues[u].remove(uri)
                                break
            except: pass
            time.sleep(15)

    def process_command(self, user, message, l_msg, tags, is_privileged, callback):
        """Traite les commandes liées à la musique"""
        if l_msg.startswith('!sr '):
            query = message[4:].strip().replace('@', '')
            self.handle_sr(user, query, tags, callback)
            return True
            
        elif l_msg.startswith('!wrongsong'):
            query = message[10:].strip()
            self.handle_wrongsong(user, query, tags, callback)
            return True
            
        elif l_msg == '!skipsong' and is_privileged:
            try:
                self.sp.next_track()
                callback("⏭️ Skip effectué.")
            except: callback("❌ Erreur lors du skip.")
            return True
            
        elif l_msg == '!song':
            try:
                curr = self.sp.current_playback()
                if curr and curr['item']:
                    callback(f"🎶 {curr['item']['name']} - {curr['item']['artists'][0]['name']}")
                else: callback("🔇 Aucune musique en cours.")
            except: pass
            return True
            
        elif l_msg == '!playlist':
            # On utilise l'ID chargé depuis le .env pour générer le lien
            callback(f"🔗 Playlist : https://open.spotify.com/playlist/{self.playlist_id}")
            return True
            
        return False

    def handle_sr(self, user, query, tags, send_msg_func):
        try:
            u_low = user.lower()
            badges = tags.get('badges', "")
            is_broadcaster = 'broadcaster' in badges
            is_modo = 'moderator' in badges or u_low in self.admins
            
            if u_low not in self.user_queues: self.user_queues[u_low] = []
            
            # 1. Vérification des limites de l'utilisateur
            if not is_broadcaster:
                max_allowed = self.limit_modo if is_modo else self.limit_user
                if len(self.user_queues[u_low]) >= max_allowed:
                    send_msg_func(f"@{user}, limite de {max_allowed} titres atteinte.")
                    return

            # 2. Recherche du titre (URL ou Texte)
            track_uri = None
            if "spotify:track:" in query or "http" in query:
                match = re.search(r'track[/:]([a-zA-Z0-9]{22})', query)
                if match: track_uri = f'spotify:track:{match.group(1)}'
            else:
                search = self.sp.search(q=query, type='track', limit=1, market='FR')
                if search['tracks']['items']:
                    track_uri = search['tracks']['items'][0]['uri']

            if not track_uri:
                send_msg_func(f"❌ Impossible de trouver '{query}' sur Spotify.")
                return

            # 3. ANTI-DOUBLONS
            if any(track_uri in q for q in self.user_queues.values()):
                send_msg_func(f"@{user}, ce titre est déjà dans la file d'attente !")
                return

            # 4. Vérification de la durée (max 10 min)
            track_info = self.sp.track(track_uri)
            if track_info['duration_ms'] > 600000:
                send_msg_func(f"@{user}, titre trop long (max 10 min).")
                return

            # --- 5. ACTIONS SPOTIFY ---
            self.sp.playlist_remove_all_occurrences_of_items(self.playlist_id, [track_uri])
            self.sp.playlist_add_items(self.playlist_id, [track_uri])
            
            try:
                self.sp.add_to_queue(track_uri)
            except Exception as e:
                print(f"⚠️ Erreur add_to_queue (Lecteur inactif ?) : {e}")
            
            # 6. Enregistrement en mémoire
            self.user_queues[u_low].append(track_uri)
            send_msg_func(f"✅ @{user} ajouté : {track_info['name']} ({track_info['artists'][0]['name']})")

        except Exception as e:
            print(f"❌ Erreur MusicManager (!sr): {e}")

    def handle_wrongsong(self, user, query, tags, send_msg_func):
        try:
            u_low = user.lower()
            badges = tags.get('badges', '')
            is_admin = u_low in self.admins or 'broadcaster' in badges or 'moderator' in badges
            
            if is_admin and query:
                res = self.sp.search(q=query, type='track', limit=1)
                if res['tracks']['items']:
                    t = res['tracks']['items'][0]
                    self.sp.playlist_remove_all_occurrences_of_items(self.playlist_id, [t['uri']])
                    for q in self.user_queues.values():
                        if t['uri'] in q: q.remove(t['uri'])
                    send_msg_func(f"🗑️ [Admin] {t['name']} retiré de la playlist.")
                else: send_msg_func(f"❌ Aucun titre trouvé pour '{query}'.")
                return

            if u_low in self.user_queues and self.user_queues[u_low]:
                uri = self.user_queues[u_low].pop()
                self.sp.playlist_remove_all_occurrences_of_items(self.playlist_id, [uri])
                send_msg_func(f"🗑️ @{user}, ton dernier titre a été retiré.")
            else:
                send_msg_func(f"@{user}, tu n'as pas de titre en file d'attente.")
        except Exception as e:
            print(f"❌ Erreur MusicManager (!wrongsong): {e}")