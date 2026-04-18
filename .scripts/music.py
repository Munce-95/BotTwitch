import re
import os
import json
import time
import threading
from difflib import SequenceMatcher

class MusicManager:
    def __init__(self, sp, playlist_id, archive_id, admin_list, limit_user, limit_modo):
        self.sp = sp
        self.playlist_id = playlist_id
        self.archive_id = archive_id
        self.admins = admin_list
        self.limit_user = limit_user
        self.limit_modo = limit_modo
        self.user_queues = {}
        self.last_track_uri = None
        
        # Chemins vers les fichiers de données
        self.cache_file = ".data/music_cache.json"
        os.makedirs(".data", exist_ok=True)

    # --- OUTILS DE COMPARAISON ET NETTOYAGE ---
    def clean_string(self, text):
        """Supprime espaces, majuscules et caractères spéciaux pour la comparaison."""
        if not text: return ""
        return re.sub(r'[^a-z0-9]', '', text.lower())

    def get_similarity(self, a, b):
        """Calcule le score de ressemblance entre deux chaînes."""
        return SequenceMatcher(None, self.clean_string(a), self.clean_string(b)).ratio() * 100

    # --- GESTION DU CACHE JSON ---
    def load_cache(self):
        if not os.path.exists(self.cache_file): return []
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []

    def save_to_cache(self, title, artist, track_uri):
        """Ajoute une musique à la mémoire si elle n'y est pas."""
        cache = self.load_cache()
        if any(item['uri'] == track_uri for item in cache): return
        
        cache.append({"title": title, "artist": artist, "uri": track_uri})
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=4, ensure_ascii=False)

    def find_in_cache(self, query):
        """Recherche intelligente dans le cache avec priorité à l'original."""
        cache = self.load_cache()
        best_match = None
        highest_score = 0
        alt_keywords = ['live', 'remix', 'acoustic', 'edit', 'cover', 'version']

        for entry in cache:
            t, a = entry['title'], entry['artist']
            # On teste : Titre+Artiste, Artiste+Titre, et Titre seul
            tests = [f"{t}{a}", f"{a}{t}", t]
            
            for test_str in tests:
                score = self.get_similarity(query, test_str)
                if score > highest_score:
                    highest_score = score
                    best_match = entry
                elif score == highest_score and highest_score >= 76:
                    # Option 1 : Si score égal, on préfère celle qui n'a pas de mots "Live/Remix"
                    current_has_alt = any(k in entry['title'].lower() for k in alt_keywords)
                    best_has_alt = any(k in best_match['title'].lower() for k in alt_keywords)
                    if best_has_alt and not current_has_alt:
                        best_match = entry
                        
        return best_match if highest_score >= 76 else None

    # --- ROUTINES DE FOND ---
    def start_worker(self):
        """Lance la surveillance et l'apprentissage automatique."""
        threading.Thread(target=self._main_loop, daemon=True).start()
        print("🎶 MusicManager (Auto-Learn & Rotation) prêt.")

    def _main_loop(self):
        """Surveille Spotify pour apprendre les musiques et vider les slots."""
        while True:
            try:
                curr = self.sp.current_playback()
                if curr and curr['is_playing'] and curr['item']:
                    track = curr['item']
                    uri = track['uri']
                    
                    # 1. Apprentissage passif
                    self.save_to_cache(track['name'], track['artists'][0]['name'], uri)

                    # 2. Nettoyage des slots utilisateurs
                    if uri != self.last_track_uri:
                        self.last_track_uri = uri
                        for u in list(self.user_queues.keys()):
                            if uri in self.user_queues[u]:
                                self.user_queues[u].remove(uri)
                                break
                
                # 3. Check de la rotation (déversement si >= 95)
                self._check_playlist_rotation()
                
            except: pass
            time.sleep(20)

    def _check_playlist_rotation(self):
        """Transfère la Live vers l'Archive si elle atteint 95 titres."""
        try:
            live_tracks = self.sp.playlist_items(self.playlist_id)['items']
            if len(live_tracks) >= 95:
                live_uris = [t['track']['uri'] for t in live_tracks if t['track']]
                
                # Récupérer l'Archive pour éviter les doublons
                arch_tracks = self.sp.playlist_items(self.archive_id)['items']
                arch_uris = set(t['track']['uri'] for t in arch_tracks if t['track'])
                
                to_archive = [u for u in live_uris if u not in arch_uris]
                
                if to_archive:
                    for i in range(0, len(to_archive), 100):
                        self.sp.playlist_add_items(self.archive_id, to_archive[i:i+100])
                
                # Vider la Live proprement
                self.sp.playlist_replace_items(self.playlist_id, [])
        except: pass

    # --- TRAITEMENT DES COMMANDES ---
    def process_command(self, user, message, l_msg, tags, is_privileged, callback):
        if l_msg.startswith('!sr '):
            self.handle_sr(user, message[4:].strip(), tags, callback)
            return True
            
        elif l_msg == '!song':
            curr = self.sp.current_playback()
            if curr and curr['item']:
                callback(f"🎶 {curr['item']['name']} - {curr['item']['artists'][0]['name']}")
            return True
            
        elif l_msg == '!playlist':
            link_live = f"https://open.spotify.com/playlist/{self.playlist_id}"
            link_archive = f"https://open.spotify.com/playlist/{self.archive_id}"
            callback(f"🔗 Playlist du mois : {link_live}")
            callback(f"🔗 Playlist totale : {link_archive}")
            return True
            
        elif l_msg.startswith('!wrongsong'):
            self.handle_wrongsong(user, message[10:].strip(), tags, callback)
            return True

        elif l_msg == '!skipsong' and is_privileged:
            try:
                self.sp.next_track()
                callback("⏭️ Skip effectué.")
            except Exception as e:
                callback("❌ Erreur lors du skip (Lecteur inactif ?).")
            return True 

        return False

    def handle_sr(self, user, query, tags, send_msg_func):
        try:
            u_low = user.lower()
            badges = tags.get('badges', "")
            
            if u_low not in self.user_queues: self.user_queues[u_low] = []
            
            # 1. Vérification des limites
            if not ('broadcaster' in badges):
                max_allowed = self.limit_modo if ('moderator' in badges or u_low in self.admins) else self.limit_user
                if len(self.user_queues[u_low]) >= max_allowed:
                    return send_msg_func(f"@{user}, limite de {max_allowed} titres atteinte.")

            # 2. Recherche (URL -> Cache -> Spotify)
            track_info = None
            if "spotify:track:" in query or "http" in query:
                match = re.search(r'track[/:]([a-zA-Z0-9]{22})', query)
                if match: 
                    t_data = self.sp.track(match.group(1))
                    track_info = {'uri': t_data['uri'], 'name': t_data['name'], 'artist': t_data['artists'][0]['name']}
            else:
                cached = self.find_in_cache(query)
                if cached:
                    track_info = {'uri': cached['uri'], 'name': cached['title'], 'artist': cached['artist']}
                else:
                    search = self.sp.search(q=query, type='track', limit=1, market='FR')
                    if search['tracks']['items']:
                        t = search['tracks']['items'][0]
                        track_info = {'uri': t['uri'], 'name': t['name'], 'artist': t['artists'][0]['name']}

            if not track_info:
                return send_msg_func(f"❌ Impossible de trouver '{query}'.")

            # 3. Anti-doublons (Playlist Live)
            live_content = self.sp.playlist_items(self.playlist_id)['items']
            if any(track_info['uri'] == t['track']['uri'] for t in live_content if t['track']):
                return send_msg_func(f"@{user}, ce titre est déjà dans la file d'attente !")

            # 4. Ajout Spotify
            self.sp.playlist_add_items(self.playlist_id, [track_info['uri']])
            try: self.sp.add_to_queue(track_info['uri'])
            except: pass
            
            # 5. Confirmation
            self.user_queues[u_low].append(track_info['uri'])
            send_msg_func(f"✅ Ajouté à la file d'attente : {track_info['name']} - {track_info['artist']}")

        except Exception as e:
            print(f"❌ Erreur handle_sr: {e}")

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