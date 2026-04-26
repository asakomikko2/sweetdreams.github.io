import os
import json
import hashlib
import requests
from pathlib import Path

# Конфигурация
YANDEX_API_KEY = "ACMA:AAGX1JqmL1FL7gKeHt2GYIQkWplF7tuV2hEkjPvy:cc178894"
BUSINESS_ID = 186718307

IMAGES_DIR = os.path.dirname(os.path.dirname(__file__)) if os.path.basename(os.path.dirname(__file__)) == 'scrapers' else os.path.dirname(__file__)
YANDEX_DIR = os.path.join(IMAGES_DIR, 'products', 'yandex')
UZUM_DIR = os.path.join(IMAGES_DIR, 'products', 'uzum')
LINKS_FILE = os.path.join(IMAGES_DIR, 'uz_links.json')

# Поля для сравнения
YANDEX_COMPARE_FIELDS = ['offerId', 'name', 'current_price', 'old_price']
UZUM_COMPARE_FIELDS = ['sku', 'product_id', 'name', 'price', 'size', 'seller']

def get_file_hash(filepath):
    """Вычисляет MD5 хеш файла"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_folder_hash(folder_path):
    """Вычисляет хеш всей папки"""
    if not os.path.exists(folder_path):
        return None
    hasher = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(folder_path)):
        dirs.sort()
        for file in sorted(files):
            if file.endswith(('.jpg', '.jpeg', '.png', '.webp', 'info.json')):
                file_path = os.path.join(root, file)
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())
    return hasher.hexdigest()

def get_json_fingerprint(data, source='yandex'):
    """Создаёт отпечаток JSON данных"""
    if source == 'yandex':
        compare_data = {k: data.get(k) for k in YANDEX_COMPARE_FIELDS if data.get(k)}
    else:
        compare_data = {k: data.get(k) for k in UZUM_COMPARE_FIELDS if data.get(k)}
    compare_data['photos_count'] = len(data.get('images', []))
    return hashlib.md5(json.dumps(compare_data, sort_keys=True).encode()).hexdigest()

def load_existing_products():
    """Загружает существующие товары"""
    existing = {'yandex': {}, 'uzum': {}}
    
    # Яндекс
    if os.path.exists(YANDEX_DIR):
        for folder in os.listdir(YANDEX_DIR):
            if folder.startswith('offer_'):
                info_path = os.path.join(YANDEX_DIR, folder, 'info.json')
                if os.path.exists(info_path):
                    with open(info_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    offer_id = data.get('offerId')
                    if offer_id:
                        existing['yandex'][offer_id] = {
                            'fingerprint': get_json_fingerprint(data, 'yandex'),
                            'folder': folder,
                            'folder_hash': get_folder_hash(os.path.join(YANDEX_DIR, folder))
                        }
    
    # Uzum
    if os.path.exists(UZUM_DIR):
        for folder in os.listdir(UZUM_DIR):
            if folder.startswith('item_'):
                info_path = os.path.join(UZUM_DIR, folder, 'info.json')
                if os.path.exists(info_path):
                    with open(info_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    sku = data.get('sku') or data.get('product_id')
                    if sku:
                        existing['uzum'][sku] = {
                            'fingerprint': get_json_fingerprint(data, 'uzum'),
                            'folder': folder,
                            'folder_hash': get_folder_hash(os.path.join(UZUM_DIR, folder))
                        }
    
    return existing

def fetch_yandex_offers():
    """Получает актуальные offerId из Яндекс API"""
    offers = {}
    page_token = None
    
    while True:
        url = f"https://api.partner.market.yandex.ru/v2/businesses/{BUSINESS_ID}/offer-mappings"
        params = {"limit": 100}
        if page_token:
            params["page_token"] = page_token
        
        headers = {
            "Api-Key": YANDEX_API_KEY,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json={}, timeout=30)
            if response.status_code != 200:
                break
            data = response.json()
            if data.get("status") != "OK":
                break
        except:
            break
        
        result = data.get("result", {})
        mappings = result.get("offerMappings", [])
        
        for item in mappings:
            offer = item.get("offer", {})
            offer_id = offer.get("offerId")
            if offer_id:
                offers[offer_id] = {
                    'name': offer.get("name", ""),
                    'current_price': offer.get("basicPrice", {}).get("value"),
                    'old_price': offer.get("basicPrice", {}).get("discountBase")
                }
        
        page_token = result.get("paging", {}).get("nextPageToken")
        if not page_token:
            break
    
    return offers

def fetch_uzum_links():
    """Получает ссылки на товары Uzum из файла"""
    if not os.path.exists(LINKS_FILE):
        return []
    with open(LINKS_FILE, 'r', encoding='utf-8') as f:
        links = json.load(f)
    return links if isinstance(links, list) else []

def check_and_get_updates():
    """Основная функция проверки. Возвращает словарь с тем, что нужно обновить"""
    print("🔍 Проверка актуальности товаров...")
    
    existing = load_existing_products()
    updates_needed = {'yandex': [], 'uzum': []}
    
    # Проверка Яндекс
    print("📦 Проверка Яндекс.Маркет...")
    try:
        yandex_offers = fetch_yandex_offers()
        yandex_count = len(yandex_offers)
        print(f"   Найдено актуальных товаров: {yandex_count}")
        
        for offer_id, offer_data in yandex_offers.items():
            if offer_id not in existing['yandex']:
                updates_needed['yandex'].append(offer_id)
                print(f"   🆕 Новый товар: {offer_id}")
            else:
                # Тут можно добавить проверку изменений цены и т.д.
                pass
        
        # Проверяем удалённые товары (есть в существующих, нет в API)
        for offer_id in existing['yandex']:
            if offer_id not in yandex_offers:
                updates_needed['yandex'].append(offer_id)  # Помечаем на удаление/обновление
                print(f"   ❌ Удалён товар: {offer_id}")
                
    except Exception as e:
        print(f"   ⚠️ Ошибка получения Яндекс товаров: {e}")
    
    # Проверка Uzum
    print("📦 Проверка Uzum...")
    try:
        uzum_links = fetch_uzum_links()
        uzum_count = len(uzum_links)
        print(f"   Найдено ссылок: {uzum_count}")
        
        # Извлекаем ID из ссылок
        import re
        current_uzum_ids = set()
        for link in uzum_links:
            match = re.search(r'/product/([^/?]+)', link)
            if match:
                product_id = match.group(1)
                current_uzum_ids.add(product_id)
                
                if product_id not in existing['uzum']:
                    updates_needed['uzum'].append(link)
                    print(f"   🆕 Новый товар: {product_id}")
        
        # Проверяем удалённые
        for sku in existing['uzum']:
            if sku not in current_uzum_ids:
                updates_needed['uzum'].append(sku)  # Помечаем на удаление
                print(f"   ❌ Удалён товар: {sku}")
                
    except Exception as e:
        print(f"   ⚠️ Ошибка получения Uzum товаров: {e}")
    
    return updates_needed

if __name__ == "__main__":
    # Тестовый запуск
    updates = check_and_get_updates()
    print("\n📊 Результат:")
    print(f"   Яндекс нужно обновить: {len(updates['yandex'])} товаров")
    print(f"   Uzum нужно обновить: {len(updates['uzum'])} товаров")
