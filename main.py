# main.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackContext, 
    MessageHandler, 
    filters,
    PreCheckoutQueryHandler
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
WEB_APP_URL = 'https://ВАШ_ДОМЕН/index.html'
PROVIDER_TOKEN = 'ВАШ_ПЛАТЕЖНЫЙ_ТОКЕН'  # Для реальных платежей
STARS_EXCHANGE_RATE = 0.012987  # 1 STAR = 0.012987 USDT

# "База данных" пользователей (в реальном приложении используйте настоящую БД)
user_db = {
    # user_id: {'balance': 0.0, 'stars': 0, 'transactions': []}
}

# Получение курсов криптовалют
def get_crypto_rates():
    try:
        response = requests.get('https://api.binance.com/api/v3/ticker/24hr')
        data = response.json()
        
        # Форматируем данные
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
        
        # Добавляем TON (используем фиктивный курс)
        rates['ton'] = {'price': 5.42, 'change': 2.3}
        
        return rates
    except Exception as e:
        logger.error(f"Ошибка получения курсов: {e}")
        return {}

# Обработчик команды /start
async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    
    # Инициализируем пользователя, если его нет в БД
    if user_id not in user_db:
        user_db[user_id] = {
            'balance': 1000.0,  # Начальный баланс
            'stars': 500,       # Начальное количество Stars
            'transactions': []
        }
    
    # Создаем кнопку для WebApp
    keyboard = [[
        InlineKeyboardButton(
            text="Открыть Orion Wallet",
            web_app={'url': WEB_APP_URL}
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f'Привет, {user.full_name}! Добро пожаловать в Orion Wallet.\n\n'
        'Нажмите кнопку ниже, чтобы открыть кошелек:',
        reply_markup=reply_markup
    )

# Отправка данных пользователя
async def user_data(update: Update, context: CallbackContext) -> None:
    user_id = int(context.args[0])
    
    if user_id in user_db:
        user_data = user_db[user_id]
        await update.message.reply_text(
            f'Данные пользователя {user_id}:\n'
            f'Баланс: {user_data["balance"]:.2f} USDT\n'
            f'Stars: {user_data["stars"]}\n'
            f'Транзакций: {len(user_data["transactions"])}'
        )
    else:
        await update.message.reply_text('Пользователь не найден')

# API для получения данных пользователя
async def user_data_api(update: Update, context: CallbackContext) -> None:
    user_id = int(update.message.text.split('=')[1])
    
    if user_id in user_db:
        user_data = user_db[user_id]
        await update.message.reply_json({
            'status': 'success',
            'user_id': user_id,
            'balance': user_data['balance'],
            'stars': user_data['stars']
        })
    else:
        await update.message.reply_json({'status': 'error', 'message': 'User not found'})

# API для получения курсов криптовалют
async def crypto_rates_api(update: Update, context: CallbackContext) -> None:
    rates = get_crypto_rates()
    user_id = update.effective_user.id
    
    # Добавляем балансы пользователя
    if user_id in user_db:
        user_data = user_db[user_id]
        for coin, data in rates.items():
            # Фиктивные балансы для демонстрации
            data['balance'] = user_data['balance'] / data['price'] * 0.1
    
    await update.message.reply_json(rates)

# Обработка данных из WebApp
async def handle_webapp_data(update: Update, context: CallbackContext) -> None:
    data = json.loads(update.web_app_data.data)
    user_id = data.get('user_id')
    action_type = data.get('type')
    
    if not user_id or user_id not in user_db:
        logger.error(f"Пользователь не найден: {user_id}")
        return
    
    user_data = user_db[user_id]
    
    if action_type == 'buy_stars':
        amount = data.get('amount', 0)
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
        crypto_amount = amount * STARS_EXCHANGE_RATE
        
        # Обновляем балансы
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
        
        # В реальном приложении здесь будет интеграция с Telegram API
        user_data['stars'] -= amount
        user_data['transactions'].append({
            'type': 'withdraw_stars',
            'amount': amount,
            'recipient': recipient,
            'date': datetime.now().isoformat()
        })
        logger.info(f"Пользователь {user_id} отправил {amount} Stars пользователю {recipient}")

# Обработка предоплатного запроса
async def precheckout(update: Update, context: CallbackContext) -> None:
    query = update.pre_checkout_query
    await query.answer(ok=True)

# Обработка успешного платежа
async def successful_payment(update: Update, context: CallbackContext) -> None:
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    
    if user_id in user_db:
        # Для примера: 1 USD = 100 Stars
        stars_amount = int(payment.total_amount / 100)
        user_db[user_id]['stars'] += stars_amount
        
        await update.message.reply_text(
            f'✅ Спасибо за покупку! Вы получили {stars_amount} Stars.\n'
            f'Ваш текущий баланс: {user_db[user_id]["stars"]} Stars'
        )

# Создание инвойса для покупки Stars
async def buy_stars(update: Update, context: CallbackContext) -> None:
    amount = 1000  # Количество Stars
    price = int(amount * STARS_EXCHANGE_RATE * 100)  # Цена в центах
    
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

def main() -> None:
    application = Application.builder().token(TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("user_data", user_data))
    application.add_handler(CommandHandler("buy_stars", buy_stars))
    
    # API эндпоинты
    application.add_handler(MessageHandler(filters.Regex(r'^/user_data_api\?'), user_data_api))
    application.add_handler(CommandHandler("crypto_rates_api", crypto_rates_api))
    
    # Обработчики WebApp данных
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    
    # Обработчики платежей
    application.add_handler(PreCheckoutQueryHandler(precheckout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
