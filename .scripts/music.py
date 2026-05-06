# type: ignore
# music.py - v1.5.10 | Final Fix: Unified Threading & Command Handler
import os
import json
import time
import shutil
import threading
import spotipy
import asyncio
import re
from googleapiclient.discovery import build
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
        
        self.yt_api_key = os.getenv("YOUTUBE_API_KEY")
        self.youtube = build('youtube', 'v3', developerKey=self.yt_api_key)
        
        self.db_dir = ".data/database"
        self.config_dir = ".data/config"
        self.queue_file = os.path.join(self.db_dir, "queue.json")
        self.msg_file = os.path.join(self.config_dir, "messages.json")
        
        os.makedirs(self.db_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        
        if not os.path.exists(self.queue_file):
            self._save_queue([]) 

        self.messages = self._setup_messages()
        self.last_track_uri = None
        self.running = True

    # --- INITIALISATION & MESSAGES ---
    def _setup_messages(self):
        if not os.path.exists(self.msg_file): return {}
        try:
            with open(self.msg_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}

    def _get_msg(self, key, **kwargs):
        msg = self.messages.get(key, f"Missing_msg:{key}")
        try: return msg.format(**kwargs)
        except: return msg

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

    # --- DB & BLACKLIST ---
    def save_to_cache(self, title, artist, track_uri, duration=None, blacklist_it=None, archived_it=None, increment_listen=False, yt_id=None):
        try:
            data = {"uri": track_uri, "title": title, "artist": artist, "duration": format_ms(duration) if isinstance(duration, int) else duration}
            if blacklist_it is not None: data["is_blacklisted"] = blacklist_it
            if archived_it is not None: data["is_archived"] = archived_it
            if yt_id: data["yt_id"] = yt_id 
            self.db.supabase.table(self.db.music_table).upsert(data, on_conflict="uri").execute()
            if increment_listen:
                self.db.supabase.rpc('increment_listen_count', {'t_name': self.db.music_table, 'c_name': self.db.listened_column, 'target_uri': track_uri}).execute()
        except Exception as e: print(f"[DB Error]: {e}")

    def is_blacklisted(self, uri, title):
        try:
            res = self.db.supabase.table(self.db.music_table).select("is_blacklisted").or_(f"uri.eq.{uri},title.ilike.{title}").execute()
            return any(item.get('is_blacklisted') for item in res.data)
        except: return False

    # --- YOUTUBE INFO ---
    def get_youtube_info(self, video_id):
        try:
            request = self.youtube.videos().list(part="snippet", id=video_id)
            response = request.execute()
            if not response['items']: return None
            s = response['items'][0]['snippet']
            return {"title": s['title'], "search_query": f"{s['title']} {s['channelTitle']}"}
        except: return None

    # --- CORE PROCESSING (THREADED) ---
    def process_request_async(self, user, source_type, data, send_msg):
        """Gère Spotify, YouTube et Texte dans un thread séparé."""
        try:
            track_info = None
            yt_id_to_save = None

            if source_type == "YOUTUBE_LINK":
                yt_id_to_save = data
                yt_info = self.get_youtube_info(data)
                if not yt_info: return send_msg(f"❌ @{user}, lien YouTube invalide.")
                results = self.sp.search(q=yt_info['search_query'], type='track', limit=1)
                tracks = results.get('tracks', {}).get('items', [])
                if not tracks: return send_msg(f"❌ @{user}, introuvable sur Spotify.")
                t = tracks[0]
                track_info = {'uri': t['uri'], 'name': t['name'], 'artist': t['artists'][0]['name'], 'duration': t['duration_ms']}

            elif source_type == "SPOTIFY_LINK":
                t = self.sp.track(data)
                track_info = {'uri': t['uri'], 'name': t['name'], 'artist': t['artists'][0]['name'], 'duration': t['duration_ms']}

            else: # TEXT_QUERY
                results = self.sp.search(q=data, type='track', limit=1)
                if results and results['tracks']['items']:
                    t = results['tracks']['items'][0]
                    track_info = {'uri': t['uri'], 'name': t['name'], 'artist': t['artists'][0]['name'], 'duration': t['duration_ms']}

            if not track_info: return send_msg(f"❌ @{user}, introuvable.")
            if track_info['duration'] > 600000: return send_msg(f"⚠️ @{user}, trop long.")
            if self.is_blacklisted(track_info['uri'], track_info['name']): return send_msg(f"🚫 @{user}, banni.")
            
            queue_data = self._load_queue()
            if any(m['uri'] == track_info['uri'] for m in queue_data): return send_msg(f"@{user}, déjà dans la file !")

            queue_data.append({'user': user, **track_info})
            self._save_queue(queue_data)
            self.save_to_cache(track_info['name'], track_info['artist'], track_info['uri'], duration=track_info['duration'], yt_id=yt_id_to_save)
            
            send_msg(self._get_msg("sr_msg", user=user, title=track_info['name'], artist=track_info['artist'], pos=len(queue_data)))

        except Exception as e:
            print(f"Async Error: {e}")
            send_msg(f"⚠️ @{user}, erreur lors du traitement.")

    # --- COMMAND HANDLERS ---
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

        source_type, data = identify_sr_type(query)
        threading.Thread(target=self.process_request_async, args=(user, source_type, data, send_msg), daemon=True).start()

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
        except Exception as e: 
            print(f"Skip Error: {e}")
            callback("❌ Erreur skip.")

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
        print("🎶 MusicManager v1.5.10 prêt.")

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