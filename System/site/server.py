import os
import json
import hashlib
import logging
import re
import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")
import requests
import time
from flask import Flask, jsonify, redirect, send_from_directory, request, render_template_string
from flask_cors import CORS
from urllib.parse import quote

app = Flask(__name__, static_folder=None)
logging.getLogger('werkzeug').setLevel(logging.ERROR)
app.logger.setLevel(logging.INFO)

ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv(
        'ALLOWED_ORIGINS',
        'http://127.0.0.1:8000,http://localhost:8000,http://192.168.0.107:8000'
    ).split(',') if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = BASE_DIR
SYSTEM_DIR = os.path.dirname(BASE_DIR)
IMAGES_DIR = os.path.join(SYSTEM_DIR, 'images')
PRODUCTS_DIR = os.path.join(IMAGES_DIR, 'products')
DATA_DIR = os.path.join(BASE_DIR, 'data')
BACKUP_DIR = os.path.join(BASE_DIR, 'backup')
PROCESSED_DESC_FILE = os.path.join(DATA_DIR, 'processed_descriptions.json')
CACHE_FILE = os.path.join(DATA_DIR, 'products_cache.json')
MAINTENANCE_FILE = os.path.join(DATA_DIR, 'maintenance_state.json')
STATE_FILE = os.path.join(DATA_DIR, 'site_state.json')
PRODUCT_INDEX_FILE = os.path.join(IMAGES_DIR, 'products_index.json')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" if TELEGRAM_TOKEN else None

GROQ_API_KEY = os.getenv('GROQ_API_KEY', '').strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

BATCH_SIZE = int(os.getenv('DESCRIPTION_BATCH_SIZE', '10'))
REQUEST_DELAY = 2
CATALOG_REBUILD_LOGS = os.getenv('CATALOG_REBUILD_LOGS') == '1'

PRODUCT_SOURCE_CONFIGS = [
    {
        'source': 'yandex',
        'folder': os.path.join(PRODUCTS_DIR, 'yandex'),
        'web_prefix': 'products/yandex',
        'legacy_folder': os.path.join(IMAGES_DIR, 'yandex_images'),
        'legacy_web_prefix': 'yandex_images',
        'allowed_prefixes': ('offer_',),
    },
    {
        'source': 'uzum',
        'folder': os.path.join(PRODUCTS_DIR, 'uzum'),
        'web_prefix': 'products/uzum',
        'legacy_folder': os.path.join(IMAGES_DIR, 'uzum_images'),
        'legacy_web_prefix': 'uzum_images',
        'allowed_prefixes': ('item_',),
    },
    {
        'source': 'manual',
        'folder': os.path.join(PRODUCTS_DIR, 'manual'),
        'web_prefix': 'products/manual',
        'legacy_folder': os.path.join(IMAGES_DIR, 'manual_products'),
        'legacy_web_prefix': 'manual_products',
        'allowed_prefixes': ('product_', 'item_', 'offer_'),
    },
]

DEFAULT_MAINTENANCE_STATE = {
    "enabled": False,
    "title": "Идут технические работы",
    "message": "Мы обновляем сайт Sweet Pillow Dreams. Пожалуйста, зайдите чуть позже.",
    "updated_at": None,
}

TRANSLIT_MAP = str.maketrans({
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
    'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
})


def groq_enabled():
    return bool(GROQ_API_KEY)


def telegram_enabled():
    return bool(TELEGRAM_API_URL and TELEGRAM_CHAT_ID)


def rebuild_log(message):
    if CATALOG_REBUILD_LOGS:
        print(message)


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp_path, path)


def load_site_state():
    legacy_products = load_json_file(CACHE_FILE, [])
    legacy_maintenance = load_json_file(MAINTENANCE_FILE, DEFAULT_MAINTENANCE_STATE.copy())
    default_state = {
        'products': legacy_products,
        'maintenance': legacy_maintenance,
        'source_signature': None,
    }
    state = load_json_file(STATE_FILE, default_state)
    merged = {
        'products': state.get('products') if isinstance(state, dict) else legacy_products,
        'maintenance': DEFAULT_MAINTENANCE_STATE.copy(),
        'source_signature': state.get('source_signature') if isinstance(state, dict) else None,
    }
    merged['maintenance'].update((state.get('maintenance') or legacy_maintenance) if isinstance(state, dict) else legacy_maintenance)
    return merged


def save_site_state(state):
    payload = {
        'products': state.get('products', []),
        'maintenance': DEFAULT_MAINTENANCE_STATE.copy(),
        'source_signature': state.get('source_signature'),
    }
    payload['maintenance'].update(state.get('maintenance') or {})
    save_json_file(STATE_FILE, payload)


def load_cached_products():
    state = load_site_state()
    current_signature = get_images_source_signature()
    if state.get('source_signature') != current_signature or not state.get('products'):
        products = load_products_from_disk()
        state['products'] = products
        state['source_signature'] = get_images_source_signature()
        save_site_state(state)
        return products

    products = normalize_products_for_public_catalog(state.get('products') or [])
    if products != (state.get('products') or []):
        state['products'] = products
        state['source_signature'] = get_images_source_signature()
        save_site_state(state)
    save_products_index(products)
    return products


def save_cached_products(products):
    state = load_site_state()
    state['products'] = normalize_products_for_public_catalog(products)
    state['source_signature'] = get_images_source_signature()
    save_site_state(state)
    save_products_index(state['products'])


def load_maintenance_state():
    return load_site_state().get('maintenance', DEFAULT_MAINTENANCE_STATE.copy())


def save_maintenance_state(state):
    site_state = load_site_state()
    merged = DEFAULT_MAINTENANCE_STATE.copy()
    merged.update(state if isinstance(state, dict) else {})
    site_state['maintenance'] = merged
    save_site_state(site_state)


def maintenance_enabled():
    return bool(load_maintenance_state().get('enabled'))


def render_maintenance_page(state):
    maintenance_path = os.path.join(BASE_DIR, 'maintenance.html')
    with open(maintenance_path, 'r', encoding='utf-8') as f:
        template = f.read()
    return render_template_string(
        template,
        title=state.get('title') or DEFAULT_MAINTENANCE_STATE['title'],
        message=state.get('message') or DEFAULT_MAINTENANCE_STATE['message'],
    )


def render_error_page(status_code=404, title='Страница не найдена', message=None):
    error_path = os.path.join(BASE_DIR, 'error.html')
    if not message:
        message = 'Мы не нашли эту страницу. Возможно, ссылка устарела или товар уже убран из каталога.'
    with open(error_path, 'r', encoding='utf-8') as f:
        template = f.read()
    return render_template_string(
        template,
        status_code=status_code,
        title=title,
        message=message,
    ), status_code


def slugify(value):
    text = (value or '').strip().lower().translate(TRANSLIT_MAP)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = re.sub(r'-{2,}', '-', text).strip('-')
    return text or 'product'


def build_product_slug(product, fallback_index=None):
    size = (product.get('size') or '').strip()
    name = (product.get('name') or '').strip()
    sku = str(product.get('sku') or '').strip().lower()
    base = slugify(' '.join(part for part in [name, size] if part))
    if sku and sku not in base:
        base = f"{base}-{slugify(sku)}"
    if fallback_index is not None:
        base = f"{base}-{fallback_index}"
    return base


def ensure_product_slugs(products):
    used = set()
    for index, product in enumerate(products, start=1):
        slug = (product.get('slug') or '').strip()
        if not slug:
            slug = build_product_slug(product)
        slug = slugify(slug)
        original = slug
        counter = 2
        while slug in used:
            slug = f"{original}-{counter}"
            counter += 1
        product['slug'] = slug
        used.add(slug)
    return products


def build_product_public_id(product, used=None):
    seed = '|'.join(str(product.get(key) or '') for key in ('source', 'source_folder', 'sku', 'name', 'size'))
    digest = hashlib.sha1(seed.encode('utf-8')).hexdigest()
    number = int(digest[:14], 16) % 900000000 + 100000000
    candidate = str(number)
    if used is not None:
        while candidate in used:
            number += 1
            if number > 999999999:
                number = 100000000
            candidate = str(number)
        used.add(candidate)
    return candidate


def ensure_product_public_ids(products):
    used = set()
    for product in products:
        public_id = str(product.get('public_id') or '').strip()
        if public_id and public_id.isdigit() and public_id not in used:
            used.add(public_id)
        else:
            public_id = build_product_public_id(product, used)
            product['public_id'] = public_id
            save_product_source_field(product, 'public_id', public_id)
    return products


def normalize_products_for_public_catalog(products):
    products = ensure_product_slugs(products)
    products = ensure_product_public_ids(products)
    products = ensure_product_localizations(products)
    return products


def save_products_index(products):
    existing = load_json_file(PRODUCT_INDEX_FILE, {})
    if (
        isinstance(existing, dict)
        and existing.get('total') == len(products)
        and existing.get('products') == products
    ):
        return
    payload = {
        'updated_at': int(time.time()),
        'total': len(products),
        'sources': ['products/yandex', 'products/uzum', 'products/manual'],
        'products': products,
    }
    save_json_file(PRODUCT_INDEX_FILE, payload)


def iter_product_storage_configs():
    for config in PRODUCT_SOURCE_CONFIGS:
        primary = config['folder']
        if os.path.exists(primary):
            yield {
                **config,
                'active_folder': primary,
                'active_web_prefix': config['web_prefix'],
                'is_legacy': False,
            }
        legacy = config.get('legacy_folder')
        if legacy and os.path.exists(legacy):
            yield {
                **config,
                'active_folder': legacy,
                'active_web_prefix': config['legacy_web_prefix'],
                'is_legacy': True,
            }


def source_config(source):
    return next((config for config in PRODUCT_SOURCE_CONFIGS if config['source'] == source), None)


def get_images_source_signature():
    hasher = hashlib.sha256()
    for config in iter_product_storage_configs():
        folder = config['active_folder']
        if not os.path.exists(folder):
            continue
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            for filename in sorted(files):
                if not filename.lower().endswith(('.json', '.jpg', '.jpeg', '.png', '.webp')):
                    continue
                path = os.path.join(root, filename)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                rel_path = os.path.relpath(path, IMAGES_DIR)
                hasher.update(rel_path.encode('utf-8'))
                hasher.update(str(stat.st_size).encode('utf-8'))
                hasher.update(str(int(stat.st_mtime)).encode('utf-8'))
    return hasher.hexdigest()


def save_product_source_field(product, field, value):
    source = product.get('source')
    folder = product.get('source_folder')
    if not source or not folder:
        return
    config = source_config(source)
    if not config:
        return

    folder_root = config['folder']
    if not os.path.exists(os.path.join(folder_root, folder, 'info.json')) and config.get('legacy_folder'):
        legacy_path = os.path.join(config['legacy_folder'], folder, 'info.json')
        if os.path.exists(legacy_path):
            folder_root = config['legacy_folder']
    info_path = os.path.join(folder_root, folder, 'info.json')
    data = load_json_file(info_path, {})
    if not isinstance(data, dict):
        return
    if data.get(field) == value:
        return
    data[field] = value
    save_json_file(info_path, data)


def save_product_site_description(product, description):
    save_product_source_field(product, 'site_description', description)


def save_product_site_description_uz(product, description):
    save_product_source_field(product, 'site_description_uz', description)


def find_product_by_identifier(identifier):
    normalized = str(identifier or '').strip()
    if not normalized:
        return None
    return next(
        (
            item for item in load_cached_products()
            if str(item.get('public_id')) == normalized
            or str(item.get('sku')) == normalized
            or str(item.get('slug')) == normalized
        ),
        None,
    )


def product_public_url(identifier):
    product = find_product_by_identifier(identifier)
    if not product:
        return None
    return f"/catalog/{quote(str(product.get('public_id')), safe='')}"


def build_catalog_stats(products):
    categories = {}
    sizes = {}
    colors = {}
    prices = []
    with_images = 0

    for product in products:
        category = str(product.get('category') or 'Без категории').strip()
        size = str(product.get('size') or '').strip()
        color = str(product.get('color') or '').strip()
        images = product.get('images') or []
        price = product.get('price')

        categories[category] = categories.get(category, 0) + 1
        if size:
            sizes[size] = sizes.get(size, 0) + 1
        if color:
            colors[color] = colors.get(color, 0) + 1
        if images:
            with_images += 1
        try:
            if price is not None:
                prices.append(float(price))
        except (TypeError, ValueError):
            pass

    def top_values(mapping, limit=8):
        return [
            {'name': name, 'count': count}
            for name, count in sorted(mapping.items(), key=lambda item: (-item[1], item[0]))[:limit]
        ]

    return {
        'total': len(products),
        'with_images': with_images,
        'without_images': max(0, len(products) - with_images),
        'categories': top_values(categories),
        'sizes': top_values(sizes, limit=12),
        'colors': top_values(colors),
        'price_min': min(prices) if prices else None,
        'price_max': max(prices) if prices else None,
    }


def request_groq(messages, *, temperature=0.7, max_tokens=500, timeout=30):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    return requests.post(GROQ_URL, json=payload, headers=headers, timeout=timeout)


def groq_json_response(messages, *, temperature=0.7, max_tokens=500, timeout=30):
    resp = request_groq(messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
    if resp.status_code != 200:
        return None, resp
    return resp.json(), resp

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    rebuild_log(f"📁 Data директория: {DATA_DIR}")
    if not os.path.exists(STATE_FILE):
        save_site_state(load_site_state())


@app.after_request
def apply_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-site'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self' https://api.groq.com https://api.telegram.org; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self';"
    )
    if response.status_code >= 400:
        started_at = getattr(request, '_started_at', None)
        elapsed_ms = (time.perf_counter() - started_at) * 1000 if started_at else 0
        app.logger.warning(
            '%s %s -> %s (%.1f ms)',
            request.method,
            request.full_path.rstrip('?'),
            response.status_code,
            elapsed_ms,
        )
    return response

def load_processed_descriptions():
    return load_json_file(PROCESSED_DESC_FILE, {})

def save_processed_descriptions(desc_dict):
    save_json_file(PROCESSED_DESC_FILE, desc_dict)

def clean_descriptions_batch(items_batch):
    if not items_batch:
        return {}
    if not groq_enabled():
        return {}
    
    products_text = ""
    for i, item in enumerate(items_batch):
        products_text += f"\n=== ТОВАР {i+1} ===\n"
        products_text += f"Название: {item['name']}\n"
        products_text += f"Исходное описание: {item['description']}\n"
    
    prompt = f"""Ты помощник для интернет-магазина подушек "Sweet Pillow Dreams". 
Тебе дан список товаров. Для КАЖДОГО товара выполни следующие действия:
1. Убрать из описания всё, что относится к перечислению размеров, акциям, скидкам, промокодам, ссылкам, контактам.
2. Убрать фразы типа "Широкий размерный ряд", "Смотрите также", "Похожие товары".
3. Оставить только полезную информацию о материале, свойствах, уходе, ортопедических качествах.
4. Добавить 1-2 предложения полезной информации, основанной на названии товара.
5. Итоговое описание должно быть грамотным, на русском языке, длиной 3-5 предложений.
6. Не используй маркетинговых клише, не упоминай конкретные магазины.

Вот список товаров:
{products_text}

ОТВЕТЬ В ТОЧНОМ ФОРМАТЕ (каждый ответ начинай с "=== ТОВАР X ===", где X - номер товара):
=== ТОВАР 1 ===
[обработанное описание для товара 1]
=== ТОВАР 2 ===
[обработанное описание для товара 2]
... и так далее для всех товаров.

Используй ТОЛЬКО русский язык. Не добавляй лишних комментариев."""

    try:
        rebuild_log(f"  📤 Отправка пачки из {len(items_batch)} товаров в Llama 4 Scout...")
        result, resp = groq_json_response(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4000,
            timeout=120,
        )
        if result:
            response_text = result['choices'][0]['message']['content']
            
            import re
            pattern = r'=== ТОВАР (\d+) ===\s*(.*?)(?==== ТОВАР \d+ ===|$)'
            matches = re.findall(pattern, response_text, re.DOTALL)
            
            results = {}
            for match in matches:
                idx = int(match[0]) - 1
                cleaned_desc = match[1].strip()
                if 0 <= idx < len(items_batch):
                    item = items_batch[idx]
                    desc_key = hashlib.md5(f"{item['name']}|{item['description']}".encode()).hexdigest()
                    results[desc_key] = cleaned_desc
                    rebuild_log(f"    ✅ Обработан товар {idx+1}: {item['name'][:40]}...")
            return results
        else:
            rebuild_log(f"  ❌ Groq error: {resp.status_code}")
            return {}
    except Exception as e:
        rebuild_log(f"  ❌ Groq exception: {e}")
        return {}


def compact_raw_description(text, limit=900):
    if not text:
        return ''
    cleaned = re.sub(r'<[^>]+>', ' ', str(text))
    cleaned = re.sub(
        r'(Отзывы|Все|Описание|Полное описание|Продавец|Смотрите также|Категория|Без карты Uzum|Вернём разницу|'
        r'Доставим|Рассрочка|К покупкам|Можно купить|Остался последний|заказов|отзывов).*',
        ' ',
        cleaned,
        flags=re.I | re.S,
    )
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:limit]


def infer_description_traits(product):
    haystack = f"{product.get('name') or ''} {product.get('description') or ''}".lower()
    category = (product.get('category') or '').lower()

    if 'наволоч' in haystack or 'наволоч' in category:
        kind = 'Наволочка'
        purpose = 'защищает подушку и помогает быстро обновить вид спального места'
    elif 'наперник' in haystack or 'наперник' in category:
        kind = 'Наперник'
        purpose = 'помогает удерживать наполнитель и продлевает срок службы подушки'
    elif 'берем' in haystack or 'u-образ' in haystack or 'u образ' in haystack:
        kind = 'Подушка для беременных'
        purpose = 'поддерживает тело во время отдыха и помогает удобнее распределить нагрузку'
    else:
        kind = 'Подушка'
        purpose = 'подходит для спокойного ежедневного сна и отдыха'

    materials = []
    if 'холлофайбер' in haystack:
        materials.append('холлофайбер')
    if 'пух' in haystack or 'перо' in haystack:
        materials.append('пух-перо')
    if 'сатин' in haystack:
        materials.append('супер-сатин')
    if 'хлоп' in haystack or 'тик' in haystack:
        materials.append('хлопковая ткань')

    colors = []
    for color in ['белый', 'серый', 'голубой', 'фиолетовый']:
        if color in haystack:
            colors.append(color)

    return kind, purpose, materials, colors


def build_local_site_description(product):
    name = (product.get('name') or 'Товар Sweet Pillow Dreams').strip()
    size = (product.get('size') or '').strip()
    kind, purpose, materials, colors = infer_description_traits(product)
    material_text = ', '.join(materials) if materials else 'практичные материалы для ежедневного использования'
    color_text = f" Цвет: {', '.join(colors)}." if colors else ''
    size_text = f" Размер {size} удобно подбирать под привычный формат постельного белья." if size else ''
    return (
        f"{name} — {kind.lower()} Sweet Pillow Dreams, которая {purpose}. "
        f"В основе: {material_text}; изделие рассчитано на аккуратный уход и регулярное использование."
        f"{size_text}{color_text} "
        "Описание очищено от маркетплейс-блоков, лишних акций и служебной информации, чтобы в каталоге оставались только полезные характеристики."
    )


def build_local_site_description_uz(product):
    name = (product.get('name') or 'Sweet Pillow Dreams mahsuloti').strip()
    size = (product.get('size') or '').strip()
    kind, purpose, materials, colors = infer_description_traits(product)
    kind_map = {
        'Наволочка': 'yostiq jildi',
        'Наперник': 'napernik',
        'Подушка для беременных': 'homiladorlar uchun yostiq',
        'Подушка': 'yostiq',
    }
    material_map = {
        'холлофайбер': 'xollofayber',
        'пух-перо': 'par va pat',
        'супер-сатин': 'super-satin',
        'хлопковая ткань': 'paxta mato',
    }
    color_map = {
        'белый': 'oq',
        'серый': 'kulrang',
        'голубой': 'moviy',
        'фиолетовый': 'binafsha',
    }
    purpose_map = {
        'защищает подушку и помогает быстро обновить вид спального места': 'yostiqni himoya qiladi va yotoq joyini tez yangilashga yordam beradi',
        'помогает удерживать наполнитель и продлевает срок службы подушки': 'to‘ldiruvchini ushlab turishga va yostiq xizmat muddatini uzaytirishga yordam beradi',
        'поддерживает тело во время отдыха и помогает удобнее распределить нагрузку': 'dam olish vaqtida tanani qo‘llab-quvvatlaydi va yukni qulayroq taqsimlaydi',
        'подходит для спокойного ежедневного сна и отдыха': 'kundalik sokin uyqu va dam olish uchun mos keladi',
    }
    material_text = ', '.join(material_map.get(item, item) for item in materials) if materials else 'kundalik foydalanish uchun amaliy materiallar'
    color_text = f" Rangi: {', '.join(color_map.get(item, item) for item in colors)}." if colors else ''
    size_text = f" {size} o‘lchami yostiq jildi yoki yotoq komplekti formatiga mos tanlashga yordam beradi." if size else ''
    return (
        f"{name} — Sweet Pillow Dreams {kind_map.get(kind, 'mahsuloti')}, "
        f"u {purpose_map.get(purpose, 'qulay foydalanish uchun mo‘ljallangan')}. "
        f"Asosida {material_text}; mahsulot tartibli parvarish va muntazam foydalanish uchun mos."
        f"{size_text}{color_text} "
        "Tavsif marketplace bloklari, aksiyalar va keraksiz xizmat matnlaridan tozalangan."
    )


def ensure_product_localizations(products):
    for product in products:
        description = product.get('description') or product.get('description_ru') or ''
        if description:
            product['description_ru'] = description
        else:
            product['description_ru'] = build_local_site_description(product)
            product['description'] = product['description_ru']
        if not product.get('description_uz'):
            product['description_uz'] = build_local_site_description_uz(product)
            save_product_site_description_uz(product, product['description_uz'])
    return products


def get_product_key(product):
    name = (product.get('name') or '').strip().lower()
    size = (product.get('size') or '').strip().lower()
    price = product.get('price')
    return hashlib.md5(f"{name}|{size}|{price}".encode()).hexdigest()

def load_products_from_disk():
    products = []
    seen_keys = set()
    processed_descs = load_processed_descriptions()
    all_raw_products = []

    for source_config_item in iter_product_storage_configs():
        source = source_config_item['source']
        allowed_prefixes = source_config_item['allowed_prefixes']
        folder = source_config_item['active_folder']
        web_prefix = source_config_item['active_web_prefix']
        rebuild_log(f"🔍 Проверяем папку: {folder}")
        if not os.path.exists(folder):
            rebuild_log(f"   ❌ Папка не найдена: {folder}")
            continue

        items = os.listdir(folder)
        rebuild_log(f"   📂 Найдено элементов: {len(items)}")
        for item in items:
            item_path = os.path.join(folder, item)
            if not os.path.isdir(item_path):
                continue
            if not item.startswith(allowed_prefixes):
                continue
            info_path = os.path.join(item_path, 'info.json')
            if not os.path.exists(info_path):
                continue

            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('hidden') is True:
                    continue

                name = data.get('name', '')
                name = name.replace('Lumi Peite:', '').replace('Lumi Peite', '').strip()
                site_images = data.get('site_images') if isinstance(data.get('site_images'), list) else []
                raw_description = compact_raw_description(data.get('description') or data.get('description_text') or '')
                site_description = data.get('site_description') or raw_description
                site_description_uz = data.get('site_description_uz') or ''

                product = {
                    'sku': str(data.get('offerId') or data.get('sku') or data.get('product_id') or ''),
                    'name': name,
                    'price': data.get('current_price') or data.get('price'),
                    'old_price': data.get('old_price'),
                    'currency': data.get('currency', 'UZS'),
                    'description': site_description,
                    'description_ru': site_description,
                    'description_uz': site_description_uz,
                    'seller': data.get('seller') or "Sweet Pillow Dreams",
                    'size': data.get('size'),
                    'category': data.get('category'),
                    'source': source,
                    'source_folder': item,
                    '_description_synced': bool(data.get('site_description')),
                    'images': [str(image) for image in site_images if image],
                    'public_id': str(data.get('public_id') or '').strip(),
                    'slug': ''
                }

                # Собираем изображения
                if not product['images']:
                    for img_file in sorted(os.listdir(item_path)):
                        if img_file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                            product['images'].append(f'/images/{web_prefix}/{item}/{img_file}')

                key = get_product_key(product)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_raw_products.append(product)

            except Exception as e:
                rebuild_log(f"   ⚠️ Ошибка чтения {info_path}: {e}")
                continue

    rebuild_log(f"📦 Всего сырых товаров: {len(all_raw_products)}")

    products_to_process = []
    for product in all_raw_products:
        if product.get('_description_synced'):
            products.append(product)
            continue
        desc_key = hashlib.md5(f"{product['name']}|{product['description']}".encode()).hexdigest()
        if desc_key in processed_descs:
            product['description'] = processed_descs[desc_key]
            save_product_site_description(product, product['description'])
            products.append(product)
        else:
            if product['description'] and len(product['description']) > 50 and groq_enabled():
                products_to_process.append({
                    'name': product['name'],
                    'description': product['description'],
                    'original_product': product,
                    'desc_key': desc_key
                })
            else:
                product['description'] = build_local_site_description(product)
                save_product_site_description(product, product['description'])
                products.append(product)

    if products_to_process:
        rebuild_log(f"\n🔄 Требуется обработка {len(products_to_process)} товаров через Llama 4 Scout...")
        for i in range(0, len(products_to_process), BATCH_SIZE):
            batch = products_to_process[i:i+BATCH_SIZE]
            rebuild_log(f"\n📦 Обработка пачки {i//BATCH_SIZE + 1}/{(len(products_to_process)-1)//BATCH_SIZE + 1} ({len(batch)} товаров)")
            batch_items = [{'name': item['name'], 'description': item['description']} for item in batch]
            results = clean_descriptions_batch(batch_items)
            for item in batch:
                if item['desc_key'] in results:
                    new_desc = results[item['desc_key']]
                    processed_descs[item['desc_key']] = new_desc
                    item['original_product']['description'] = new_desc
                    save_product_site_description(item['original_product'], new_desc)
                    products.append(item['original_product'])
                    rebuild_log(f"    ✅ Сохранён: {item['name'][:50]}...")
                else:
                    fallback_desc = build_local_site_description(item['original_product'])
                    item['original_product']['description'] = fallback_desc
                    save_product_site_description(item['original_product'], fallback_desc)
                    products.append(item['original_product'])
                    rebuild_log(f"    ⚠️ Не обработан: {item['name'][:50]}...")
            save_processed_descriptions(processed_descs)
            rebuild_log(f"  💾 Прогресс сохранён ({len(processed_descs)} описаний в кэше)")
            if i + BATCH_SIZE < len(products_to_process):
                time.sleep(REQUEST_DELAY)

    for product in products:
        product.pop('_description_synced', None)
    products.sort(key=lambda p: p['name'].lower())
    products = normalize_products_for_public_catalog(products)
    save_products_index(products)
    return products


@app.before_request
def remember_request_start():
    request._started_at = time.perf_counter()


@app.before_request
def enforce_maintenance_mode():
    if not maintenance_enabled():
        return None

    state = load_maintenance_state()
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'maintenance',
            'title': state.get('title') or DEFAULT_MAINTENANCE_STATE['title'],
            'message': state.get('message') or DEFAULT_MAINTENANCE_STATE['message'],
        }), 503

    return render_maintenance_page(state), 503

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/catalog')
@app.route('/catalog/')
def catalog_index():
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'index.html')


@app.route('/catalog/index.html')
def catalog_index_legacy():
    return redirect('/catalog', code=301)


@app.route('/catalog/product')
@app.route('/catalog/product.html')
def product_page():
    identifier = request.args.get('item') or request.args.get('sku')
    if identifier:
        public_url = product_public_url(identifier)
        return redirect(public_url or f"/catalog/product/{quote(identifier, safe='')}", code=301)
    if request.path.endswith('.html'):
        return redirect('/catalog', code=301)
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'product.html')


@app.route('/catalog/product/<path:identifier>')
def product_clean_page(identifier):
    public_url = product_public_url(identifier)
    if public_url:
        return redirect(public_url, code=301)
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'product.html')


@app.route('/catalog/<int:public_id>')
def product_numeric_page(public_id):
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'product.html')


@app.route('/catalog/<path:identifier>')
def catalog_product_fallback(identifier):
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'product.html')


@app.route('/catalog/cart')
@app.route('/catalog/cart.html')
def cart_page():
    if request.path.endswith('.html'):
        return redirect('/catalog/cart', code=301)
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'cart.html')

@app.route('/catalog/style.css')
def catalog_css():
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'style.css')

@app.route('/catalog/ai.js')
def catalog_ai_js():
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'ai.js')

@app.route('/catalog/i18n.js')
def catalog_i18n_js():
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'i18n.js')

@app.route('/catalog/script.js')
def catalog_js():
    return send_from_directory(os.path.join(BASE_DIR, 'catalog'), 'script.js')

@app.route('/style.css')
def css():
    return send_from_directory(BASE_DIR, 'style.css')

@app.route('/script.js')
def js():
    return send_from_directory(BASE_DIR, 'script.js')

@app.route('/data/<path:filename>')
def data_files(filename):
    return jsonify({'error': 'not_found'}), 404

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/api/products')
def api_products():
    products = load_cached_products()
    if products:
        return jsonify(products)
    products = load_products_from_disk()
    save_cached_products(products)
    return jsonify(products)


@app.route('/api/products/<path:identifier>')
def api_product(identifier):
    product = find_product_by_identifier(identifier)
    if not product:
        return jsonify({'error': 'product_not_found'}), 404
    return jsonify(product)


@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'not_found'}), 404
    return render_error_page(404)


@app.route('/api/stats')
def api_stats():
    return jsonify(build_catalog_stats(load_cached_products()))


@app.route('/healthz')
def healthz():
    products = load_cached_products()
    return jsonify({
        'status': 'ok',
        'maintenance': maintenance_enabled(),
        'products_cached': bool(products),
        'products_count': len(products),
    })

@app.route('/api/rebuild', methods=['POST'])
def rebuild():
    if os.path.exists(PROCESSED_DESC_FILE):
        os.remove(PROCESSED_DESC_FILE)
    products = load_products_from_disk()
    save_cached_products(products)
    return jsonify({'status': 'ok', 'count': len(products)})

@app.route('/api/send-order', methods=['POST'])
def send_order():
    data = request.json
    order_text = data.get('text', '')
    if not order_text:
        return jsonify({'error': 'No text'}), 400
    if not telegram_enabled():
        return jsonify({'error': 'Telegram integration is not configured'}), 503
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': order_text, 'parse_mode': 'HTML'}
    try:
        resp = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        if resp.status_code == 200:
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'error': resp.text}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    messages = data.get('messages')
    user_message = data.get('message', '')
    if not messages and not user_message:
        return jsonify({'error': 'No message'}), 400
    if not groq_enabled():
        fallback = (
            "Консультант Sweet Pillow Dreams временно недоступен. Напишите нам в Telegram @pillows_uz, "
        )
        return jsonify({'reply': fallback})

    if not messages:
        messages = [{"role": "user", "content": user_message}]
    
    try:
        result, resp = groq_json_response(messages, temperature=0.7, max_tokens=500, timeout=30)
        if result:
            reply = result['choices'][0]['message']['content']
            return jsonify({'reply': reply})
        else:
            return jsonify({'error': f'API error: {resp.status_code}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    ensure_dirs()
    if not load_cached_products():
        rebuild_log("🔄 Предварительная обработка товаров через нейросеть Llama 4 Scout...")
        rebuild_log(f"📦 Размер пачки: {BATCH_SIZE} товаров")
        rebuild_log(f"⏱️ Задержка между пачками: {REQUEST_DELAY} сек")
        try:
            products = load_products_from_disk()
            save_cached_products(products)
            rebuild_log(f"\n✅ Обработано {len(products)} товаров")
            rebuild_log(f"💾 Кэш сохранён в {STATE_FILE}")
        except KeyboardInterrupt:
            rebuild_log("\n⚠️ Прервано пользователем. Кэш сохранён частично.")
            rebuild_log("💡 Запустите снова для продолжения обработки.")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8000')), debug=False)
