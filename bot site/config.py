# SYSTEM/bot site/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из папки бота
ENV_FILE = Path(__file__).parent / '.env'
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# ============ ТОКЕН БОТА ============
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env файле!")

BOT_NAME = "Sweet Pillow Dreams Admin"

# ============ GROQ API ============
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv('GROQ_MODEL', 'meta-llama/llama-4-scout-17b-16e-instruct')

# ============ ДОСТУП ============
ALLOWED_USER_IDS = {int(x.strip()) for x in os.getenv('ALLOWED_USER_IDS', '').split(',') if x.strip()}
if not ALLOWED_USER_IDS:
    raise ValueError("ALLOWED_USER_IDS не задан в .env файле!")

# ============ САЙТ ============
SITE_BASE_URL = os.getenv('SITE_BASE_URL', 'http://127.0.0.1:8000')
SITE_PUBLIC_PRODUCT_PATH = "/catalog"

# ============ ПУТИ ============
BASE_DIR = Path(__file__).resolve().parent.parent
SYSTEM_DIR = BASE_DIR
SITE_DIR = SYSTEM_DIR / 'site'
IMAGES_DIR = SYSTEM_DIR / 'images'
PRODUCTS_DIR = IMAGES_DIR / 'products'
YANDEX_IMAGES_DIR = PRODUCTS_DIR / 'yandex'
UZUM_IMAGES_DIR = PRODUCTS_DIR / 'uzum'
MANUAL_IMAGES_DIR = PRODUCTS_DIR / 'manual'
SCRAPERS_DIR = IMAGES_DIR / 'scrapers'
UZ_LINKS_FILE = IMAGES_DIR / 'uz_links.json'
DATA_DIR = SITE_DIR / 'data'
BACKUP_DIR = SITE_DIR / 'backup'
BACKUP_ARCHIVE = SITE_DIR / 'backup_site.zip'
SITE_STATE_FILE = DATA_DIR / 'site_state.json'

# ============ НАСТРОЙКИ ПО УМОЛЧАНИЮ ============
DEFAULT_SELLER = "Sweet Pillow Dreams"
DEFAULT_CURRENCY = "UZS"
DEFAULT_SOURCE = "manual"

DEFAULT_MAINTENANCE_STATE = {
    "enabled": False,
    "title": "Идут технические работы",
    "message": "Мы обновляем сайт Sweet Pillow Dreams. Пожалуйста, зайдите чуть позже.",
    "updated_at": None,
}

ALLOWED_SITE_FILE_EXTENSIONS = {".html", ".css", ".js", ".py", ".json"}

SITE_FILE_OPTIONS = [
    {"id": "home_html", "path": "index.html", "label": "Главная HTML", "description": "Главная страница сайта."},
    {"id": "home_css", "path": "style.css", "label": "Главная CSS", "description": "Главные стили."},
    {"id": "server_py", "path": "server.py", "label": "Flask сервер", "description": "Сервер сайта."},
    {"id": "maintenance_html", "path": "maintenance.html", "label": "Техработы HTML", "description": "Страница техработ."},
    {"id": "catalog_html", "path": "catalog/index.html", "label": "Каталог HTML", "description": "Каталог товаров."},
    {"id": "catalog_css", "path": "catalog/style.css", "label": "Каталог CSS", "description": "Стили каталога."},
    {"id": "catalog_js", "path": "catalog/script.js", "label": "Каталог JS", "description": "Логика каталога."},
    {"id": "catalog_ai_js", "path": "catalog/ai.js", "label": "AI логика", "description": "Логика помощника."},
    {"id": "product_html", "path": "catalog/product.html", "label": "Товар HTML", "description": "Страница товара."},
    {"id": "cart_html", "path": "catalog/cart.html", "label": "Корзина HTML", "description": "Страница корзины."},
    {"id": "products_json", "path": "data/products_cache.json", "label": "Товары JSON", "description": "Кэш каталога."},
]
PRODUCTS_FILE = DATA_DIR / 'products.json'
MAINTENANCE_FILE = DATA_DIR / 'maintenance.json'