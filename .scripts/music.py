# type: ignore
import re
import os
import json
import time
import threading
import spotipy
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
        self.current_track_name = "Inconnu"
        self.current_track_artist = "Inconnu"
        
        self.running = True
        self.cache_file = ".data/music_cache.json"
        self.queue_file = ".data/queue.json"
        os.makedirs(".data", exist_ok=True)
        
        if not os.path.exists(self.queue_file):
            self._save_queue([])

    # --- OUTILS ---
    def clean_string(self, text):
        if not text: return ""
        return re.sub(r'[^a-z0-9]', '', text.lower())

    def get_similarity(self, a, b):
        return SequenceMatcher(None, self.clean_string(a), self.clean_string(b)).ratio() * 100

    def format_ms(self, ms):
        seconds = int((ms / 1000) % 60)
        minutes = int((ms / (1000 * 60)) % 60)
        return f"{minutes}:{seconds:02d}"

    # --- GESTION DU JSON QUEUE ---
    def _load_queue(self):
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []

    def _save_queue(self, data):
        try:
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except: pass

    # --- CACHE & APPRENTISSAGE ---
    def load_cache(self):
        if not os.path.exists(self.cache_file): return []
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []

    def save_to_cache(self, title, artist, track_uri, status=0):
        cache = self.load_cache()
        for item in cache:
            if item['uri'] == track_uri:
                if status == -2: item['status'] = -2
                self._save_cache_file(cache)
                return
        
        cache.append({"title": title, "artist": artist, "uri": track_uri, "status": status})
        self._save_cache_file(cache)

    def _save_cache_file(self, cache):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=4, ensure_ascii=False)
        except: pass

    def find_in_cache(self, query):
        cache = self.load_cache()
        best_match = None
        highest_score = 0
        for entry in cache:
            t, a = entry['title'], entry['artist']
            for test_str in [f"{t}{a}", f"{a}{t}", t]:
                score = self.get_similarity(query, test_str)
                if score > highest_score:
                    highest_score = score
                    best_match = entry
        return best_match if highest_score >= 76 else None

    # --- WORKER ---
    def start_worker(self):
        self.running = True
        threading.Thread(target=self._main_loop, daemon=True).start()
        print("🎶 MusicManager v1.4.3 démarré (Blacklist & Smart Queue).")

    def _main_loop(self):
        rotation_counter = 0
        injected_uris = set()

        while self.running:
            try:
                curr = self.sp.current_playback()
                sleep_time = 15

                if curr and curr['item']:
                    track = curr['item']
                    uri = track['uri']
                    duration = track['duration_ms']
                    progress = curr['progress_ms']
                    remaining = duration - progress

                    if uri != self.last_track_uri:
                        self.last_track_uri = uri
                        self.current_track_name = track['name']
                        self.current_track_artist = track['artists'][0]['name']
                        self.save_to_cache(self.current_track_name, self.current_track_artist, uri)

                    queue_data = self._load_queue()
                    if queue_data:
                        next_track = queue_data[0]
                        if duration < 20000 or remaining < 10000:
                            if next_track['uri'] not in injected_uris:
                                try:
                                    self.sp.add_to_queue(next_track['uri'])
                                    injected_uris.add(next_track['uri'])
                                    queue_data.pop(0)
                                    self._save_queue(queue_data)
                                    u_low = next_track['user'].lower()
                                    if u_low in self.user_queues and next_track['uri'] in self.user_queues[u_low]:
                                        self.user_queues[u_low].remove(next_track['uri'])
                                except: pass
                        
                        rem_sec = remaining / 1000
                        sleep_time = max(5, min(rem_sec - 8, 30))

                rotation_counter += 1
                if rotation_counter >= 30:
                    self._check_playlist_rotation()
                    rotation_counter = 0
                    injected_uris.clear()

            except:
                sleep_time = 20
            
            time.sleep(sleep_time)

    def _check_playlist_rotation(self):
        try:
            live_tracks = self.sp.playlist_items(self.playlist_id)['items']
            if len(live_tracks) >= 95:
                live_uris = [t['track']['uri'] for t in live_tracks if t.get('track')]
                self.sp.playlist_add_items(self.archive_id, live_uris)
                self.sp.playlist_replace_items(self.playlist_id, [])
        except: pass

    # --- COMMANDES ---
    def process_command(self, user, message, l_msg, tags, is_privileged, callback):
        if l_msg.startswith('!sr '):
            self.handle_sr(user, message[4:].strip(), tags, callback)
            return True
        elif l_msg == '!song':
            curr = self.sp.current_playback()
            if curr and curr['item']:
                t = curr['item']
                dur = self.format_ms(t['duration_ms'])
                callback(f"🎶 {t['name']} - {t['artists'][0]['name']} [{dur}]")
            else:
                callback(f"🎶 {self.current_track_name} - {self.current_track_artist}")
            return True
        elif l_msg == '!queue':
            queue_data = self._load_queue()
            if not queue_data: callback("📋 La file d'attente est vide.")
            else:
                names = [f"{i+1}. {m['name']}" for i, m in enumerate(queue_data[:5])]
                callback(f"📋 Prochainement : {' // '.join(names)}")
            return True
        elif l_msg.startswith('!wrongsong'):
            self.handle_wrongsong(user, message[10:].strip(), tags, callback)
            return True
        elif l_msg.startswith('!clearqueue') and is_privileged:
            self.handle_clearqueue(message[11:].strip(), callback)
            return True
        elif (l_msg == '!skipsong') and is_privileged:
            self.handle_skip(callback)
            return True 
        return False

    def handle_sr(self, user, query, tags, send_msg_func):
        try:
            u_low = user.lower()
            badges = tags.get('badges', "")
            if u_low not in self.user_queues: self.user_queues[u_low] = []
            
            if not ('broadcaster' in badges):
                max_allowed = self.limit_modo if ('moderator' in badges or u_low in self.admins) else self.limit_user
                if len(self.user_queues[u_low]) >= max_allowed:
                    return send_msg_func(f"@{user}, limite de {max_allowed} titres atteinte.")

            track_info = None
            cached = self.find_in_cache(query)
            
            if cached and cached.get('status') == -2:
                return send_msg_func(f"🚫 @{user}, ce titre est banni.")

            if "track" in query:
                match = re.search(r'track[/:]([a-zA-Z0-9]{22})', query)
                if match: 
                    t = self.sp.track(match.group(1))
                    track_info = {'uri': t['uri'], 'name': t['name'], 'artist': t['artists'][0]['name'], 'duration': t['duration_ms']}
            else:
                if cached:
                    t = self.sp.track(cached['uri'])
                    track_info = {'uri': t['uri'], 'name': t['name'], 'artist': t['artists'][0]['name'], 'duration': t['duration_ms']}
                else:
                    search = self.sp.search(q=query, type='track', limit=1, market='FR')
                    if search['tracks']['items']:
                        t = search['tracks']['items'][0]
                        track_info = {'uri': t['uri'], 'name': t['name'], 'artist': t['artists'][0]['name'], 'duration': t['duration_ms']}

            if not track_info: return send_msg_func(f"❌ Impossible de trouver '{query}'.")

            # --- VERIFICATION DURÉE ---
            if track_info['duration'] > 600000:
                return send_msg_func(f"⚠️ @{user}, la musique est trop longue (max 10:00).")

            # --- VERIFICATION DOUBLONS (URI + SIMILARITÉ) ---
            current_queue = self._load_queue()
            if any(m['uri'] == track_info['uri'] for m in current_queue):
                return send_msg_func(f"@{user}, ce titre est déjà dans la file !")
            
            new_title_full = f"{track_info['name']} {track_info['artist']}"
            for m in current_queue:
                existing_title_full = f"{m['name']} {m.get('artist', '')}"
                if self.get_similarity(new_title_full, existing_title_full) > 85:
                    return send_msg_func(f"@{user}, un titre similaire est déjà en attente.")

            current_queue.append({
                'user': user, 
                'name': track_info['name'], 
                'artist': track_info['artist'], 
                'uri': track_info['uri'], 
                'duration': track_info['duration']
            })
            self._save_queue(current_queue)
            self.sp.playlist_add_items(self.playlist_id, [track_info['uri']])
            self.user_queues[u_low].append(track_info['uri'])
            send_msg_func(f"✅ Ajouté : {track_info['name']} [{self.format_ms(track_info['duration'])}] (Pos: {len(current_queue)})")

        except Exception as e:
            print(f"Erreur SR: {e}")
            if "404" in str(e):
                send_msg_func(f"⚠️ @{user}, lien invalide ou titre introuvable (404).")
            else:
                send_msg_func(f"⚠️ @{user}, erreur lors de la recherche.")

    def handle_skip(self, callback):
        try:
            queue_data = self._load_queue()
            if queue_data:
                next_t = queue_data.pop(0)
                self.sp.add_to_queue(next_t['uri'])
                self.sp.next_track()
                
                self._save_queue(queue_data)
                u_low = next_t['user'].lower()
                if u_low in self.user_queues and next_t['uri'] in self.user_queues[u_low]:
                    self.user_queues[u_low].remove(next_t['uri'])
                
                callback(f"⏭️ Skip ! Passage à : {next_t['name']}")
            else:
                self.sp.next_track()
                callback("⏭️ Skip (Retour à la playlist originale).")
        except Exception as e:
            print(f"Erreur Skip: {e}")
            callback("❌ Erreur lors du skip.")

    def handle_clearqueue(self, target, callback):
        queue_data = self._load_queue()
        if not target or target.lower() == "all":
            self._save_queue([])
            self.user_queues.clear()
            callback("🗑️ File d'attente vidée.")
        elif target.startswith('@'):
            user_to_clear = target[1:].lower()
            new_queue = [m for m in queue_data if m['user'].lower() != user_to_clear]
            self._save_queue(new_queue)
            if user_to_clear in self.user_queues: self.user_queues[user_to_clear] = []
            callback(f"🗑️ Musiques de @{user_to_clear} retirées.")
        else:
            best_match = None
            highest_score = 0
            for m in queue_data:
                score = self.get_similarity(target, m['name'])
                if score > highest_score:
                    highest_score, best_match = score, m
            if best_match and highest_score > 70:
                queue_data.remove(best_match)
                self._save_queue(queue_data)
                callback(f"🗑️ Retiré : {best_match['name']}")
            else: callback("❌ Titre non trouvé.")

    def handle_wrongsong(self, user, query, tags, send_msg_func):
        u_low = user.lower()
        badges = tags.get('badges', '')
        is_admin = u_low in self.admins or 'broadcaster' in badges or 'moderator' in badges
        queue_data = self._load_queue()

        if is_admin and query:
            search = self.sp.search(q=query, type='track', limit=1)
            if search['tracks']['items']:
                t = search['tracks']['items'][0]
                uri = t['uri']
                self.save_to_cache(t['name'], t['artists'][0]['name'], uri, status=-2)
                new_queue = [m for m in queue_data if m['uri'] != uri]
                self._save_queue(new_queue)
                try:
                    self.sp.playlist_remove_all_occurrences_of_items(self.playlist_id, [uri])
                    self.sp.playlist_remove_all_occurrences_of_items(self.archive_id, [uri])
                except: pass
                send_msg_func(f"[Admin] {t['name']} : Supprimé définitivement.")
            return

        if u_low in self.user_queues and self.user_queues[u_low]:
            uri_to_rev = self.user_queues[u_low].pop()
            new_queue = [m for m in queue_data if m['uri'] != uri_to_rev]
            self._save_queue(new_queue)
            self.sp.playlist_remove_all_occurrences_of_items(self.playlist_id, [uri_to_rev])
            send_msg_func(f"🗑️ @{user}, dernier titre retiré.")