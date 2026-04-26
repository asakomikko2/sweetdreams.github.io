import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone

import config


TRANSLIT_MAP = str.maketrans({
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
    'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
})


def load_json(path, default):
    if not path.exists():
        return deepcopy(default)
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return deepcopy(default)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    tmp_path.replace(path)


def sort_products(products):
    return sorted(products, key=lambda item: (item.get("name") or "").lower())


def next_folder(base_dir, prefix):
    base_dir.mkdir(parents=True, exist_ok=True)
    max_index = 0
    for path in base_dir.iterdir():
        if not path.is_dir() or not path.name.startswith(prefix):
            continue
        tail = path.name.replace(prefix, "", 1)
        if tail.isdigit():
            max_index = max(max_index, int(tail))
    return base_dir / f"{prefix}{max_index + 1}"


def iter_source_info_files():
    sources = [
        ("yandex", config.YANDEX_IMAGES_DIR),
        ("uzum", config.UZUM_IMAGES_DIR),
        ("manual", config.MANUAL_IMAGES_DIR),
    ]
    for source, folder in sources:
        if not folder.exists():
            continue
        for info_path in folder.glob("*/info.json"):
            yield source, info_path


def source_info_path_for_product(product):
    source = normalize_text(product.get("source"))
    folder = normalize_text(product.get("source_folder"))
    source_dir = {
        "yandex": config.YANDEX_IMAGES_DIR,
        "uzum": config.UZUM_IMAGES_DIR,
        "manual": config.MANUAL_IMAGES_DIR,
    }.get(source)
    if source_dir and folder:
        path = source_dir / folder / "info.json"
        if path.exists():
            return source, path

    sku = normalize_text(product.get("sku"))
    name = normalize_text(product.get("name")).lower()
    for candidate_source, info_path in iter_source_info_files():
        data = load_json(info_path, {})
        ids = {
            normalize_text(data.get("offerId")),
            normalize_text(data.get("sku")),
            normalize_text(data.get("product_id")),
        }
        if sku and sku in ids:
            return candidate_source, info_path
        if name and normalize_text(data.get("name")).lower() == name:
            return candidate_source, info_path
    return None, None


def sync_product_to_images(product):
    source, info_path = source_info_path_for_product(product)
    if not info_path:
        source = "manual"
        product_dir = next_folder(config.MANUAL_IMAGES_DIR, "product_")
        product_dir.mkdir(parents=True, exist_ok=True)
        info_path = product_dir / "info.json"
        product["source_folder"] = product_dir.name
        product["source"] = source
    else:
        product["source"] = source
        product["source_folder"] = info_path.parent.name

    data = load_json(info_path, {})
    if not isinstance(data, dict):
        data = {}

    sku = normalize_text(product.get("sku"))
    data["name"] = normalize_text(product.get("name"))
    data["sku"] = sku
    if source == "yandex":
        data["offerId"] = normalize_text(data.get("offerId")) or sku
        data["current_price"] = product.get("price")
    else:
        data["price"] = product.get("price")
    data["old_price"] = product.get("old_price")
    data["currency"] = normalize_text(product.get("currency")) or config.DEFAULT_CURRENCY
    data["seller"] = normalize_text(product.get("seller")) or config.DEFAULT_SELLER
    data["site_description"] = normalize_text(product.get("description"))
    data["size"] = normalize_text(product.get("size"))
    data["category"] = normalize_text(product.get("category"))
    data["source"] = source
    data["site_images"] = normalize_images(product.get("images"))
    data["public_id"] = normalize_text(product.get("public_id"))
    data["pictures_count"] = len(data["site_images"])
    data["folder"] = info_path.parent.name
    data["hidden"] = bool(product.get("hidden", False))
    save_json(info_path, data)
    return product


def mark_product_hidden_in_images(product):
    source, info_path = source_info_path_for_product(product)
    if not info_path:
        return False
    data = load_json(info_path, {})
    if not isinstance(data, dict):
        data = {}
    data["hidden"] = True
    save_json(info_path, data)
    return True


def load_products():
    state = load_json(config.SITE_STATE_FILE, {"products": [], "maintenance": config.DEFAULT_MAINTENANCE_STATE})
    return state.get("products", []) if isinstance(state, dict) else []


def save_products(products):
    state = load_json(config.SITE_STATE_FILE, {"products": [], "maintenance": config.DEFAULT_MAINTENANCE_STATE})
    if not isinstance(state, dict):
        state = {"products": [], "maintenance": config.DEFAULT_MAINTENANCE_STATE.copy()}
    state["products"] = ensure_product_public_ids(products)
    state.setdefault("maintenance", config.DEFAULT_MAINTENANCE_STATE.copy())
    save_json(config.SITE_STATE_FILE, state)


def load_maintenance_state():
    site_state = load_json(config.SITE_STATE_FILE, {"products": [], "maintenance": config.DEFAULT_MAINTENANCE_STATE})
    state = site_state.get("maintenance", {}) if isinstance(site_state, dict) else {}
    merged = deepcopy(config.DEFAULT_MAINTENANCE_STATE)
    merged.update(state if isinstance(state, dict) else {})
    return merged


def save_maintenance_state(state):
    payload = deepcopy(config.DEFAULT_MAINTENANCE_STATE)
    payload.update(state)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    site_state = load_json(config.SITE_STATE_FILE, {"products": [], "maintenance": config.DEFAULT_MAINTENANCE_STATE})
    if not isinstance(site_state, dict):
        site_state = {"products": [], "maintenance": config.DEFAULT_MAINTENANCE_STATE.copy()}
    site_state.setdefault("products", [])
    site_state["maintenance"] = payload
    save_json(config.SITE_STATE_FILE, site_state)


def create_empty_product():
    return {
        "sku": "",
        "name": "",
        "price": "",
        "old_price": "",
        "currency": config.DEFAULT_CURRENCY,
        "description": "",
        "seller": config.DEFAULT_SELLER,
        "size": "",
        "category": "",
        "source": config.DEFAULT_SOURCE,
        "images": [],
    }


def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def normalize_number(value, field_name):
    text = normalize_text(value)
    if text.lower() in {"", "none", "null", "-", "без"}:
        return None
    normalized = text.replace(" ", "").replace(",", ".")
    try:
        number = float(normalized)
    except ValueError as error:
        raise ValueError(f"Поле «{field_name}» должно быть числом.") from error
    if number < 0:
        raise ValueError(f"Поле «{field_name}» не может быть отрицательным.")
    return number


def normalize_images(value):
    if isinstance(value, list):
        return [normalize_text(item) for item in value if normalize_text(item)]
    raw = normalize_text(value)
    if not raw:
        return []
    parts = []
    for chunk in raw.replace("\n", ",").split(","):
        item = normalize_text(chunk)
        if item:
            parts.append(item)
    return parts


def slugify(value):
    text = normalize_text(value).lower().translate(TRANSLIT_MAP)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = re.sub(r'-{2,}', '-', text).strip('-')
    return text or 'product'


def build_product_slug(product):
    base = slugify(' '.join(filter(None, [
        product.get('name'),
        product.get('size'),
    ])))
    sku = slugify(product.get('sku'))
    if sku and sku not in base:
        base = f"{base}-{sku}"
    return base


def build_product_sku(product):
    parts = [slugify(product.get("name"))]
    if product.get("size"):
        parts.append(slugify(product.get("size")))
    base = "-".join(part for part in parts if part).upper()
    if not base:
        base = "SPD-ITEM"
    if len(base) > 42:
        base = base[:42].rstrip("-")
    return base


def build_product_public_id(product, used=None):
    seed = "|".join(normalize_text(product.get(key)) for key in ("source", "source_folder", "sku", "name", "size"))
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
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
        public_id = normalize_text(product.get("public_id"))
        if public_id and public_id.isdigit() and public_id not in used:
            used.add(public_id)
        else:
            product["public_id"] = build_product_public_id(product, used)
    return products


def build_default_description(product):
    name = normalize_text(product.get("name")) or "Товар Sweet Pillow Dreams"
    size = normalize_text(product.get("size"))
    category = normalize_text(product.get("category")).lower()

    if "наволоч" in category:
        base = f"{name} для аккуратного обновления спальни и комфортного ежедневного использования."
    elif "наперник" in category:
        base = f"{name} помогает аккуратно защитить наполнитель и продлить срок службы подушки."
    else:
        base = f"{name} создан для более комфортного сна и спокойного повседневного использования."

    if size:
        base += f" Размер {size} помогает точнее подобрать изделие под нужный формат."
    else:
        base += " Подходит для домашнего использования и аккуратного ухода за спальной зоной."
    return base


def ensure_unique_sku(products, sku):
    existing_skus = {str(item.get("sku")) for item in products}
    if sku not in existing_skus:
        return sku
    index = 2
    while f"{sku}-{index}" in existing_skus:
        index += 1
    return f"{sku}-{index}"


def prepare_product_for_save(draft):
    product = {
        "sku": normalize_text(draft.get("sku")),
        "name": normalize_text(draft.get("name")),
        "price": normalize_number(draft.get("price"), "Цена"),
        "old_price": normalize_number(draft.get("old_price"), "Старая цена"),
        "currency": normalize_text(draft.get("currency")) or config.DEFAULT_CURRENCY,
        "description": normalize_text(draft.get("description")),
        "seller": normalize_text(draft.get("seller")) or config.DEFAULT_SELLER,
        "size": normalize_text(draft.get("size")) or None,
        "category": normalize_text(draft.get("category")) or None,
        "source": normalize_text(draft.get("source")) or config.DEFAULT_SOURCE,
        "images": normalize_images(draft.get("images")),
        "public_id": normalize_text(draft.get("public_id")),
        "slug": "",
    }

    if not product["name"]:
        raise ValueError("Нужно заполнить название.")
    if product["price"] is None:
        raise ValueError("Нужно заполнить цену.")
    if not product["description"]:
        product["description"] = build_default_description(product)

    if not product["sku"]:
        product["sku"] = build_product_sku(product)
    product["slug"] = build_product_slug(product)
    if not product["public_id"]:
        product["public_id"] = build_product_public_id(product)
    return product


def add_product(draft):
    products = load_products()
    product = prepare_product_for_save(draft)
    product["sku"] = ensure_unique_sku(products, product["sku"])
    existing_slug = next((item for item in products if str(item.get("slug")) == product["slug"]), None)
    if existing_slug:
        product["slug"] = f"{product['slug']}-{slugify(product['sku'])}"
    product = sync_product_to_images(product)
    products.append(product)
    products = sort_products(products)
    save_products(products)
    return product


def list_products(page=1, page_size=8):
    products = sort_products(load_products())
    total = len(products)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), total_pages))
    start = (page - 1) * page_size
    return products[start:start + page_size], page, total_pages, total


def product_stats():
    products = load_products()
    categories = {}
    sizes = {}
    prices = []
    with_images = 0

    for product in products:
        category = normalize_text(product.get("category")) or "Без категории"
        size = normalize_text(product.get("size"))
        images = product.get("images") or []
        price = product.get("price")

        categories[category] = categories.get(category, 0) + 1
        if size:
            sizes[size] = sizes.get(size, 0) + 1
        if images:
            with_images += 1
        try:
            if price is not None:
                prices.append(float(price))
        except (TypeError, ValueError):
            pass

    def top(mapping, limit=8):
        return sorted(mapping.items(), key=lambda item: (-item[1], item[0]))[:limit]

    return {
        "total": len(products),
        "with_images": with_images,
        "without_images": max(0, len(products) - with_images),
        "categories": top(categories),
        "sizes": top(sizes, limit=12),
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
    }


def get_product(sku):
    return next((item for item in load_products() if str(item.get("sku")) == str(sku)), None)


def normalize_product_update(field, value):
    if field == "images":
        return normalize_images(value)
    if field in {"price", "old_price"}:
        return normalize_number(value, "Цена" if field == "price" else "Старая цена")
    if field in {"size", "category"} and normalize_text(value) in {"-", "—"}:
        return None
    return normalize_text(value)


def update_product(sku, changes):
    products = load_products()
    target = next((item for item in products if str(item.get("sku")) == str(sku)), None)
    if not target:
        raise ValueError("Товар не найден.")

    for field, value in changes.items():
        if field == "sku":
            continue
        target[field] = normalize_product_update(field, value)

    if not normalize_text(target.get("name")):
        raise ValueError("Название не может быть пустым.")
    if target.get("price") is None:
        raise ValueError("Цена не может быть пустой.")
    if not normalize_text(target.get("description")):
        target["description"] = build_default_description(target)

    target["currency"] = normalize_text(target.get("currency")) or config.DEFAULT_CURRENCY
    target["seller"] = normalize_text(target.get("seller")) or config.DEFAULT_SELLER
    target["source"] = normalize_text(target.get("source")) or config.DEFAULT_SOURCE
    target["slug"] = build_product_slug(target)
    target["public_id"] = normalize_text(target.get("public_id")) or build_product_public_id(target)
    sync_product_to_images(target)

    used = set()
    for item in sort_products(products):
        slug = item.get("slug") or build_product_slug(item)
        base = slug
        counter = 2
        while slug in used:
            slug = f"{base}-{counter}"
            counter += 1
        item["slug"] = slug
        used.add(slug)

    products = sort_products(products)
    save_products(products)
    return next(item for item in products if str(item.get("sku")) == str(sku))


def find_products(query, limit=8):
    needle = normalize_text(query).lower()
    if not needle:
        return []
    products = load_products()
    matched = []
    for item in products:
        haystacks = [
            normalize_text(item.get("sku")).lower(),
            normalize_text(item.get("name")).lower(),
            normalize_text(item.get("description")).lower(),
        ]
        if any(needle in haystack for haystack in haystacks):
            matched.append(item)
        if len(matched) >= limit:
            break
    return matched


def delete_product(sku):
    products = load_products()
    target = next((item for item in products if str(item.get("sku")) == str(sku)), None)
    if not target:
        raise ValueError("Товар не найден.")
    mark_product_hidden_in_images(target)
    products = [item for item in products if str(item.get("sku")) != str(sku)]
    save_products(products)
    return target
