# type: ignore
import os
import json
from supabase import create_client, Client

class DatabaseManager:
    def __init__(self):
        # Récupération et vérification stricte des clés
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        channel = os.getenv("TWITCH_CHANNEL")

        if not url or not key or not channel:
            print("❌ ERREUR CRITIQUE : Configuration Supabase ou Twitch manquante dans le .env")
            raise ValueError("Le bot ne peut pas démarrer sans SUPABASE_URL, SUPABASE_KEY et TWITCH_CHANNEL.")
            
        self.supabase: Client = create_client(url, key)
        
        # Identifiants dynamiques
        self.twitch_id = channel.lower().replace("-", "_")
        self.music_table = os.getenv("MUSIC_TABLE", "music_cache")
        self.listened_column = f"listened_{self.twitch_id}"
        self.viewer_table = f"viewers_{self.twitch_id}"

    def initialize_infrastructure(self):
        """Crée automatiquement les tables et colonnes si elles n'existent pas."""
        print(f"--- [DB] Initialisation pour {self.twitch_id} ---")
        try:
            # 1. Créer la table musique (via RPC)
            self.supabase.rpc('create_music_table_if_not_exists', {
                'table_name': self.music_table
            }).execute()

            # 2. Ajouter la colonne spécifique d'écoute pour ce streamer
            self.supabase.rpc('add_column_if_not_exists', {
                't_name': self.music_table,
                'c_name': self.listened_column,
                'c_type': 'int4 DEFAULT 0'
            }).execute()

            # 3. Créer la table des viewers spécifique au streamer
            self.supabase.rpc('create_viewer_table', {
                'table_name': self.viewer_table
            }).execute()

            print("✅ [DB] Infrastructure prête et synchronisée.")
            
            # 4. Lancer la migration
            self.migrate_legacy_data()
            
            return True
        except Exception as e:
            print(f"❌ [DB] Erreur lors de la configuration : {e}")
            return False

    def migrate_legacy_data(self):
        """Transfère music_cache.json vers Supabase."""
        # On définit le chemin exact que tu m'as donné
        json_file = '.data/database/music_cache.json'
        
        # On vérifie aussi à la racine au cas où
        if not os.path.exists(json_file):
            json_file = 'music_cache.json'
            if not os.path.exists(json_file):
                return

        print(f"📦 [Migration] Fichier détecté dans : {json_file}")
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data:
                print("[Migration] Le fichier est vide.")
                return

            entries = []
            # Gestion Dict ou Liste
            items = data.items() if isinstance(data, dict) else [(i.get('uri'), i) for i in data if i.get('uri')]

            for uri, info in items:
                if not uri: continue
                entries.append({
                    "uri": uri,
                    "title": info.get("title", "Unknown"),
                    "artist": info.get("artist", "Unknown"),
                    "yt_id": info.get("yt_id"),
                    "duration": str(info.get("duration", "0:00")),
                    "is_blacklisted": info.get("is_blacklisted", False),
                    "is_archived": info.get("is_archived", False),
                    self.listened_column: info.get("listened", 0)
                })

            if entries:
                print(f"🚀 [Migration] Transfert de {len(entries)} titres vers Supabase...")
                for i in range(0, len(entries), 100):
                    batch = entries[i:i+100]
                    self.supabase.table(self.music_table).upsert(batch, on_conflict="uri").execute()

                # On renomme le fichier pour éviter de migrer à chaque redémarrage
                os.rename(json_file, f"{json_file}.bak")
                print(f"✅ [Migration] Terminée. Fichier renommé en .bak")
            
        except Exception as e:
            print(f"⚠️ [Migration] Erreur : {e}")