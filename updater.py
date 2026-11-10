import os
import sys
import json
import urllib.request
import zipfile
import tempfile
import subprocess
import tkinter as tk
from tkinter import messagebox
import threading

# ВАШИ ДАННЫЕ (замените на свои)
GITHUB_REPO = "BortiStar/TwitchChatReader" 
CURRENT_VERSION = "1.0.0" # Меняйте при каждом релизе

def get_latest_release():
    """Получает информацию о последнем релизе с GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "TCR-Updater"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Ошибка проверки обновлений: {e}")
        return None

def download_and_update(download_url, root_window):
    """Скачивает ZIP и запускает процесс обновления"""
    try:
        # 1. Скачиваем архив во временную папку
        temp_dir = tempfile.gettempdir()
        zip_path = os.path.join(temp_dir, "tcr_update.zip")
        
        req = urllib.request.Request(download_url, headers={"User-Agent": "TCR-Updater"})
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            out_file.write(response.read())
            
        # 2. Создаем BAT-скрипт для замены файлов (так как EXE не может сам себя перезаписать)
        # Определяем папку, где сейчас лежит EXE
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
            exe_name = os.path.basename(sys.executable)
        else:
            # Для запуска из исходников (для тестов)
            app_dir = os.path.dirname(os.path.abspath(__file__))
            exe_name = "TwitchChatReader.exe"

        bat_path = os.path.join(temp_dir, "update_tcr.bat")
        
        # В скрипте ждем 2 секунды (чтобы EXE успел закрыться), распаковываем и запускаем
        bat_content = f"""
@echo off
timeout /t 2 /nobreak > NUL
echo Updating TwitchChatReader...
powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{app_dir}' -Force"
start "" "{os.path.join(app_dir, exe_name)}"
del "%~f0"
"""
        with open(bat_path, "w") as f:
            f.write(bat_content)

        # 3. Запускаем скрипт и закрываем текущее приложение
        subprocess.Popen([bat_path], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        root_window.destroy()
        sys.exit(0)

    except Exception as e:
        messagebox.showerror("Ошибка обновления", f"Не удалось обновить приложение:\n{e}")

def check_for_updates(root_window):
    """Вызывается при старте программы в отдельном потоке"""
    release = get_latest_release()
    if not release:
        return

    latest_version = release.get("tag_name", "").lstrip("v")
    
    if latest_version and latest_version != CURRENT_VERSION:
        # Ищем ZIP-архив в релизе
        download_url = None
        for asset in release.get("assets", []):
            if asset["name"].endswith(".zip"):
                download_url = asset["browser_download_url"]
                break
        
        if not download_url:
            return

        # Показываем окно в главном потоке
        def ask_user():
            answer = messagebox.askyesno(
                "Доступно обновление", 
                f"Доступна новая версия {latest_version}!\nТекущая версия: {CURRENT_VERSION}\n\nСкачать и установить сейчас? (Приложение перезапустится)"
            )
            if answer:
                threading.Thread(target=download_and_update, args=(download_url, root_window), daemon=True).start()
                
        root_window.after(0, ask_user)