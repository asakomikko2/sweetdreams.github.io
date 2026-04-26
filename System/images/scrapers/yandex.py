import os
import shutil
import requests
import time
import re
import json
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "scrapers" else SCRIPT_DIR
os.chdir(SCRIPT_DIR)

API_KEY = "ACMA:AAGX1JqmL1FL7gKeHt2GYIQkWplF7tuV2hEkjPvy:cc178894"
BUSINESS_ID = 186718307
OUTPUT_DIR = os.path.join(IMAGES_DIR, "products", "yandex")

HEADERS = {
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

def clean_description(text):
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text)
    return text.strip()

def delete_output_folder():
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_price(price_field):
    if price_field is None:
        return None
    if isinstance(price_field, (int, float)):
        return float(price_field)
    if isinstance(price_field, dict):
        if 'value' in price_field:
            return float(price_field['value'])
        if 'amount' in price_field:
            return float(price_field['amount'])
    if isinstance(price_field, str):
        try:
            return float(price_field)
        except:
            return None
    return None

def extract_currency(price_field):
    if price_field is None:
        return "UZS"
    if isinstance(price_field, dict):
        if 'currencyId' in price_field:
            return price_field['currencyId']
        if 'currency' in price_field:
            return price_field['currency']
    return "UZS"

def get_all_offers():
    offers = []
    page_token = None
    page = 1
    while True:
        url = f"https://api.partner.market.yandex.ru/v2/businesses/{BUSINESS_ID}/offer-mappings"
        params = {"limit": 100}
        if page_token:
            params["page_token"] = page_token
        try:
            response = requests.post(url, headers=HEADERS, params=params, json={})
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
                basic_price = offer.get('basicPrice')
                current_price = extract_price(basic_price)
                currency = extract_currency(basic_price)
                old_price = None
                if basic_price and isinstance(basic_price, dict) and 'discountBase' in basic_price:
                    old_price = float(basic_price['discountBase'])
                if current_price is None and 'price' in offer:
                    current_price = extract_price(offer['price'])
                if old_price is None and 'oldPrice' in offer:
                    old_price = extract_price(offer['oldPrice'])
                product_url = f"https://market.yandex.uz/product--{offer_id}"
                offers.append({
                    "offerId": offer_id,
                    "name": offer.get("name", ""),
                    "description": clean_description(offer.get("description", "")),
                    "pictures": offer.get("pictures", []),
                    "current_price": current_price,
                    "old_price": old_price,
                    "currency": currency,
                    "url": product_url
                })
        page_token = result.get("paging", {}).get("nextPageToken")
        if not page_token:
            break
        page += 1
        time.sleep(0.2)
    return offers

def fetch_offer_details(offer_id):
    try:
        url = f"https://api.partner.market.yandex.ru/v2/businesses/{BUSINESS_ID}/offer-mappings"
        payload = {"offerMappings": [{"offer": {"offerId": offer_id}}]}
        response = requests.post(url, headers=HEADERS, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "OK":
                result = data.get("result", {})
                mappings = result.get("offerMappings", [])
                if mappings:
                    offer = mappings[0].get("offer", {})
                    basic_price = offer.get('basicPrice')
                    current_price = extract_price(basic_price)
                    currency = extract_currency(basic_price)
                    old_price = None
                    if basic_price and isinstance(basic_price, dict) and 'discountBase' in basic_price:
                        old_price = float(basic_price['discountBase'])
                    product_url = f"https://market.yandex.uz/product--{offer_id}"
                    return {
                        "name": offer.get("name", ""),
                        "description": clean_description(offer.get("description", "")),
                        "pictures": offer.get("pictures", []),
                        "current_price": current_price,
                        "old_price": old_price,
                        "currency": currency,
                        "url": product_url
                    }
        return None
    except Exception:
        return None

def download_image(url, folder, filename):
    try:
        resp = requests.get(url, timeout=15, stream=True)
        resp.raise_for_status()
        if 'image' in resp.headers.get('Content-Type', ''):
            path = os.path.join(folder, filename)
            with open(path, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception:
        pass
    return False

def save_description_json(folder_path, offer):
    json_path = os.path.join(folder_path, "info.json")
    data = {
        "offerId": offer["offerId"],
        "name": offer["name"],
        "description": offer["description"],
        "current_price": offer.get("current_price"),
        "old_price": offer.get("old_price"),
        "currency": offer.get("currency", "UZS"),
        "url": offer.get("url", ""),
        "pictures_count": len(offer["pictures"]),
        "folder": os.path.basename(folder_path)
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    delete_output_folder()
    print("YANDEX_LOADING")
    sys.stdout.flush()
    offers = get_all_offers()
    print(f"YANDEX_COUNT {len(offers)}")
    sys.stdout.flush()
    total_photos = 0
    for idx, offer in enumerate(offers, start=1):
        folder_name = f"offer_{idx}"
        folder_path = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        pics = offer["pictures"]
        if not pics:
            details = fetch_offer_details(offer["offerId"])
            if details:
                pics = details["pictures"]
                if details.get("current_price") is not None:
                    offer["current_price"] = details["current_price"]
                if details.get("old_price") is not None:
                    offer["old_price"] = details["old_price"]
                if details.get("currency"):
                    offer["currency"] = details["currency"]
                if details.get("url"):
                    offer["url"] = details["url"]
                if details.get("description") and len(details["description"]) > len(offer["description"]):
                    offer["description"] = details["description"]
                if details.get("name") and len(details["name"]) > len(offer["name"]):
                    offer["name"] = details["name"]
                offer["pictures"] = pics
        save_description_json(folder_path, offer)
        if pics:
            saved = 0
            for pic_num, pic_url in enumerate(pics, start=1):
                if not pic_url.startswith('http'):
                    continue
                if 'avatars.mds.yandex.net' not in pic_url:
                    continue
                ext = 'jpg'
                if '.' in pic_url.split('/')[-1]:
                    ext = pic_url.split('/')[-1].split('?')[0].lower()
                if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                    ext = 'jpg'
                filename = f"{pic_num}.{ext}"
                filepath = os.path.join(folder_path, filename)
                if os.path.exists(filepath):
                    continue
                if download_image(pic_url, folder_path, filename):
                    saved += 1
            total_photos += saved
        if idx % 20 == 0:
            print(f"YANDEX_PROGRESS {idx}")
            sys.stdout.flush()
        time.sleep(0.05)
    print(f"YANDEX_END {len(offers)} {total_photos}")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
