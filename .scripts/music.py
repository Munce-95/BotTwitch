# type: ignore
# music.py - v1.5.6 | YouTube Integration Step 4 - Spotify Bridge
import os
import json
import time
import shutil
import threading
import spotipy
import asyncio
from googleapiclient.discovery import build
# Importation des utilitaires
from utils import identify_sr_type, clean_string, format_ms

class MusicManager:
    def __init__(self, sp, playlist_id, archive_id, admin_list, limit_user, limit_modo, db_manager):
        self.sp = sp
        self.playlist_id = playlist_id
        self.archive_id = archive_id
        self.admins = admin_list
        self.limit_user = limit_user
        self.limit_modo = limit_modo
        self.db = db_manager 
        
        # Initialisation API YouTube (Récupérée du .env)
        self.yt_api_key = os.getenv("YOUTUBE_API_KEY")
        self.youtube = build('youtube', 'v3', developerKey=self.yt_api_key)
        
        # Chemins
        self.db_dir = ".data/database"
        self.config_dir = ".data/config"
        self.queue_file = os.path.join(self.db_dir, "queue.json")
        self.msg_file = os.path.join(self.config_dir, "messages.json")
        self.msg_example = os.path.join(self.config_dir, "messages.json.example")
        
        os.makedirs(self.db_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        
        if not os.path.exists(self.queue_file):
            self._save_queue([]) 

        self.messages = self._setup_messages()
        self.last_track_uri = None
        self.running = True

    # --- INITIALISATION & MESSAGES ---
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

    # --- PERSISTANCE QUEUE (LOCAL) ---
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

    # --- GESTION CACHE & DB (SUPABASE) ---
    def save_to_cache(self, title, artist, track_uri, duration=None, blacklist_it=None, archived_it=None, increment_listen=False, yt_id=None):
        try:
            data = {
                "uri": track_uri,
                "title": title,
                "artist": artist,
                "duration": format_ms(duration) if isinstance(duration, int) else duration
            }
            if blacklist_it is not None: data["is_blacklisted"] = blacklist_it
            if archived_it is not None: data["is_archived"] = archived_it
            if yt_id: data["yt_id"] = yt_id 
            
            self.db.supabase.table(self.db.music_table).upsert(data, on_conflict="uri").execute()

            if increment_listen:
                self.db.supabase.rpc('increment_listen_count', {
                    't_name': self.db.music_table,
                    'c_name': self.db.listened_column,
                    'target_uri': track_uri
                }).execute()
        except Exception as e:
            print(f"[DB Error] save_to_cache: {e}")

    def is_blacklisted(self, uri, title):
        try:
            res = self.db.supabase.table(self.db.music_table)\
                .select("is_blacklisted")\
                .or_(f"uri.eq.{uri},title.ilike.{title}")\
                .execute()
            return any(item.get('is_blacklisted') for item in res.data)
        except: return False

    # --- YOUTUBE LOGIC (ÉTAPE 2, 3 & 4) ---
    def check_youtube_db(self, yt_id):
        """Vérifie l'ID dans la colonne yt_id de Supabase."""
        try:
            res = self.db.supabase.table(self.db.music_table)\
                .select("is_blacklisted")\
                .eq("yt_id", yt_id)\
                .execute()
            if res.data:
                return any(item.get('is_blacklisted') for item in res.data)
            return False
        except: return False

    def get_youtube_info(self, video_id):
        """Récupère le titre et la chaîne via l'API Google."""
        try:
            request = self.youtube.videos().list(part="snippet", id=video_id)
            response = request.execute()
            if not response['items']: return None

            snippet = response['items'][0]['snippet']
            return {
                "title": snippet['title'],
                "channel": snippet['channelTitle'],
                "search_query": f"{snippet['title']} {snippet['channelTitle']}"
            }
        except Exception as e:
            print(f"YT API Error: {e}")
            return None

    async def process_youtube_request(self, user, yt_id, send_msg):
        """Workflow Complet YouTube (Étapes 2, 3 & 4)."""
        # ÉTAPE 2 : Check Blacklist/DB par ID YT
        if self.check_youtube_db(yt_id):
            return send_msg(f"🚫 @{user}, ce lien YouTube est banni ou déjà listé.")

        # ÉTAPE 3 : Parsing API YouTube
        yt_data = self.get_youtube_info(yt_id)
        if not yt_data:
            return send_msg(f"❌ @{user}, lien invalide ou privé sur YouTube.")

        # ÉTAPE 4 : Bridge Spotify (Conversion et Ajout)
        try:
            results = self.sp.search(q=yt_data['search_query'], type='track', limit=1)
            tracks = results.get('tracks', {}).get('items', [])

            if not tracks:
                print(f"[YT] : Link found = {yt_data['title']} // NOT FOUND ON SPOTIFY")
                return send_msg(f"❌ @{user}, Spotify ne trouve pas d'équivalent pour : {yt_data['title'][:30]}...")

            t = tracks[0]
            track_info = {
                'uri': t['uri'], 
                'name': t['name'], 
                'artist': t['artists'][0]['name'], 
                'duration': t['duration_ms']
            }

            # Log Terminal Complet pour ton monitoring
            print(f"[YT] : Link found = {yt_data['title']} // FOUND ON SPOTIFY : {track_info['name']}")

            # Vérification Blacklist Spotify & Doublon Queue
            if self.is_blacklisted(track_info['uri'], track_info['name']):
                return send_msg(f"🚫 @{user}, cette musique est bannie sur Spotify.")

            queue_data = self._load_queue()
            if any(m['uri'] == track_info['uri'] for m in queue_data):
                return send_msg(f"@{user}, déjà dans la file !")

            # Ajout final à la queue locale
            queue_data.append({'user': user, **track_info})
            self._save_queue(queue_data)
            
            # Sauvegarde DB avec yt_id (pour que l'étape 2 fonctionne au prochain coup)
            self.save_to_cache(track_info['name'], track_info['artist'], track_info['uri'], 
                               duration=track_info['duration'], yt_id=yt_id)

            send_msg(self._get_msg("sr_msg", user=user, title=track_info['name'], artist=track_info['artist'], pos=len(queue_data)))

        except Exception as e:
            print(f"Error in Step 4: {e}")
            send_msg("⚠️ Erreur lors de la conversion Spotify.")

    # --- COMMANDES ---
    def process_command(self, user, message, l_msg, tags, is_privileged, callback):
        if l_msg.startswith('!sr '):
            self.handle_sr(user, message[4:].strip(), tags, callback)
        elif l_msg == '!song':
            curr = self.sp.current_playback()
            if curr and curr.get('item'):
                t = curr['item']
                artist = t['artists'][0].get('name', 'Inconnu')
                callback(self._get_msg("song_msg", title=t.get('name', 'Sans titre'), artist=artist, timer=format_ms(t.get('duration_ms'))))
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

        try:
            source_type, data = identify_sr_type(query)
            
            if source_type == "YOUTUBE_LINK":
                # --- FIX: Récupération de la boucle pour l'asynchrone ---
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                
                # On planifie l'exécution de la coroutine
                loop.create_task(self.process_youtube_request(user, data, send_msg))
                return

            # --- Logique Spotify Classique ---
            track_info = None
            if source_type == "SPOTIFY_LINK":
                t = self.sp.track(data)
                track_info = {'uri': t['uri'], 'name': t['name'], 'artist': t['artists'][0]['name'], 'duration': t['duration_ms']}
            else: # TEXT_QUERY
                results = self.sp.search(q=data, type='track', limit=1)
                if results and results['tracks']['items']:
                    t = results['tracks']['items'][0]
                    track_info = {'uri': t['uri'], 'name': t['name'], 'artist': t['artists'][0]['name'], 'duration': t['duration_ms']}

            if not track_info: 
                return send_msg("❌ Musique introuvable.")
            
            if track_info['duration'] > 600000: 
                return send_msg(f"⚠️ @{user}, trop long (max 10:00).")
            
            if self.is_blacklisted(track_info['uri'], track_info['name']): 
                return send_msg(f"🚫 @{user}, ce titre est banni.")
            
            if any(m['uri'] == track_info['uri'] for m in queue_data): 
                return send_msg(f"@{user}, déjà dans la file !")

            # Enregistrement
            queue_data.append({
                'user': user, 
                'name': track_info['name'], 
                'artist': track_info['artist'], 
                'uri': track_info['uri'], 
                'duration': track_info['duration']
            })
            self._save_queue(queue_data)
            self.save_to_cache(track_info['name'], track_info['artist'], track_info['uri'], duration=track_info['duration'])
            
            send_msg(self._get_msg("sr_msg", user=user, title=track_info['name'], artist=track_info['artist'], pos=len(queue_data)))
            
        except Exception as e:
            print(f"[SR Error] : {e}")
            send_msg("⚠️ Erreur lors de l'ajout.")

    def handle_skip(self, callback):
        try:
            queue_data = self._load_queue()
            if queue_data:
                next_t = queue_data.pop(0)
                self.sp.playlist_add_items(self.playlist_id, [next_t['uri']])
                self.sp.add_to_queue(next_t['uri'])
                self.sp.next_track()
                self._save_queue(queue_data)
                callback(f"⏭️ Skip ! Titre de @{next_t['user']} : {next_t['name']}")
            else:
                self.sp.next_track()
                callback("⏭️ Skip effectué.")
        except: callback("❌ Erreur skip.")

    def handle_wrongsong(self, user, query, tags, send_msg):
        u_low = user.lower()
        queue_data = self._load_queue()
        if (u_low in self.admins or 'broadcaster' in tags.get('badges', {})) and query:
            new_queue = [m for m in queue_data if clean_string(query) not in clean_string(m['name'])]
            self._save_queue(new_queue)
            return send_msg("🗑️ Retiré par Admin.")
        user_titles = [m for m in queue_data if m['user'].lower() == u_low]
        if user_titles:
            last_uri = user_titles[-1]['uri']
            new_queue = [m for m in queue_data if not (m['user'].lower() == u_low and m['uri'] == last_uri)]
            self._save_queue(new_queue)
            send_msg(f"🗑️ @{user}, dernier titre retiré.")
        else: send_msg(f"⚠️ @{user}, rien à annuler.")

    def handle_clearqueue(self, target, callback):
        if not target or target.lower() == "all":
            self._save_queue([])
            callback("🗑️ File vidée.")
        else:
            t = target.replace('@', '').lower()
            queue_data = self._load_queue()
            new_q = [m for m in queue_data if m['user'].lower() != t]
            self._save_queue(new_q)
            callback(f"🗑️ Queue de @{t} vidée.")

    def start_worker(self):
        threading.Thread(target=self._main_loop, daemon=True).start()
        print("🎶 MusicManager v1.5.6 prêt.")

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
                        next_t = queue_data[0]
                        if next_t['uri'] not in injected_uris:
                            self.sp.playlist_add_items(self.playlist_id, [next_t['uri']])
                            self.sp.add_to_queue(next_t['uri'])
                            injected_uris.add(next_t['uri'])
                            queue_data.pop(0)
                            self._save_queue(queue_data)
                    if uri != self.last_track_uri:
                        self.last_track_uri = uri
                        injected_uris.clear()
                        self.save_to_cache(track.get('name'), track['artists'][0].get('name'), uri, duration=track.get('duration_ms'), increment_listen=True)
                if time.time() - last_rot > 1800:
                    last_rot = time.time()
            except: pass
            time.sleep(10)