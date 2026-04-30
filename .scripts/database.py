import os
import json
from supabase import create_client, Client

class DatabaseManager:
    def __init__(self):
        # Récupération des informations de connexion
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            print("❌ ERREUR : SUPABASE_URL ou SUPABASE_KEY manquante dans le .env")
            
        self.supabase: Client = create_client(url, key)
        
        # Identifiants dynamiques pour le multi-streamer
        self.twitch_id = os.getenv("TWITCH_CHANNEL").lower().replace("-", "_")
        self.music_table = os.getenv("MUSIC_TABLE", "music_cache")
        self.listened_column = f"listened_{self.twitch_id}"
        self.viewer_table = f"viewers_{self.twitch_id}"

    def initialize_infrastructure(self):
        """Crée automatiquement les tables et colonnes si elles n'existent pas."""
        print(f"[DB] Initialisation de l'infrastructure pour {self.twitch_id}...")
        try:
            # 1. Créer la table musique de base
            self.supabase.rpc('create_music_table_if_not_exists', {
                'table_name': self.music_table
            }).execute()

            # 2. Ajouter la colonne spécifique listened_XXX
            self.supabase.rpc('add_column_if_not_exists', {
                't_name': self.music_table,
                'c_name': self.listened_column,
                'c_type': 'int4 DEFAULT 0'
            }).execute()

            # 3. Créer la table des viewers
            self.supabase.rpc('create_viewer_table', {
                'table_name': self.viewer_table
            }).execute()

            print("[DB] Infrastructure validée avec succès.")
            return True
        except Exception as e:
            print(f"[DB] Erreur d'initialisation : {e}")
            return False

    def migrate_legacy_data(self):
        """Transfère music_cache.json vers Supabase si le fichier existe."""
        json_file = 'music_cache.json'
        
        if not os.path.exists(json_file):
            return

        print(f"[Migration] Fichier {json_file} détecté. Début du transfert...")

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data:
                print("[Migration] Fichier vide.")
                return

            entries = []
            for uri, info in data.items():
                entries.append({
                    "uri": uri,
                    "title": info.get("title", "Unknown"),
                    "artist": info.get("artist", "Unknown"),
                    "yt_id": info.get("yt_id"),
                    "duration": info.get("duration", 0),
                    "is_blacklisted": info.get("is_blacklisted", False),
                    "is_archived": info.get("is_archived", False),
                    self.listened_column: info.get("listened", 0)
                })

            # Envoi par paquets de 100
            for i in range(0, len(entries), 100):
                batch = entries[i:i+100]
                self.supabase.table(self.music_table).upsert(batch, on_conflict="uri").execute()
                print(f"[Migration] {i + len(batch)} / {len(entries)} titres transférés...")

            # Archivage
            os.rename(json_file, f"{json_file}.bak")
            print(f"[Migration] Terminée. {json_file} renommé en .bak")

        except Exception as e:
            print(f"[Migration] Erreur : {e}")