import telebot
import sqlite3
from telebot import types
from googleapiclient.discovery import build

# --- 1. Инициализация и настройка ---

TOKEN = 'your_token' # Замените на ваш токен
MAIN_ADMIN_ID = 123456789 # Замените на ваш ID

# Клавиатура для выбора должности
role_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
btn1 = types.KeyboardButton('Обычный ученик (волонтер)')
btn2 = types.KeyboardButton('Куратор')
btn3 = types.KeyboardButton('Ответственное лицо')
role_keyboard.add(btn1, btn2, btn3)


bot = telebot.TeleBot(TOKEN)
DB_NAME = 'bot_data.db'

# --- 2. Функции для работы с базой данных ---

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Таблица пользователей (user_id, status, username, region, city, role, is_registered)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL,
            username TEXT,
            region TEXT,
            city TEXT,
            role TEXT,
            is_registered INTEGER DEFAULT 0
        )
    ''')
    # Таблица для хранения контента (id, text, author_id, created_at)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            author_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def get_user_status(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'new'

def is_user_registered(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT is_registered FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def update_user_status(user_id, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (status, user_id))
    conn.commit()
    conn.close()

def add_new_user(user_id, username, status='new'):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Добавляем пользователя с is_registered=0
    cursor.execute('INSERT OR REPLACE INTO users (user_id, username, status, is_registered) VALUES (?, ?, ?, ?)', 
                   (user_id, username, status, 0))
    conn.commit()
    conn.close()

def update_registration_data(user_id, region, city, role):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET 
        region = ?, 
        city = ?, 
        role = ?, 
        is_registered = 1,
        status = 'user'
        WHERE user_id = ?
    ''', (region, city, role, user_id))
    conn.commit()
    conn.close()

def get_pending_requests():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username FROM users WHERE status = "pending"',)
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_admins():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username FROM users WHERE status = "admin"',)
    results = cursor.fetchall()
    conn.close()
    return results

def add_content(text, author_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO content (text, author_id) VALUES (?, ?)', (text, author_id))
    conn.commit()
    conn.close()

def get_all_content():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT text FROM content ORDER BY id DESC')
    results = cursor.fetchall()
    conn.close()
    return results
