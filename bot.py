# pip install pyTelegramBotAPI schedule

import telebot
from telebot import types
import sqlite3
import threading
import time
import schedule
from datetime import datetime
import pytz
import os
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def run_web():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_web, daemon=True).start()

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

TOKEN = "8618853225:AAEbqj9915d1lNq8TGjhVVNdQ5BUZG2x44c"
bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    is_done INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    remind_time TEXT,
    is_sent INTEGER DEFAULT 0
)
""")
conn.commit()

# ---------- Reply клавиатура ----------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✍️ Записать задачу", "📂 Мои задачи")
    kb.row("⏰ Напомнить", "❓ Помощь")
    kb.row(" Отмена")
    return kb

# ---------- /start ----------
@bot.message_handler(commands=["start"])
def start_cmd(message):
    with open('welcome.gif', 'rb') as gif_file:
        bot.send_animation(
            message.chat.id,
            gif_file,
            caption=(
                "🌸 *Добро пожаловать!*\n\n"
                "Я — твой уютный помощник по задачам. 📋\n"
                "Буду напоминать о задачах и не дам ничего забыть.\n\n"
                "👇 *Нажимай на кнопки внизу*, чтобы начать."
            ),
            parse_mode='Markdown',
            reply_markup=main_menu()
        )

# ---------- /help ----------
def handle_help(message):
    text = (
        "ℹ️ *Как пользоваться ботом:*\n\n"
        "✍️ /add — добавить новую задачу\n"
        "📂 /list — показать список задач\n"
        "⏰ /remind — создать напоминание\n"
        "📂 /my_reminders — мои напоминания\n"
        "❓ /help — эта помощь\n\n"
        "🎯 *Совет:* Нажимай на кнопки внизу — это быстрее!"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=main_menu())

@bot.message_handler(commands=["help"])
def help_cmd(message):
    handle_help(message)

@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def help_btn(message):
    handle_help(message)

# ---------- /add ----------
def handle_add(message):
    msg = bot.send_message(message.chat.id, "✍️ *Введи текст новой задачи:*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_task)

def save_task(message):
    if message.text in ["✍️ Записать задачу", "📂 Мои задачи", "❓ Помощь", "⏰ Напомнить", " Отмена"]:
        bot.send_message(message.chat.id, "❌ Сначала заверши добавление задачи или напиши «Отмена».")
        bot.register_next_step_handler(message, save_task)
        return

    if message.text == "Отмена":
        bot.send_message(message.chat.id, "Действие отменено. Возврат в главное меню.", reply_markup=main_menu())
        return

    cur.execute("INSERT INTO tasks (user_id, text) VALUES (?, ?)", (message.from_user.id, message.text))
    conn.commit()
    bot.send_message(message.chat.id, "✅ *Задача сохранена!*\n\n📌 Ты можешь посмотреть её в списке задач.", parse_mode='Markdown', reply_markup=main_menu())

@bot.message_handler(commands=["add"])
def add_cmd(message):
    handle_add(message)

@bot.message_handler(func=lambda m: m.text == "✍️ Записать задачу")
def add_btn(message):
    handle_add(message)

# ---------- /list ----------
def handle_list(message):
    cur.execute("SELECT id, text, is_done FROM tasks WHERE user_id=?", (message.from_user.id,))
    tasks = cur.fetchall()
    if not tasks:
        bot.send_message(message.chat.id, "🎉 У тебя пока нет задач! Нажми «Записать задачу», чтобы начать.", reply_markup=main_menu())
        return

    kb = types.InlineKeyboardMarkup(row_width=2)
    for task_id, text, is_done in tasks:
        if is_done:
            display_text = f"~~{text}~~"
            status_emoji = "✅"
        else:
            display_text = f"*{text}*"
            status_emoji = "⏳"

        btn_done = types.InlineKeyboardButton(f"{status_emoji} {display_text}", callback_data=f"done_{task_id}" if not is_done else "ignore")
        btn_del = types.InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{task_id}")
        kb.row(btn_done, btn_del)

    btn_close = types.InlineKeyboardButton("✖️ Закрыть список", callback_data="close_list")
    kb.row(btn_close)

    bot.send_message(message.chat.id, "📂 *Твои задачи:*", parse_mode='Markdown', reply_markup=kb)
def list_cmd(message):
    handle_list(message)

@bot.message_handler(func=lambda m: m.text == "📂 Мои задачи")
def list_btn(message):
    handle_list(message)

@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def done_callback(call):
    task_id = int(call.data.split("_")[1])
    cur.execute("UPDATE tasks SET is_done=1 WHERE id=?", (task_id,))
    conn.commit()
    bot.answer_callback_query(call.id, "✅ Задача выполнена!")
    bot.edit_message_text("🎉 *Молодец! Задача отмечена выполненной.*", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    handle_list(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_task_callback(call):
    task_id = int(call.data.split("_")[1])
    cur.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    bot.answer_callback_query(call.id, "🗑️ Задача удалена!")
    handle_list(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "close_list")
def close_list_callback(call):
    bot.edit_message_text("📂 Список закрыт.", call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🏠 *Главное меню:*", parse_mode='Markdown', reply_markup=main_menu())

# ---------- /remind ----------
def handle_remind(message):
    msg = bot.send_message(message.chat.id, "⏰ *Введи текст напоминания:*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, get_remind_time)

def get_remind_time(message):
    if message.text in ["✍️ Записать задачу", "📂 Мои задачи", "❓ Помощь", "⏰ Напомнить", " Отмена"]:
        bot.send_message(message.chat.id, "❌ Сначала заверши создание напоминания или напиши «Отмена».")
        bot.register_next_step_handler(message, get_remind_time)
        return

    if message.text == "Отмена":
        bot.send_message(message.chat.id, "Действие отменено. Возврат в главное меню.", reply_markup=main_menu())
        return

    text = message.text
    msg = bot.send_message(message.chat.id, "🕐 *Введи время в формате ЧЧ:ММ:*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_reminder, text)

def save_reminder(message, text):
    time_str = message.text.strip()

    if time_str in ["✍️ Записать задачу", "📂 Мои задачи", "❓ Помощь", "⏰ Напомнить", " Отмена"]:
        bot.send_message(message.chat.id, "❌ Сначала заверши создание напоминания или напиши «Отмена».")
        bot.register_next_step_handler(message, save_reminder, text)
        return

    if time_str == "Отмена":
        bot.send_message(message.chat.id, "Действие отменено. Возврат в главное меню.", reply_markup=main_menu())
        return

    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат времени. Попробуй ещё раз.", reply_markup=main_menu())
        return

    cur.execute("INSERT INTO reminders (user_id, text, remind_time) VALUES (?, ?, ?)", (message.from_user.id, text, time_str))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ Напоминание на *{time_str}* установлено! ⏰", parse_mode='Markdown', reply_markup=main_menu())

@bot.message_handler(commands=["remind"])
def remind_cmd(message):
    handle_remind(message)

@bot.message_handler(func=lambda m: m.text == "⏰ Напомнить")
def remind_btn(message):
    handle_remind(message)

# ---------- /my_reminders ----------
@bot.message_handler(commands=["my_reminders"])
def my_reminders_cmd(message):
    cur.execute("SELECT id, text, remind_time FROM reminders WHERE user_id=? AND is_sent=0", (message.from_user.id,))
    reminders = cur.fetchall()
    if not reminders:
        bot.send_message(message.chat.id, "📭 У тебя пока нет активных напоминаний.")
        return

    kb = types.InlineKeyboardMarkup()
    for r_id, text, r_time in reminders:
        btn_text = f"{r_time} - {text} ❌"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"delrem_{r_id}"))
    bot.send_message(message.chat.id, "⏰ *Твои напоминания:*", parse_mode='Markdown', reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delrem_"))
def delrem_callback(call):
    r_id = int(call.data.split("_")[1])
    cur.execute("DELETE FROM reminders WHERE id=?", (r_id,))
    conn.commit()
    bot.answer_callback_query(call.id, "🗑️ Напоминание удалено")
    bot.edit_message_text("🗑️ Напоминание удалено.", call.message.chat.id, call.message.message_id)

# ---------- Планировщик ----------
def check_reminders():
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz).strftime("%H:%M")
    cur.execute("SELECT id, user_id, text FROM reminders WHERE remind_time=? AND is_sent=0", (now,))
    due = cur.fetchall()
    for r_id, user_id, text in due:
        try:
            bot.send_message(user_id, f"⏰ *Напоминание:* {text}", parse_mode='Markdown')
        except Exception as e:
            print(f"Ошибка отправки: {e}")
        cur.execute("UPDATE reminders SET is_sent=1 WHERE id=?", (r_id,))
        conn.commit()

def run_scheduler():
    schedule.every(1).minutes.do(check_reminders)
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_scheduler, daemon=True).start()

# ---------- Запуск ----------
if __name__ == "__main__":
    bot.infinity_polling()
