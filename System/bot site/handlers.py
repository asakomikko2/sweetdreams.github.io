from html import escape

from telegram import InputFile, Update
from telegram.ext import ContextTypes

import config
import keyboards
import services
import storage


PRODUCT_FIELDS = {
    "name": ("Название", "Введите полное название товара."),
    "price": ("Цена", "Введите цену числом, например: 52000"),
    "description": ("Описание", "Введите описание товара. Лучше 2-4 предложения без markdown. Поле можно пропустить и бот соберёт базовый текст сам."),
    "size": ("Размер", "Введите размер, например: 50x70. Можно «-», если поле не нужно."),
    "category": ("Категория", "Введите свою категорию или нажмите одну из готовых кнопок ниже."),
    "images": ("Изображения", "Отправьте пути или URL через запятую. Можно несколько значений."),
}


def is_authorized(update: Update):
    user = update.effective_user
    return bool(user and user.id in config.ALLOWED_USER_IDS)


def authorized_only(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not is_authorized(update):
            return
        return await handler(update, context, *args, **kwargs)
    return wrapper


def short_value(value):
    if isinstance(value, list):
        if not value:
            return "—"
        preview = ", ".join(value[:2])
        if len(value) > 2:
            preview += f" и ещё {len(value) - 2}"
        return preview
    if value in ("", None):
        return "—"
    return str(value)


def truncate_value(value, limit=420):
    text = short_value(value)
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "…"


def format_home_text():
    return (
        f"<b>{escape(config.BOT_NAME)}</b>\n\n"
        "Управление каталогом, файлами сайта, техработами, сводкой ассортимента и проверкой Groq.\n"
        "Все сценарии запускаются через inline-кнопки ниже."
    )


def format_files_menu_text(notice=None):
    lines = [
        "🗂 <b>Файлы сайта и backup</b>",
        "",
        "Здесь можно безопасно заменить один из основных файлов сайта, скачать backup-архив или откатить сайт к последней сохранённой копии.",
        "Перед каждой заменой бот полностью очищает старый backup и заново копирует туда всю папку сайта.",
    ]
    if notice:
        lines.extend(["", f"• {escape(notice)}"])
    return "\n".join(lines)


def format_upload_text(notice=None):
    lines = [
        "🗂 <b>Замена файла сайта</b>",
        "",
        "Сначала выберите готовый файл кнопкой ниже, потом просто отправьте новый файл документом.",
        "Ничего вручную писать не нужно.",
        "",
        "Что можно заменить:",
    ]
    for option in config.SITE_FILE_OPTIONS:
        lines.append(
            f"\n<b>{escape(option['label'])}</b>\n"
            f"<code>{escape(option['path'])}</code>\n"
            f"{escape(option['description'])}"
        )
    if notice:
        lines.extend(["", f"• {escape(notice)}"])
    return "\n".join(lines)


def format_product_editor(draft, pending_field=None, notice=None):
    lines = [
        "🧩 <b>Добавление товара</b>",
        "",
        "Заполняем только главное: название, цена, описание, размер, категория и картинки.",
        "SKU, валюта, продавец, источник и slug будут подставлены автоматически.",
    ]
    if pending_field:
        label, prompt = PRODUCT_FIELDS[pending_field]
        lines.extend(["", f"Сейчас ожидаю поле: <b>{label}</b>", escape(prompt)])
    if notice:
        lines.extend(["", f"• {escape(notice)}"])
    lines.extend([
        "",
        f"<b>Название:</b> {escape(short_value(draft.get('name')))}",
        f"<b>Цена:</b> {escape(short_value(draft.get('price')))}",
        f"<b>Описание:</b> {escape(short_value(draft.get('description')))}",
        f"<b>Размер:</b> {escape(short_value(draft.get('size')))}",
        f"<b>Категория:</b> {escape(short_value(draft.get('category')))}",
        f"<b>Изображения:</b> {escape(short_value(draft.get('images')))}",
        f"<b>Авто SKU:</b> {escape(short_value(draft.get('sku')) or 'сгенерируется при сохранении')}",
    ])
    return "\n".join(lines)


def format_maintenance_text(state):
    status = "включены" if state.get("enabled") else "выключены"
    return (
        "🛠 <b>Техработы</b>\n\n"
        f"Текущее состояние: <b>{status}</b>\n"
        f"Заголовок: <b>{escape(state.get('title') or '—')}</b>\n"
        f"Сообщение: <b>{escape(state.get('message') or '—')}</b>\n\n"
        "Текст фиксированный. Здесь доступно только включение или выключение режима."
    )


def format_product_card(product, mode="browse"):
    if mode == "delete":
        action_hint = "Ниже можно удалить товар из каталога."
    elif mode == "edit":
        action_hint = "Ниже можно перейти к редактированию полей."
    else:
        action_hint = "Ниже можно открыть товар на сайте."
    return (
        "📦 <b>Карточка товара</b>\n\n"
        f"<b>Название:</b> {escape(product.get('name') or '—')}\n"
        f"<b>SKU:</b> {escape(str(product.get('sku') or '—'))}\n"
        f"<b>Slug:</b> {escape(str(product.get('slug') or '—'))}\n"
        f"<b>Цена:</b> {escape(str(product.get('price') if product.get('price') is not None else '—'))}\n"
        f"<b>Размер:</b> {escape(str(product.get('size') or '—'))}\n"
        f"<b>Категория:</b> {escape(str(product.get('category') or '—'))}\n"
        f"<b>Описание:</b> {escape(truncate_value(product.get('description')))}\n\n"
        f"<b>Фото:</b> {len(product.get('images') or [])}\n"
        f"{action_hint}"
    )


def format_product_picker(mode, page=1, total_pages=1, total=0):
    titles = {
        "browse": "🔎 <b>Товары</b>",
        "delete": "🗑 <b>Удаление товара</b>",
        "edit": "✏️ <b>Редактирование товара</b>",
    }
    return (
        f"{titles.get(mode, titles['browse'])}\n\n"
        "Выберите товар из списка или нажмите поиск.\n"
        f"Страница: <b>{page}/{total_pages}</b>\n"
        f"Всего товаров: <b>{total}</b>"
    )


def format_assortment_text():
    stats = storage.product_stats()
    categories = stats["categories"] or [("Без данных", 0)]
    sizes = stats["sizes"] or [("Без данных", 0)]
    price_min = f"{stats['price_min']:,.0f}".replace(",", " ") if stats["price_min"] is not None else "—"
    price_max = f"{stats['price_max']:,.0f}".replace(",", " ") if stats["price_max"] is not None else "—"

    lines = [
        "📊 <b>Сводка ассортимента</b>",
        "",
        f"Всего товаров: <b>{stats['total']}</b>",
        f"С фото: <b>{stats['with_images']}</b>",
        f"Без фото: <b>{stats['without_images']}</b>",
        f"Диапазон цен: <b>{price_min} - {price_max}</b>",
        "",
        "<b>Категории:</b>",
    ]
    lines.extend(f"• {escape(name)}: <b>{count}</b>" for name, count in categories[:6])
    lines.extend(["", "<b>Популярные размеры:</b>"])
    lines.extend(f"• {escape(name)}: <b>{count}</b>" for name, count in sizes[:8])
    return "\n".join(lines)


async def send_or_edit_panel(update, context, text, reply_markup):
    query = update.callback_query
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.effective_chat.send_message(text, reply_markup=reply_markup, parse_mode="HTML")


async def send_status_proof(chat_id, context, title):
    payload = services.fetch_site_status()
    image_path = services.create_status_proof_image(title, payload)
    caption = (
        f"{title}\n"
        f"HTTP статус: {payload['status_code'] if payload['status_code'] is not None else 'ERR'}\n"
        f"URL: {config.SITE_BASE_URL}"
    )
    with open(image_path, "rb") as file:
        await context.bot.send_photo(chat_id=chat_id, photo=InputFile(file), caption=caption)


async def send_product_card(update, context, product, mode="browse"):
    query = update.callback_query
    text = format_product_card(product, mode=mode)
    keyboard = keyboards.product_preview_keyboard(product, mode=mode)
    images = product.get("images") or []
    photo_source = services.resolve_product_image(images[0]) if images else None

    if query:
        try:
            await query.edit_message_text("Карточка товара отправлена ниже.", parse_mode="HTML")
        except Exception:
            pass

    if photo_source:
        if hasattr(photo_source, "exists"):
            with open(photo_source, "rb") as file:
                await update.effective_chat.send_photo(
                    photo=InputFile(file),
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        else:
            await update.effective_chat.send_photo(
                photo=photo_source,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        return

    await update.effective_chat.send_message(text, reply_markup=keyboard, parse_mode="HTML")


@authorized_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting_site_upload", None)
    context.user_data.pop("selected_site_file", None)
    context.user_data.pop("pending_import_link", None)
    context.user_data.pop("pending_product_field", None)
    context.user_data.pop("pending_edit_field", None)
    context.user_data.pop("pending_edit_sku", None)
    context.user_data.pop("pending_search_query", None)
    await send_or_edit_panel(update, context, format_home_text(), keyboards.main_menu_keyboard())


@authorized_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("pending_import_link"):
        await apply_import_link(update, context)
        return
    if context.user_data.get("pending_edit_field"):
        await apply_edit_field(update, context)
        return
    if context.user_data.get("pending_product_field"):
        await apply_product_field(update, context)
        return
    if context.user_data.get("pending_search_query"):
        await apply_search_query(update, context)
        return
    if context.user_data.get("awaiting_site_upload"):
        selected_option_id = context.user_data.get("selected_site_file")
        selected_option = None
        if selected_option_id:
            try:
                selected_option = services.get_site_file_option(selected_option_id)
            except ValueError:
                selected_option = None
        await update.effective_chat.send_message(
            (
                f"Сейчас жду файл для замены <b>{escape(selected_option['label'])}</b>.\n"
                f"Он будет записан в <code>{escape(selected_option['path'])}</code>."
                if selected_option
                else "Сначала выберите файл кнопкой, а потом отправьте документ."
            ),
            parse_mode="HTML",
        )
        return
    await update.effective_chat.send_message(
        "Используйте inline-кнопки панели управления.",
        parse_mode="HTML",
    )


async def open_product_editor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["product_draft"] = storage.create_empty_product()
    context.user_data["pending_product_field"] = None
    await send_or_edit_panel(update, context, format_product_editor(context.user_data["product_draft"]), keyboards.product_editor_keyboard())


async def open_delete_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_product_picker(update, context, "delete")


async def open_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_product_picker(update, context, "browse")


async def open_edit_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_product_picker(update, context, "edit")


async def open_product_picker(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="browse"):
    await send_or_edit_panel(
        update,
        context,
        {
            "browse": "🔎 <b>Поиск и список товаров</b>\n\nВыберите способ просмотра товаров.",
            "delete": "🗑 <b>Удаление товара</b>\n\nВыберите товар списком или найдите его поиском.",
            "edit": "✏️ <b>Редактирование товара</b>\n\nВыберите товар списком или найдите его поиском.",
        }.get(mode, "Выберите способ."),
        keyboards.product_pick_method_keyboard(mode),
    )


async def open_product_list(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="browse", page=1):
    products, page, total_pages, total = storage.list_products(page=page, page_size=7)
    context.user_data["browse_products"] = products
    context.user_data["browse_mode"] = mode
    context.user_data["browse_page"] = page
    await send_or_edit_panel(
        update,
        context,
        format_product_picker(mode, page, total_pages, total),
        keyboards.product_list_keyboard(products, mode=mode, page=page, total_pages=total_pages),
    )


async def open_product_search(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="browse"):
    context.user_data["pending_search_query"] = "browse"
    if mode in {"browse", "delete", "edit"}:
        context.user_data["pending_search_query"] = mode
    await send_or_edit_panel(
        update,
        context,
        "🔎 <b>Поиск товара</b>\n\nПришлите SKU или часть названия.",
        keyboards.product_pick_method_keyboard(mode),
    )


async def open_files_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, notice=None):
    await send_or_edit_panel(update, context, format_files_menu_text(notice), keyboards.files_menu_keyboard())


async def open_site_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_site_upload"] = True
    context.user_data.pop("selected_site_file", None)
    await send_or_edit_panel(update, context, format_upload_text(), keyboards.upload_keyboard())


async def open_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = storage.load_maintenance_state()
    await send_or_edit_panel(update, context, format_maintenance_text(state), keyboards.maintenance_keyboard(state.get("enabled")))


async def send_site_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = storage.load_products()
    maintenance = storage.load_maintenance_state()
    status = "включены" if maintenance.get("enabled") else "выключены"
    backup_status = "есть" if config.BACKUP_DIR.exists() else "ещё не создан"
    text = (
        "<b>Статус сайта</b>\n\n"
        f"Товаров в каталоге: <b>{len(products)}</b>\n"
        f"Техработы: <b>{status}</b>\n"
        f"Backup: <b>{backup_status}</b>\n"
        f"URL сайта: <b>{escape(config.SITE_BASE_URL)}</b>\n"
        f"Обновлено: <b>{escape(str(maintenance.get('updated_at') or '—'))}</b>"
    )
    await send_or_edit_panel(update, context, text, keyboards.main_menu_keyboard())


async def send_assortment_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_or_edit_panel(update, context, format_assortment_text(), keyboards.main_menu_keyboard())


async def send_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok, details = services.ping_groq()
    prefix = "✅" if ok else "❌"
    await send_or_edit_panel(update, context, f"{prefix} <b>Пинг Groq</b>\n\n{escape(details)}", keyboards.main_menu_keyboard())


async def send_backup_archive(chat_id, context):
    try:
        archive_path = services.create_backup_archive()
    except ValueError as error:
        await context.bot.send_message(chat_id=chat_id, text=str(error))
        return

    try:
        with open(archive_path, "rb") as file:
            await context.bot.send_document(
                chat_id=chat_id,
                document=InputFile(file, filename=archive_path.name),
                caption="Актуальный backup сайта перед последним обновлением.",
            )
    finally:
        services.remove_backup_archive()


async def apply_product_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get("pending_product_field")
    draft = context.user_data.get("product_draft", storage.create_empty_product())
    value = (update.message.text or "").strip()

    if field == "images":
        draft[field] = storage.normalize_images(value)
    elif field in {"price", "old_price"}:
        draft[field] = value
    else:
        if value in {"-", "—"} and field in {"size", "category", "old_price"}:
            value = ""
        draft[field] = value

    context.user_data["product_draft"] = draft
    context.user_data["pending_product_field"] = None
    await update.effective_chat.send_message(
        format_product_editor(draft, notice=f"Поле «{PRODUCT_FIELDS[field][0]}» обновлено."),
        reply_markup=keyboards.product_editor_keyboard(),
        parse_mode="HTML",
    )


async def apply_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get("pending_edit_field")
    sku = context.user_data.get("pending_edit_sku")
    value = (update.message.text or "").strip()

    if field not in PRODUCT_FIELDS or not sku:
        context.user_data.pop("pending_edit_field", None)
        context.user_data.pop("pending_edit_sku", None)
        await update.effective_chat.send_message("Редактирование сброшено. Откройте товар заново.")
        return

    try:
        product = storage.update_product(sku, {field: value})
    except ValueError as error:
        await update.effective_chat.send_message(f"Не сохранил: {escape(str(error))}", parse_mode="HTML")
        return

    context.user_data.pop("pending_edit_field", None)
    context.user_data.pop("pending_edit_sku", None)
    await update.effective_chat.send_message(
        f"✅ Поле «{PRODUCT_FIELDS[field][0]}» обновлено.",
        reply_markup=keyboards.product_edit_keyboard(product["sku"]),
    )
    await send_product_card(update, context, product, mode="edit")


async def apply_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("pending_search_query")
    query = (update.message.text or "").strip()
    context.user_data["pending_search_query"] = None

    products = storage.find_products(query, limit=7)
    if not products:
        await update.effective_chat.send_message("Ничего не нашёл. Попробуйте другой SKU или фрагмент названия.")
        return

    context.user_data["browse_products"] = products
    context.user_data["browse_mode"] = mode
    title = "Результаты для удаления:" if mode == "delete" else "Результаты для редактирования:" if mode == "edit" else "Результаты поиска:"
    keyboard_mode = mode if mode in {"delete", "edit"} else "browse"
    await update.effective_chat.send_message(
        title,
        reply_markup=keyboards.product_list_keyboard(products, mode=keyboard_mode, page=1, total_pages=1),
    )


async def apply_import_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = (update.message.text or "").strip()
    context.user_data.pop("pending_import_link", None)
    await update.effective_chat.send_message("⏳ Импортирую товар: читаю ссылку, сохраняю фото и info.json в images...")
    try:
        result = services.import_uzum_product_from_url(url)
    except ValueError as error:
        await update.effective_chat.send_message(
            f"Не получилось импортировать: {escape(str(error))}",
            parse_mode="HTML",
            reply_markup=keyboards.product_editor_keyboard(),
        )
        return
    except Exception as error:
        await update.effective_chat.send_message(
            f"Импорт остановился с ошибкой: {escape(str(error))}",
            parse_mode="HTML",
            reply_markup=keyboards.product_editor_keyboard(),
        )
        return

    await update.effective_chat.send_message(
        "✅ <b>Товар добавлен через images</b>\n\n"
        f"Название: {escape(result['name'] or '—')}\n"
        f"SKU: {escape(str(result['sku'] or '—'))}\n"
        f"Папка: <code>images/uzum_images/{escape(result['folder'])}</code>\n"
        f"Фото сохранено: <b>{result['images']}</b>\n\n"
        "Сайт подхватит товар из images автоматически.",
        parse_mode="HTML",
        reply_markup=keyboards.main_menu_keyboard(),
    )


@authorized_only
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document if update.message else None
    if document and context.user_data.get("pending_edit_field") == "images":
        await apply_uploaded_product_image(update, context, document.file_id, document.file_name)
        return
    if document and context.user_data.get("pending_product_field") == "images":
        await apply_uploaded_product_image(update, context, document.file_id, document.file_name)
        return

    if not context.user_data.get("awaiting_site_upload"):
        return

    if not document:
        return

    option_id = context.user_data.get("selected_site_file")
    if not option_id:
        await update.effective_chat.send_message(
            "Сначала выберите, какой именно файл сайта хотите заменить.",
            reply_markup=keyboards.upload_keyboard(),
        )
        return

    option = services.get_site_file_option(option_id)
    try:
        result = await services.replace_site_file_from_telegram(document, context.bot, option["path"])
    except ValueError as error:
        await update.effective_chat.send_message(
            format_upload_text(str(error)),
            reply_markup=keyboards.upload_keyboard(),
            parse_mode="HTML",
        )
        return
    except Exception as error:
        await update.effective_chat.send_message(
            format_upload_text(f"Не удалось обновить файл: {error}"),
            reply_markup=keyboards.upload_keyboard(),
            parse_mode="HTML",
        )
        return

    context.user_data["awaiting_site_upload"] = False
    context.user_data.pop("selected_site_file", None)
    await update.effective_chat.send_message(
        "✅ <b>Файл сайта обновлён</b>\n\n"
        f"Файл: <b>{escape(option['label'])}</b>\n"
        f"Путь: <code>{escape(result['relative_path'])}</code>\n"
        f"Backup: <code>{escape(str(result['backup_dir']))}</code>",
        parse_mode="HTML",
        reply_markup=keyboards.files_menu_keyboard(),
    )


@authorized_only
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    if context.user_data.get("pending_edit_field") != "images" and context.user_data.get("pending_product_field") != "images":
        return
    photo = update.message.photo[-1]
    await apply_uploaded_product_image(update, context, photo.file_id, "telegram_photo.jpg")


async def apply_uploaded_product_image(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id, original_name=None):
    try:
        image_path = await services.save_telegram_product_image(file_id, context.bot, original_name)
    except Exception as error:
        await update.effective_chat.send_message(f"Не получилось сохранить картинку: {escape(str(error))}", parse_mode="HTML")
        return

    if context.user_data.get("pending_edit_field") == "images":
        sku = context.user_data.get("pending_edit_sku")
        product = storage.get_product(sku)
        images = list(product.get("images") or []) if product else []
        images.append(image_path)
        product = storage.update_product(sku, {"images": images})
        context.user_data.pop("pending_edit_field", None)
        context.user_data.pop("pending_edit_sku", None)
        await update.effective_chat.send_message(
            "✅ Картинка добавлена к товару.",
            reply_markup=keyboards.product_edit_keyboard(product["sku"]),
        )
        await send_product_card(update, context, product, mode="edit")
        return

    draft = context.user_data.get("product_draft", storage.create_empty_product())
    draft["images"] = list(draft.get("images") or []) + [image_path]
    context.user_data["product_draft"] = draft
    context.user_data["pending_product_field"] = None
    await update.effective_chat.send_message(
        format_product_editor(draft, notice="Картинка добавлена."),
        reply_markup=keyboards.product_editor_keyboard(),
        parse_mode="HTML",
    )


@authorized_only
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data or ""

    if data == "noop":
        return
    if data == "menu:home":
        await start(update, context)
        return
    if data == "menu:add":
        await open_product_editor(update, context)
        return
    if data == "menu:edit":
        await open_edit_products(update, context)
        return
    if data == "menu:delete":
        await open_delete_search(update, context)
        return
    if data == "menu:find":
        await open_search(update, context)
        return
    if data == "menu:status":
        await send_site_status(update, context)
        return
    if data == "menu:assortment":
        await send_assortment_summary(update, context)
        return
    if data == "menu:maintenance":
        await open_maintenance(update, context)
        return
    if data == "menu:ping":
        await send_ping(update, context)
        return
    if data in {"browse:search", "delete:search", "edit:search"}:
        await open_product_search(update, context, data.split(":")[0])
        return
    if data.startswith(("browse:list:", "delete:list:", "edit:list:")):
        mode, _, page_text = data.partition(":list:")
        await open_product_list(update, context, mode=mode, page=int(page_text or 1))
        return
    if data == "menu:files":
        await open_files_menu(update, context)
        return
    if data == "files:replace":
        await open_site_upload(update, context)
        return
    if data == "files:backup:download":
        await send_backup_archive(query.message.chat_id, context)
        await open_files_menu(update, context, "Backup.zip отправлен и удалён у бота после отправки.")
        return
    if data == "files:backup:restore":
        await query.edit_message_text(
            "⚠️ <b>Откат сайта</b>\n\n"
            "Сайт будет полностью восстановлен из последней папки backup.\n"
            "Текущие файлы сайта будут заменены.",
            parse_mode="HTML",
            reply_markup=keyboards.backup_restore_keyboard(),
        )
        return
    if data == "files:backup:restore:confirm":
        try:
            services.restore_site_from_backup()
        except ValueError as error:
            await open_files_menu(update, context, str(error))
            return
        await open_files_menu(update, context, "Сайт восстановлен из последнего backup.")
        await send_status_proof(query.message.chat_id, context, "Подтверждение: сайт после отката")
        return
    if data == "upload:cancel":
        context.user_data["awaiting_site_upload"] = False
        context.user_data.pop("selected_site_file", None)
        await open_files_menu(update, context)
        return
    if data.startswith("upload:file:"):
        option_id = data.split(":", 2)[-1]
        try:
            option = services.get_site_file_option(option_id)
        except ValueError as error:
            await query.edit_message_text(str(error), reply_markup=keyboards.files_menu_keyboard())
            return
        context.user_data["awaiting_site_upload"] = True
        context.user_data["selected_site_file"] = option_id
        await query.edit_message_text(
            "📥 <b>Файл выбран для замены</b>\n\n"
            f"<b>{escape(option['label'])}</b>\n"
            f"Путь: <code>{escape(option['path'])}</code>\n"
            f"{escape(option['description'])}\n\n"
            "Теперь просто отправьте новый файл документом. Backup будет создан автоматически перед заменой.",
            parse_mode="HTML",
            reply_markup=keyboards.selected_upload_keyboard(option_id),
        )
        return

    if data.startswith("product:set:"):
        field = data.split(":")[-1]
        if field in PRODUCT_FIELDS:
            context.user_data["pending_product_field"] = field
            draft = context.user_data.get("product_draft", storage.create_empty_product())
            await query.edit_message_text(
                format_product_editor(draft, pending_field=field),
                reply_markup=keyboards.product_editor_keyboard(),
                parse_mode="HTML",
            )
        return
    if data == "product:from_link":
        context.user_data["pending_import_link"] = True
        await query.edit_message_text(
            "🔗 <b>Добавление товара по ссылке</b>\n\n"
            "Пришлите ссылку на товар Uzum одним сообщением. Бот сохранит товар в папку <code>images/uzum_images</code>, скачает фото и добавит ссылку в <code>images/uz_links.json</code>.",
            parse_mode="HTML",
            reply_markup=keyboards.product_editor_keyboard(),
        )
        return
    if data.startswith("edit:set:"):
        _, _, rest = data.partition("edit:set:")
        field, _, sku = rest.partition(":")
        if field in PRODUCT_FIELDS and sku:
            context.user_data["pending_edit_field"] = field
            context.user_data["pending_edit_sku"] = sku
            product = storage.get_product(sku)
            current = product.get(field) if product else ""
            await query.edit_message_text(
                "✏️ <b>Редактирование товара</b>\n\n"
                f"Поле: <b>{escape(PRODUCT_FIELDS[field][0])}</b>\n"
                f"Сейчас: {escape(truncate_value(current, 240))}\n\n"
                f"{escape(PRODUCT_FIELDS[field][1])}",
                parse_mode="HTML",
                reply_markup=keyboards.product_edit_keyboard(sku),
            )
        return
    if data.startswith("edit:category:"):
        _, _, rest = data.partition("edit:category:")
        category, _, sku = rest.rpartition(":")
        try:
            product = storage.update_product(sku, {"category": category})
        except ValueError as error:
            await query.edit_message_text(f"Не сохранил: {escape(str(error))}", parse_mode="HTML")
            return
        await query.edit_message_text(
            f"✅ Категория обновлена: <b>{escape(category)}</b>",
            parse_mode="HTML",
            reply_markup=keyboards.product_edit_keyboard(product["sku"]),
        )
        await send_product_card(update, context, product, mode="edit")
        return
    if data.startswith("product:category:"):
        category = data.split(":", 2)[-1]
        draft = context.user_data.get("product_draft", storage.create_empty_product())
        draft["category"] = category
        context.user_data["product_draft"] = draft
        context.user_data["pending_product_field"] = None
        await query.edit_message_text(
            format_product_editor(draft, notice=f"Категория «{category}» установлена."),
            reply_markup=keyboards.product_editor_keyboard(),
            parse_mode="HTML",
        )
        return

    if data == "product:reset":
        context.user_data["product_draft"] = storage.create_empty_product()
        context.user_data["pending_product_field"] = None
        await query.edit_message_text(
            format_product_editor(context.user_data["product_draft"], notice="Черновик очищен."),
            reply_markup=keyboards.product_editor_keyboard(),
            parse_mode="HTML",
        )
        return

    if data == "product:cancel":
        context.user_data.pop("product_draft", None)
        context.user_data.pop("pending_product_field", None)
        context.user_data.pop("pending_import_link", None)
        await start(update, context)
        return

    if data == "product:save":
        draft = context.user_data.get("product_draft", storage.create_empty_product())
        try:
            product = storage.add_product(draft)
        except ValueError as error:
            await query.edit_message_text(
                format_product_editor(draft, notice=str(error)),
                reply_markup=keyboards.product_editor_keyboard(),
                parse_mode="HTML",
            )
            return
        context.user_data.pop("product_draft", None)
        context.user_data.pop("pending_product_field", None)
        await query.edit_message_text(
            "✅ <b>Товар сохранён</b>\n\n"
            f"Название: {escape(product['name'])}\n"
            f"SKU: {escape(product['sku'])}\n"
            f"Slug: {escape(product['slug'])}",
            parse_mode="HTML",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    if data == "maintenance:toggle":
        state = storage.load_maintenance_state()
        state["enabled"] = not bool(state.get("enabled"))
        storage.save_maintenance_state(state)
        await query.edit_message_text(
            format_maintenance_text(state),
            parse_mode="HTML",
            reply_markup=keyboards.maintenance_keyboard(state.get("enabled")),
        )
        title = "Подтверждение: сайт включён" if not state.get("enabled") else "Подтверждение: сайт в техработах"
        await send_status_proof(query.message.chat_id, context, title)
        return

    if data == "maintenance:check":
        await send_status_proof(query.message.chat_id, context, "Проверка доступности сайта")
        return

    if data.startswith("browse:pick:") or data.startswith("delete:pick:") or data.startswith("edit:pick:"):
        mode = data.split(":", 1)[0]
        try:
            index = int(data.rsplit(":", 1)[-1])
        except ValueError:
            await query.edit_message_text("Не получилось открыть товар.")
            return
        products = context.user_data.get("browse_products", [])
        product = products[index] if 0 <= index < len(products) else None
        if not product:
            await query.edit_message_text("Не получилось найти товар.")
            return
        await send_product_card(update, context, product, mode=mode)
        return

    if data.startswith("browse:show:") or data.startswith("delete:show:") or data.startswith("edit:show:"):
        sku = data.split(":", 2)[-1]
        product = storage.get_product(sku)
        if not product:
            await query.edit_message_text("Не получилось найти товар.")
            return
        mode = "delete" if data.startswith("delete:") else "edit" if data.startswith("edit:") else "browse"
        await send_product_card(update, context, product, mode=mode)
        return

    if data == "edit:fields:":
        return
    if data.startswith("edit:fields:"):
        sku = data.split(":", 2)[-1]
        product = storage.get_product(sku)
        if not product:
            await query.edit_message_text("Товар не найден.")
            return
        await query.edit_message_text(
            "✏️ <b>Что изменить?</b>\n\n"
            f"{escape(product.get('name') or sku)}",
            parse_mode="HTML",
            reply_markup=keyboards.product_edit_keyboard(sku),
        )
        return

    if data == "browse:back" or data == "delete:back" or data == "edit:back":
        products = context.user_data.get("browse_products", [])
        if not products:
            await start(update, context)
            return
        mode = context.user_data.get("browse_mode") or ("delete" if data.startswith("delete") else "edit" if data.startswith("edit") else "browse")
        title = "Результаты для удаления:" if mode == "delete" else "Результаты для редактирования:" if mode == "edit" else "Результаты поиска:"
        await query.edit_message_text(
            title,
            reply_markup=keyboards.product_list_keyboard(products, mode=mode, page=1, total_pages=1),
        )
        return

    if data.startswith("delete:confirm:"):
        sku = data.split(":", 2)[-1]
        product = next((item for item in storage.load_products() if str(item.get("sku")) == sku), None)
        if not product:
            await query.edit_message_text("Товар уже удалён.")
            return
        await query.edit_message_text(
            "⚠️ <b>Удаление товара</b>\n\n"
            f"Вы точно хотите удалить:\n<b>{escape(product.get('name') or sku)}</b>\nSKU: <b>{escape(str(sku))}</b>",
            parse_mode="HTML",
            reply_markup=keyboards.delete_confirm_keyboard(sku),
        )
        return

    if data.startswith("delete:apply:"):
        sku = data.split(":", 2)[-1]
        try:
            deleted = storage.delete_product(sku)
        except ValueError as error:
            await query.edit_message_text(f"❌ {escape(str(error))}", parse_mode="HTML", reply_markup=keyboards.main_menu_keyboard())
            return
        products = context.user_data.get("browse_products", [])
        context.user_data["browse_products"] = [item for item in products if str(item.get("sku")) != sku]
        await query.edit_message_text(
            "✅ <b>Товар удалён</b>\n\n"
            f"Название: {escape(deleted.get('name') or '—')}\n"
            f"SKU: {escape(str(deleted.get('sku') or '—'))}",
            parse_mode="HTML",
            reply_markup=keyboards.main_menu_keyboard(),
        )
