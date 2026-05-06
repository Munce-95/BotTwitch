# type: ignore
# commands.py

def handle_command(bot, user, message, l_msg, tags, is_privileged):
    """
    Gestionnaire central des commandes (!) - v1.4.4 | Maitrise des données
    """
    ts = bot.get_timestamp()

    # --- 1. COMMANDES MUSIQUE (Délégation au MusicManager) ---
    music_cmds = ['!sr', '!song', '!skipsong', '!wrongsong', '!playlist', '!queue', '!clearqueue']
    
    if any(l_msg.startswith(cmd) for cmd in music_cmds):
        if bot.music.process_command(user, message, l_msg, tags, is_privileged, bot.send_msg):
            return True

    # --- 2. COMMANDES SYSTÈME (Admins/Modos/VIP) ---
    if not is_privileged:
        return False 

    # !ping
    if l_msg == '!ping':
        bot.send_msg(f"Pong! 🏓")
        return True
    
    # !version
    if l_msg == '!version':
        bot.send_msg(f"@{user} > Bot Version v1.5.10 | Base de données Supabase et Lien YouTube !")
        return True

    # !setlevel @user niveau (Shield Management + Auto Unban)
    if l_msg.startswith('!setlevel '):
        parts = message.split(' ')
        if len(parts) >= 3:
            target = parts[1].replace('@', '').lower()
            try:
                new_lvl = int(parts[2])
                
                # Mise à jour dans le Shield (JSON)
                bot.shield.update_user(target, new_score=new_lvl)
                
                # Unban Twitch automatique (silencieux)
                if new_lvl >= 0:
                    bot.send_msg(f"/unban {target}")
                
                bot.send_msg(f"⚙️ Niveau de @{target} actualisé.")
                
            except ValueError:
                bot.send_msg(f"❌ Erreur : Le niveau doit être un chiffre.")
        return True

    return False