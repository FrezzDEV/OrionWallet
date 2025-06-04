# main.py
import asyncio
import logging
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import requests

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = '7814519439:AAGHwL-o20low67Mh-HB1Cs0fTmNlnX6RwQ'
WEB_APP_URL = 'https://frezzdev.github.io/OrionWallet/'
PROVIDER_TOKEN = 'ВАШ_ПЛАТЕЖНЫЙ_ТОКЕН'
STARS_EXCHANGE_RATE = 0.012987  # 1 STAR = 0.012987 USDT

user_db = {}

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

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def start(message: types.Message, command: CommandObject):
    user = message.from_user
    user_id = user.id
    if user_id not in user_db:
        user_db[user_id] = {
            'balance': 1000.0,
            'stars': 500,
            'transactions': [],
            'username': user.username or user.full_name
        }
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть Orion Wallet", web_app=types.WebAppInfo(url=WEB_APP_URL))]
        ]
    )
    await message.answer(
        f'Привет, {user_db[user_id]["username"]}! Добро пожаловать в Orion Wallet.\n'
        'Нажмите кнопку ниже, чтобы открыть кошелек:',
        reply_markup=keyboard
    )

@dp.message(Command("user_data"))
async def user_data(message: types.Message, command: CommandObject):
    try:
        user_id = int(command.args)
        if user_id in user_db:
            user_data = user_db[user_id]
            await message.answer(
                f'Данные пользователя @{user_data["username"]}:\n'
                f'Баланс: {user_data["balance"]:.2f} USDT\n'
                f'Stars: {user_data["stars"]}\n'
                f'Транзакций: {len(user_data["transactions"])}'
            )
        else:
            await message.answer('Пользователь не найден')
    except (IndexError, ValueError, TypeError):
        await message.answer('Ошибка: укажите корректный user_id')

@dp.message(F.text.regexp(r'^/user_data_api\?'))
async def user_data_api(message: types.Message):
    try:
        user_id = int(message.text.split('=')[1])
        if user_id in user_db:
            user_data = user_db[user_id]
            await message.answer(json.dumps({
                'status': 'success',
                'user_id': user_id,
                'username': user_data['username'],
                'balance': user_data['balance'],
                'stars': user_data['stars']
            }), parse_mode=None)
        else:
            await message.answer(json.dumps({'status': 'error', 'message': 'User not found'}), parse_mode=None)
    except (IndexError, ValueError):
        await message.answer(json.dumps({'status': 'error', 'message': 'Invalid user_id'}), parse_mode=None)

@dp.message(Command("crypto_rates_api"))
async def crypto_rates_api(message: types.Message):
    rates = get_crypto_rates()
    user_id = message.from_user.id
    if user_id in user_db:
        user_data = user_db[user_id]
        for coin, data in rates.items():
            data['balance'] = user_data['balance'] / data['price'] * 0.1
    await message.answer(json.dumps(rates), parse_mode=None)

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
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

@dp.pre_checkout_query()
async def precheckout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
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
        await message.answer(
            f'✅ Спасибо за покупку! Вы получили {stars_amount} Stars.\n'
            f'Ваш текущий баланс: {user_db[user_id]["stars"]} Stars'
        )

@dp.message(Command("buy_stars"))
async def buy_stars(message: types.Message, command: CommandObject):
    try:
        amount = int(command.args) if command.args else 1000
        price = int(amount * STARS_EXCHANGE_RATE * 100)
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Покупка Telegram Stars",
            description=f"Покупка {amount} Telegram Stars",
            payload=f"stars_purchase_{amount}",
            provider_token=PROVIDER_TOKEN,
            currency="USD",
            prices=[LabeledPrice(label="Stars", amount=price)],
            start_parameter="buy_stars"
        )
    except (IndexError, ValueError, TypeError):
        await message.answer('Ошибка: укажите количество Stars, например /buy_stars 1000')

@dp.errors()
async def error_handler(update, exception):
    logger.error(f"Ошибка: {exception}")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
