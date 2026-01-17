import asyncio
import logging
import sys
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Імпорт планувальника
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 1. Налаштування
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    print("❌ Помилка: Перевірте .env файл (BOT_TOKEN або GEMINI_API_KEY відсутні)")
    sys.exit(1)

# Налаштування Gemini
genai.configure(api_key=GEMINI_API_KEY)
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash", 
    safety_settings=safety_settings
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- СТАНИ (FSM) ---
class MoodInteraction(StatesGroup):
    waiting_for_note = State()

# 2. Робота з Базою Даних
def init_db():
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, joined_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mood_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  mood TEXT, 
                  note TEXT, 
                  timestamp DATETIME)''')
    conn.commit()
    conn.close()

def get_all_users():
    """Отримує список ID всіх користувачів для розсилки"""
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def log_mood_start(user_id, mood):
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    timestamp = datetime.now()
    c.execute("INSERT INTO mood_logs (user_id, mood, note, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, mood, "", timestamp))
    log_id = c.lastrowid
    conn.commit()
    conn.close()
    return log_id

def update_mood_note(log_id, note):
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    c.execute("UPDATE mood_logs SET note = ? WHERE id = ?", (note, log_id))
    conn.commit()
    conn.close()

def get_stats_data(user_id, days):
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    date_threshold = datetime.now() - timedelta(days=days)
    c.execute("SELECT mood FROM mood_logs WHERE user_id = ? AND timestamp > ?", 
              (user_id, date_threshold))
    rows = c.fetchall()
    conn.close()
    return rows

def get_recent_logs(user_id, limit=5):
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    c.execute("SELECT mood, note, timestamp FROM mood_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", 
              (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

# 3. Клавіатури
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Як справи? 📝", callback_data="checkin")
    builder.button(text="Статистика 📊", callback_data="stats_menu")
    builder.button(text="Порада AI 🧠", callback_data="advice")
    builder.adjust(1)
    return builder.as_markup()

def get_mood_keyboard():
    builder = InlineKeyboardBuilder()
    moods = ["Чудово 🤩", "Добре 🙂", "Нормально 😐", "Сумно 😔", "Жахливо 😫"]
    for mood in moods:
        builder.button(text=mood, callback_data=f"mood_{mood}")
    builder.adjust(1)
    return builder.as_markup()

def get_stats_period_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="За 7 днів 🗓", callback_data="period_7")
    builder.button(text="За 30 днів 🗓", callback_data="period_30")
    builder.adjust(2)
    return builder.as_markup()

def get_skip_note_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустити ➡️", callback_data="skip_note")
    return builder.as_markup()

# --- Розклад (Scheduler) ---
async def daily_morning_checkin(bot: Bot):
    """Ця функція запускається автоматично щоранку"""
    users = get_all_users()
    print(f"⏰ Починаю ранкову розсилку для {len(users)} користувачів...")
    
    for user_id in users:
        try:
            await bot.send_message(
                user_id, 
                "☀️ <b>Доброго ранку!</b>\n\nЧас прокинутись і зачекінити свій настрій. Як ти сьогодні?", 
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            print(f"Не вдалося надіслати повідомлення користувачу {user_id}: {e}")

# 4. Обробники (Handlers)
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    conn = sqlite3.connect('mood.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", 
              (message.from_user.id, datetime.now()))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"Привіт, {message.from_user.first_name}! 👋\nЯ твій персональний AI-трекер настрою.", 
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "checkin")
async def start_checkin(callback: types.CallbackQuery):
    await callback.message.edit_text("Як ти себе почуваєш зараз?", reply_markup=get_mood_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("mood_"))
async def save_mood_ask_note(callback: types.CallbackQuery, state: FSMContext):
    mood = callback.data.split("_")[1]
    log_id = log_mood_start(callback.from_user.id, mood)
    await state.update_data(current_log_id=log_id, current_mood=mood)
    await state.set_state(MoodInteraction.waiting_for_note)
    
    await callback.message.edit_text(
        f"Настрій '{mood}' записано! ✅\n\nНапиши коротко, що саме вплинуло на твій настрій?", 
        reply_markup=get_skip_note_keyboard()
    )
    await callback.answer()

@dp.message(MoodInteraction.waiting_for_note)
async def process_note(message: types.Message, state: FSMContext):
    data = await state.get_data()
    log_id = data.get("current_log_id")
    update_mood_note(log_id, message.text)
    await state.clear()
    await message.answer("Дякую! Твою нотатку збережено. ✍️", reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "skip_note", MoodInteraction.waiting_for_note)
async def skip_note_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Добре, записав тільки настрій! 👌", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "stats_menu")
async def show_stats_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("За який період показати статистику?", reply_markup=get_stats_period_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("period_"))
async def calculate_stats(callback: types.CallbackQuery):
    days = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    logs = get_stats_data(user_id, days)
    
    if not logs:
        await callback.message.edit_text(f"За останні {days} днів записів немає 🤷‍♂️", reply_markup=get_main_keyboard())
        return

    await callback.message.edit_text(f"⏳ Аналізую твої останні {days} днів...", reply_markup=None)

    total_logs = len(logs)
    mood_counts = {}
    for log in logs:
        mood = log[0]
        mood_counts[mood] = mood_counts.get(mood, 0) + 1
    
    stats_text = f"📊 <b>Статистика за {days} днів:</b>\n\n"
    for mood, count in mood_counts.items():
        percentage = (count / total_logs) * 100
        stats_text += f"{mood}: {count} ({percentage:.1f}%)\n"
    
    prompt = f"""
    Ось статистика настрою користувача за останні {days} днів:
    {stats_text}
    Напиши одну коротку мотивуючу фразу.
    """
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        ai_comment = response.text
    except:
        ai_comment = "Тримай хвіст пістолетом! ✨"

    final_text = f"{stats_text}\n💡 <b>Думка AI:</b>\n{ai_comment}"
    
    try:
        await callback.message.edit_text(final_text, parse_mode="HTML", reply_markup=get_main_keyboard())
    except:
        await callback.message.answer(final_text, parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "advice")
async def get_ai_advice(callback: types.CallbackQuery):
    msg = await callback.message.answer("🤖 Аналізую твій стан... (зачекай)")
    logs = get_recent_logs(callback.from_user.id, 5)
    if not logs:
        await msg.edit_text("Спочатку зроби хоча б один запис!", reply_markup=get_main_keyboard())
        return

    history_text = ""
    for row in logs:
        mood, note, timestamp = row
        note_text = f" (Думки: {note})" if note else ""
        history_text += f"- {mood}{note_text}\n"
    
    prompt = f"""
    Ти - найкращий друг і психолог. Ось останні записи користувача:
    {history_text}
    Проаналізуй це. Дай коротку пораду (до 4 речень). 
    """
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        if response.text:
            await msg.edit_text(f"💭 <b>Порада:</b>\n\n{response.text}", parse_mode="HTML", reply_markup=get_main_keyboard())
        else:
            await msg.edit_text("Спробуй ще раз.", reply_markup=get_main_keyboard())
    except Exception as e:
        await msg.edit_text(f"Помилка AI: {str(e)}", reply_markup=get_main_keyboard())
    await callback.answer()

# Запуск
async def main():
    init_db()
    
    # --- НАЛАШТУВАННЯ ПЛАНУВАЛЬНИКА ---
    scheduler = AsyncIOScheduler(timezone='Europe/Kyiv') # Встановіть ваш часовий пояс
    # Запускаємо о 9:00 ранку
    scheduler.add_job(daily_morning_checkin, trigger='cron', hour=9, minute=0, args=[bot])
    scheduler.start()
    
    print("Бот і Планувальник запущені...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот вимкнено")