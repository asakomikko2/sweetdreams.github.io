import os
import shutil
import re
import json
import requests
import sys
import hashlib
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from urllib.parse import urljoin, urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "scrapers" else SCRIPT_DIR
os.chdir(SCRIPT_DIR)

LINKS_FILE = os.path.join(IMAGES_DIR, "uz_links.json")
OUTPUT_DIR = os.path.join(IMAGES_DIR, "products", "uzum")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.224 Mobile Safari/537.36",
}
MIN_IMAGE_SIZE = 800
MAX_IMAGES = 6

def clean_price(text):
    if not text:
        return None
    cleaned = re.sub(r'[^\d]', '', text)
    return int(cleaned) if cleaned else None

def get_product_id(url):
    match = re.search(r'/product/([^/?]+)', url)
    return match.group(1) if match else None

def get_sku_from_url(url):
    match = re.search(r'skuId=(\d+)', url)
    return match.group(1) if match else None

def normalize_url(url):
    parsed = urlparse(url)
    query_params = {}
    if parsed.query:
        for p in parsed.query.split('&'):
            if '=' in p:
                k, v = p.split('=', 1)
                if k == 'skuId':
                    query_params[k] = v
    new_query = '&'.join(f"{k}={v}" for k, v in query_params.items())
    return parsed._replace(query=new_query).geturl()

def extract_size_mapping(soup, base_url):
    mapping = {}
    for selector in ['button', 'a', 'div', 'span']:
        for elem in soup.find_all(selector):
            text = elem.get_text(strip=True)
            size_match = re.search(r'(\d+[×x]\d+)', text)
            if not size_match:
                continue
            size = size_match.group(1)
            sku = None
            if elem.get('data-sku'):
                sku = elem.get('data-sku')
            elif elem.get('href') and 'skuId=' in elem['href']:
                sku_match = re.search(r'skuId=(\d+)', elem['href'])
                if sku_match:
                    sku = sku_match.group(1)
            if sku:
                mapping[sku] = size
    for script in soup.find_all('script'):
        if not script.string:
            continue
        pairs = re.findall(r'"skuId"\s*:\s*(\d+).*?"optionName"\s*:\s*"([^"]+)"', script.string, re.DOTALL)
        for sku, option in pairs:
            size_match = re.search(r'(\d+[×x]\d+)', option)
            if size_match:
                mapping[sku] = size_match.group(1)
    return mapping

def extract_seller(soup):
    seller_block = soup.find(class_=re.compile(r'seller|shop|vendor', re.I))
    if seller_block:
        seller_link = seller_block.find('a', href=re.compile(r'/shop/'))
        if seller_link:
            seller_name = seller_link.get_text(strip=True)
            seller_name = re.sub(r'[\d.]+.*', '', seller_name).strip()
            return seller_name if seller_name else "Не указан"
        text = seller_block.get_text(separator=' ', strip=True)
        match = re.search(r'Продавец[:：]\s*(.+?)(?:\s*[●•]|\s*$)', text, re.I)
        if match:
            seller_name = match.group(1).strip()
            seller_name = re.sub(r'[\d.]+.*', '', seller_name).strip()
            return seller_name if seller_name else "Не указан"
        lines = text.split('\n')
        for line in lines:
            if line and not re.search(r'рейтинг|отзыв|звезд', line, re.I):
                seller_name = re.sub(r'[\d.]+.*', '', line).strip()
                if seller_name:
                    return seller_name
    for elem in soup.find_all(text=re.compile(r'Продавец', re.I)):
        parent = elem.parent
        if parent:
            seller_text = parent.get_text(separator=' ', strip=True)
            match = re.search(r'Продавец[:：]\s*(.+?)(?:\s*[●•]|\s*$)', seller_text, re.I)
            if match:
                seller_name = match.group(1).strip()
                seller_name = re.sub(r'[\d.]+.*', '', seller_name).strip()
                return seller_name if seller_name else "Не указан"
            next_elem = parent.find_next_sibling()
            if next_elem:
                seller_name = next_elem.get_text(strip=True)
                seller_name = re.sub(r'[\d.]+.*', '', seller_name).strip()
                return seller_name if seller_name else "Не указан"
    shop_link = soup.find('a', href=re.compile(r'/shop/'))
    if shop_link:
        seller_name = shop_link.get_text(strip=True)
        seller_name = re.sub(r'[\d.]+.*', '', seller_name).strip()
        return seller_name if seller_name else "Не указан"
    return "Не указан"

def extract_price_without_card(html):
    match = re.search(r'Без карты Uzum[\s:]*(\d[\d\s]*)\s*сум', html, re.IGNORECASE)
    if match:
        return clean_price(match.group(1))
    return None

def get_image_hash(image_data):
    return hashlib.md5(image_data).hexdigest()

def is_main_product_section(soup, url):
    """
    Проверяет, что мы находимся в основном блоке товара,
    а не в разделе "Похожие" или "Смотрите также".
    """
    # Проверяем URL – если есть skuId, значит это конкретный товар
    if 'skuId=' in url:
        return True
    # Проверяем заголовок h1 – он обычно уникален для товара
    h1 = soup.find('h1')
    if h1 and h1.get_text(strip=True):
        return True
    return False

def extract_unique_images(soup, base_url):
    """
    Собирает уникальные качественные изображения ТОЛЬКО из основного блока товара.
    Игнорирует блоки "Похожие товары", "Смотрите также".
    """
    # Если это не основной товар, возвращаем пустой список
    if not is_main_product_section(soup, base_url):
        return []
    
    candidates = {}
    urls = set()
    
    # 1. og:image – всегда основное фото
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        urls.add(og_image['content'])
    
    # 2. Ищем только изображения из основного блока товара (до блока "Похожие")
    # Находим основную галерею
    gallery = soup.find('div', class_=re.compile(r'gallery|product-gallery|swiper'))
    if gallery:
        for img in gallery.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and src.startswith('http'):
                if not any(x in src for x in ['thumb', 'icon', 'logo', 'avatar', '40x40', '60x60', 'favicon']):
                    urls.add(src)
    
    # 3. Если галерея не найдена, ищем img в области до блока "recommendations"
    # Обрезаем HTML до блока рекомендаций
    html = str(soup)
    recommendations_pos = html.find('recommendations')
    if recommendations_pos != -1:
        html = html[:recommendations_pos]
        soup_cut = BeautifulSoup(html, 'html.parser')
    else:
        soup_cut = soup
    
    for img in soup_cut.find_all('img'):
        src = img.get('src') or img.get('data-src')
        if src and src.startswith('http'):
            if not any(x in src for x in ['thumb', 'icon', 'logo', 'avatar', '40x40', '60x60', 'favicon']):
                urls.add(src)
    
    # 4. Из скриптов – но тоже только до рекомендаций
    for script in soup_cut.find_all('script'):
        if not script.string:
            continue
        found = re.findall(r'(https?://images\.uzum\.uz/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))', script.string, re.I)
        for url in found:
            if not any(x in url for x in ['thumb', 'icon', 'logo', 'avatar', '40x40', '60x60', 'favicon']):
                urls.add(url)
    
    # 5. Скачиваем и анализируем каждое изображение
    for url in urls:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Android 10; Mobile) AppleWebKit/537.36"}
            resp = requests.get(url, timeout=10, stream=True, headers=headers)
            resp.raise_for_status()
            if 'image' not in resp.headers.get('Content-Type', ''):
                continue
            img_data = resp.content
            if len(img_data) < 5000:
                continue
            img_hash = get_image_hash(img_data)
            img = Image.open(BytesIO(img_data))
            width, height = img.size
            if width < MIN_IMAGE_SIZE and height < MIN_IMAGE_SIZE:
                continue
            if img_hash not in candidates or (width * height) > (candidates[img_hash][0] * candidates[img_hash][1]):
                candidates[img_hash] = (width, height, url, img_data)
        except Exception:
            continue
    
    # 6. Выбираем MAX_IMAGES самых больших изображений
    sorted_images = sorted(candidates.values(), key=lambda x: x[0] * x[1], reverse=True)
    final_images = sorted_images[:MAX_IMAGES]
    return [img[2] for img in final_images]

def parse_uzum_product(url, size_mapping=None):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')
        
        product = {}
        product['url'] = url
        product['product_id'] = get_product_id(url)
        sku = get_sku_from_url(url)
        product['sku'] = sku
        
        if sku and size_mapping and sku in size_mapping:
            product['size'] = size_mapping[sku]
        else:
            product['size'] = extract_size_from_page(soup, url)
        
        product['seller'] = extract_seller(soup)
        name_tag = soup.find('h1')
        product['name'] = name_tag.get_text(strip=True) if name_tag else ""
        
        desc_tag = soup.find('div', class_=re.compile('description'))
        if desc_tag:
            product['description_html'] = str(desc_tag)
            product['description_text'] = desc_tag.get_text(separator='\n', strip=True)
        else:
            product['description_html'] = ""
            product['description_text'] = ""
        
        breadcrumbs = soup.find_all('a', class_=re.compile('breadcrumb'))
        product['category'] = breadcrumbs[-1].get_text(strip=True) if breadcrumbs else ""
        product['price'] = extract_price_without_card(html)
        product['currency'] = "UZS"
        product['images'] = extract_unique_images(soup, url)
        
        return product
    except Exception:
        return None

def extract_size_from_page(soup, url):
    active = soup.find(class_=re.compile(r'active|selected'))
    if active:
        text = active.get_text(strip=True)
        size_match = re.search(r'(\d+[×x]\d+)', text)
        if size_match:
            return size_match.group(1)
    name_tag = soup.find('h1')
    if name_tag:
        name = name_tag.get_text(strip=True)
        size_match = re.search(r'(\d+[×x]\d+)', name)
        if size_match:
            return size_match.group(1)
    return "Не указан"

def download_image(img_url, folder, filename):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Android 10; Mobile) AppleWebKit/537.36"}
        resp = requests.get(img_url, timeout=15, stream=True, headers=headers)
        resp.raise_for_status()
        if 'image' in resp.headers.get('Content-Type', ''):
            img_data = resp.content
            img = Image.open(BytesIO(img_data))
            width, height = img.size
            if width < MIN_IMAGE_SIZE and height < MIN_IMAGE_SIZE:
                return False
            path = os.path.join(folder, filename)
            with open(path, 'wb') as f:
                f.write(img_data)
            return True
    except Exception:
        return False

def save_product_json(folder_path, product):
    json_path = os.path.join(folder_path, "info.json")
    data = {
        "product_id": product.get("product_id"),
        "sku": product.get("sku"),
        "name": product.get("name"),
        "size": product.get("size", ""),
        "seller": product.get("seller", ""),
        "description_html": product.get("description_html", ""),
        "description_text": product.get("description_text", ""),
        "price": product.get("price"),
        "currency": product.get("currency", "UZS"),
        "category": product.get("category"),
        "url": product.get("url"),
        "pictures_count": len(product.get("images", [])),
        "folder": os.path.basename(folder_path)
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    if not os.path.exists(LINKS_FILE):
        print("UZUM_START 0")
        return
    with open(LINKS_FILE, 'r', encoding='utf-8') as f:
        start_urls = json.load(f)
    if not isinstance(start_urls, list):
        print("UZUM_START 0")
        return
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total_processed = 0
    total_photos = 0
    print(f"UZUM_LOADING {len(start_urls)}")
    sys.stdout.flush()
    for idx_main, main_url in enumerate(start_urls, 1):
        main_url = main_url.strip()
        try:
            resp = requests.get(main_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            size_mapping = extract_size_mapping(soup, main_url)
        except:
            continue
        base_without_sku = re.sub(r'\?skuId=\d+', '', main_url)
        urls_to_process = []
        for sku in size_mapping.keys():
            url_with_sku = f"{base_without_sku}?skuId={sku}"
            urls_to_process.append(normalize_url(url_with_sku))
        processed = set()
        for url in urls_to_process:
            if url in processed:
                continue
            processed.add(url)
            product = parse_uzum_product(url, size_mapping)
            if not product:
                continue
            folder_name = f"item_{total_processed+1}"
            folder_path = os.path.join(OUTPUT_DIR, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            save_product_json(folder_path, product)
            images = product.get("images", [])
            saved = 0
            for i, img_url in enumerate(images, 1):
                ext = 'jpg'
                if '.' in img_url.split('/')[-1]:
                    ext = img_url.split('/')[-1].split('?')[0].lower()
                if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                    ext = 'jpg'
                filename = f"{i}.{ext}"
                filepath = os.path.join(folder_path, filename)
                if os.path.exists(filepath):
                    saved += 1
                    continue
                if download_image(img_url, folder_path, filename):
                    saved += 1
            total_photos += saved
            total_processed += 1
            if total_processed % 10 == 0:
                print(f"UZUM_PROGRESS {total_processed}")
                sys.stdout.flush()
    print(f"UZUM_END {total_processed} {total_photos}")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
