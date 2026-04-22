# type: ignore
# music.py - v1.4.4 | Système de Transition Sécurisé & Système de Queue 1.4.3
import re
import os
import json
import time
import shutil
import threading
import spotipy

class MusicManager:
    def __init__(self, sp, playlist_id, archive_id, admin_list, limit_user, limit_modo):
        self.sp = sp
        self.playlist_id = playlist_id
        self.archive_id = archive_id
        self.admins = admin_list
        self.limit_user = limit_user
        self.limit_modo = limit_modo
        
        # Chemins
        self.db_dir = ".data/database"
        self.config_dir = ".data/config"
        self.cache_file = os.path.join(self.db_dir, "music_cache.json")
        self.queue_file = os.path.join(self.db_dir, "queue.json")
        self.transition_file = os.path.join(self.db_dir, "transition.json")
        self.msg_file = os.path.join(self.config_dir, "messages.json")
        self.msg_example = os.path.join(self.config_dir, "messages.json.example")
        
        os.makedirs(self.db_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        
        if not os.path.exists(self.queue_file):
            self._save_queue([]) # Initialise en LISTE comme en 1.4.3

        if not os.path.exists(self.transition_file):
            with open(self.transition_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
        
        self.messages = self._setup_messages()
        self.last_track_uri = None
        self.running = True
        self.user_queues_count = {} # Pour suivre les limites par utilisateur

    # --- INITIALISATION ---
    def _setup_messages(self):
        if not os.path.exists(self.msg_file):
            if os.path.exists(self.msg_example):
                shutil.copyfile(self.msg_example, self.msg_file)
            else: return {}
        try:
            with open(self.msg_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}

    def _get_msg(self, key, **kwargs):
        msg = self.messages.get(key, f"Missing_msg:{key}")
        try: return msg.format(**kwargs)
        except: return msg

    # --- PERSISTANCE (Format 1.4.3 Liste) ---
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

    def load_cache(self):
        if not os.path.exists(self.cache_file): return []
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []

    def save_to_cache(self, title, artist, track_uri, duration=None, blacklist_it=None, archived_it=None, increment_listen=False):
        cache = self.load_cache()
        found = False
        for item in cache:
            if not isinstance(item, dict): continue
            if item.get('uri') == track_uri:
                if blacklist_it is not None: item['is_blacklisted'] = blacklist_it
                if archived_it is not None: item['is_archived'] = archived_it
                if duration: item['duration'] = self.format_ms(duration)
                if increment_listen: item['listened'] = item.get('listened', 0) + 1
                found = True
                break
        if not found:
            cache.append({
                "title": title, "artist": artist, "uri": track_uri, 
                "duration": self.format_ms(duration) if duration else "??:??",
                "is_blacklisted": blacklist_it if blacklist_it is not None else False,
                "is_archived": archived_it if archived_it is not None else False,
                "listened": 1 if increment_listen else 0
            })
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=4, ensure_ascii=False)

    # --- PROTOCOLE DE ROTATION ---
    def _check_playlist_rotation(self):
        try:
            print(f"🔄 Début du scan de rotation...")
            
            # 1. On charge le cache pour identifier ce qui est déjà archivé
            cache = self.load_cache()
            archived_uris = {item['uri'] for item in cache if isinstance(item, dict) and item.get('is_archived')}
            
            uris_to_process = []
            track_details = {}
            
            res = self.sp.playlist_tracks(self.playlist_id)
            items = res.get('items', [])
            
            for it in items:
                data = it.get('item') or it.get('track')
                if data and data.get('uri'):
                    uri = data['uri']
                    
                    # 2. On n'ajoute à la liste de traitement que si ce n'est pas déjà archivé
                    if uri not in archived_uris:
                        uris_to_process.append(uri)
                        name = data.get('name', 'Titre Inconnu')
                        artists = data.get('artists', [])
                        artist = artists[0].get('name', 'Artiste Inconnu') if (isinstance(artists, list) and len(artists) > 0) else "Artiste Inconnu"
                        track_details[uri] = (name, artist)
            
            # Si aucun nouveau titre n'est à archiver, on vide quand même la playlist Live
            if not uris_to_process:
                if items: # Si la playlist n'était pas vide, on nettoie
                    self.sp.playlist_replace_items(self.playlist_id, [])
                return

            # 3. Transfert vers la playlist Archive par blocs de 100
            for i in range(0, len(uris_to_process), 100):
                self.sp.playlist_add_items(self.archive_id, uris_to_process[i:i+100])
            
            # 4. Mise à jour du cache pour chaque titre traité
            for uri in uris_to_process:
                name, artist = track_details.get(uri, ("Inconnu", "Inconnu"))
                self.save_to_cache(name, artist, uri, archived_it=True)
            
            # 5. Nettoyage de la playlist Live
            self.sp.playlist_replace_items(self.playlist_id, [])
            print(f"✅ Rotation terminée ({len(uris_to_process)} nouveaux titres archivés).")
            
        except Exception as e:
            print(f"❌ Erreur Rotation : {e}")

    # --- COMMANDES ---
    def process_command(self, user, message, l_msg, tags, is_privileged, callback):
        if l_msg.startswith('!sr '):
            self.handle_sr(user, message[4:].strip(), tags, callback)
        elif l_msg == '!song':
            curr = self.sp.current_playback()
            if curr and curr.get('item'):
                t = curr['item']
                artists = t.get('artists', [])
                artist = artists[0].get('name', 'Inconnu') if (isinstance(artists, list) and len(artists) > 0) else "Inconnu"
                callback(self._get_msg("song_msg", title=t.get('name', 'Sans titre'), artist=artist, timer=self.format_ms(t.get('duration_ms'))))
            else: callback(self._get_msg("song_none_msg"))
        elif l_msg == '!playlist':
            l_url = f"https://open.spotify.com/playlist/{self.playlist_id}"
            a_url = f"https://open.spotify.com/playlist/{self.archive_id}"
            callback(self._get_msg("playlist_msg", live_url=l_url, archive_url=a_url))
        elif l_msg == '!queue':
            queue_data = self._load_queue()
            if not queue_data: callback("📋 La file d'attente est vide.")
            else:
                names = [f"{i+1}. {m['name']}" for i, m in enumerate(queue_data[:5])]
                callback(f"📋 Prochainement ({len(queue_data)}) : {' // '.join(names)}")
        elif l_msg.startswith('!wrongsong'):
            self.handle_wrongsong(user, message[10:].strip(), tags, callback)
        elif l_msg.startswith('!clearqueue') and is_privileged:
            self.handle_clearqueue(message[11:].strip(), callback)
        elif l_msg == '!skipsong' and is_privileged:
            self.handle_skip(callback)
            return True
        else: return False
        return True

    def handle_sr(self, user, query, tags, send_msg):
        u_low = user.lower()
        queue_data = self._load_queue()
        
        user_count = sum(1 for m in queue_data if m['user'].lower() == u_low)
        badges = tags.get('badges', {})
        is_mod = 'moderator' in badges or u_low in self.admins
        is_broadcaster = 'broadcaster' in badges
        max_allowed = self.limit_modo if is_mod else self.limit_user
        
        if not is_broadcaster and user_count >= max_allowed:
            return send_msg(f"@{user}, limite de {max_allowed} titres atteinte.")

        track_info = None

        try:
            if "track" in query:
                match = re.search(r'track/([a-zA-Z0-9]{22})', query)
                if not match:
                    match = re.search(r'track[/:].*?([a-zA-Z0-9]{22})', query)
                
                if match:
                    t = self.sp.track(match.group(1))
                    track_info = {
                        'uri': t['uri'], 'name': t['name'], 
                        'artist': t['artists'][0]['name'], 'duration': t['duration_ms']
                    }

            if not track_info:
                results = self.sp.search(q=query, type='track', limit=1)
                if results and results['tracks']['items']:
                    t = results['tracks']['items'][0]
                    track_info = {
                        'uri': t['uri'], 'name': t['name'], 
                        'artist': t['artists'][0]['name'], 'duration': t['duration_ms']
                    }

            if not track_info:
                return send_msg("❌ Musique introuvable.")

            if track_info['duration'] > 600000:
                return send_msg(f"⚠️ @{user}, la musique est trop longue (max 10:00).")

            cache = self.load_cache()
            for item in cache:
                if item.get('is_blacklisted'):
                    if item.get('uri') == track_info['uri'] or self.clean_string(track_info['name']) == self.clean_string(item.get('title')):
                        return send_msg(f"🚫 @{user}, ce titre est banni.")

            if any(m['uri'] == track_info['uri'] for m in queue_data):
                return send_msg(f"@{user}, ce titre est déjà dans la file !")

            queue_data.append({
                'user': user, 'name': track_info['name'], 'artist': track_info['artist'], 
                'uri': track_info['uri'], 'duration': track_info['duration']
            })
            self._save_queue(queue_data)
            self.save_to_cache(track_info['name'], track_info['artist'], track_info['uri'])
            
            send_msg(self._get_msg("sr_msg", user=user, title=track_info['name'], artist=track_info['artist'], pos=len(queue_data)))
            
        except Exception as e:
            print(f"Erreur SR détaillée: {e}")
            send_msg("⚠️ Erreur lors de l'ajout.")

    def handle_skip(self, callback):
        try:
            queue_data = self._load_queue()
            if queue_data:
                next_t = queue_data.pop(0)
                
                # AJOUT À LA PLAYLIST LIVE (Seulement lors du passage réel)
                try:
                    self.sp.playlist_add_items(self.playlist_id, [next_t['uri']])
                except: pass

                self.sp.add_to_queue(next_t['uri'])
                self.sp.next_track()
                
                self._save_queue(queue_data)
                callback(f"⏭️ Skip ! Passage au titre de @{next_t['user']} : {next_t['name']}")
            else:
                self.sp.next_track()
                callback("⏭️ Skip effectué (Retour playlist).")
        except Exception as e:
            print(f"Erreur Skip: {e}")
            callback("❌ Erreur lors du skip.")

    def handle_wrongsong(self, user, query, tags, send_msg):
        u_low = user.lower()
        queue_data = self._load_queue()
        
        if (u_low in self.admins or 'broadcaster' in tags.get('badges', {})) and query:
            new_queue = [m for m in queue_data if self.clean_string(query) not in self.clean_string(m['name'])]
            self._save_queue(new_queue)
            return send_msg("🗑️ Titre retiré de la file par Admin.")

        user_titles = [m for m in queue_data if m['user'].lower() == u_low]
        if user_titles:
            last_uri = user_titles[-1]['uri']
            new_queue = [m for m in queue_data if not (m['user'].lower() == u_low and m['uri'] == last_uri)]
            self._save_queue(new_queue)
            send_msg(f"🗑️ @{user}, ton dernier titre a été retiré.")
        else:
            send_msg(f"⚠️ @{user}, rien à annuler.")

    def handle_clearqueue(self, target, callback):
        if not target or target.lower() == "all":
            self._save_queue([])
            callback("🗑️ File d'attente vidée.")
        else:
            t = target.replace('@', '').lower()
            queue_data = self._load_queue()
            new_q = [m for m in queue_data if m['user'].lower() != t]
            self._save_queue(new_q)
            callback(f"🗑️ Queue de @{t} vidée.")

    def start_worker(self):
        self._check_playlist_rotation()
        threading.Thread(target=self._main_loop, daemon=True).start()
        print("🎶 MusicManager v1.4.4-Hybrid prêt.")

    def _main_loop(self):
        last_rot = time.time()
        injected_uris = set()
        
        while self.running:
            try:
                curr = self.sp.current_playback()
                if curr and curr.get('item'):
                    track = curr['item']
                    uri = track.get('uri')
                    
                    remaining = track['duration_ms'] - curr['progress_ms']
                    queue_data = self._load_queue()
                    
                    if queue_data and remaining < 15000:
                        next_track = queue_data[0]
                        if next_track['uri'] not in injected_uris:
                            try:
                                # AJOUT À LA PLAYLIST LIVE (Seulement lors du passage réel)
                                self.sp.playlist_add_items(self.playlist_id, [next_track['uri']])
                                
                                self.sp.add_to_queue(next_track['uri'])
                                injected_uris.add(next_track['uri'])
                                queue_data.pop(0)
                                self._save_queue(queue_data)
                            except: pass
                    
                    if uri != self.last_track_uri:
                        self.last_track_uri = uri
                        injected_uris.clear()
                        self.save_to_cache(track.get('name'), track['artists'][0].get('name'), uri, 
                                           duration=track.get('duration_ms'), increment_listen=True)
                
                if time.time() - last_rot > 1800:
                    self._check_playlist_rotation()
                    last_rot = time.time()
                    
            except Exception as e:
                print(f"⚠️ Erreur loop : {e}")
            time.sleep(10)

    def clean_string(self, text):
        if not text: return ""
        return re.sub(r'[^a-z0-9]', '', text.lower())

    def format_ms(self, ms):
        if not ms: return "0:00"
        seconds = int((ms / 1000) % 60)
        minutes = int((ms / (1000 * 60)) % 60)
        return f"{minutes}:{seconds:02d}"