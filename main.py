# main.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    Filters,
    PreCheckoutQueryHandler,
    CallbackQueryHandler
)
import asyncio
import json
import logging
import requests
import sqlite3
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = '7814519439:AAGHwL-o20low67Mh-HB1Cs0fTmNlnX6RwQ'
WEB_APP_URL = 'https://frezzdev.github.io/basic-rel/'
PROVIDER_TOKEN = 'ВАШ_ПЛАТЕЖНЫЙ_ТОКЕН'  # Замените на реальный токен
STARS_EXCHANGE_RATE = 0.012987  # 1 STAR = 0.012987 USDT

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('orion_wallet.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 1000.0,
            stars INTEGER DEFAULT 500
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            currency TEXT,
            recipient TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Получение курсов криптовалют
def get_crypto_rates():
    try:
        response = requests.get('https://api.binance.com/api/v3/ticker/24hr', timeout=5)
        response.raise_for_status()
        data = response.json()
        
        rates = {}
        for item in data:
            symbol = item['symbol']
            if symbol.endswith('USDT'):
                coin = symbol.replace('USDT', '').lower()
                if coin in ['btc', 'eth', 'bnb', 'sol', 'xrp', 'ada', 'doge', 'dot', 'matic']:
                    rates[coin] = {
                        'price': float(item['lastPrice']),
                        'change': float(item['priceChangePercent'])
                    }
        rates['ton'] = {'price': 5.42, 'change': 2.3}
        return rates
    except requests.RequestException as e:
        logger.error(f"Ошибка получения курсов: {e}")
        return {}

# Обработчик команды /start
async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    
    conn = sqlite3.connect('orion_wallet.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user_data = c.fetchone()
    
    if not user_data:
        c.execute('INSERT INTO users (user_id, username, balance, stars) VALUES (?, ?, ?, ?)',
                  (user_id, user.username or user.full_name, 1000.0, 500))
        conn.commit()
    
    conn.close()
    
    keyboard = [[
        InlineKeyboardButton(
            text="Открыть Orion Wallet",
            web_app={'url': WEB_APP_URL}
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f'Привет, @{user.username or user.full_name}! Добро пожаловать в Orion Wallet.\n'
        'Нажмите кнопку ниже, чтобы открыть кошелек:',
        reply_markup=reply_markup
    )

# Получение данных пользователя
async def user_data(update: Update, context: CallbackContext) -> None:
    try:
        user_id = int(context.args[0])
        conn = sqlite3.connect('orion_wallet.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            await update.message.reply_text(
                f'Данные пользователя @{user_data[1]}:\n'
                f'Баланс: {user_data[2]:.2f} USDT\n'
                f'Stars: {user_data[3]}\n'
            )
        else:
            await update.message.reply_text('Пользователь не найден')
    except (IndexError, ValueError):
        await update.message.reply_text('Ошибка: укажите корректный user_id')

# API для получения данных пользователя
async def user_data_api(update: Update, context: CallbackContext) -> None:
    try:
        user_id = int(update.message.text.split('=')[1])
        conn = sqlite3.connect('orion_wallet.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            await update.message.reply_json({
                'status': 'success',
                'user_id': user_id,
                'username': user_data[1],
                'balance': user_data[2],
                'stars': user_data[3]
            })
        else:
            await update.message.reply_json({'status': 'error', 'message': 'User not found'})
    except (IndexError, ValueError):
        await update.message.reply_json({'status': 'error', 'message': 'Invalid user_id'})

# API для получения курсов криптовалют
async def crypto_rates_api(update: Update, context: CallbackContext) -> None:
    rates = get_crypto_rates()
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('orion_wallet.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        for coin, data in rates.items():
            data['balance'] = user_data[0] / data['price'] * 0.1
    
    await update.message.reply_json(rates)

# Обработка данных из WebApp
async def handle_webapp_data(update: Update, context: CallbackContext) -> None:
    try:
        data = json.loads(update.web_app_data.data)
        user_id = data.get('user_id')
        action_type = data.get('type')
        
        conn = sqlite3.connect('orion_wallet.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user_data = c.fetchone()
        
        if not user_data:
            logger.error(f"Пользователь не найден: {user_id}")
            conn.close()
            return
        
        if action_type == 'buy_stars':
            amount = data.get('amount', 0)
            if amount <= 0:
                logger.error(f"Некорректное количество Stars: {amount}")
                conn.close()
                return
            c.execute('UPDATE users SET stars = stars + ? WHERE user_id = ?', (amount, user_id))
            c.execute('INSERT INTO transactions (user_id, type, amount, date) VALUES (?, ?, ?, ?)',
                      (user_id, 'buy_stars', amount, datetime.now().isoformat()))
            conn.commit()
            logger.info(f"Пользователь {user_id} купил {amount} Stars")
        
        elif action_type == 'exchange_stars':
            amount = data.get('amount', 0)
            currency = data.get('currency', 'usdt')
            if amount <= 0 or user_data[3] < amount:
                logger.error(f"Недостаточно Stars или некорректное количество: {amount}")
                conn.close()
                return
            crypto_amount = amount * STARS_EXCHANGE_RATE
            c.execute('UPDATE users SET stars = stars - ?, balance = balance + ? WHERE user_id = ?',
                      (amount, crypto_amount, user_id))
            c.execute('INSERT INTO transactions (user_id, type, amount, currency, crypto_amount, date) VALUES (?, ?, ?, ?, ?, ?)',
                      (user_id, 'exchange_stars', amount, currency, crypto_amount, datetime.now().isoformat()))
            conn.commit()
            logger.info(f"Пользователь {user_id} обменял {amount} Stars на {crypto_amount:.6f} {currency.upper()}")
        
        elif action_type == 'withdraw_stars':
            amount = data.get('amount', 0)
            recipient = data.get('recipient', '')
            if amount <= 0 or user_data[3] < amount:
                logger.error(f"Недостаточно Stars или некорректное количество: {amount}")
                conn.close()
                return
            c.execute('UPDATE users SET stars = stars - ? WHERE user_id = ?', (amount, user_id))
            c.execute('INSERT INTO transactions (user_id, type, amount, recipient, date) VALUES (?, ?, ?, ?, ?)',
                      (user_id, 'withdraw_stars', amount, recipient, datetime.now().isoformat()))
            conn.commit()
            logger.info(f"Пользователь {user_id} отправил {amount} Stars пользователю {recipient}")
        
        conn.close()
    
    except json.JSONDecodeError:
        logger.error("Ошибка декодирования JSON из WebApp")
    except Exception as e:
        logger.error(f"Ошибка обработки WebApp данных: {e}")

# Обработка предоплатного запроса
async def precheckout(update: Update, context: CallbackContext) -> None:
    await update.pre_checkout_query.answer(ok=True)

# Обработка успешного платежа
async def successful_payment(update: Update, context: CallbackContext) -> None:
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('orion_wallet.db')
    c = conn.cursor()
    stars_amount = int(payment.total_amount / 100)
    c.execute('UPDATE users SET stars = stars + ? WHERE user_id = ?', (stars_amount, user_id))
    c.execute('INSERT INTO transactions (user_id, type, amount, date) VALUES (?, ?, ?, ?)',
              (user_id, 'buy_stars', stars_amount, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f'✅ Спасибо за покупку! Вы получили {stars_amount} Stars.\n'
        f'Ваш текущий баланс: {stars_amount} Stars'
    )

# Создание инвойса для покупки Stars
async def buy_stars(update: Update, context: CallbackContext) -> None:
    try:
        amount = int(context.args[0]) if context.args else 1000
        price = int(amount * STARS_EXCHANGE_RATE * 100)
        
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title="Покупка Telegram Stars",
            description=f"Покупка {amount} Telegram Stars",
            payload=f"stars_purchase_{amount}",
            provider_token=PROVIDER_TOKEN,
            currency="USD",
            prices=[LabeledPrice("Stars", price)],
            start_parameter="buy_stars"
        )
    except (IndexError, ValueError):
        await update.message.reply_text('Ошибка: укажите количество Stars, например /buy_stars 1000')

# Обработчик ошибок
async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(f"Ошибка: {context.error}")
    if update:
        await update.message.reply_text('Произошла ошибка. Попробуйте позже.')

def main() -> None:
    init_db()
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("user_data", user_data))
    application.add_handler(CommandHandler("buy_stars", buy_stars))
    application.add_handler(MessageHandler(Filters.regex(r'^/user_data_api\?'), user_data_api))
    application.add_handler(CommandHandler("crypto_rates_api", crypto_rates_api))
    application.add_handler(MessageHandler(Filters.status_update.web_app_data, handle_webapp_data))
    application.add_handler(PreCheckoutQueryHandler(precheckout))
    application.add_handler(MessageHandler(Filters.successful_payment, successful_payment))
    application.add_error_handler(error_handler)
    
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
