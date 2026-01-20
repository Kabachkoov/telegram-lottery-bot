import asyncio
import random
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode, ChatType
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json
import os
import uuid
import re
from fastapi import FastAPI
import uvicorn
import threading

# Загружаем настройки
from dotenv import load_dotenv
load_dotenv()

# 🔧 Настройки бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "8586002466:AAGfteiLy5V6rXrDzwun4-U45tL5-RCqTjw")
MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID", "7666608094"))
BOT_USERNAME = "FoxGift_NFT_bot"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 🚀 Инициализация бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# 📁 Файлы данных
DATA_FILE = "lottery_data.json"
CHANNELS_FILE = "channels_data.json"

# 🔧 Проверка токена
if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    logger.error("⚠️ Установите BOT_TOKEN в переменных окружения!")

# ========================
# 📊 ФУНКЦИИ ДЛЯ ДАННЫХ
# ========================

def load_data():
    """Загружаем данные о розыгрышах"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"active_lotteries": {}, "ended_lotteries": {}, "users": {}}

def save_data(data):
    """Сохраняем данные"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_lottery_id():
    """Генерируем ID для розыгрыша"""
    return str(uuid.uuid4())[:8]

def generate_ticket_number():
    """Генерируем номер билета"""
    return random.randint(100000, 999999)

# ========================
# 🎭 СОСТОЯНИЯ ДЛЯ АДМИНА
# ========================

class AdminStates(StatesGroup):
    waiting_for_prize_count = State()
    waiting_for_ticket_price = State()
    waiting_for_duration = State()
    waiting_for_lottery_text = State()

# ========================
# 🎬 КОМАНДА СТАРТ
# ========================

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Команда старт"""
    user_id = str(message.from_user.id)
    data = load_data()
    
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "balance": 0,
            "total_spent": 0,
            "total_tickets": 0,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "registered_at": datetime.now().isoformat()
        }
        save_data(data)
    
    if int(user_id) == MAIN_ADMIN_ID:
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="🎪 Создать розыгрыш")],
                [types.KeyboardButton(text="🏁 Завершить розыгрыш")],
                [types.KeyboardButton(text="📊 Статистика")],
                [types.KeyboardButton(text="📋 Мои билеты")]
            ],
            resize_keyboard=True
        )
        await message.answer("👑 Привет, Админ! Что делаем?", reply_markup=keyboard)
    else:
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="🎫 Купить билет")],
                [types.KeyboardButton(text="💰 Баланс")],
                [types.KeyboardButton(text="📋 Мои билеты")]
            ],
            resize_keyboard=True
        )
        await message.answer("🎉 Привет! Добро пожаловать в бот розыгрышей!", reply_markup=keyboard)

# ========================
# 🎪 СОЗДАНИЕ РОЗЫГРЫША
# ========================

@router.message(F.text == "🎪 Создать розыгрыш")
async def create_lottery_start(message: Message, state: FSMContext):
    if message.from_user.id != MAIN_ADMIN_ID:
        await message.answer("🚫 Только для администратора!")
        return
    
    await message.answer(
        "🎪 <b>Создаем новый розыгрыш!</b>\n\n"
        "🎯 <b>Шаг 1 из 4</b>\n"
        "Сколько будет призовых мест?\n"
        "<i>Введи число, например: 3</i>"
    )
    await state.set_state(AdminStates.waiting_for_prize_count)

@router.message(AdminStates.waiting_for_prize_count)
async def process_prize_count(message: Message, state: FSMContext):
    try:
        prize_count = int(message.text)
        if prize_count <= 0:
            await message.answer("❌ Число должно быть больше нуля!")
            return
        
        await state.update_data(prize_count=prize_count)
        
        await message.answer(
            "💰 <b>Шаг 2 из 4</b>\n"
            "Сколько будет стоить один билет?\n"
            "<i>Цена в звездах, например: 5</i>"
        )
        await state.set_state(AdminStates.waiting_for_ticket_price)
        
    except ValueError:
        await message.answer("❌ Введи нормальное число!")

@router.message(AdminStates.waiting_for_ticket_price)
async def process_ticket_price(message: Message, state: FSMContext):
    try:
        ticket_price = int(message.text)
        if ticket_price <= 0:
            await message.answer("❌ Цена должна быть больше нуля!")
            return
        
        await state.update_data(ticket_price=ticket_price)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏱️ 1 час", callback_data="duration_1h")],
            [InlineKeyboardButton(text="⏱️ 3 часа", callback_data="duration_3h")],
            [InlineKeyboardButton(text="⏱️ 6 часов", callback_data="duration_6h")],
            [InlineKeyboardButton(text="⏱️ 12 часов", callback_data="duration_12h")],
            [InlineKeyboardButton(text="📅 1 день", callback_data="duration_1d")],
            [InlineKeyboardButton(text="📅 3 дня", callback_data="duration_3d")],
            [InlineKeyboardButton(text="📅 7 дней", callback_data="duration_7d")],
            [InlineKeyboardButton(text="✍️ Свой вариант", callback_data="duration_custom")]
        ])
        
        await message.answer(
            "⏰ <b>Шаг 3 из 4</b>\n"
            "Выбери длительность розыгрыша:",
            reply_markup=keyboard
        )
        await state.set_state(AdminStates.waiting_for_duration)
        
    except ValueError:
        await message.answer("❌ Введи число!")

@router.callback_query(F.data.startswith("duration_"), AdminStates.waiting_for_duration)
async def process_duration_selection(callback: CallbackQuery, state: FSMContext):
    duration_type = callback.data
    
    duration_map = {
        "duration_1h": timedelta(hours=1),
        "duration_3h": timedelta(hours=3),
        "duration_6h": timedelta(hours=6),
        "duration_12h": timedelta(hours=12),
        "duration_1d": timedelta(days=1),
        "duration_3d": timedelta(days=3),
        "duration_7d": timedelta(days=7),
    }
    
    if duration_type in duration_map:
        duration = duration_map[duration_type]
        await state.update_data(duration_obj=duration)
        
        await callback.message.answer(
            "📝 <b>Шаг 4 из 4</b>\n"
            "Пришли мне текст для анонса розыгрыша:\n\n"
            "<i>Можно использовать HTML-разметку</i>"
        )
        await state.set_state(AdminStates.waiting_for_lottery_text)
        
    elif duration_type == "duration_custom":
        await callback.message.answer(
            "✍️ <b>Введи свою длительность:</b>\n\n"
            "<i>Примеры:\n"
            "• 2 часа\n"
            "• 3 дня\n"
            "• 1 час 30 минут</i>"
        )
    
    await callback.answer()

@router.message(AdminStates.waiting_for_duration)
async def process_duration_input(message: Message, state: FSMContext):
    text = message.text.lower().strip()
    
    try:
        if "день" in text or "дня" in text or "дней" in text:
            numbers = re.findall(r'\d+', text)
            if numbers:
                days = int(numbers[0])
                duration = timedelta(days=days)
        
        elif "час" in text or "часа" in text or "часов" in text:
            numbers = re.findall(r'\d+', text)
            if numbers:
                hours = int(numbers[0])
                duration = timedelta(hours=hours)
        
        elif "минут" in text:
            numbers = re.findall(r'\d+', text)
            if numbers:
                minutes = int(numbers[0])
                duration = timedelta(minutes=minutes)
        
        else:
            days = int(text)
            duration = timedelta(days=days)
        
        if duration.total_seconds() < 60:
            await message.answer("❌ Минимальная длительность - 1 минута!")
            return
        
        await state.update_data(duration_obj=duration)
        
        await message.answer(
            "📝 <b>Шаг 4 из 4</b>\n"
            "Пришли мне текст для анонса розыгрыша:\n\n"
            "<i>Можно использовать HTML-разметку</i>"
        )
        await state.set_state(AdminStates.waiting_for_lottery_text)
        
    except:
        await message.answer("❌ Не могу распознать время!")

@router.message(AdminStates.waiting_for_lottery_text)
async def process_lottery_text(message: Message, state: FSMContext):
    lottery_text = message.text.strip()
    
    if not lottery_text:
        await message.answer("❌ Текст не может быть пустым!")
        return
    
    data = await state.get_data()
    prize_count = data['prize_count']
    ticket_price = data['ticket_price']
    duration = data['duration_obj']
    
    lottery_id = generate_lottery_id()
    end_date = datetime.now() + duration
    
    lottery_data = {
        "id": lottery_id,
        "prize_count": prize_count,
        "ticket_price": ticket_price,
        "duration_seconds": int(duration.total_seconds()),
        "lottery_text": lottery_text,
        "created_at": datetime.now().isoformat(),
        "ends_at": end_date.isoformat(),
        "sold_tickets": 0,
        "participants": {},
        "tickets": [],
        "is_active": True
    }
    
    data_storage = load_data()
    data_storage["active_lotteries"][lottery_id] = lottery_data
    save_data(data_storage)
    
    ends_date = end_date.strftime('%d.%m.%Y в %H:%M')
    
    admin_message = (
        f"✅ <b>Розыгрыш создан!</b>\n\n"
        f"🎯 <b>Призовых мест:</b> {prize_count}\n"
        f"💰 <b>Цена билета:</b> {ticket_price} звезд\n"
        f"⏰ <b>Завершится:</b> {ends_date}\n"
        f"🆔 <b>ID:</b> <code>{lottery_id}</code>\n\n"
        f"🎉 <b>Розыгрыш запущен!</b>"
    )
    
    await message.answer(admin_message)
    await state.clear()

# ========================
# 🎫 ПОКУПКА БИЛЕТОВ
# ========================

@router.message(F.text == "🎫 Купить билет")
async def buy_ticket_menu(message: Message):
    data = load_data()
    
    if not data["active_lotteries"]:
        await message.answer("📭 Сейчас нет активных розыгрышей")
        return
    
    user_id = str(message.from_user.id)
    user_balance = data["users"][user_id]["balance"] if user_id in data["users"] else 0
    
    builder = InlineKeyboardBuilder()
    for lottery_id, lottery in data["active_lotteries"].items():
        ends_date = datetime.fromisoformat(lottery["ends_at"]).strftime('%d.%m')
        builder.row(
            types.InlineKeyboardButton(
                text=f"🎪 {lottery['prize_count']} призов • {lottery['ticket_price']}⭐ • до {ends_date}",
                callback_data=f"view_lottery_{lottery_id}"
            )
        )
    
    await message.answer(
        f"🎫 <b>Выбери розыгрыш</b>\n"
        f"⭐ Баланс: {user_balance} звезд",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("view_lottery_"))
async def view_lottery_details(callback: CallbackQuery):
    lottery_id = callback.data.replace("view_lottery_", "")
    data = load_data()
    
    if lottery_id not in data["active_lotteries"]:
        await callback.answer("❌ Розыгрыш не найден!")
        return
    
    lottery = data["active_lotteries"][lottery_id]
    user_id = str(callback.from_user.id)
    user_balance = data["users"][user_id]["balance"] if user_id in data["users"] else 0
    
    ends_date = datetime.fromisoformat(lottery["ends_at"]).strftime('%d.%m.%Y в %H:%M')
    
    text = (
        f"🎪 <b>РОЗЫГРЫШ #{lottery_id}</b>\n\n"
        f"🎯 Призовых мест: {lottery['prize_count']}\n"
        f"💰 Цена билета: {lottery['ticket_price']} звезд\n"
        f"⏰ Завершится: {ends_date}\n"
        f"🎫 Продано билетов: {lottery['sold_tickets']}\n"
        f"👥 Участников: {len(lottery.get('participants', {}))}\n\n"
        f"⭐ Твой баланс: {user_balance} звезд"
    )
    
    builder = InlineKeyboardBuilder()
    
    if user_balance >= lottery["ticket_price"]:
        builder.row(
            types.InlineKeyboardButton(
                text=f"✅ КУПИТЬ БИЛЕТ за {lottery['ticket_price']}⭐",
                callback_data=f"buy_ticket_{lottery_id}"
            )
        )
    else:
        builder.row(
            types.InlineKeyboardButton(
                text="💳 ПОПОЛНИТЬ БАЛАНС",
                callback_data="deposit_funds"
            )
        )
    
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ НАЗАД",
            callback_data="back_to_lotteries"
        )
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("buy_ticket_"))
async def buy_ticket_process(callback: CallbackQuery):
    lottery_id = callback.data.replace("buy_ticket_", "")
    user_id = str(callback.from_user.id)
    data = load_data()
    
    if lottery_id not in data["active_lotteries"]:
        await callback.answer("❌ Розыгрыш не найден!")
        return
    
    lottery = data["active_lotteries"][lottery_id]
    
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "balance": 0,
            "total_spent": 0,
            "total_tickets": 0,
            "username": callback.from_user.username,
            "first_name": callback.from_user.first_name
        }
    
    user_data = data["users"][user_id]
    
    if user_data["balance"] < lottery["ticket_price"]:
        await callback.answer("❌ Не хватает звезд!")
        return
    
    # Покупка билета
    user_data["balance"] -= lottery["ticket_price"]
    user_data["total_spent"] += lottery["ticket_price"]
    user_data["total_tickets"] += 1
    
    ticket_number = generate_ticket_number()
    
    if user_id not in lottery["participants"]:
        lottery["participants"][user_id] = []
    
    lottery["participants"][user_id].append(ticket_number)
    lottery["tickets"].append({
        "number": ticket_number,
        "user_id": user_id,
        "username": callback.from_user.username,
        "first_name": callback.from_user.first_name,
        "purchased_at": datetime.now().isoformat()
    })
    lottery["sold_tickets"] += 1
    
    save_data(data)
    
    await callback.message.edit_text(
        f"🎉 <b>БИЛЕТ КУПЛЕН!</b>\n\n"
        f"🎫 Номер билета: <code>{ticket_number}</code>\n"
        f"💰 Стоимость: {lottery['ticket_price']} звезд\n"
        f"⭐ Остаток: {user_data['balance']} звезд\n\n"
        f"🍀 Удачи в розыгрыше!"
    )
    
    # Уведомление админу
    if MAIN_ADMIN_ID:
        await bot.send_message(
            MAIN_ADMIN_ID,
            f"🛒 НОВАЯ ПОКУПКА!\n"
            f"👤 @{callback.from_user.username or 'без username'}\n"
            f"🎪 Розыгрыш: {lottery_id}\n"
            f"🎫 Билет: {ticket_number}\n"
            f"💰 Цена: {lottery['ticket_price']}⭐"
        )

# ========================
# 📊 СТАТИСТИКА
# ========================

@router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message):
    data = load_data()
    
    active_count = len(data["active_lotteries"])
    ended_count = len(data["ended_lotteries"])
    total_users = len(data["users"])
    
    total_balance = sum(user["balance"] for user in data["users"].values())
    total_spent = sum(user["total_spent"] for user in data["users"].values())
    
    stats_text = (
        f"📊 <b>СТАТИСТИКА БОТА</b>\n\n"
        f"🎪 Активных розыгрышей: {active_count}\n"
        f"🏁 Завершенных: {ended_count}\n"
        f"👥 Пользователей: {total_users}\n\n"
        f"💰 Общий баланс: {total_balance} ⭐\n"
        f"💸 Потрачено: {total_spent} ⭐\n"
    )
    
    await message.answer(stats_text)

# ========================
# 📋 МОИ БИЛЕТЫ
# ========================

@router.message(F.text == "📋 Мои билеты")
async def my_tickets(message: Message):
    user_id = str(message.from_user.id)
    data = load_data()
    
    user_tickets = []
    
    # Ищем билеты в активных розыгрышах
    for lottery_id, lottery in data["active_lotteries"].items():
        if user_id in lottery.get("participants", {}):
            tickets = lottery["participants"][user_id]
            for ticket in tickets:
                user_tickets.append({
                    "lottery_id": lottery_id,
                    "ticket": ticket,
                    "status": "активен",
                    "prize_count": lottery["prize_count"]
                })
    
    if not user_tickets:
        await message.answer("🎫 У вас пока нет билетов")
        return
    
    tickets_text = "🎫 <b>ВАШИ БИЛЕТЫ:</b>\n\n"
    for i, ticket in enumerate(user_tickets, 1):
        tickets_text += (
            f"{i}. Розыгрыш <code>{ticket['lottery_id']}</code>\n"
            f"   Билет: <code>{ticket['ticket']}</code>\n"
            f"   Статус: {ticket['status']}\n"
            f"   Призовых мест: {ticket['prize_count']}\n\n"
        )
    
    await message.answer(tickets_text)

# ========================
# 🏁 ЗАВЕРШЕНИЕ РОЗЫГРЫША
# ========================

@router.message(F.text == "🏁 Завершить розыгрыш")
async def end_lottery_menu(message: Message):
    if message.from_user.id != MAIN_ADMIN_ID:
        await message.answer("🚫 Только для администратора!")
        return
    
    data = load_data()
    
    if not data["active_lotteries"]:
        await message.answer("📭 Нет активных розыгрышей")
        return
    
    builder = InlineKeyboardBuilder()
    for lottery_id, lottery in data["active_lotteries"].items():
        ends_date = datetime.fromisoformat(lottery["ends_at"]).strftime('%d.%m %H:%M')
        builder.row(
            types.InlineKeyboardButton(
                text=f"🎪 #{lottery_id} - {lottery['sold_tickets']} билетов - до {ends_date}",
                callback_data=f"end_lottery_{lottery_id}"
            )
        )
    
    await message.answer(
        "🏁 <b>Выбери розыгрыш для завершения:</b>",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("end_lottery_"))
async def end_lottery_callback(callback: CallbackQuery):
    if callback.from_user.id != MAIN_ADMIN_ID:
        await callback.answer("🚫 Только для администратора!")
        return
    
    lottery_id = callback.data.replace("end_lottery_", "")
    data = load_data()
    
    if lottery_id not in data["active_lotteries"]:
        await callback.answer("❌ Розыгрыш не найден!")
        return
    
    lottery = data["active_lotteries"][lottery_id]
    
    # Определяем победителей
    tickets = lottery.get("tickets", [])
    participants = list(lottery.get("participants", {}).keys())
    prize_count = lottery["prize_count"]
    
    winners = []
    
    if tickets and len(participants) > 0:
        all_tickets = [ticket for ticket in tickets]
        actual_prize_count = min(prize_count, len(all_tickets))
        
        if actual_prize_count > 0:
            winner_tickets = random.sample(all_tickets, actual_prize_count)
            
            for ticket in winner_tickets:
                winners.append({
                    "user_id": ticket["user_id"],
                    "username": ticket["username"] or "без username",
                    "first_name": ticket["first_name"] or "Пользователь",
                    "ticket": ticket["number"]
                })
    
    # Сохраняем результаты
    lottery["ended_at"] = datetime.now().isoformat()
    lottery["is_active"] = False
    lottery["winners"] = winners
    
    data["ended_lotteries"][lottery_id] = lottery
    del data["active_lotteries"][lottery_id]
    
    save_data(data)
    
    # Отчет администратору
    report = (
        f"✅ <b>РОЗЫГРЫШ ЗАВЕРШЕН!</b>\n\n"
        f"🎪 ID: {lottery_id}\n"
        f"🏆 Призовых мест: {prize_count}\n"
        f"🎫 Билетов продано: {lottery['sold_tickets']}\n"
        f"👥 Участников: {len(participants)}\n"
        f"🏅 Победителей: {len(winners)}\n\n"
    )
    
    if winners:
        report += "<b>🏆 ПОБЕДИТЕЛИ:</b>\n"
        for i, winner in enumerate(winners, 1):
            report += f"{i}. {winner['first_name']} (@{winner['username']}) - билет {winner['ticket']}\n"
    
    await callback.message.edit_text(report)
    await callback.answer("✅ Розыгрыш завершен!")

# ========================
# 💰 БАЛАНС
# ========================

@router.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    user_id = str(message.from_user.id)
    data = load_data()
    
    if user_id in data["users"]:
        user_data = data["users"][user_id]
        balance_text = (
            f"💰 <b>ВАШ БАЛАНС</b>\n\n"
            f"⭐ Звезд: {user_data['balance']}\n"
            f"💸 Потрачено: {user_data['total_spent']}\n"
            f"🎫 Билетов куплено: {user_data['total_tickets']}\n\n"
            f"🎲 <i>Удачи в розыгрышах!</i>"
        )
    else:
        balance_text = "💰 У вас еще нет баланса\n⭐ Пополните для участия в розыгрышах!"
    
    await message.answer(balance_text)

# ========================
# 🚀 FASTAPI ДЛЯ RENDER
# ========================

app = FastAPI()

@app.get("/")
async def root():
    return {
        "status": "online", 
        "service": "Telegram Lottery Bot",
        "uptime": "24/7",
        "admin": MAIN_ADMIN_ID
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/stats")
async def api_stats():
    data = load_data()
    return {
        "active_lotteries": len(data["active_lotteries"]),
        "total_users": len(data["users"]),
        "timestamp": datetime.now().isoformat()
    }

# ========================
# 🔄 ФУНКЦИЯ ЗАПУСКА БОТА
# ========================

async def run_bot():
    """Запускает Telegram бота"""
    logger.info("🤖 Telegram бот запускается...")
    logger.info(f"👑 Админ ID: {MAIN_ADMIN_ID}")
    logger.info(f"🌐 Режим: {'Render.com' if os.getenv('RENDER') else 'Локальный'}")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка в работе бота: {e}")
        raise

def start_bot_in_thread():
    """Запускает бота в отдельном потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())

# ========================
# 🚀 ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# ========================

def main():
    """Основная функция запуска"""
    # Проверяем, запущены ли мы на Render
    is_render = os.getenv('RENDER') or os.getenv('PORT')
    
    if is_render:
        logger.info("🌐 Запуск в облачной среде Render.com")
        
        # Запускаем бота в отдельном потоке
        bot_thread = threading.Thread(target=start_bot_in_thread, daemon=True)
        bot_thread.start()
        logger.info("✅ Telegram бот запущен в фоновом режиме")
        
        # Запускаем веб-сервер (обязательно для Render)
        port = int(os.environ.get("PORT", 8000))
        logger.info(f"🌐 Веб-сервер запускается на порту {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
        
    else:
        logger.info("💻 Локальный запуск")
        # Локальный запуск
        asyncio.run(run_bot())

if __name__ == "__main__":
    main()
