import subprocess
import sys
import threading
import queue
import time
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.dirname(SCRIPT_DIR)
BASE_DIR = os.path.dirname(IMAGES_DIR)

def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except:
        return 80

def print_header(title):
    width = get_terminal_width()
    dash_count = max(0, width - len(title) - 2)
    print("\n" + "─" * dash_count + " " + title + " " + "─" * dash_count)

def print_footer(title):
    width = get_terminal_width()
    dash_count = max(0, width - len(title) - 2)
    print("─" * dash_count + " " + title + " " + "─" * dash_count + "\n")

def reader(proc, prefix, q):
    for line in iter(proc.stdout.readline, ''):
        q.put((prefix, line.strip()))
    proc.stdout.close()

def run_parallel():
    yandex_script = os.path.join(SCRIPT_DIR, "yandex.py")
    uzum_script = os.path.join(SCRIPT_DIR, "uzum.py")
    yandex_proc = subprocess.Popen([sys.executable, yandex_script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    uzum_proc = subprocess.Popen([sys.executable, uzum_script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    q = queue.Queue()
    yandex_thread = threading.Thread(target=reader, args=(yandex_proc, "YANDEX", q))
    uzum_thread = threading.Thread(target=reader, args=(uzum_proc, "UZUM", q))
    yandex_thread.start()
    uzum_thread.start()

    yandex_done = False
    uzum_done = False

    while not (yandex_done and uzum_done):
        try:
            prefix, line = q.get(timeout=0.1)
        except queue.Empty:
            if yandex_proc.poll() is not None and not yandex_done:
                yandex_done = True
                yandex_thread.join(timeout=0.5)
            if uzum_proc.poll() is not None and not uzum_done:
                uzum_done = True
                uzum_thread.join(timeout=0.5)
            continue

        if prefix == "YANDEX":
            if line.startswith("YANDEX_LOADING"):
                print_header("ЯНДЕКС МАРКЕТ")
                print("⏳ Загрузка товаров...")
            elif line.startswith("YANDEX_COUNT"):
                count = line.split()[1]
                print(f"📦 Найдено товаров: {count}")
            elif line.startswith("YANDEX_PROGRESS"):
                progress = line.split()[1]
                print(f"📸 Обработано {progress} товаров...")
            elif line.startswith("YANDEX_END"):
                parts = line.split()
                if len(parts) >= 3:
                    count, photos = parts[1], parts[2]
                    print(f"✅ Завершено: {count} товаров, скачано {photos} фото")
                print_footer("ЯНДЕКС МАРКЕТ")
            elif line:
                print(f"[Яндекс] {line}")
        elif prefix == "UZUM":
            if line.startswith("UZUM_LOADING"):
                parts = line.split()
                count = parts[1] if len(parts) > 1 else "?"
                print_header("UZUM")
                print(f"🔗 Загружено ссылок: {count}")
            elif line.startswith("UZUM_PROGRESS"):
                progress = line.split()[1]
                print(f"🛒 Обработано {progress} товаров...")
            elif line.startswith("UZUM_END"):
                parts = line.split()
                if len(parts) >= 3:
                    count, photos = parts[1], parts[2]
                    print(f"✅ Завершено: {count} товаров, скачано {photos} фото")
                print_footer("UZUM")
            elif line:
                print(f"[Uzum] {line}")

    yandex_proc.wait()
    uzum_proc.wait()
    print("\n🎉 Парсинг завершён. Сборка данных для сайта...")
    # Запускаем сборщик данных, который лежит в папке site (на уровень выше)
    build_script = os.path.join(BASE_DIR, "site", "build_site_data.py")
    if os.path.exists(build_script):
        result = subprocess.run([sys.executable, build_script], capture_output=False)
        if result.returncode == 0:
            print("✅ Данные для сайта обновлены.")
        else:
            print("⚠️ Ошибка при обновлении данных сайта.")
    else:
        print(f"⚠️ Файл {build_script} не найден. Сайт не обновлён.")

if __name__ == "__main__":
    run_parallel()
