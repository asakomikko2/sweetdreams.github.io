from html import escape

from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

import config
import handlers
import services
import storage


def build_startup_message():
    products = storage.load_products()
    maintenance = storage.load_maintenance_state()
    site = services.fetch_site_status(timeout=4)
    maintenance_text = "включены" if maintenance.get("enabled") else "выключены"
    site_text = f"HTTP {site['status_code']}" if site["status_code"] is not None else "недоступен"
    return (
        f"<b>{escape(config.BOT_NAME)} запущен</b>\n\n"
        f"Товаров в каталоге: <b>{len(products)}</b>\n"
        f"Техработы: <b>{maintenance_text}</b>\n"
        f"Сайт: <b>{escape(site_text)}</b>\n"
        f"Админов в доступе: <b>{len(config.ALLOWED_USER_IDS)}</b>"
    )


async def notify_startup(application):
    print(f"{config.BOT_NAME} запущен. Админов: {len(config.ALLOWED_USER_IDS)}.")
    try:
        await application.bot.set_my_commands([
            BotCommand("start", "Открыть панель управления"),
            BotCommand("menu", "Показать меню"),
            BotCommand("help", "Помощь по боту"),
        ])
    except Exception as error:
        print(f"Не удалось обновить команды бота: {error}")

    text = build_startup_message()
    for user_id in config.ALLOWED_USER_IDS:
        try:
            await application.bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
        except Exception as error:
            print(f"Не удалось отправить уведомление о запуске {user_id}: {error}")


def main():
    if not config.BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN.")
    if not config.ALLOWED_USER_IDS:
        raise RuntimeError("Не задан BOT_ALLOWED_USER_IDS.")

    application = Application.builder().token(config.BOT_TOKEN).post_init(notify_startup).build()

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("menu", handlers.start))
    application.add_handler(CommandHandler("help", handlers.start))
    application.add_handler(CallbackQueryHandler(handlers.handle_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handlers.handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handlers.handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text))

    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
