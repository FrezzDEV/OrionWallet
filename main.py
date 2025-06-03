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
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = '7814519439:AAGHwL-o20low67Mh-HB1Cs0fTmNlnX6RwQ'
WEB_APP_URL = 'https://frezzdev.github.io/Website-TG/'
PROVIDER_TOKEN = 'ВАШ_ПЛАТЕЖНЫЙ_ТОКЕН'
STARS_EXCHANGE_RATE = 0.012987  # 1 STAR = 0.012987 USDT

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
async def start(update: Update, context: CallbackContext) -> None:
    """Запускает бота и открывает WebApp."""
    user = update.effective_user
    user_id = user.id
    
    # Инициализация пользователя
    if user_id not in user_db:
        user_db[user_id] = {
            'balance': 1000.0,
            'stars': 500,
            'transactions': [],
            'username': user.username or user.full_name
        }
    
    keyboard = [[
        InlineKeyboardButton(
            text="Открыть Orion Wallet",
            web_app={'url': https://frezzdev.github.io/Website-TG/}
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f'Привет, {user_db[user_id]["username"]}! Добро пожаловать в Orion Wallet.\n'
        'Нажмите кнопку ниже, чтобы открыть кошелек:',
        reply_markup=reply_markup
    )

# Получение данных пользователя
async def user_data(update: Update, context: CallbackContext) -> None:
    """Возвращает данные пользователя по его ID."""
    try:
        user_id = int(context.args[0])
        if user_id in user_db:
            user_data = user_db[user_id]
            await update.message.reply_text(
                f'Данные пользователя @{user_data["username"]}:\n'
                f'Баланс: {user_data["balance"]:.2f} USDT\n'
                f'Stars: {user_data["stars"]}\n'
                f'Транзакций: {len(user_data["transactions"])}'
            )
        else:
            await update.message.reply_text('Пользователь не найден')
    except (IndexError, ValueError):
        await update.message.reply_text('Ошибка: укажите корректный user_id')

# API для получения данных пользователя
async def user_data_api(update: Update, context: CallbackContext) -> None:
    """API-эндпоинт для получения данных пользователя."""
    try:
        user_id = int(update.message.text.split('=')[1])
        if user_id in user_db:
            user_data = user_db[user_id]
            await update.message.reply_json({
                'status': 'success',
                'user_id': user_id,
                'username': user_data['username'],
                'balance': user_data['balance'],
                'stars': user_data['stars']
            })
        else:
            await update.message.reply_json({'status': 'error', 'message': 'User not found'})
    except (IndexError, ValueError):
        await update.message.reply_json({'status': 'error', 'message': 'Invalid user_id'})

# API для получения курсов криптовалют
async def crypto_rates_api(update: Update, context: CallbackContext) -> None:
    """API-эндпоинт для получения курсов криптовалют."""
    rates = get_crypto_rates()
    user_id = update.effective_user.id
    
    if user_id in user_db:
        user_data = user_db[user_id]
        for coin, data in rates.items():
            data['balance'] = user_data['balance'] / data['price'] * 0.1
    
    await update.message.reply_json(rates)

# Обработка данных из WebApp
async def handle_webapp_data(update: Update, context: CallbackContext) -> None:
    """Обработка данных, отправленных из WebApp."""
    try:
        data = json.loads(update.web_app_data.data)
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
async def precheckout(update: Update, context: CallbackContext) -> None:
    """Подтверждение предоплатного запроса."""
    await update.pre_checkout_query.answer(ok=True)

# Обработка успешного платежа
async def successful_payment(update: Update, context: CallbackContext) -> None:
    """Обработка успешного платежа за Stars."""
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    
    if user_id in user_db:
        stars_amount = int(payment.total_amount / 100)
        user_db[user_id]['stars'] += stars_amount
        user_db[user_id]['transactions'].append({
            'type': 'buy_stars',
            'amount': stars_amount,
            'date': datetime.now().isoformat()
        })
        await update.message.reply_text(
            f'✅ Спасибо за покупку! Вы получили {stars_amount} Stars.\n'
            f'Ваш текущий баланс: {user_db[user_id]["stars"]} Stars'
        )

# Создание инвойса для покупки Stars
async def buy_stars(update: Update, context: CallbackContext) -> None:
    """Создание инвойса для покупки Telegram Stars."""
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
    """Обработка ошибок бота."""
    logger.error(f"Ошибка: {context.error}")
    if update:
        await update.message.reply_text('Произошла ошибка. Попробуйте позже.')

def main() -> None:
    """Запуск бота."""
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
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
