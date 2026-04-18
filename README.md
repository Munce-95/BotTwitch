# Bot Twitch Songrequest & Chat Shield 🛡️

Ce bot permet aux viewers de demander des musiques Spotify via le chat Twitch tout en protégeant le stream contre le spam et les bots publicitaires grâce à un système de réputation intelligent.

## 🚀 Installation

1. **Python** : Installe Python 3.10+ (Coche bien la case "Add Python to PATH" sur Windows).
2. **Dépendances** :
   - Windows : Double-clique sur start_bot.bat.
   - Linux/Mac : Lance ./start_bot_linux.sh dans un terminal.
3. **Configuration** :
   - Au premier lancement, le script créera un fichier .env.
   - Remplis-le avec tes identifiants (Spotify Client ID, Token Twitch, etc.).
   - Relance le script. C'est tout.

## 📂 Structure des fichiers

   - **.env** : Tes clés secrètes (ne jamais partager !).
   - **.data/** : Contient ad_bot_suspicion.txt pour le filtrage des bots.
   - **requirements.txt** : Liste des outils (géré automatiquement par le script).

## 🛡️ Le Système Shield (Réputation)

Le bot gère automatiquement la confiance accordée aux viewers pour éviter les faux positifs :

- 🔴**Niveau -1 (Banni)** : Accès interdit. Le compte est un bot a 99% sûr
- 🟠**Niveau 0 (Suspect)** : Accès restreint. Doit envoyer 3 messages sains pour remonter au Niveau 1.
- 🟡**Niveau 1 (Nouveau)** : Nouveau venu. Limité à 3 messages de spam ou gibberish avant d'être sanctionné (TimeOut).
- 🟢**Niveau 2 (Habitué)** : Confiance acquise après 50 messages. Tolérance de spam étendue (7 messages) et immunité sur les mots-clés liés à l'art (portfolio, designer, etc.).
- 💎**Niveau 3 (Admin/Modo)** : Immunité totale contre tous les filtres de sécurité.

**Fonctionnalités clés du Shield :**
- **Priorité Whitelist** : Les liens Spotify, YouTube et Twitch ne sont JAMAIS bloqués.
- **Protection Mots Courts** : Empêche les bannissements accidentels (ex: le mot "art" dans "carte" est ignoré, mais "art" tout seul est détecté).
- **Purge Automatique** : Supprime les utilisateurs inactifs (Niveau 0 ou 1) après 30 jours d'absence pour garder une base de données fluide.

## 🎵 Commandes du Chat

### Pour les Viewers
- **!sr "nom ou lien"** : Cherche et ajoute une musique à la playlist.
- **!wrongsong** : Supprime la dernière chanson que tu as ajoutée.
- **!song** : Affiche le titre et l'artiste de la musique actuelle.
- **!playlist** : Envoie le lien Spotify de la playlist du stream.

### Pour les Modérateurs & Admins
- **!skipsong** : Passe instantanément à la musique suivante sur Spotify.
- **!wrongsong "titre"** : Supprime une musique spécifique de la playlist par son nom.
- **!shield reload** : Recharge la blacklist (ad_bot_suspicion.txt) sans redémarrer le bot.

## ⚙️ Configuration (Fichier .env)

- **SPOTIFY_CLIENT_ID / SECRET** : Tes identifiants Spotify Developer.
- **PLAYLIST_ID** : L'ID de 22 caractères de ta playlist Spotify.
- **TWITCH_TOKEN** : Ton token OAuth Twitch (commençant par oauth:).
- **ADMINS** : Liste des pseudos (en minuscules) autorisés à modérer.

## 🛠️ Dépannage

- **Erreur 400 (Base62 ID)** : L'ID de ta playlist est mal copié dans .env.
- **Erreur 403 (Forbidden)** : Ton compte n'est pas ajouté dans la section "Users and Access" de ton application sur le Dashboard Spotify Developer.
- **Le bot ne fait rien** : Spotify doit être en cours de lecture sur l'un de tes appareils (PC, Mobile, Console) pour que le bot puisse interagir avec la file d'attente.
- **Faux positifs** : Si un viewer est banni par erreur, vérifie si un mot dans 'ad_bot_suspicion.txt' n'est pas trop court ou ajoute le mot dans la liste 'art_keywords' de 'shield.py'."""
