from flask import Flask, request, jsonify
import telegram

app = Flask(__name__)
bot = telegram.Bot(token='7846505135:AAHAMEpaMYKqDsRZBeMFw0XN9IHwkm2zDOg')
chat_id = -1002467157048

@app.route("/submit", methods=["POST"])
def submit_order():
    data = request.json
    message = (
        "@top4ik3333\n\n"
        "🛍️ Новый заказ!\n\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"📨 Telegram: @{data['username']}\n"
        "📦 Товары:\n" + "\n".join(f"• {item}" for item in data['cart'])
    )
    bot.send_message(chat_id=chat_id, text=message)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("✅ Бот запущен: http://127.0.0.1:5000")
    app.run(debug=True)