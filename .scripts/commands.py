# commands.py

def handle_command(bot, user, message, l_msg, tags, is_privileged):
    """
    Gestionnaire central des commandes (!)
    """
    ts = bot.get_timestamp()

    # --- 1. COMMANDES MUSIQUE (Délégation au MusicManager) ---
    # Ces commandes restent accessibles selon les limites définies dans MusicManager
    music_cmds = ['!sr', '!song', '!skipsong', '!wrongsong', '!playlist']
    if any(l_msg.startswith(cmd) for cmd in music_cmds):
        print(f"[{ts}] 🎵 MUSIC : {user} -> {message}")
        bot.music.process_command(user, message, l_msg, tags, is_privileged, bot.send_msg)
        return True

    # --- 2. COMMANDES SYSTÈME (Réservées Admins/Modos/VIP) ---
    if not is_privileged:
        return False # On ignore la suite si l'utilisateur n'a pas les droits

    if l_msg == '!ping':
        bot.send_msg(f"Pong! 🏓")
        return True
    
    if l_msg == '!version':
        bot.send_msg(f"@{user} > Bot Version v1.4.2 | Architecture : Modulaire")
        return True
    
	# Commande !setlevel @user niveau
    if l_msg.startswith('!setlevel '):
        parts = message.split(' ')
        if len(parts) == 3:
            target = parts[1].replace('@', '').lower()
            try:
                new_lvl = int(parts[2])
                # On appelle update_user du shield via l'objet bot
                bot.shield.update_user(target, new_score=new_lvl)
                bot.send_msg(f"⚙️ [Shield] Le niveau de @{target} est maintenant {new_lvl}.")
            except ValueError:
                bot.send_msg(f"❌ Erreur : Le niveau doit être un chiffre (ex: !setlevel @pseudo 2).")
        return True

    # Si aucune commande n'est reconnue
    return False