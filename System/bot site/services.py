import importlib.util
import json
import os
import tempfile
import time
import warnings
from datetime import datetime
from pathlib import Path
import shutil

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")
import requests
from PIL import Image, ImageDraw, ImageFont

import config


def ping_groq():
    if not config.GROQ_API_KEY:
        return False, "GROQ_API_KEY не задан."

    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.GROQ_MODEL,
        "messages": [{"role": "user", "content": "Ответь одним словом: ok"}],
        "temperature": 0,
        "max_tokens": 8,
    }

    started = time.perf_counter()
    try:
        response = requests.post(config.GROQ_URL, headers=headers, json=payload, timeout=20)
        elapsed = time.perf_counter() - started
    except Exception as error:
        return False, f"Запрос не удался: {error}"

    if response.status_code != 200:
        return False, f"HTTP {response.status_code}: {response.text[:300]}"

    try:
        data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()
    except Exception as error:
        return False, f"Не удалось разобрать ответ: {error}"

    return True, f"Groq отвечает. Модель: {config.GROQ_MODEL}\nЗадержка: {elapsed:.2f} сек\nОтвет: {answer}"


def fetch_site_status(timeout=12):
    started = time.perf_counter()
    try:
        response = requests.get(config.SITE_BASE_URL, timeout=timeout)
        elapsed = time.perf_counter() - started
        body = response.text[:200]
        return {
            "ok": response.status_code == 200,
            "status_code": response.status_code,
            "elapsed": elapsed,
            "body": body,
            "error": None,
        }
    except Exception as error:
        return {
            "ok": False,
            "status_code": None,
            "elapsed": None,
            "body": "",
            "error": str(error),
        }


def refresh_site_catalog():
    try:
        response = requests.get(f"{config.SITE_BASE_URL}/api/stats", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def next_folder(base_dir, prefix):
    base_dir.mkdir(parents=True, exist_ok=True)
    max_index = 0
    for path in base_dir.iterdir():
        if path.is_dir() and path.name.startswith(prefix):
            tail = path.name.replace(prefix, "", 1)
            if tail.isdigit():
                max_index = max(max_index, int(tail))
    return base_dir / f"{prefix}{max_index + 1}"


def load_uzum_tools():
    module_path = config.SCRAPERS_DIR / "uzum.py"
    if not module_path.exists():
        raise ValueError("Не найден images/scrapers/uzum.py для импорта товара по ссылке.")
    previous_cwd = Path.cwd()
    try:
        spec = importlib.util.spec_from_file_location("spd_uzum_tools", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        os.chdir(previous_cwd)


def remember_uzum_link(url):
    links = []
    if config.UZ_LINKS_FILE.exists():
        try:
            with config.UZ_LINKS_FILE.open("r", encoding="utf-8") as file:
                links = json.load(file)
        except (json.JSONDecodeError, OSError):
            links = []
    if not isinstance(links, list):
        links = []
    if url not in links:
        links.append(url)
        tmp_path = config.UZ_LINKS_FILE.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(links, file, ensure_ascii=False, indent=2)
            file.write("\n")
        tmp_path.replace(config.UZ_LINKS_FILE)


def import_uzum_product_from_url(url):
    clean_url = (url or "").strip()
    if "uzum.uz" not in clean_url:
        raise ValueError("Пока автоматический импорт поддерживает только ссылки Uzum.")

    uzum = load_uzum_tools()
    product = uzum.parse_uzum_product(clean_url)
    if not product or not product.get("name"):
        raise ValueError("Не получилось прочитать товар по ссылке. Проверьте URL или попробуйте позже.")

    folder_path = next_folder(config.UZUM_IMAGES_DIR, "item_")
    folder_path.mkdir(parents=True, exist_ok=True)
    uzum.save_product_json(str(folder_path), product)

    saved = 0
    for index, image_url in enumerate(product.get("images") or [], start=1):
        suffix = Path(image_url.split("?")[0]).suffix.lower().lstrip(".") or "jpg"
        if suffix not in {"jpg", "jpeg", "png", "webp"}:
            suffix = "jpg"
        if uzum.download_image(image_url, str(folder_path), f"{index}.{suffix}"):
            saved += 1

    remember_uzum_link(clean_url)
    refresh_site_catalog()
    return {
        "name": product.get("name"),
        "sku": product.get("sku") or product.get("product_id"),
        "folder": folder_path.name,
        "images": saved,
    }


def _font(size):
    for path in [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]:
        font_path = Path(path)
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def create_status_proof_image(title, status_payload):
    width, height = 1280, 720
    image = Image.new("RGB", (width, height), "#07151d")
    draw = ImageDraw.Draw(image)

    draw.ellipse((840, -90, 1280, 350), fill="#123847")
    draw.ellipse((-90, 420, 320, 860), fill="#163440")
    draw.rounded_rectangle((70, 70, 1210, 650), radius=36, fill="#0d202a", outline="#245968", width=2)

    title_font = _font(58)
    subtitle_font = _font(30)
    body_font = _font(24)
    small_font = _font(20)

    accent = "#48e0cf" if status_payload["ok"] else "#ffd082"
    state_text = "Сайт отвечает" if status_payload["ok"] else "Сайт заблокирован или недоступен"
    state_code = status_payload["status_code"] if status_payload["status_code"] is not None else "ERR"
    error_line = status_payload["error"] or state_text
    body_preview = status_payload["body"].replace("\n", " ").strip()[:120] or "Тело ответа скрыто"

    draw.text((120, 120), title, font=title_font, fill="#f2ffff")
    draw.text((120, 198), state_text, font=subtitle_font, fill=accent)

    draw.rounded_rectangle((120, 260, 1160, 360), radius=26, fill="#102935", outline="#214d5a", width=2)
    draw.text((160, 292), f"URL: {config.SITE_BASE_URL}", font=body_font, fill="#d3edf0")
    draw.text((160, 326), f"HTTP статус: {state_code}", font=body_font, fill="#d3edf0")

    draw.rounded_rectangle((120, 392, 1160, 540), radius=26, fill="#0c2530", outline="#1b4250", width=2)
    draw.text((160, 424), f"Проверено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", font=body_font, fill="#eefeff")
    draw.text((160, 460), f"Время ответа: {status_payload['elapsed']:.2f} сек" if status_payload["elapsed"] else "Время ответа: недоступно", font=body_font, fill="#d3edf0")
    draw.text((160, 496), error_line[:78], font=small_font, fill="#a8cbd0")

    draw.text((120, 586), f"Фрагмент ответа: {body_preview}", font=small_font, fill="#88acb3")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.close()
    image.save(tmp.name, format="PNG")
    return tmp.name


def resolve_site_relative_path(raw_path, fallback_name=None):
    candidate = (raw_path or "").strip()
    if not candidate:
        candidate = (fallback_name or "").strip()
    if not candidate:
        raise ValueError("Не указан путь файла. Добавьте его в caption, например: catalog/ai.js")

    target_path = (config.SITE_DIR / candidate).resolve()
    site_root = config.SITE_DIR.resolve()
    if site_root not in [target_path, *target_path.parents]:
        raise ValueError("Путь выходит за пределы папки site и запрещён.")
    if target_path.suffix.lower() not in config.ALLOWED_SITE_FILE_EXTENSIONS:
        raise ValueError("Можно заменять только файлы html, css, js, py и json.")
    return target_path, target_path.relative_to(site_root)


def refresh_site_backup():
    backup_dir = config.BACKUP_DIR

    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    shutil.copytree(config.SITE_DIR, backup_dir, dirs_exist_ok=False)
    return backup_dir


def create_backup_archive():
    backup_dir = config.BACKUP_DIR
    archive_path = config.BACKUP_ARCHIVE
    if not backup_dir.exists():
        raise ValueError("Папка backup пока не создана. Сначала обновите или сохраните сайт.")
    if archive_path.exists():
        archive_path.unlink()
    shutil.make_archive(str(archive_path.with_suffix("")), "zip", root_dir=backup_dir)
    return archive_path


def remove_backup_archive():
    if config.BACKUP_ARCHIVE.exists():
        config.BACKUP_ARCHIVE.unlink()


def restore_site_from_backup():
    backup_dir = config.BACKUP_DIR
    if not backup_dir.exists():
        raise ValueError("Backup не найден. Сначала создайте его обновлением файла.")
    if config.SITE_DIR.exists():
        shutil.rmtree(config.SITE_DIR)
    shutil.copytree(backup_dir, config.SITE_DIR, dirs_exist_ok=False)
    return config.SITE_DIR


def get_site_file_option(option_id):
    for option in config.SITE_FILE_OPTIONS:
        if option["id"] == option_id:
            return option
    raise ValueError("Неизвестный файл для замены.")


def resolve_product_image(image_path):
    value = (image_path or "").strip()
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("/images/"):
        local_path = config.SYSTEM_DIR / value.lstrip("/")
        return local_path if local_path.exists() else None
    local_path = config.SITE_DIR / value.lstrip("/")
    return local_path if local_path.exists() else None


async def save_telegram_product_image(file_id, bot, original_name=None):
    uploads_dir = config.SYSTEM_DIR / "images" / "manual_uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_name or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    filename = f"product_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{suffix}"
    target_path = uploads_dir / filename
    telegram_file = await bot.get_file(file_id)
    await telegram_file.download_to_drive(custom_path=str(target_path))
    return f"/images/manual_uploads/{filename}"


async def replace_site_file_from_telegram(document, bot, raw_target_path):
    target_path, relative_path = resolve_site_relative_path(raw_target_path, document.file_name)
    incoming_suffix = Path(document.file_name or "").suffix.lower()
    if incoming_suffix and incoming_suffix != target_path.suffix.lower():
        raise ValueError(
            f"Тип файла не совпадает. Для {relative_path} нужен файл {target_path.suffix.lower()}."
        )
    refresh_site_backup()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    telegram_file = await bot.get_file(document.file_id)
    await telegram_file.download_to_drive(custom_path=str(target_path))

    return {
        "target_path": target_path,
        "relative_path": str(relative_path),
        "backup_dir": config.BACKUP_DIR,
    }
