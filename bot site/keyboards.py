from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from urllib.parse import quote

import config


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Добавить товар", callback_data="menu:add"),
            InlineKeyboardButton("Редактировать товар", callback_data="menu:edit"),
        ],
        [
            InlineKeyboardButton("Найти товар", callback_data="menu:find"),
            InlineKeyboardButton("Удалить товар", callback_data="menu:delete"),
        ],
        [
            InlineKeyboardButton("Статус сайта", callback_data="menu:status"),
            InlineKeyboardButton("Техработы", callback_data="menu:maintenance"),
        ],
        [
            InlineKeyboardButton("Сводка ассортимента", callback_data="menu:assortment"),
            InlineKeyboardButton("Пинг Groq", callback_data="menu:ping"),
        ],
        [InlineKeyboardButton("Файлы сайта и backup", callback_data="menu:files")],
    ])


def product_editor_keyboard():
    rows = [
        [
            InlineKeyboardButton("Название", callback_data="product:set:name"),
            InlineKeyboardButton("Цена", callback_data="product:set:price"),
        ],
        [InlineKeyboardButton("Описание", callback_data="product:set:description")],
        [
            InlineKeyboardButton("Размер", callback_data="product:set:size"),
            InlineKeyboardButton("Картинки", callback_data="product:set:images"),
        ],
        [
            InlineKeyboardButton("Категория: Подушки", callback_data="product:category:Подушки"),
            InlineKeyboardButton("Категория: Наволочки", callback_data="product:category:Наволочки"),
        ],
        [
            InlineKeyboardButton("Категория: Наперники", callback_data="product:category:Наперники"),
            InlineKeyboardButton("Категория: Другое", callback_data="product:set:category"),
        ],
        [
            InlineKeyboardButton("Сбросить", callback_data="product:reset"),
            InlineKeyboardButton("Отмена", callback_data="product:cancel"),
        ],
        [InlineKeyboardButton("Добавить по ссылке Uzum", callback_data="product:from_link")],
        [InlineKeyboardButton("Сохранить товар", callback_data="product:save")],
        [InlineKeyboardButton("Главное меню", callback_data="menu:home")],
    ]
    return InlineKeyboardMarkup(rows)


def product_pick_method_keyboard(mode="edit"):
    title = {
        "edit": "edit",
        "delete": "delete",
        "browse": "browse",
    }.get(mode, "edit")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Список товаров", callback_data=f"{title}:list:1"),
            InlineKeyboardButton("Поиск", callback_data=f"{title}:search"),
        ],
        [InlineKeyboardButton("Главное меню", callback_data="menu:home")],
    ])


def product_edit_keyboard(sku):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Название", callback_data=f"edit:set:name:{sku}"),
            InlineKeyboardButton("Цена", callback_data=f"edit:set:price:{sku}"),
        ],
        [InlineKeyboardButton("Описание", callback_data=f"edit:set:description:{sku}")],
        [
            InlineKeyboardButton("Размер", callback_data=f"edit:set:size:{sku}"),
            InlineKeyboardButton("Картинки", callback_data=f"edit:set:images:{sku}"),
        ],
        [
            InlineKeyboardButton("Подушки", callback_data=f"edit:category:Подушки:{sku}"),
            InlineKeyboardButton("Наволочки", callback_data=f"edit:category:Наволочки:{sku}"),
        ],
        [
            InlineKeyboardButton("Наперники", callback_data=f"edit:category:Наперники:{sku}"),
            InlineKeyboardButton("Своя категория", callback_data=f"edit:set:category:{sku}"),
        ],
        [
            InlineKeyboardButton("К списку", callback_data="edit:list:1"),
            InlineKeyboardButton("Главное меню", callback_data="menu:home"),
        ],
    ])


def maintenance_keyboard(enabled):
    toggle_label = "Выключить техработы" if enabled else "Включить техработы"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data="maintenance:toggle")],
        [InlineKeyboardButton("Проверить доступ сайта", callback_data="maintenance:check")],
        [InlineKeyboardButton("Главное меню", callback_data="menu:home")],
    ])


def files_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Заменить файл сайта", callback_data="files:replace")],
        [
            InlineKeyboardButton("Скачать backup.zip", callback_data="files:backup:download"),
            InlineKeyboardButton("Откатить backup", callback_data="files:backup:restore"),
        ],
        [InlineKeyboardButton("Главное меню", callback_data="menu:home")],
    ])


def upload_keyboard():
    rows = []
    options = config.SITE_FILE_OPTIONS
    for index in range(0, len(options), 2):
        chunk = options[index:index + 2]
        rows.append([
            InlineKeyboardButton(option["label"], callback_data=f"upload:file:{option['id']}")
            for option in chunk
        ])
    rows.append([InlineKeyboardButton("Назад к файлам", callback_data="menu:files")])
    rows.append([InlineKeyboardButton("Главное меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def selected_upload_keyboard(selected_option_id=None):
    rows = []
    if selected_option_id:
        rows.append([InlineKeyboardButton("Сменить файл", callback_data="files:replace")])
    rows.append([InlineKeyboardButton("Отмена", callback_data="upload:cancel")])
    rows.append([InlineKeyboardButton("Главное меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def backup_restore_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Да, откатить", callback_data="files:backup:restore:confirm"),
            InlineKeyboardButton("Отмена", callback_data="menu:files"),
        ],
        [InlineKeyboardButton("Главное меню", callback_data="menu:home")],
    ])


def product_list_keyboard(products, mode="browse", page=1, total_pages=1):
    rows = []
    prefix = "delete" if mode == "delete" else "edit" if mode == "edit" else "browse"
    for index, item in enumerate(products):
        label = item.get("name") or item.get("sku") or "Товар"
        rows.append([InlineKeyboardButton(label[:64], callback_data=f"{prefix}:pick:{index}")])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("Назад", callback_data=f"{prefix}:list:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Дальше", callback_data=f"{prefix}:list:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("Поиск", callback_data=f"{prefix}:search")])
    rows.append([InlineKeyboardButton("Главное меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def product_preview_keyboard(product, mode="browse"):
    identifier = product.get("public_id") or product.get("sku") or product.get("slug") or ""
    url = f"{config.SITE_BASE_URL}{config.SITE_PUBLIC_PRODUCT_PATH}/{quote(str(identifier), safe='')}"
    rows = [[InlineKeyboardButton("Открыть товар на сайте", url=url)]]
    if mode == "delete":
        rows.append([InlineKeyboardButton("Удалить товар", callback_data=f"delete:confirm:{product.get('sku')}")])
        rows.append([InlineKeyboardButton("Назад к удалению", callback_data="delete:back")])
    elif mode == "edit":
        rows.append([InlineKeyboardButton("Редактировать поля", callback_data=f"edit:fields:{product.get('sku')}")])
        rows.append([InlineKeyboardButton("Назад к списку", callback_data="edit:back")])
    else:
        rows.append([InlineKeyboardButton("Назад к результатам", callback_data="browse:back")])
    rows.append([InlineKeyboardButton("Главное меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def delete_confirm_keyboard(sku):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Да, удалить", callback_data=f"delete:apply:{sku}"),
            InlineKeyboardButton("Отмена", callback_data=f"delete:show:{sku}"),
        ],
        [InlineKeyboardButton("Главное меню", callback_data="menu:home")],
    ])
