# main.py
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
import json
import logging
import requests
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
PROVIDER_TOKEN = 'ВАШ_ПЛАТЕЖНЫЙ_ТОКЕН'  # Replace with actual payment provider token
STARS_EXCHANGE_RATE = 0.012987  # 1 STAR = 0.012987 USDT

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# Хранилище данных пользователей (в реальном приложении использовать БД)
user_db = {}

# Получение курсов криптовалют
def get_crypto_rates():
    """
    Получение текущих курсов криптовалют с Binance API.
    Возвращает словарь с ценами и изменением за 24 часа.
    """
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
        
        # Добавляем TON (фиктивный курс для примера)
        rates['ton'] = {'price': 5.42, 'change': 2.3}
        return rates
    except requests.RequestException as e:
        logger.error(f"Ошибка получения курсов: {e}")
        return {}

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    """Запускает бота и открывает WebApp."""
    user = message.from_user
    user_id = user.id
    
    # Инициализация пользователя
    if user_id not in user_db:
        user_db[user_id] = {
            'balance': 1000.0,
            'stars': 500,
            'transactions': [],
            'username': user.username or user.first_name
        }
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(
        text="Открыть Orion Wallet",
        web_app={'url': WEB_APP_URL}
    ))
    
    bot.reply_to(
        message,
        f'Привет, {user_db[user_id]["username"]}! Добро пожаловать в Orion Wallet.\n'
        'Нажмите кнопку ниже, чтобы открыть кошелек:',
        reply_markup=keyboard
    )

# Получение данных пользователя
@bot.message_handler(commands=['user_data'])
def user_data(message):
    """Возвращает данные пользователя по его ID."""
    try:
        user_id = int(message.text.split()[1])
        if user_id in user_db:
            user_data = user_db[user_id]
            bot.reply_to(
                message,
                f'Данные пользователя @{user_data["username"]}:\n'
                f'Баланс: {user_data["balance"]:.2f} USDT\n'
                f'Stars: {user_data["stars"]}\n'
                f'Транзакций: {len(user_data["transactions"])}'
            )
        else:
            bot.reply_to(message, 'Пользователь не найден')
    except (IndexError, ValueError):
        bot.reply_to(message, 'Ошибка: укажите корректный user_id')

# API для получения данных пользователя
@bot.message_handler(regexp=r'^/user_data_api\?')
def user_data_api(message):
    """API-эндпоинт для получения данных пользователя."""
    try:
        user_id = int(message.text.split('=')[1])
        if user_id in user_db:
            user_data = user_db[user_id]
            bot.reply_to(message, json.dumps({
                'status': 'success',
                'user_id': user_id,
                'username': user_data['username'],
                'balance': user_data['balance'],
                'stars': user_data['stars']
            }))
        else:
            bot.reply_to(message, json.dumps({'status': 'error', 'message': 'User not found'}))
    except (IndexError, ValueError):
        bot.reply_to(message, json.dumps({'status': 'error', 'message': 'Invalid user_id'}))

# API для получения курсов криптовалют
@bot.message_handler(commands=['crypto_rates_api'])
def crypto_rates_api(message):
    """API-эндпоинт для получения курсов криптовалют."""
    rates = get_crypto_rates()
    user_id = message.from_user.id
    
    if user_id in user_db:
        user_data = user_db[user_id]
        for coin, data in rates.items():
            data['balance'] = user_data['balance'] / data['price'] * 0.1
    
    bot.reply_to(message, json.dumps(rates))

# Обработка данных из WebApp
@bot.message_handler(content_types=['web_app_data'])
def handle_webapp_data(message):
    """Обработка данных, отправленных из WebApp."""
    try:
        data = json.loads(message.web_app_data.data)
        user_id = data.get('user_id')
        action_type = data.get('type')
        
        if not user_id or user_id not in user_db:
            logger.error(f"Пользователь не найден: {user_id}")
            return
        
        user_data = user_db[user_id]
        
        if action_type == 'buy_stars':
            amount = data.get('amount', 0)
            if amount <= 0:
                logger.error(f"Некорректное количество Stars: {amount}")
                return
            user_data['stars'] += amount
            user_data['transactions'].append({
                'type': 'buy_stars',
                'amount': amount,
                'date': datetime.now().isoformat()
            })
            logger.info(f"Пользователь {user_id} купил {amount} Stars")
        
        elif action_type == 'exchange_stars':
            amount = data.get('amount', 0)
            currency = data.get('currency', 'usdt')
            if amount <= 0 or user_data['stars'] < amount:
                logger.error(f"Недостаточно Stars или некорректное количество: {amount}")
                return
            crypto_amount = amount * STARS_EXCHANGE_RATE
            user_data['stars'] -= amount
            user_data['balance'] += crypto_amount
            user_data['transactions'].append({
                'type': 'exchange_stars',
                'amount': amount,
                'currency': currency,
                'crypto_amount': crypto_amount,
                'date': datetime.now().isoformat()
            })
            logger.info(f"Пользователь {user_id} обменял {amount} Stars на {crypto_amount:.6f} {currency.upper()}")
        
        elif action_type == 'withdraw_stars':
            amount = data.get('amount', 0)
            recipient = data.get('recipient', '')
            if amount <= 0 or user_data['stars'] < amount:
                logger.error(f"Недостаточно Stars или некорректное количество: {amount}")
                return
            user_data['stars'] -= amount
            user_data['transactions'].append({
                'type': 'withdraw_stars',
                'amount': amount,
                'recipient': recipient,
                'date': datetime.now().isoformat()
            })
            logger.info(f"Пользователь {user_id} отправил {amount} Stars пользователю {recipient}")
    
    except json.JSONDecodeError:
        logger.error("Ошибка декодирования JSON из WebApp")
    except Exception as e:
        logger.error(f"Ошибка обработки WebApp данных: {e}")

# Обработка предоплатного запроса
@bot.pre_checkout_query_handler(func=lambda query: True)
def precheckout(pre_checkout_query):
    """Подтверждение предоплатного запроса."""
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Обработка успешного платежа
@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    """Обработка успешного платежа за Stars."""
    payment = message.successful_payment
    user_id = message.from_user.id
    
    if user_id in user_db:
        stars_amount = int(payment.total_amount / 100)
        user_db[user_id]['stars'] += stars_amount
        user_db[user_id]['transactions'].append({
            'type': 'buy_stars',
            'amount': stars_amount,
            'date': datetime.now().isoformat()
        })
        bot.reply_to(
            message,
            f'✅ Спасибо за покупку! Вы получили {stars_amount} Stars.\n'
            f'Ваш текущий баланс: {user_db[user_id]["stars"]} Stars'
        )

# Создание инвойса для покупки Stars
@bot.message_handler(commands=['buy_stars'])
def buy_stars(message):
    """Создание инвойса для покупки Telegram Stars."""
    try:
        amount = int(message.text.split()[1]) if len(message.text.split()) > 1 else 1000
        price = int(amount * STARS_EXCHANGE_RATE * 100)
        
        bot.send_invoice(
            chat_id=message.chat.id,
            title="Покупка Telegram Stars",
            description=f"Покупка {amount} Telegram Stars",
            invoice_payload=f"stars_purchase_{amount}",
            provider_token=PROVIDER_TOKEN,
            currency="USD",
            prices=[LabeledPrice(label="Stars", amount=price)],
            start_parameter="buy_stars"
        )
    except (IndexError, ValueError):
        bot.reply_to(message, 'Ошибка: укажите количество Stars, например /buy_stars 1000')

# Обработчик ошибок
def error_handler(e):
    """Обработка ошибок бота."""
    logger.error(f"Ошибка: {e}")
    if hasattr(e, 'message'):
        bot.reply_to(e.message, 'Произошла ошибка. Попробуйте позже.')

def main():
    """Запуск бота."""
    print("Бот запущен...")
    bot.infinity_polling()

if __name__ == '__main__':
    main()
