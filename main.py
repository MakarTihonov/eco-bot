import telebot
import sqlite3
import random
import string
import datetime
import pytz
import io
import html
import time
import psutil
import os
import signal
import sys
import hashlib
import qrcode
import csv
import pandas as pd
from telebot import apihelper
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
from reportlab.lib import colors
from reportlab.lib.units import cm
from openpyxl.utils import get_column_letter

# --- Константы  ---
TOKEN = '' 
MAIN_ADMIN_ID =  123456789
DB_NAME = 'bot_data.db'
report_cooldowns = {}
last_message_times = {}
apihelper.ENABLE_MIDDLEWARE = True 
# --- Инициализация планировщика (Глобально) ---
timezone_spb = pytz.timezone('Europe/Moscow')
scheduler = BackgroundScheduler(timezone=timezone_spb)
FONT_PATH = 'Arial.ttf' 
try:
    pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))
except Exception as e:
    print(f"Ошибка загрузки шрифта для PDF: {e}")
#СПИСОК СУБЪЕКТОВ РФ 
RUSSIAN_SUBJECTS = [
    "Республика Адыгея", "Республика Алтай", "Республика Башкортостан", "Республика Бурятия", "Республика Дагестан", 
    "Республика Ингушетия", "Кабардино-Балкарская Республика", "Республика Калмыкия", "Карачаево-Черкесская Республика", 
    "Республика Карелия", "Республика Коми", "Республика Крым", "Республика Марий Эл", "Республика Мордовия", 
    "Республика Саха (Якутия)", "Республика Северная Осетия — Алания", "Республика Татарстан", "Республика Тыва", 
    "Удмуртская Республика", "Республика Хакасия", "Чеченская Республика", "Чувашская Республика", "Алтайский край", 
    "Забайкальский край", "Камчатский край", "Краснодарский край", "Красноярский край", "Пермский край", 
    "Приморский край", "Ставропольский край", "Хабаровский край", "Амурская область", "Архангельская область", 
    "Астраханская область", "Белгородская область", "Брянская область", "Владимирская область", "Волгоградская область", 
    "Вологодская область", "Воронежская область", "Ивановская область", "Иркутская область", "Калининградская область", 
    "Калужская область", "Кемеровская область — Кузбасс", "Кировская область", "Костромская область", 
    "Курганская область", "Курская область", "Ленинградская область", "Липецкая область", "Магаданская область", 
    "Московская область", "Мурманская область", "Нижегородская область", "Новгородская область", "Новосибирская область", 
    "Омская область", "Оренбургская область", "Орловская область", "Пензенская область", "Псковская область", 
    "Ростовская область", "Рязанская область", "Самарская область", "Саратовская область", "Сахалинская область", 
    "Свердловская область", "Смоленская область", "Тамбовская область", "Тверская область", "Томская область", 
    "Тульская область", "Тюменская область", "Ульяновская область", "Челябинская область", "Ярославская область", 
    "Город Москва", "Город Санкт-Петербург", "Город Севастополь", "Еврейская автономная область", 
    "Ненецкий автономный округ", "Ханты-Мансийский автономный округ — Югра", "Чукотский автономный округ", 
    "Ямало-Ненецкий автономный округ",
    "Донецкая Народная Республика",
    "Луганская Народная Республика",
    "Запорожская область",
    "Херсонская область"
]

# --- Клавиатуры ---
role_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
btn1 = types.KeyboardButton('Ученик (волонтер)')
btn2 = types.KeyboardButton('Куратор')
btn3 = types.KeyboardButton('Ответственное лицо')
role_keyboard.add(btn1, btn2, btn3)
# --- Новая клавиатура для обычных пользователей
user_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
btn_content = types.KeyboardButton('📖 Посты')
btn_events = types.KeyboardButton('🌳 Мероприятия')
btn_profile = types.KeyboardButton('👤 Профиль')
btn_faq = types.KeyboardButton('📚 FAQ')
btn_all_commands = types.KeyboardButton('📜 Все команды')
btn_cancel_user = types.KeyboardButton('❌ Отмена')
user_keyboard.add(btn_content, btn_events, btn_profile, btn_faq)
user_keyboard.add(btn_all_commands, btn_cancel_user)
bot = telebot.TeleBot(TOKEN)
if not hasattr(bot, 'user_data'):
    bot.user_data = {}

# --- 2. Функции для работы с базой данных ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;') 
    conn.execute('PRAGMA foreign_keys = ON;') 
    return conn

def init_db():
    """Инициализация базы данных и создание таблиц, если их нет."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Таблица пользователей (user_id, status, username, region, city, role, is_registered, hours и тд.)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                username TEXT,
                region TEXT,
                city TEXT,
                role TEXT,
                is_registered INTEGER DEFAULT 0,
                hours INTEGER DEFAULT 0, 
                full_name TEXT,           
                age INTEGER              
            )
        ''')
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            # Если колонка уже есть, sqlite3 выдаст ошибку, которую игнорируем
            pass
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                author_id INTEGER,
                scope TEXT NOT NULL DEFAULT 'all',
                region TEXT
            )
        ''')
        
        # Таблица для эко-мероприятий (с добавленной колонкой check_in_code)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                region TEXT NOT NULL,
                event_date TEXT,
                location TEXT,
                creator_id INTEGER NOT NULL,
                check_in_code TEXT DEFAULT NULL
            )
        ''')
        
        # Таблица для FAQ
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                region TEXT DEFAULT 'all',
                author_id INTEGER
            )
        ''')
        
        # Таблица для записей на мероприятия
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_registrations (
                registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                is_attended INTEGER DEFAULT 0,
                UNIQUE(event_id, user_id), 
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE, 
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE 
            )
        ''')
        try:
            pass
        except sqlite3.OperationalError:
            pass
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id INTEGER NOT NULL,
                reporter_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', 
                reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (content_id) REFERENCES content(id) ON DELETE CASCADE, 
                FOREIGN KEY (reporter_user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        # Таблица для отслеживания дневного лимита часов админов (admin_id, date, hours_awarded)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_limits (
                admin_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                hours_awarded INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (admin_id, date)
            )
        ''')
        # Таблица для отслеживания фактов превышения лимита админами (admin_id, violation_date, month_year)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                violation_date TEXT NOT NULL,
                month_year TEXT NOT NULL
            )
        ''')
        try:
            cursor.execute("ALTER TABLE content_reports ADD COLUMN report_text TEXT")
            conn.commit()
            print("Колонка report_text успешно добавлена!")
        except sqlite3.OperationalError:
            print("Ошибка: возможно, колонка уже существует или таблица не найдена.")
        conn.commit()

@bot.message_handler(func=lambda message: get_user_status(message.chat.id) == 'banned')
def handle_banned_users(message):
    bot.send_message(message.chat.id, "🚫 Вы забанены и не можете использовать бота.")
    return

def add_content(text, author_id, scope, region=None):
    """Добавляет новый контент в БД с указанием области видимости (scope)."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO content (text, author_id, scope, region) VALUES (?, ?, ?, ?)', 
                       (text, author_id, scope, region))
        conn.commit()

def create_event(title, description, region, event_date, location, creator_id, check_in_code=None):
    """Создает новое мероприятие в БД."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO events (title, description, region, event_date, location, creator_id, check_in_code) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, region, event_date, location, creator_id, check_in_code))
        conn.commit()

def get_all_content_for_user(user_id):
    user_region = get_user_region(user_id)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT text, region, scope, id FROM content 
            WHERE scope = 'all' 
            OR (scope = 'region' AND region = ?)
            ORDER BY id DESC
        ''', (user_region,))
        results = cursor.fetchall()
    return results

def get_events_for_region(region, view_mode='new'):
    """Получает активные (новые) или старые мероприятия для указанного региона."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        today_date = datetime.datetime.now(timezone_spb).strftime('%Y-%m-%d %H:%M') 
        if view_mode == 'new':
            sql_query = '''
                SELECT id, title, description, event_date, location FROM events 
                WHERE region = ? AND event_date >= ?
                ORDER BY event_date ASC
            '''
            cursor.execute(sql_query, (region, today_date))
        elif view_mode == 'old':
             sql_query = '''
                SELECT id, title, description, event_date, location FROM events 
                WHERE region = ? AND event_date < ?
                ORDER BY event_date DESC
            '''
             cursor.execute(sql_query, (region, today_date)) 
        else:
            sql_query = '''
                SELECT id, title, description, event_date, location FROM events 
                WHERE region = ?
                ORDER BY event_date DESC
            '''
            cursor.execute(sql_query, (region,)) 
        results = cursor.fetchall()
    return results

def add_faq_item(question, answer, region='all', author_id=None):
    """Добавляет новый вопрос-ответ в FAQ."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO faq (question, answer, region, author_id) 
            VALUES (?, ?, ?, ?)
        ''', (question, answer, region, author_id))
        conn.commit()

def get_faq_for_user_region(user_region):
    """Получает глобальные и региональные вопросы FAQ для пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT question, answer, region FROM faq 
            WHERE region = 'all' OR region = ?
            ORDER BY region DESC, question ASC
        ''', (user_region,))
        results = cursor.fetchall()
    return results

def add_hours(user_id, hours_to_add):
    """Начисляет или снимает часы пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET hours = hours + ? 
            WHERE user_id = ?
        ''', (hours_to_add, user_id))
        conn.commit()

def get_user_hours(user_id):
    """Получает текущее количество часов пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT hours FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    return result[0] if result else 0

def check_and_update_admin_limit(admin_id, hours_to_add):
    today = datetime.date.today().strftime('%Y-%m-%d')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Проверяем текущее значение
        cursor.execute('SELECT hours_awarded FROM admin_limits WHERE admin_id = ? AND date = ?', (admin_id, today))
        row = cursor.fetchone()
        
        if row:
            current_today = row[0]
            if current_today + hours_to_add > 150:
                return False  # Лимит превышен
            
            # 2. Если запись есть, обновляем ее
            cursor.execute('''
                UPDATE admin_limits 
                SET hours_awarded = hours_awarded + ? 
                WHERE admin_id = ? AND date = ?
            ''', (hours_to_add, admin_id, today))
        else:
            # 3. Если записи нет, создаем новую
            if hours_to_add > 150:
                return False
            cursor.execute('''
                INSERT INTO admin_limits (admin_id, date, hours_awarded) 
                VALUES (?, ?, ?)
            ''', (admin_id, today, hours_to_add))
            
        conn.commit()
    return True

def get_monthly_violations_report(month_year):
    """
    Генерирует отчет о количестве нарушений лимита для каждого админа за указанный месяц/год.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT admin_id, COUNT(*) as violation_count FROM admin_violations
            WHERE month_year = ?
            GROUP BY admin_id
            HAVING violation_count > 35
        ''', (month_year,))
        results = cursor.fetchall()
    return results

def get_responsible_persons_in_region(region):
    """Получает user_id всех Ответственных лиц в определенном регионе."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username FROM users 
            WHERE (status = "admin" OR role = "Ответственное лицо") AND region = ?
        ''', (region,))
        results = cursor.fetchall()
    return results 

def send_monthly_violation_report():
    """
    Отправляет ежемесячный отчет главному администратору о злостных нарушителях лимита.
    """
    today = datetime.date.today()
    first_of_month = today.replace(day=1) 
    last_month = first_of_month - datetime.timedelta(days=1)
    target_month_year = last_month.strftime('%Y-%m')

    violations = get_monthly_violations_report(target_month_year)
    
    if not violations:
        return

    report_text = f"<b>🚨 ЕЖЕМЕСЯЧНЫЙ ОТЧЕТ О НАРУШЕНИЯХ (За {target_month_year}) 🚨</b>\n\n"
    for admin_id, count in violations:
        # Получаем данные админа
        user_details = get_user_details(admin_id)
        username = user_details[0] if user_details else f"ID: {admin_id}"
        
        report_text += f"👤 Админ: @{username} (ID: {admin_id})\n"
        report_text += f"Кол-во нарушений лимита: <b>{count} раз</b>\n"

        markup = types.InlineKeyboardMarkup()
        btn_demote = types.InlineKeyboardButton("Лишить прав админа ❌", callback_data=f"demote_{admin_id}")
        btn_message = types.InlineKeyboardButton("Написать напрямую ✉️", callback_data=f"reply_{admin_id}")
        markup.add(btn_demote, btn_message)
        bot.send_message(MAIN_ADMIN_ID, report_text, reply_markup=markup, parse_mode='HTML')
        report_text = "" 

def get_top_volunteers(region=None, limit=10):
    """Получает список лучших волонтеров (по региону или глобально)."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        if region:
            cursor.execute('''
                SELECT username, hours FROM users 
                WHERE region = ? AND is_registered = 1 
                ORDER BY hours DESC LIMIT ?
            ''', (region, limit))
        else:
            cursor.execute('''
                SELECT username, hours FROM users 
                WHERE is_registered = 1 
                ORDER BY hours DESC LIMIT ?
            ''', (limit,))
        results = cursor.fetchall()
    return results

def get_user_id_by_username(username):
    """Получает user_id по username."""
    clean_username = username.lstrip('@') 
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE username LIKE ?', (clean_username,))
        result = cursor.fetchone()
    return result[0] if result else None

def register_for_event(user_id, event_id):
    """Регистрирует пользователя на мероприятие."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO event_registrations (user_id, event_id) VALUES (?, ?)', (user_id, event_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def is_user_registered_for_event(user_id, event_id):
    """Проверяет, зарегистрирован ли пользователь на конкретное мероприятие."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM event_registrations WHERE user_id = ? AND event_id = ?', (user_id, event_id))
        count = cursor.fetchone()[0]
    return count > 0

def get_user_status(user_id):
    """Получает текущий статус пользователя."""
    if user_id == MAIN_ADMIN_ID:
        return 'admin'
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    return result[0] if result else 'new'

def update_user_status(user_id, status):
    """Обновляет статус пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (status, user_id))
        conn.commit()

# Функция для бана пользователя
def ban_user_in_db(user_id):
    update_user_status(user_id, 'banned')

def unban_user_in_db(user_id):
    update_user_status(user_id, 'user') 

def get_monthly_violations_report_current(month_year):
    """
    Получает список всех нарушений за текущий месяц для команды /view_violations.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT admin_id, violation_date FROM admin_violations
            WHERE month_year = ?
            ORDER BY violation_date DESC
        ''', (month_year,))
        results = cursor.fetchall()
    return results

def get_stats_from_db():
    """Получает общую статистику по системе."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Общее количество пользователей
        users_count = cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        # Количество админов (включая главного админа)
        admins_count = cursor.execute('SELECT COUNT(*) FROM users WHERE status = "admin"').fetchone()[0]
        # Количество постов
        content_count = cursor.execute('SELECT COUNT(*) FROM content').fetchone()[0]
        # Количество мероприятий
        events_count = cursor.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        hours_count = cursor.execute('SELECT SUM(hours) FROM users').fetchone()[0] or 0
        
        return users_count, admins_count, content_count, events_count, hours_count

def is_command_and_cancel_process(message):
    """Проверяет, является ли сообщение командой. Если да, отменяет текущий step-handler и возвращает пользователя в соответствующее меню (админ/пользователь). 
    Возвращает True, если была команда, False в противном случае."""
    user_id = message.chat.id
    if message.text and message.text.startswith('/'):
        bot.clear_step_handler_by_chat_id(user_id)
        bot.send_message(user_id, f"Действие отменено командой: {message.text}")
        status = get_user_status(user_id)
        if status == 'admin':
            admin_panel(message) 
        else:
            bot.send_message(user_id, "Воспользуйтесь меню ниже.", reply_markup=user_keyboard) 
        return True
    return False

def is_user_registered(user_id):
    """Проверяет, завершил ли пользователь регистрацию."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT is_registered FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    return result is not None and result[0] == 1

def update_user_status(user_id, status):
    """Обновляет статус пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (status, user_id))
        conn.commit()

def add_new_user(user_id, username, status='new'):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, status, is_registered, hours, is_active) 
            VALUES (?, ?, ?, 0, 0, 1)
        ''', (user_id, username, status))
        cursor.execute('UPDATE users SET is_active = 1, username = ? WHERE user_id = ?', (username, user_id))
        conn.commit()

def update_registration_data_fixed(user_id, region, city, role, full_name, age, status):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET 
            region = ?, city = ?, role = ?, full_name = ?, age = ?, 
            is_registered = 1, status = ?
            WHERE user_id = ?
        ''', (region, city, role, full_name, age, status, user_id))
        conn.commit()

def get_pending_requests():
    """Получает список пользователей, ожидающих одобрения админа."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username FROM users WHERE status = "pending"')
        results = cursor.fetchall()
    return results

def get_all_admins():
    """Получает список всех администраторов."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username FROM users WHERE status = "admin"')
        results = cursor.fetchall()
    return results

def get_user_region(user_id):
    """Получает регион пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT region FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    return result[0] if result else None

def get_users_in_region(region):
    """Получает user_id всех пользователей в определенном регионе."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE region = ?', (region,))
        results = cursor.fetchall()
    return [row[0] for row in results] 
# --- 3. Обработчики команд и процесс регистрации ---

@bot.message_handler(commands=['my_rating'])
def display_my_rating(message):
    user_id = message.chat.id
    if not is_user_registered(user_id):
        enforce_registration(message)
        return

    hours = get_user_hours(user_id)
    bot.send_message(user_id, f"🌟 Ваш текущий рейтинг: **{hours} часов**.", parse_mode='Markdown')

@bot.message_handler(commands=['eco_faq'])
def view_faq(message):
    user_id = message.chat.id
    user_region = get_user_region(user_id)
    
    if not user_region:
        user_region = 'N/A' 

    faq_items = get_faq_for_user_region(user_region)

    if faq_items:
        response = f"📚 <b>Экологический FAQ</b> (для региона {user_region}):\n\n"
        current_scope = None
        for question, answer, region_scope in faq_items:
            if region_scope != current_scope:
                scope_title = "Общие вопросы 🌍" if region_scope == 'all' else f"Вопросы по вашему региону 🏠"
                response += f"\n--- <i>{scope_title}</i> ---\n"
                current_scope = region_scope
            response += f"❓ <b>{question}</b>\n➡️ {answer}\n\n"
        bot.send_message(user_id, response, parse_mode='HTML')
    else:
        bot.send_message(user_id, "К сожалению, раздел FAQ пока пуст.")

@bot.message_handler(commands=['add_faq'])
def prompt_add_faq(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    
    if status == 'admin':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('Глобальный (для всех) 🌍', 'Только для моего региона 🏠')
        msg = bot.send_message(user_id, "Выберите область видимости для нового вопроса FAQ:", reply_markup=markup)
        bot.user_data[user_id] = {'adding_faq': True}
        bot.register_next_step_handler(msg, process_faq_scope)
    else:
        bot.send_message(user_id, "У вас нет прав для добавления FAQ. 🚫")

def get_user_event_history(user_id, limit=3):
    """Получает названия и даты последних мероприятий, в которых участвовал пользователь."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT E.title, E.event_date
            FROM event_registrations AS ER
            JOIN events AS E ON ER.event_id = E.id
            WHERE ER.user_id = ?
            ORDER BY E.event_date DESC 
            LIMIT ?
        ''', (user_id, limit))
        results = cursor.fetchall()
    return results

def process_faq_scope(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    if user_id not in bot.user_data or not bot.user_data[user_id].get('adding_faq'): return

    scope_choice_text = message.text.lower()
    if 'для всех' in scope_choice_text or 'глобальный' in scope_choice_text:
        scope = 'all'
    elif 'моего региона' in scope_choice_text:
        scope = get_user_region(user_id)
        if not scope:
            bot.send_message(user_id, "Не удалось определить ваш регион. Начните заново /add_faq.")
            del bot.user_data[user_id]
            return
    else:
        msg = bot.send_message(user_id, "Неверный выбор. Пожалуйста, используйте кнопки.")
        bot.register_next_step_handler(msg, process_faq_scope) 
        return

    bot.user_data[user_id]['scope'] = scope
    msg = bot.send_message(user_id, "Отлично. Теперь введите сам **вопрос** (например: 'Куда сдать батарейки?'):", reply_markup=types.ReplyKeyboardRemove(), parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_faq_question)

def clear_old_report_cooldowns():
    now = time.time()
    to_delete = [uid for uid, timestamp in report_cooldowns.items() if now - timestamp > 900]
    for uid in to_delete:
        del report_cooldowns[uid]
    if to_delete:
        print(f"[{datetime.datetime.now()}] Очищено {len(to_delete)} записей из лимита жалоб.")

def generate_certificate(user_id, full_name, hours, region, city):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    try:
        pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))
    except:
        print("Ошибка: Arial.ttf не найден")

# 1. Генерируем уникальный проверочный код (защита от подделки)
    cert_id = hashlib.md5(f"{user_id}:{datetime.date.today()}".encode()).hexdigest()[:10].upper()

    # --- ВОДЯНОЙ ЗНАК (Background) ---
    p.saveState() # Сохраняем состояние для прозрачности
    p.setStrokeColor(colors.lightgrey)
    p.setFillColor(colors.whitesmoke)
    p.setFont('Arial', 80)
    p.translate(width/2, height/2) # Смещаемся в центр
    p.rotate(45) # Поворачиваем текст
    p.drawCentredString(0, 0, "ECO-BOT VERIFIED") # Пишем знак
    p.restoreState() # Возвращаем настройки (убираем прозрачность и поворот)

# --- 2. Эко-Рамка (Альбомная) ---
    p.setStrokeColor(colors.forestgreen) 
    p.setLineWidth(5)
    # Рисуем рамку с отступом 1 см
    p.rect(1*cm, 1*cm, width-2*cm, height-2*cm)
    p.setLineWidth(1)
    p.rect(1.2*cm, 1.2*cm, width-2.4*cm, height-2.4*cm) 
    
# --- 3. Заголовок ---
    p.setFont('Arial', 40)
    p.drawCentredString(width/2, height - 4*cm, "СЕРТИФИКАТ")
    p.setFont('Arial', 20)
    p.drawCentredString(width/2, height - 5.5*cm, "ПОДТВЕРЖДАЮЩИЙ ВОЛОНТЕРСКУЮ ДЕЯТЕЛЬНОСТЬ")

# --- 4. ФИО волонтера ---
    p.setFont('Arial', 30)
    p.drawCentredString(width/2, height / 2 + 1*cm, full_name.title())
    p.setFont('Arial', 16)
    p.drawCentredString(width/2, height / 2 - 0.5*cm, f"г. {city.title()}, {region}")

# --- 5. Инфо-блок с часами ---
    p.setFillColor(colors.lightgreen)
    p.rect(width/2 - 6*cm, height / 2 - 4*cm, 12*cm, 1.5*cm, fill=1)
    p.setFillColor(colors.black)
    p.setFont('Arial', 22)
    p.drawCentredString(width/2, height / 2 - 3.4*cm, f"{hours} ВОЛОНТЕРСКИХ ЧАСОВ")

# --- 6. Нижняя часть (Подписи) ---
    p.setFont('Arial', 12)
    
    # Слева: Директор
    p.drawString(3*cm, 4*cm, "__________________________")
    p.drawString(3*cm, 3.4*cm, "Генеральный директор")
    p.setFont('Arial', 14)
    p.drawString(3*cm, 4.3*cm, "General admin EcoBot") 
    
    # Справа: Дата
    p.setFont('Arial', 12)
    p.drawRightString(width - 3*cm, 4*cm, "__________________________")
    p.drawRightString(width - 3*cm, 3.4*cm, f"Дата выдачи: {datetime.date.today().strftime('%d.%m.%Y')}")

# --- 7. Печать (Сдвинута к центру внизу) ---
    p.setStrokeColor(colors.darkgreen) 
    p.circle(width/2, 3.5*cm, 1.8*cm)
    p.setFont('Arial', 8)
    p.drawCentredString(width/2, 4*cm, "ЭКО-БОТ РОССИЯ")
    p.drawCentredString(width/2, 3.5*cm, "ОФИЦИАЛЬНАЯ")
    p.drawCentredString(width/2, 3*cm, "ПЕЧАТЬ")

# --- 8. УНИКАЛЬНЫЙ ID СЕРТИФИКАТА ---
    p.setFont('Arial', 8)
    p.setFillColor(colors.grey)
    p.drawString(1.5*cm, 1.5*cm, f"VERIFICATION ID: {cert_id}")
    
    # Защитная надпись мелким шрифтом по периметру
    p.setFont('Arial', 6)
    protection_line = "OFFICIAL DOCUMENT • ECO-BOT RUSSIA 2026 • NON-TRANSFERABLE • " * 10
    p.drawString(1.2*cm, height - 0.8*cm, protection_line)

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

def get_volunteer_rank(hours):
    """Определяет звание волонтера на основе набранных часов."""
    if hours < 10: return "Новичок 🌱"
    if hours < 50: return "Помощник 🌿"
    if hours < 150: return "Энтузиаст 🌲"
    if hours < 500: return "Мастер Экологии 🌍"
    return "Легенда Природы 👑"

# --- Функция жалоб главному админу ---
@bot.message_handler(commands=['report_admin'])
def report_to_admin_prompt(message):
    print("Команда /report_admin получена!") 
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id)
    now = time.time()
    if user_id in report_cooldowns and now - report_cooldowns[user_id] < 900:
        bot.send_message(user_id, "⏳ Попробуйте через 15 минут.")
        return
    msg = bot.send_message(user_id, "Опишите ваш вопрос администратору:")
    bot.register_next_step_handler(msg, send_report_to_admin)
    report_cooldowns[user_id] = now

@bot.message_handler(commands=['get_certificate'])
def handle_get_certificate(message):
    user_id = message.chat.id
    details = get_user_details(user_id)
    if not details: return
    hours = details[5]
    if hours < 100:
        bot.send_message(user_id, f"❌ Для сертификата нужно 100 часов. У вас: {hours}")
        return
    # Если нажал НЕ ГЛАВНЫЙ АДМИН, а пользователь/куратор
    if user_id != MAIN_ADMIN_ID:
        markup = types.InlineKeyboardMarkup()
        btn_issue = types.InlineKeyboardButton("Выдать сертификат ✅", callback_data=f"admin_issue_cert_{user_id}")
        markup.add(btn_issue)
        bot.send_message(user_id, "⏳ Ваш запрос на сертификат отправлен на проверку главному администратору.")
        bot.send_message(MAIN_ADMIN_ID, f"📜 <b>Запрос сертификата</b>\n\nОт: {details[6]}\nID: <code>{user_id}</code>\nЧасов: {hours}", 
                         parse_mode='HTML', reply_markup=markup)
    else:
        pdf_file = generate_certificate(user_id, details[6], hours, details[1], details[2])
        bot.send_document(user_id, pdf_file, caption="Ваш официальный сертификат.")

def process_faq_question(message):
    if is_command_and_cancel_process(message): return
    if message.text == '/cancel':
        cancel_process(message)
        return
    user_id = message.chat.id
    if user_id not in bot.user_data or 'scope' not in bot.user_data[user_id]: return
    if message.content_type != 'text':
        msg = bot.send_message(message.chat.id, "⚠️ Ошибка! Введите текст (буквами):")
        bot.register_next_step_handler(msg, process_fullname_step)
        return
    bot.user_data[user_id]['question'] = message.text
    msg = bot.send_message(user_id, "Теперь введите **ответ** на этот вопрос:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_faq_answer)

def process_faq_answer(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    if user_id not in bot.user_data or 'question' not in bot.user_data[user_id]: return
    if message.content_type != 'text':
        msg = bot.send_message(message.chat.id, "⚠️ Ошибка! Введите текст (буквами):")
        bot.register_next_step_handler(msg, process_fullname_step)
        return
    answer = message.text
    question = bot.user_data[user_id]['question']
    scope = bot.user_data[user_id]['scope']
    
    add_faq_item(question, answer, scope, user_id)
    bot.send_message(user_id, f"✅ Вопрос в FAQ успешно добавлен с областью видимости: {scope}.")
    del bot.user_data[user_id]

@bot.message_handler(commands=['top_volunteers'])
def display_top_volunteers(message):
    user_id = message.chat.id
    region = get_user_region(user_id)
    if not region:
        bot.send_message(user_id, "Чтобы увидеть региональный рейтинг, укажите регион в /change.")
        return
    top_list = get_top_volunteers(region=region)
    safe_region = html.escape(region)
    title = f"🏆 <b>Топ 10 волонтеров ({safe_region})</b>"
    if top_list:
        response = f"{title}:\n\n"
        for i, (username, hours) in enumerate(top_list, 1):
            if username:
                safe_username = html.escape(username)
                display_name = f"@{safe_username}"
            else:
                display_name = f"Участник #{i}"
            response += f"{i}. {display_name}: <b>{hours}</b> часов\n"
        user_rank = get_user_regional_rank(user_id, region)
        if user_rank:
             response += f"\n--------------------------\n"
             response += f"👤 Ваше место: <b>#{user_rank}</b> в регионе"
        bot.send_message(user_id, response, parse_mode='HTML') 
    else:
        bot.send_message(user_id, f"В регионе {safe_region} пока нет волонтеров.", parse_mode='HTML')

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    text = message.text
    greeting = get_greeting() 
    username = message.from_user.username if message.from_user.username else f"волонтер_{user_id}"
# 1. Сначала проверяем, не по QR-коду ли пришел человек
    if len(text.split()) > 1:
        payload = text.split()[1] 
        # 1. Если отсканирован QR на 3 часа
        if payload.startswith('checkin_'):
            code = payload.replace('checkin', '').strip('_')
            process_qr_checkin(user_id, code, hours=3)
            return
        # 2. Если отсканирован QR на 2 часа
        if payload.startswith('short_'):
            code = payload.replace('short', '').strip('_')
            process_qr_checkin(user_id, code, hours=2)
            return
# 2. Если это не QR-код, проверяем, зарегистрирован ли он
    if not is_user_registered(user_id):
        add_new_user(user_id, username, status='registering') 
        msg = bot.send_message(user_id, "👋 Добро пожаловать! Для регистрации введите ваш **регион**:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_region_text_input)
    else:
        bot.send_message(user_id, f"{greeting}, {username}! Рады вас видеть.", reply_markup=user_keyboard)

def process_qr_checkin(user_id, code, hours):
    # 1. Ищем мероприятие в базе данных по коду
    event_data = get_event_by_code(code) 
    if not event_data:
        bot.send_message(user_id, "❌ Ошибка: Мероприятие не найдено или код неверный.")
        return
    event_id, title = event_data
    # 2. ПРОВЕРКА: Использовал ли пользователь уже ЛЮБОЙ код для этого мероприятия
    if has_user_checked_in(user_id, event_id):
        bot.send_message(user_id, f"❌ Вы уже получили часы за мероприятие «{title}». Повторное начисление невозможно.")
        return
    # 3. ПРОВЕРКА: Был ли пользователь вообще записан на это мероприятие
    if not is_user_registered_for_event(user_id, event_id):
        bot.send_message(user_id, f"❌ Вы не можете получить часы, так как не были записаны на «{title}» через бота.")
        return
    # 4. Начисляем часы (2 или 3 в зависимости от ссылки)
    add_hours(user_id, hours)
    # 5. СТАВИМ ОТМЕТКУ, что часы получены 
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE event_registrations 
            SET is_attended = 1 
            WHERE user_id = ? AND event_id = ?
        ''', (user_id, event_id))
        conn.commit()
    bot.send_message(user_id, f"🎉 Успешно! Вам начислено <b>{hours} ч.</b> за мероприятие: {title}", parse_mode='HTML')

def ping_monitor():
    """Функция для проверки активности бота и предотвращения 'засыпания'."""
    now_str = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')
    log_msg = f"[PING MONITOR] Бот активен. Время: {now_str}"
    print(log_msg)
    current_hour = datetime.datetime.now(pytz.timezone('Europe/Moscow')).hour
    if current_hour % 12 == 0:
        try:
            bot.send_message(MAIN_ADMIN_ID, f"🤖 <b>Системный отчет:</b> Бот работает стабильно.\nНагрузка в норме. {now_str}", parse_mode='HTML')
        except Exception as e:
            print(f"Ошибка пинг-уведомления админу: {e}")

# команда help
@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.chat.id, "Привет! Вот, что я умею: \n" 
    "\n"
    "/view_content - Просмотр постов, которые доступны для вас. \n" 
    "/view_events - Просмотр и запись на доступные мероприятия. \n"
    "/request_admin - Для заявки на должность админимстратора. \n"
    "/report_admin - Пожаловаться на администратора или контент. \n"
    "/profile - Посмотреть свой профиль. \n"
    "/my_rating - Посмотреть свой рейтинг. \n"
    "/top_volunteers - Рейтинг пользователей по региону. \n" 
    "/top_global - Рейтинг пользователей по стране. \n"
    "/eco_faq - Посмотреть полезную информацию и ответы на вопросы. \n" 
    "/cancel - Отмена действия. \n"
    "/my_events - Посмотреть запись на мероприятия. \n"
    "/admin - Доступные команды для администратора. \n" ) 

@bot.message_handler(commands=['all_command'])
def all_command(message):
    user_id = message.chat.id
    if user_id != MAIN_ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для использования этой команды.")
        return
    bot.send_message(message.chat.id, "Список всех команд: \n"
    " \n"
    "👤 Команды пользователя (волонтера) \n" 
    "Эти команды доступны всем зарегистрированным участникам: \n" 
    " \n"
    "/start — Запуск бота и начало регистрации (ФИО, возраст, регион, город). \n"
    "/profile или кнопка 👤 Профиль — Просмотр ваших данных: ФИО, город, звание, волонтерские часы и история событий. \n"
    "/view_content или кнопка 📖 Посты — Просмотр полезных материалов и новостей (глобальных или вашего региона). \n"
    "/view_events или кнопка 🌳 Мероприятия — Список актуальных и прошедших экологических акций для записи. \n"
    "/eco_faq или кнопка 📚 FAQ — База знаний по экологии и переработке. \n"
    "/my_rating — Просмотр вашего текущего баланса волонтерских часов. \n"
    "/top_volunteers — Рейтинг ТОП-10 волонтеров вашего региона. \n"
    "/top_global — Глобальный рейтинг волонтеров по всей стране. \n"
    "/checkin — Ввод секретного кода с мероприятия для получения волонтерских часов. \n"
    "/change — Меню изменения личных данных (регион, город). \n"
    "/request_admin — Подать заявку главному администратору на получение прав модератора. \n"
    "/report_admin — Отправить жалобу или вопрос напрямую главному администратору. \n"
    "/my_events - Посмотреть запись на мероприятия. \n"
    "/help — Полный список всех доступных команд. \n"
    "/cancel — Отмена любого текущего действия или ввода текста. \n" 
    " \n"
    "👑 Команды администратора (Ответственного лица) \n"
    "Доступны пользователям со статусом admin: \n" 
    " \n"
    "/admin или /admin_panel — Главная панель управления со всеми кнопками модерации. \n"
    "/add_content — Создание нового поста (с выбором: для всех или только для своего региона). \n"
    "/create_event — Создание нового мероприятия в своем регионе с генерацией кода подтверждения. \n"
    "/award_hours — Начисление или списание волонтерских часов пользователю (по ID или Username). \n"
    "/manage_content — Просмотр и удаление ваших опубликованных постов. \n"
    "/manage_reports — Просмотр и обработка жалоб пользователей на контент. \n"
    "/stats — Общая статистика бота (количество людей, постов, мероприятий). \n"
    "/add_faq — Добавление нового вопроса и ответа в базу FAQ. \n"
    "/issue_cert [ID] — Генерация и выдача PDF-сертификата пользователю (если у него 100+ часов). \n" 
    " \n"
    "👑 Команды ГЛАВНОГО администратора \n"
    "Эксклюзивные права управления системой: \n" 
    " \n"
    "/ban [ID] — Полная блокировка пользователя в боте. \n"
    "/unban [ID] — Разблокировка пользователя. \n"
    "/set_role [ID] [Роль] — Ручное назначение роли (Куратор, Волонтер и т.д.) или статуса admin. \n"
    "/view_violations — Отчет о нарушениях дневных лимитов (150ч) другими администраторами. \n"
    "/export_stats — Выгрузка всей базы данных пользователей в формате Excel/CSV. \n"
    "/ping - Понять работает ли бот. ")
    
@bot.message_handler(commands=['main'])
def all_command(message):
    user_id = message.chat.id
    if user_id != MAIN_ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав для использования этой команды.")
        return
    bot.send_message(message.chat.id, "👑 Команды главного администратора: \n" 
    " \n"
    "/ban [ID] — Полная блокировка пользователя в боте. \n"
    "/unban [ID] — Разблокировка пользователя. \n"
    "/set_role [ID] [Роль] — Ручное назначение роли (Куратор, Волонтер и т.д.) или статуса admin. \n"
    "/view_violations — Отчет о нарушениях дневных лимитов (150ч) другими администраторами. \n"
    "/export_stats — Выгрузка всей базы данных пользователей в формате Excel/CSV. \n"
    "/ping - Понять работает ли бот. \n"
    "/stats - Посмотреть статистику бота. \n"
    "/force_backup - Выгрузка БД (полностью)")

@bot.message_handler(commands=['admin'])
def admin(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    if status == 'admin':
        bot.send_message(message.chat.id, "Команды для админа: \n" 
        " \n"
        "/add_content - Добавить контент. \n"
        "/add_faq — Добавление нового вопроса и ответа в базу FAQ. \n"
        "/create_event - Создать мероприятие. \n" 
        "/admin_panel - Панель администратора. \n" 
        "/manage_content - Удалить и посмотреть контент.\n" 
        "/award_hours - Добавить волонтёрские часы пользователю. \n" 
        "/stats - Посмотреть статистику бота. \n"
        "/issue_cert [ID] — Генерация и выдача PDF-сертификата пользователю (если у него 100+ часов). \n"
        "/main - Команды ТОЛЬКО для главного администратора.")
    else:
        bot.send_message(message.chat.id, "Вы не являетесь администратором!")

@bot.message_handler(commands=['ping'])
def ping(message):
    cpu_usage = psutil.cpu_percent()
    ram_usage = psutil.virtual_memory().percent
    bot.send_message(
        message.chat.id, 
        f"✅ <b>Бот онлайн</b>\n"
        f"💻 Нагрузка CPU: {cpu_usage}%\n"
        f"🧠 Нагрузка RAM: {ram_usage}%\n"
        f"⏰ Время сервера: {datetime.datetime.now().strftime('%H:%M:%S')}",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['my_events'])
def view_my_registrations(message):
    user_id = message.chat.id
    if not is_user_registered(user_id):
        bot.send_message(user_id, "<b>❌ Ошибка:</b> Сначала завершите регистрацию!", parse_mode='HTML')
        return
    now_str = datetime.datetime.now(timezone_spb).strftime('%Y-%m-%d %H:%M')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT E.title, E.event_date, E.location 
            FROM events E 
            JOIN event_registrations ER ON E.id = ER.event_id 
            WHERE ER.user_id = ? AND E.event_date >= ?
            ORDER BY E.event_date ASC
        ''', (user_id, now_str))
        rows = cursor.fetchall()
    if not rows:
        bot.send_message(user_id, "📅 <b>У вас нет активных записей на мероприятия.</b>", parse_mode='HTML')
        return
    res = "📅 <b>ВАШИ ЗАПИСИ:</b>\n\n"
    for title, date, loc in rows:
        res += f"🌳 <b>{title}</b>\n"
        res += f"⏰ <i>Дата:</i> <code>{date}</code>\n"
        res += f"📍 <i>Место:</i> {loc}\n"
        res += "--------------------------\n"
    bot.send_message(user_id, res, parse_mode='HTML')

@bot.message_handler(commands=['issue_cert'])
def admin_issue_cert(message):
    parts = message.text.split()
# 1. Сначала проверяем, есть ли вообще аргументы после команды
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ **Ошибка:** Вы не ввели ID.\nИспользуйте: `/issue_cert 12345678`", parse_mode='Markdown')
        return
# 2. Проверяем, является ли ID числом
    if not parts[1].isdigit():
        bot.send_message(message.chat.id, "❌ **Ошибка:** ID должен состоять только из цифр.")
        return
# 3. Проверяем права администратора
    if get_user_status(message.chat.id) != 'admin':
        bot.send_message(message.chat.id, "У вас нет прав администратора.")
        return
    try:
        target_user_id = int(parts[1]) 
        details = get_user_details(target_user_id)
        if details:
            username, region, city, role, status, hours, full_name, age = details
            if hours < 150:
                bot.send_message(message.chat.id, "У пользователя недостаточно часов.")
                return
            pdf = generate_certificate(target_user_id, details[6], details[5], details[1], details[2])
            sent_msg = bot.send_document(message.chat.id, pdf, visible_file_name=f"Cert_{target_user_id}.pdf")
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Отправить пользователю", callback_data=f"send_cert_{target_user_id}_{sent_msg.message_id}"),
                types.InlineKeyboardButton("❌ Оставить у себя", callback_data=f"deny_send_cert_{target_user_id}")
            )
            bot.send_message(message.chat.id, "Переслать этот сертификат пользователю?", reply_markup=markup)
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "❌ Неверный формат. Используйте: `/issue_cert ID_пользователя`", parse_mode='Markdown')
        return

# --- Команды для бана/разбана (только для MAIN_ADMIN_ID) ---

@bot.message_handler(commands=['ban'])
def prompt_ban_user(message):
    if message.chat.id != MAIN_ADMIN_ID:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды. 👑")
        return
    
    msg = bot.send_message(message.chat.id, "Введите ID пользователя, которого хотите забанить:")
    bot.register_next_step_handler(msg, process_ban_user)

def process_ban_user(message):
    user_id_to_ban_str = message.text.strip()
    try:
        user_id_to_ban = int(user_id_to_ban_str)
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат ID. Введите числовой ID.")
        return

    if user_id_to_ban == MAIN_ADMIN_ID:
        bot.send_message(message.chat.id, "Невозможно забанить главного администратора!")
        return

    ban_user_in_db(user_id_to_ban)
    bot.send_message(message.chat.id, f"✅ Пользователь ID {user_id_to_ban} забанен.")
    try:
        bot.send_message(user_id_to_ban, "🚨 Вы были забанены администратором и больше не можете пользоваться ботом.")
    except Exception as e:
        print(f"Не удалось уведомить забаненного пользователя: {e}")


@bot.message_handler(commands=['unban'])
def prompt_unban_user(message):
    if message.chat.id != MAIN_ADMIN_ID:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды. 👑")
        return
    
    msg = bot.send_message(message.chat.id, "Введите ID пользователя, которого хотите разбанить:")
    bot.register_next_step_handler(msg, process_unban_user)

def process_unban_user(message):
    user_id_to_unban_str = message.text.strip()
    try:
        user_id_to_unban = int(user_id_to_unban_str)
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат ID. Введите числовой ID.")
        return
        
    unban_user_in_db(user_id_to_unban)
    bot.send_message(message.chat.id, f"✅ Пользователь ID {user_id_to_unban} разбанен.")
    try:
        bot.send_message(user_id_to_unban, "✅ С вас снят бан, вы снова можете пользоваться ботом.")
    except Exception as e:
        print(f"Не удалось уведомить разбаненного пользователя: {e}")

# --- Команда просмотра статистики ---

@bot.message_handler(commands=['stats'])
def display_stats(message):
    user_id = message.chat.id
    if get_user_status(user_id) not in ['admin', 'Ответственное лицо']:
         bot.send_message(user_id, "У вас нет прав для просмотра статистики.")
         return

    users_count, admins_count, content_count, events_count, hours_count = get_stats_from_db()
    
    response = (
        f"📊 **Статистика бота:**\n\n"
        f"👤 Всего пользователей: **{users_count}**\n"
        f"👑 Администраторов: **{admins_count}**\n"
        f"📝 Всего постов: **{content_count}**\n"
        f"🌳 Всего мероприятий: **{events_count}**\n"
        f"🌐 Всего волонтерских часов: **{hours_count}**\n"
    )
    bot.send_message(user_id, response, parse_mode='Markdown')

# --- Команда просмотра нарушений лимита (только для MAIN_ADMIN_ID) ---

@bot.message_handler(commands=['view_violations'])
def display_violations_report(message):
    if message.chat.id != MAIN_ADMIN_ID:
        bot.send_message(message.chat.id, "У вас нет прав для просмотра этого отчета. 👑")
        return
        
    today = datetime.date.today()
    target_month_year = today.strftime('%Y-%m')
    violations = get_monthly_violations_report_current(target_month_year)
    if not violations:
        bot.send_message(MAIN_ADMIN_ID, f"Отчет о нарушениях за {target_month_year}: нарушений пока не зафиксировано.")
        return
    report_text = f"<b>🚨 ОТЧЕТ О НАРУШЕНИЯХ ЗА ТЕКУЩИЙ МЕСЯЦ ({target_month_year}) 🚨</b>\n\n"
    current_admin = None
    for admin_id, violation_date in violations:
        if admin_id != current_admin:
             if current_admin is not None:
                  report_text += "\n"
             user_details = get_user_details(admin_id)
             username = user_details[0] if user_details else f"ID: {admin_id}"
             report_text += f"👤 Админ: @{username} (ID: {admin_id})\n"
             current_admin = admin_id
        report_text += f"— Нарушение: {violation_date}\n"
    bot.send_message(MAIN_ADMIN_ID, report_text, parse_mode='HTML')

# Шаг 1: Получение региона
def process_region_text_input(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    user_input = message.text.strip().lower()
    if message.text == '/cancel':
        cancel_process(message)
        return
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название региона или первую букву текстом.")
        bot.register_next_step_handler(msg, process_region_text_input)
        return

    # 1. Поиск точного совпадения или совпадения по началу строки
    suggestions = [region for region in RUSSIAN_SUBJECTS if region.lower() == user_input or region.lower().startswith(user_input)]
    if suggestions:
        if len(suggestions) == 1:
            finalize_region_selection(user_id, suggestions[0], None)
        else:
            markup = types.InlineKeyboardMarkup()
            for region in suggestions:
                region_index = RUSSIAN_SUBJECTS.index(region)
                markup.add(types.InlineKeyboardButton(region, callback_data=f"select_region_{region_index}"))
            bot.send_message(user_id, "Найдено несколько вариантов. Выберите нужный регион кнопкой:", reply_markup=markup)
    else:
        msg = bot.send_message(user_id, "Регион не найден. Пожалуйста, проверьте название или введите другую букву. Чтобы попробовать снова, введите название или /cancel.")
        bot.register_next_step_handler(msg, process_region_text_input)

# --- Новая вспомогательная функция для завершения выбора региона ---
def finalize_region_selection(user_id, region_name, message_id=None):
    bot.clear_step_handler_by_chat_id(user_id)
    if user_id not in bot.user_data: 
        bot.user_data[user_id] = {}
    bot.user_data[user_id]['region'] = region_name
    if message_id:
        try:
            bot.edit_message_text(f"✅ Выбран регион: **{region_name}**", user_id, message_id, parse_mode='Markdown')
        except:
            bot.send_message(user_id, f"✅ Выбран регион: **{region_name}**", parse_mode='Markdown')
    status = get_user_status(user_id)
    if status in ['registering', 'new'] or 'full_name' not in bot.user_data[user_id]:
        msg = bot.send_message(user_id, "Спасибо. Теперь введите название вашего **города или населенного пункта**:")
        bot.register_next_step_handler(msg, process_city_step)
    else:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET region = ? WHERE user_id = ?', (region_name, user_id))
            conn.commit()
        bot.send_message(user_id, f"✅ Ваш регион успешно изменен на: {region_name}", reply_markup=user_keyboard)

# ШАГ 2: После города спрашиваем ФИО
def process_city_step(message):
    user_id = message.chat.id 
    if len(message.text) < 2 or any(char.isdigit() for char in message.text):
        msg = bot.send_message(user_id, "❌ Название города не может быть таким коротким или содержать цифры. Введите еще раз:")
        bot.register_next_step_handler(msg, process_city_step) 
        return
    if is_interrupted(message): return
    user_id = message.chat.id
    bot.user_data[user_id]['city'] = message.text
    msg = bot.send_message(user_id, "Введите ваше **ФИО** (полностью):", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_fullname_step)

# ШАГ 3: После ФИО спрашиваем возраст
def process_fullname_step(message):
    if is_interrupted(message): return
    user_id = message.chat.id
# 1. Проверка на дурака (тип данных)
    if message.content_type != 'text':
        msg = bot.send_message(user_id, "⚠️ Ошибка! Введите ФИО буквами:")
        bot.register_next_step_handler(msg, process_fullname_step)
        return
    full_name = message.text.strip()
# 2. Проверка на наличие ссылок (анти-реклама)
    if "http" in full_name.lower() or "t.me" in full_name.lower():
        msg = bot.send_message(user_id, "❌ В ФИО нельзя вставлять ссылки. Введите настоящее имя:")
        bot.register_next_step_handler(msg, process_fullname_step)
        return
# 3. Проверка на слишком короткое или длинное ФИО
    if len(full_name) < 5 or len(full_name) > 100:
        msg = bot.send_message(user_id, "❌ ФИО должно быть длиннее 5 и короче 100 символов. Попробуйте еще раз:")
        bot.register_next_step_handler(msg, process_fullname_step)
        return
# 4. Проверка на спецсимволы 
    import re
    if not re.match(r'^[а-яА-ЯёЁa-zA-Z\s-]+$', full_name):
        msg = bot.send_message(user_id, "❌ Используйте только буквы. Цифры и спецсимволы в ФИО запрещены:")
        bot.register_next_step_handler(msg, process_fullname_step)
        return
    bot.user_data[user_id]['full_name'] = full_name.title()
    msg = bot.send_message(user_id, "Введите ваш <b>возраст</b> (только цифры):", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_age_step)

# ШАГ 4: После возраста спрашиваем роль
def process_age_step(message):
    if is_interrupted(message): return
    user_id = message.chat.id
    try:
        age = int(message.text)
        if not (7 <= age <= 100): raise ValueError
    except ValueError:
        msg = bot.send_message(user_id, "Введите корректный возраст цифрами (от 7 до 100):")
        bot.register_next_step_handler(msg, process_age_step)
        return
    bot.user_data[user_id]['age'] = age
    msg = bot.send_message(user_id, "Выберите вашу **должность** кнопками:", reply_markup=role_keyboard, parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_role_step)

# ШАГ 5: Финал
def process_role_step(message):
    if is_interrupted(message): return
    user_id = message.chat.id
    role = message.text
    if role not in ['Ученик (волонтер)', 'Куратор', 'Ответственное лицо']:
        msg = bot.send_message(user_id, "❌ Пожалуйста, используйте кнопки для выбора роли:", reply_markup=role_keyboard)
        bot.register_next_step_handler(msg, process_role_step)
        return
    user_data = bot.user_data.get(user_id)
    if not user_data:
        bot.send_message(user_id, "❌ Ошибка сессии. Начните регистрацию заново: /start")
        return
    if role == 'Ответственное лицо':
        username = f"@{message.from_user.username}" if message.from_user.username else "нет"
        msg_to_admin = (
            f"👑 **НОВАЯ ЗАЯВКА: ОТВЕТСТВЕННОЕ ЛИЦО**\n\n"
            f"👤 **ФИО:** {user_data.get('full_name')}\n"
            f"🆔 **ID:** <code>{user_id}</code>\n"
            f"🔗 **Юзернейм:** {username}\n"
            f"📍 **Регион:** {user_data.get('region')}\n"
            f"🏙 **Город:** {user_data.get('city')}"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("Разрешить ✅", callback_data=f"grant_resp_{user_id}"),
            types.InlineKeyboardButton("Отказать ❌", callback_data=f"deny_resp_{user_id}")
        )
        bot.send_message(MAIN_ADMIN_ID, msg_to_admin, reply_markup=markup, parse_mode='HTML')
        bot.send_message(user_id, "✅ Ваша регистрация завершена. Разрешение на должность 'Ответственное лицо' отправлено главному администратору. Ожидайте уведомления.", reply_markup=user_keyboard)
        # Сохраняем в БД со статусом ожидания (pending_role)
        update_registration_data_fixed(
            user_id, user_data['region'], user_data['city'], 
            role, user_data['full_name'], user_data['age'], 'pending_role'
        )
    else:
        # Для Волонтера и Куратора
        update_registration_data_fixed(
            user_id, user_data['region'], user_data['city'], 
            role, user_data['full_name'], user_data['age'], 'user'
        )
        bot.send_message(user_id, "🎉 Регистрация завершена! Вы в системе.", reply_markup=user_keyboard)
    # Очистка временных данных
    bot.user_data.pop(user_id, None)

@bot.message_handler(func=lambda message: 
    message.content_type == 'text' and 
    not message.text.startswith('/') and 
    not is_user_registered(message.chat.id) and 
    get_user_status(message.chat.id) != 'registering' 
)
def enforce_registration(message):
    bot.send_message(message.chat.id, "Пожалуйста, сначала завершите регистрацию, отправив команду /start.")

@bot.message_handler(commands=['request_admin'])
def request_admin_access(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    if status == 'user' or status == 'new':
        update_user_status(user_id, 'pending')
        bot.send_message(user_id, "Заявка на получение прав администратора отправлена на рассмотрение. ⏳")
        username = message.from_user.username or f"ID: {user_id}"
        notification_text = f"Новая заявка на администрирование от @{username} (ID: {user_id})."
        markup = types.InlineKeyboardMarkup()
        btn_approve = types.InlineKeyboardButton("Одобрить ✅", callback_data=f"approve_{user_id}")
        btn_reject = types.InlineKeyboardButton("Отклонить ❌", callback_data=f"reject_{user_id}")
        markup.add(btn_approve, btn_reject)
        if MAIN_ADMIN_ID:
            bot.send_message(MAIN_ADMIN_ID, notification_text, reply_markup=markup)
    elif status == 'pending':
        bot.send_message(user_id, "Ваша заявка уже находится на рассмотрении. 👀")
    elif status == 'admin':
        bot.send_message(user_id, "У вас уже есть права администратора. ✅")

@bot.message_handler(commands=['view_content'])
def view_content(message):
    user_id = message.chat.id
    show_content_page(user_id, page=0)

def show_content_page(user_id, page=0):
    content_list = get_all_content_for_user(user_id)
    if not content_list:
        bot.send_message(user_id, "Записей пока нет.")
        return
    total_pages = len(content_list)
    if page >= total_pages or page < 0: page = 0
    
    content = content_list[page]
    text, region, scope, content_id = content
    scope_info = f"[{region}]" if scope == 'region' else "[Global 🌍]"
    
    response_text = f"<b>Запись {page + 1} из {total_pages}</b>\n\n{text}\n\n<code>{scope_info}</code>"
    
    markup = types.InlineKeyboardMarkup()
    nav_btns = []
    if page > 0:
        nav_btns.append(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"content_page_{page-1}"))
    if page < total_pages - 1:
        nav_btns.append(types.InlineKeyboardButton("Вперед ➡️", callback_data=f"content_page_{page+1}"))
    
    if nav_btns: markup.row(*nav_btns)
    markup.add(types.InlineKeyboardButton("🚨 Пожаловаться", callback_data=f"report_content_{content_id}"))
    try:
        bot.send_message(user_id, response_text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        pass

@bot.message_handler(commands=['export_stats'])
def prompt_export_choice(message):
    """Меню выбора типа отчета для главного администратора."""
    if message.chat.id != MAIN_ADMIN_ID:
        bot.send_message(message.chat.id, "У вас нет прав для экспорта данных. 👑")
        return
    
    # Создаем объект клавиатуры перед использованием
    markup = types.InlineKeyboardMarkup()
    
    # Добавляем кнопки выбора таблиц
    markup.add(types.InlineKeyboardButton("👥 Таблица волонтеров", callback_data="export_table_users"))
    markup.add(types.InlineKeyboardButton("📝 Таблица постов", callback_data="export_table_content"))
    markup.add(types.InlineKeyboardButton("🌳 Таблица мероприятий", callback_data="export_table_events"))
    markup.add(types.InlineKeyboardButton("🚨 Нарушения админов", callback_data="export_table_violations"))
    markup.add(types.InlineKeyboardButton("⏱ Текущие лимиты", callback_data="export_table_limits"))
    
    bot.send_message(
        message.chat.id, 
        "📊 **Выберите таблицу для экспорта в Excel:**", 
        reply_markup=markup, 
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('export_table_'))
def handle_excel_export_callback(call):
    admin_id = call.message.chat.id
    if admin_id != MAIN_ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для экспорта всей базы данных.", show_alert=True)
        return
    table_type = call.data.split('_')[-1]
    bot.answer_callback_query(call.id, "Генерирую Excel... ⏳")
    queries = {
        'users': {
            'sql': "SELECT user_id as 'ID', full_name as 'ФИО', age as 'Возраст', region as 'Регион', city as 'Город', hours as 'Часы', role as 'Роль' FROM users",
            'sheet': "Волонтеры", 'filename': "Volunteers.xlsx"
        },
        'content': {
            'sql': "SELECT id as 'ID', text as 'Текст', author_id as 'Автор ID', scope as 'Охват' FROM content",
            'sheet': "Посты", 'filename': "Content.xlsx"
        },
        'events': {
            'sql': "SELECT id as 'ID', title as 'Название', event_date as 'Дата', location as 'Место' FROM events",
            'sheet': "Мероприятия", 'filename': "Events.xlsx"
        },
        'limits': {
            'sql': "SELECT admin_id as 'ID Админа', date as 'Дата', hours_awarded as 'Выдано часов' FROM admin_limits",
            'sheet': "Дневные лимиты", 'filename': "Admin_Limits.xlsx"
        },
        'violations': {
            'sql': "SELECT admin_id as 'ID Админа', violation_date as 'Дата', month_year as 'Месяц' FROM admin_violations",
            'sheet': "Нарушения", 'filename': "Violations_Report.xlsx"
        }
    }
    config = queries.get(table_type)
    if not config: return
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(config['sql'], conn)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=config['sheet'])
            worksheet = writer.sheets[config['sheet']]
            for i, col in enumerate(df.columns, 1):
                column_letter = get_column_letter(i)
                max_str_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[column_letter].width = max_str_len
        output.seek(0)
        bot.send_document(admin_id, (config['filename'], output.getvalue()), caption=f"✅ Отчет [{config['sheet']}] готов.")
        safe_delete_message(admin_id, call.message.message_id)
    except Exception as e:
        bot.send_message(admin_id, f"❌ Ошибка экспорта: {e}")

@bot.message_handler(commands=['add_content'])
def prompt_add_content(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    
    if status == 'admin':
        bot.clear_step_handler_by_chat_id(user_id) 
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('Опубликовать для всех 🌍', 'Опубликовать только для моего региона 🏠')
        msg = bot.send_message(user_id, "Выберите область видимости, затем отправьте текст:", reply_markup=markup, parse_mode='Markdown')
        if user_id not in bot.user_data:
            bot.user_data[user_id] = {}
        bot.user_data[user_id]['adding_content'] = True
        bot.register_next_step_handler(msg, process_content_scope_step)
    else:
        bot.send_message(user_id, "У вас нет прав для добавления контента. 🚫")

# --- Команды для работы с мероприятиями ---
def process_content_scope_step(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    if message.text == '/cancel' or message.text == '❌ Отмена':
        cancel_process(message)
        return
    scope_choice_text = message.text.lower()
    if 'для всех' in scope_choice_text:
        scope = 'all'
    elif 'моего региона' in scope_choice_text:
        scope = 'region'
    else:
        msg = bot.send_message(user_id, "Пожалуйста, используйте кнопки для выбора или нажмите ❌ Отмена.")
        bot.register_next_step_handler(msg, process_content_scope_step) 
        return
    bot.user_data[user_id]['scope'] = scope
    msg = bot.send_message(user_id, "Отправьте текст контента:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_content_step)

def get_event_by_code(code):
    """Получает детали мероприятия по коду регистрации."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, title FROM events WHERE check_in_code = ?', (code,))
        result = cursor.fetchone()
    return result

def has_user_checked_in(user_id, event_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM event_registrations WHERE user_id = ? AND event_id = ? AND is_attended = 1', (user_id, event_id))
        return cursor.fetchone() is not None
    
def process_checkin_code(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message) 
        return
    if user_id not in bot.user_data or not bot.user_data[user_id].get('awaiting_checkin_code'): 
        return
    code = message.text.strip().upper()
    event_data = get_event_by_code(code)
    if not event_data:
        bot.send_message(user_id, "❌ Неверный код. Попробуйте еще раз или введите /cancel.")
        bot.register_next_step_handler(message, process_checkin_code)
        return
    event_id, event_title = event_data
    if has_user_checked_in(user_id, event_id):
        bot.send_message(user_id, f"❌ Вы уже получили часы за мероприятие «{event_title}».")
        if user_id in bot.user_data: del bot.user_data[user_id]
        return
    if not is_user_registered_for_event(user_id, event_id):
        bot.send_message(user_id, "❌ Вы не можете получить часы, так как не были записаны на это мероприятие через меню!")
        return
    if not is_user_registered_for_event(user_id, event_id):
        bot.send_message(user_id, f"❌ Вы не были записаны на «{event_title}». Сначала запишитесь через /view_events.")
        if user_id in bot.user_data: del bot.user_data[user_id]
        return
    POINTS_FOR_CHECKIN = 3
    add_hours(user_id, POINTS_FOR_CHECKIN) 
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE event_registrations SET is_attended = 1 WHERE user_id = ? AND event_id = ?', (user_id, event_id))
        conn.commit()
    bot.send_message(user_id, f"🎉 Успешно! Вам начислено **{POINTS_FOR_CHECKIN} часов**.", parse_mode='Markdown')
    if user_id in bot.user_data:
        bot.user_data[user_id].pop('awaiting_checkin_code', None)
    code = message.text.strip().upper()
    clean_code = code.replace('CHECKIN_', '').replace('SHORT_', '')
    process_qr_checkin(user_id, clean_code, hours=3)
used_special_codes = set() 

def process_special_checkin(user_id, special_code):
    if not is_user_registered(user_id):
        bot.send_message(user_id, "❌ Сначала завершите регистрацию через /start.")
        return
    if special_code in used_special_codes:
        bot.send_message(user_id, "❌ Этот код уже был использован ранее!")
        return
    POINTS_FOR_SPECIAL = 2
    add_hours(user_id, POINTS_FOR_SPECIAL)
    used_special_codes.add(special_code)
    bot.send_message(user_id, f"🎉 Часы начислены автоматически через QR-код! Вам добавлено {POINTS_FOR_SPECIAL} часов.")

def add_content_report(content_id, reporter_user_id, report_text):
    """Регистрирует новую жалобу на контент и возвращает ID отчета."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO content_reports (content_id, reporter_user_id, report_text) 
            VALUES (?, ?, ?)
        ''', (content_id, reporter_user_id, report_text))
        conn.commit()
        return cursor.lastrowid 

def process_event_title(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id) 
    if user_id not in bot.user_data or not bot.user_data[user_id].get('creating_event'): return
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название текстом.")
        bot.register_next_step_handler(msg, process_event_title)
        return
    bot.user_data[user_id]['title'] = message.text
    msg = bot.send_message(user_id, "Введите **описание** мероприятия:")
    bot.register_next_step_handler(msg, process_event_description)

def setup_scheduler():
    # 1. Сброс лимитов каждый день ровно в полночь
    scheduler.add_job(clear_old_admin_limits, 'cron', hour=0, minute=0)
    # 2. Ежемесячный отчет о нарушениях (1-е число месяца, 00:01)
    scheduler.add_job(send_monthly_violation_report, 'cron', day=1, hour=0, minute=1)
    scheduler.add_job(weekly_backup, 'cron', day_of_week='sun', hour=23, minute=0)
    scheduler.add_job(clear_temporary_memory, 'cron', hour=4, minute=0)
    scheduler.add_job(optimize_db_size, 'cron', day=1, hour=5, minute=0) 
    scheduler.add_job(check_registration_leftovers, 'interval', hours=6)
    scheduler.add_job(clear_old_report_cooldowns, 'interval', minutes=30)
    scheduler.add_job(ping_monitor, 'interval', hours=4)
    scheduler.add_job(send_event_reminders, 'interval', minutes=30)
    if not scheduler.running:
        scheduler.start()

def send_event_reminders():
    """ Напоминание пользователям за 24 часа до начала мероприятия. Оптимизировано для бесплатного тарифа PythonAnywhere."""
    now_moscow = datetime.datetime.now(timezone_spb)
    threshold = now_moscow + datetime.timedelta(days=1)
    now_str = now_moscow.strftime('%Y-%m-%d %H:%M')
    threshold_str = threshold.strftime('%Y-%m-%d %H:%M')
    print(f"[{datetime.datetime.now()}] Запуск рассылки напоминаний...")
    print(f"Ищем события между {now_str} и {threshold_str}")
    with get_db_connection() as conn:
        cursor = conn.cursor()
    # 1. Находим все мероприятия, которые начнутся в ближайшие 24 часа
        cursor.execute('''
            SELECT id, title, event_date, location FROM events 
            WHERE event_date >= ? AND event_date <= ?
        ''', (now_str, threshold_str))
        events_tomorrow = cursor.fetchall()
        if not events_tomorrow:
            print("Событий на ближайшие 24 часа не найдено.")
            return
        for event_id, title, event_date, location in events_tomorrow:
    # 2. Находим всех зарегистрированных пользователей на это событие
            cursor.execute('SELECT user_id FROM event_registrations WHERE event_id = ?', (event_id,))
            registrations = cursor.fetchall()
            for user_id_tuple in registrations:
                user_id = user_id_tuple[0] 
                try:
                    reminder_text = (
                        f"⏰ **ЭКО-НАПОМИНАНИЕ**\n\n"
                        f"Завтра состоится мероприятие, на которое вы записаны:\n"
                        f"🌳 «<b>{title}</b>»\n\n"
                        f"📅 <b>Время:</b> {event_date}\n"
                        f"📍 <b>Место:</b> {location}\n\n"
                        f"Приходите вовремя, мы вас ждем! 🙌"
                    )
                    bot.send_message(user_id, reminder_text, parse_mode='HTML')
                    time.sleep(0.1) 
                except telebot.apihelper.ApiTelegramException as e:
                    if e.error_code == 403:
                        print(f"Пользователь {user_id} заблокировал бота. Напоминание не отправлено.")
                    else:
                        print(f"Ошибка API при отправке {user_id}: {e}")
                except Exception as e:
                    print(f"Непредвиденная ошибка при напоминании {user_id}: {e}")
    print(f"[{datetime.datetime.now()}] Рассылка напоминаний завершена.")

@bot.message_handler(commands=['create_event'])
def prompt_create_event(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    
    if status != 'admin':
        bot.send_message(user_id, "У вас нет прав администратора.")
        return

    region = get_user_region(user_id)
    if not region:
        bot.send_message(user_id, "Сначала укажите ваш регион в профиле.")
        return
    
    bot.clear_step_handler_by_chat_id(user_id)
    if user_id not in bot.user_data:
        bot.user_data[user_id] = {}
    
    bot.user_data[user_id].update({
        'creating_event': True, 
        'region': region
    })
    
    msg = bot.send_message(user_id, f"📍 Создаем мероприятие для региона: **{region}**\n\nВведите **название**:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_event_title)

def process_event_description(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    if user_id not in bot.user_data: return
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное описание текстом.")
        bot.register_next_step_handler(msg, process_event_description)
        return
        
    bot.user_data[user_id]['description'] = message.text
    msg = bot.send_message(user_id, "Введите **дату и время** мероприятия (например, '25.12 в 14:00'):")
    bot.register_next_step_handler(msg, process_event_date)

def get_pending_reports():
    """Получает список ожидающих рассмотрения жалоб."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT CR.report_id, CR.content_id, CR.report_text, CR.reporter_user_id, C.author_id 
            FROM content_reports AS CR
            JOIN content AS C ON CR.content_id = C.id
            WHERE CR.status = 'pending'
            ORDER BY CR.reported_at ASC
        ''')
        results = cursor.fetchall()
    return results

def update_report_status(report_id, status):
    """Обновляет статус жалобы (resolved/dismissed)."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE content_reports SET status = ? WHERE report_id = ?', (status, report_id))
        conn.commit()

def delete_content_and_reports(content_id):
    """Исправленная функция удаления: убирает пост и все жалобы на него."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM content_reports WHERE content_id = ?', (content_id,))
        cursor.execute('DELETE FROM content WHERE id = ?', (content_id,))
        conn.commit()
def delete_content_item(content_id):
    delete_content_and_reports(content_id)

def process_report_reason(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id) 

    if user_id not in bot.user_data or 'reporting_content_id' not in bot.user_data[user_id]:
        bot.send_message(user_id, "Произошла ошибка при подаче жалобы. Попробуйте снова /view_content.")
        return

    content_id = bot.user_data[user_id]['reporting_content_id']
    report_text = message.text
    reporter_username = message.from_user.username or f"ID: {user_id}"
    report_id = add_content_report(content_id, user_id, report_text)

    bot.send_message(user_id, "✅ Ваша жалоба принята и отправлена на рассмотрение модераторам.")

    if MAIN_ADMIN_ID:
        notification_message = (
            f"<b>🚨 НОВАЯ ЖАЛОБА #{report_id} НА КОНТЕНТ #{content_id} 🚨</b>\n\n"
            f"От пользователя: @{reporter_username}\n"
            f"Причина: {report_text}\n"
        )
        
        markup = types.InlineKeyboardMarkup()
        btn_view = types.InlineKeyboardButton("Посмотреть в панели", callback_data="admin_view_reports")
        markup.add(btn_view)

        try:
            bot.send_message(MAIN_ADMIN_ID, notification_message, parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            print(f"Ошибка при отправке уведомления админу {MAIN_ADMIN_ID}: {e}")
    del bot.user_data[user_id]

def process_event_date(message):
    if is_interrupted(message): return 
    user_id = message.chat.id
    user_input = message.text
    validated_dt = parse_strict_date(user_input)
    if validated_dt is None:
        msg = bot.send_message(
            user_id, 
            "⚠️ **Ошибка формата!**\n\n"
            "Введите дату строго по образцу:\n"
            "`ДД.ММ.ГГ ЧЧ:ММ` (например: `15.05.26 10:30`)",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_event_date)
        return
    bot.user_data[user_id]['date'] = validated_dt.strftime('%Y-%m-%d %H:%M')
    msg = bot.send_message(user_id, f"✅ Дата принята ({validated_dt.strftime('%d.%m.%y %H:%M')}). Введите **место проведения**:")
    bot.register_next_step_handler(msg, process_event_location)

def generate_unique_check_in_code(length=6):
    """Генерирует уникальный код, которого еще нет в базе данных."""
    characters = string.ascii_uppercase + string.digits
    with get_db_connection() as conn:
        cursor = conn.cursor()
        while True:
            code = ''.join(random.choice(characters) for _ in range(length))
            cursor.execute('SELECT 1 FROM events WHERE check_in_code = ?', (code,))
            if not cursor.fetchone():
                return code

def process_event_location(message):
    # 1. Проверка на прерывание командой 
    if is_command_and_cancel_process(message): 
        return
    user_id = message.chat.id
    # 2. Проверка на текстовый ввод 
    if message.content_type != 'text':
        msg = bot.send_message(user_id, "⚠️ Ошибка! Введите адрес проведения текстом:")
        bot.register_next_step_handler(msg, process_event_location)
        return
    # 3. Проверка на /cancel 
    if message.text == '/cancel':
        cancel_process(message)
        return
    # 4. Проверка существования сессии в памяти
    if user_id not in bot.user_data or 'title' not in bot.user_data[user_id]:
        bot.send_message(user_id, "❌ Сессия истекла или данные утеряны. Начните заново: /create_event")
        return
    user_data = bot.user_data[user_id]
    location = message.text.strip()
    # 5. Генерация уникального кода для 3 часов 
    code_3h = generate_unique_check_in_code()
    try:
        create_event(
            title=user_data['title'],
            description=user_data['description'],
            region=user_data['region'],
            event_date=user_data['date'],
            location=location,
            creator_id=user_id,
            check_in_code=code_3h  
        )
        bot_username = bot.get_me().username
        # Ссылки для QR-кодов 
        link_3h = f"https://t.me/{bot_username}?start=checkin_{code_3h}"
        link_2h = f"https://t.me/{bot_username}?start=short_{code_3h}"
        # 6. Отправка первого QR-кода (3 часа)
        send_qr_from_memory(
            user_id, 
            link_3h, 
            f"✅ **Мероприятие создано!**\n\n"
            f"📸 QR-код на **3 ЧАСА**\n"
            f"Для волонтеров, отработавших полную смену."
        )
        # 7. Отправка второго QR-кода (2 часа)
        send_qr_from_memory(
            user_id, 
            link_2h, 
            f"⚠️ QR-код на **2 ЧАСА**\n"
            f"Для волонтеров, ушедших раньше."
        )
    except Exception as e:
        bot.send_message(user_id, f"❌ Произошла ошибка при сохранении: {e}")
        print(f"Error in process_event_location: {e}")
    # 8. Очистка временных данных сессии
    keys_to_remove = ['creating_event', 'title', 'description', 'date', 'region']
    for key in keys_to_remove:
        bot.user_data[user_id].pop(key, None)

# --- Вспомогательная функция для генерации и отправки QR из памяти ---
def send_qr_from_memory(chat_id, qr_data, caption):
    """Генерирует QR и отправляет его без сохранения на диск."""
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        bio.name = 'event_qr.png'
        img.save(bio, 'PNG')
        bio.seek(0)
        bot.send_photo(chat_id, bio, caption=caption, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка генерации QR: {e}")
        bot.send_message(chat_id, f"{caption}\n\n(Ошибка генерации изображения, используйте ссылку выше)")

@bot.message_handler(commands=['view_events'])
def prompt_view_events_choice(message):
    user_id = message.chat.id
    region = get_user_region(user_id)
    if not region:
        bot.send_message(user_id, "Чтобы просматривать мероприятия, пожалуйста, укажите свой регион в /start или /change.")
        return
    try:
        region_index = RUSSIAN_SUBJECTS.index(region)
    except ValueError:
        bot.send_message(user_id, "Ошибка региона. Пожалуйста, укажите регион в /change.")
        return
    markup = types.InlineKeyboardMarkup()
    btn_new = types.InlineKeyboardButton("Актуальные (Новые) 🌳", callback_data=f"view_events_new_{region_index}")
    btn_old = types.InlineKeyboardButton("Прошедшие (Старые) ⏳", callback_data=f"view_events_old_{region_index}")
    markup.add(btn_new, btn_old)
    bot.send_message(user_id, f"В регионе {region}. Какие мероприятия показать?", reply_markup=markup)

def display_events_list(message, region, view_mode):
    user_id = message.chat.id
    clean_region = region.replace("_", " ")
    events = get_events_for_region(clean_region, view_mode)
    if not events:
        bot.send_message(user_id, f"В регионе {clean_region} пока нет мероприятий ({view_mode}).")
        return
    for ev_id, title, desc, date, loc in events:
        markup = types.InlineKeyboardMarkup()
        # Кнопка регистрации
        markup.add(types.InlineKeyboardButton("📝 Записаться", callback_data=f"register_event_{ev_id}"))
        text = f"🌳 **{title}**\n\n{desc}\n\n📍 {loc}\n📅 {date}"
        bot.send_message(user_id, text, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "request_cert_admin")
def request_cert(call):
    user_id = call.message.chat.id
    region = get_user_region(user_id)
    responsible_persons = get_responsible_persons_in_region(region)
    if responsible_persons:
        for responsible_person_id, _ in responsible_persons:
            bot.send_message(responsible_person_id, f"🚨 **Запрос сертификата!**\nПользователь ID: `{user_id}` набрал {get_user_hours(user_id)}ч.\nДля выдачи введите: `/issue_cert {user_id}`", parse_mode='Markdown')
        bot.answer_callback_query(call.id, "Запрос отправлен кураторам вашего региона.", show_alert=True)
    else:
        bot.send_message(user_id, "В вашем регионе пока нет кураторов. Обратитесь в поддержку.")

def graceful_shutdown(signum, frame):
    """Функция, которая вызывается при остановке сервера."""
    print(f"\n[{datetime.datetime.now()}] ⚠️ Получен сигнал остановки ({signum}). Завершаю работу...")
    try:
        # 1. Останавливаем планировщик, чтобы он не запускал новые задачи
        if scheduler.running:
            scheduler.shutdown(wait=False)
            print("✅ Планировщик остановлен.")
        # 2. Сохраняем критические данные 
        print("✅ Данные сессий защищены.")
        # 3. Закрываем соединения с БД 
        print("👋 Бот успешно выключен. До встречи в 2026!")
    except Exception as e:
        print(f"❌ Ошибка при завершении: {e}")
    finally:
        sys.exit(0)
# Регистрируем обработчики сигналов
signal.signal(signal.SIGTERM, graceful_shutdown) 
signal.signal(signal.SIGINT, graceful_shutdown)  

def get_greeting():
    """Возвращает приветствие в зависимости от времени суток (МСК)."""
    tz_moscow = pytz.timezone('Europe/Moscow')
    now = datetime.datetime.now(tz_moscow)
    hour = now.hour
    if 5 <= hour < 12:
        return "Доброе утро 🌅"
    elif 12 <= hour < 18:
        return "Добрый день ☀️"
    elif 18 <= hour < 23:
        return "Добрый вечер 🌙"
    else:
        return "Доброй ночи 🌌"

def choose_input_method_step(message):
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    if user_id not in bot.user_data or not bot.user_data[user_id].get('awaiting_hours_method'): return

    if 'id' in message.text.lower():
        method = 'id'
        prompt_text = "Вы выбрали ввод по ID. Введите ID пользователя и часы (пример: `123456789 50`):"
    elif 'username' in message.text.lower():
        method = 'username'
        prompt_text = "Вы выбрали ввод по Username. Введите Username и часы (пример: `@username 50`):"
    else:
        msg = bot.send_message(user_id, "Неверный выбор. Пожалуйста, используйте кнопки.")
        bot.register_next_step_handler(msg, choose_input_method_step)
        return

    bot.user_data[user_id]['method'] = method
    msg = bot.send_message(user_id, prompt_text, reply_markup=types.ReplyKeyboardRemove(), parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_award_hoursts)

def check_for_spam(text):
    """Простая проверка на спам или неприемлемый контент."""
    forbidden_words = ['мат', 'спам', 'реклама', 'продам'] 
    if any(word in text.lower() for word in forbidden_words):
        return True
    return False

def process_content_step(message):
    if is_interrupted(message): return
    user_id = message.chat.id
    if user_id not in bot.user_data or 'scope' not in bot.user_data[user_id]:
        bot.send_message(user_id, "Данные утеряны. Начните заново: /add_content")
        del bot.user_data[user_id]
        return
    content_text = message.text
    if content_text is None:
        msg = bot.send_message(user_id, "Пожалуйста, отправьте текстовое сообщение:")
        bot.register_next_step_handler(msg, process_content_step)
        return 
    if len(content_text) > 2500: 
        msg = bot.send_message(user_id, "❌ Текст поста слишком длинный (максимум 2500 символов). Введите еще раз:")
        bot.register_next_step_handler(msg, process_content_step)
        return
    if check_for_spam(content_text):
        bot.send_message(user_id, "❌ Ваш пост отклонен автоматическим фильтром контента (спам/запрещенные слова).")
        if user_id in bot.user_data: del bot.user_data[user_id]
        return
    if len(message.text) < 10:
        msg = bot.send_message(user_id, "❌ Текст поста слишком короткий (минимум 10 символов). Введите еще раз:")
        bot.register_next_step_handler(msg, process_content_step)
        return
    if message.content_type != 'text':
        msg = bot.send_message(message.chat.id, "⚠️ Ошибка! Введите текст (буквами):")
        bot.register_next_step_handler(msg, process_fullname_step)
        return
    author_id = message.chat.id
    scope = bot.user_data[author_id]['scope']
    region = get_user_region(author_id) if scope == 'region' else None
    add_content(content_text, author_id, scope, region)
    bot.send_message(author_id, "Контент успешно добавлен и теперь доступен пользователям. ✅")
    if user_id in bot.user_data:
        del bot.user_data[user_id]

# --- 4. Обработчики команд администратора ---
@bot.message_handler(commands=['admin_panel'])
def admin_panel(message):
    user_id = message.chat.id
    status = get_user_status(user_id)

    if status == 'admin':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        
        btn_commands = types.KeyboardButton('📜 Все команды') 
        btn_cancel_admin = types.KeyboardButton('❌ Отмена')
        btn_requests = types.KeyboardButton('Посмотреть заявки на админа 👀')
        btn_list_admins = types.KeyboardButton('Список администраторов 👥')
        btn_add_content = types.KeyboardButton('Добавить контент ✍️')
        btn_send_notification = types.KeyboardButton('Отправить оповещение 📣')
        btn_my_content = types.KeyboardButton('Мои посты 📝')

        markup.row(btn_commands, btn_cancel_admin)
        markup.row(btn_requests, btn_list_admins)
        markup.row(btn_add_content, btn_my_content) 
        markup.row(btn_send_notification)
        
        bot.send_message(user_id, "Добро пожаловать в админ-панель:", reply_markup=markup)
    else:
        bot.send_message(user_id, "У вас нет доступа к админ-панели. 🚫")

# 1. Сначала сама функция 
def prompt_send_notification(message):
    user_id = message.chat.id
    if get_user_status(user_id) != 'admin':
        bot.send_message(user_id, "У вас нет прав для рассылки уведомлений. 🚫")
        return
    region = get_user_region(user_id)
    if not region:
        bot.send_message(user_id, "Не удалось определить ваш регион для рассылки. 🏠")
        return
    msg = bot.send_message(user_id, f"📣 Рассылка для региона: **{region}**\n\nВведите текст сообщения или /cancel для отмены:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_send_notification_step, region)

# 2. Обработчик текста рассылки
def process_send_notification_step(message, region):
    if is_interrupted(message): return
    
    notification_text = message.text
    user_ids = get_users_in_region(region)
    sent_count = 0
    blocked_count = 0

    for target_id in user_ids:
        if target_id == message.chat.id: continue
        try:
            bot.send_message(target_id, f"📣 **ОПОВЕЩЕНИЕ ({region})**\n\n{notification_text}", parse_mode='Markdown')
            sent_count += 1
        except Exception:
            blocked_count += 1

    bot.send_message(message.chat.id, f"✅ Отправлено: {sent_count}\n🚫 Заблокировали бота: {blocked_count}")

def is_interrupted(message):
    """
    Проверяет, является ли сообщение командой. Если да, отменяет текущий шаг.
    """
    user_id = message.chat.id
    if message.text and message.text.startswith('/'):
        bot.clear_step_handler_by_chat_id(user_id)
        
        # Если это команда отмены — просто пишем об отмене
        if message.text == '/cancel':
            bot.send_message(user_id, "❌ Действие отменено.")
        else:
            # Если любая другая команда (например /help), предупреждаем, что действие прервано
            bot.send_message(user_id, f"⚠️ Предыдущее действие прервано командой {message.text}")
        
        # Возвращаем пользователя в меню в зависимости от статуса
        status = get_user_status(user_id)
        if status == 'admin':
            admin_panel(message)
        else:
            bot.send_message(user_id, "Воспользуйтесь меню:", reply_markup=user_keyboard)
        return True
    return False

# ТОЧЕЧНЫЕ ОБРАБОТЧИКИ КНОПОК
@bot.message_handler(func=lambda message: message.text == 'Посмотреть заявки на админа 👀' and get_user_status(message.chat.id) == 'admin')
def handle_requests_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    view_pending_requests(message)

@bot.message_handler(func=lambda message: message.text == 'Список администраторов 👥' and get_user_status(message.chat.id) == 'admin')
def handle_admins_list_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    view_admin_list(message)

# Теперь обработчик реагирует и на команду /profile, и на текст кнопки
@bot.message_handler(commands=['profile'])
@bot.message_handler(func=lambda message: message.text == '👤 Профиль')
def handle_profile_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    view_profile(message)

@bot.message_handler(func=lambda message: message.text == '📖 Посты')
def handle_content_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    view_content(message)

@bot.message_handler(func=lambda message: message.text == '🌳 Мероприятия')
def handle_events_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    prompt_view_events_choice(message)

@bot.message_handler(func=lambda message: message.text == '📚 FAQ')
def handle_faq_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    view_faq(message)

@bot.message_handler(func=lambda message: message.text == '📜 Все команды')
def handle_help_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    help(message)

@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def handle_cancel_btn(message):
    cancel_process(message)

@bot.message_handler(func=lambda message: message.text == 'Добавить контент ✍️' and get_user_status(message.chat.id) == 'admin')
def handle_add_content_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    prompt_add_content(message)

@bot.message_handler(func=lambda message: message.text == 'Мои посты 📝' and get_user_status(message.chat.id) == 'admin')
def handle_my_posts_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    handle_my_content_button(message)

@bot.message_handler(func=lambda message: message.text == '🗺 Изменить регион')
def handle_edit_reg_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    edit_region_prompt(message)

@bot.message_handler(func=lambda message: message.text == '🏙 Изменить город')
def handle_edit_city_btn(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    edit_city_prompt(message)

@bot.message_handler(func=lambda message: message.text == 'Отправить оповещение 📣')
def handle_send_notification_button(message):
    user_id = message.chat.id
    if get_user_status(user_id) != 'admin': return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌍 Для всех пользователей", callback_data="notif_all"))
    markup.add(types.InlineKeyboardButton("🏠 Только мой регион", callback_data="notif_region"))
    bot.send_message(user_id, "Выберите охват оповещения:", reply_markup=markup)
@bot.callback_query_handler(func=lambda call: call.data.startswith('notif_'))
def prompt_notif_text(call):
    scope = call.data.split('_')[1] 
    msg = bot.send_message(call.message.chat.id, "Введите текст сообщения для рассылки:")
    bot.register_next_step_handler(msg, process_mass_notification, scope)

@bot.message_handler(func=lambda message: message.text == 'Добавить вопрос в FAQ ❓' and get_user_status(message.chat.id) == 'admin')
def handle_add_faq_button(message):
    prompt_add_faq(message)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('send_cert_', 'deny_send_cert_')))
def handle_cert_send_decision(call):
    admin_id = call.message.chat.id
    parts = call.data.split('_')
    action = parts[0] 
    try:
        if action == 'send':
            target_user_id = int(parts[-2]) 
            doc_msg_id = int(parts[-1]) 
            bot.copy_message(target_user_id, admin_id, doc_msg_id)
            bot.send_message(target_user_id, "🌟 Ваш сертификат подтвержден и отправлен!")
            bot.send_message(admin_id, "✅ Отправлено пользователю.")
        else:
            target_user_id = int(parts[-1])
            bot.send_message(admin_id, f"❌ Отправка пользователю {target_user_id} отклонена.")
        bot.delete_message(admin_id, call.message.message_id)
    except Exception as e:
        bot.send_message(admin_id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['force_backup'])
def manual_backup(message):
    if message.chat.id == MAIN_ADMIN_ID:
        weekly_backup()
        bot.send_message(MAIN_ADMIN_ID, "✅ Бэкап базы данных выполнен вручную.")

@bot.message_handler(func=lambda message: message.text == 'Мои посты 📝')
def handle_my_content_button(message):
    user_id = message.chat.id
    if get_user_status(user_id) != 'admin':
        return
    show_my_content_page(user_id, page=0)

def show_my_content_page(user_id, page=0):
    """Отображение постов, созданных текущим админом (пагинация)."""
    content_list = get_admin_content(user_id) 
    if not content_list:
        bot.send_message(user_id, "Вы еще не опубликовали ни одного поста.")
        return
    total_pages = len(content_list)
    if page >= total_pages: page = 0
    if page < 0: page = total_pages - 1
    content_id, text, scope, region = content_list[page]
    scope_info = f"Регион: {region}" if scope == 'region' else "Для всех 🌍"
    response = (
        f"📝 <b>Ваш пост {page + 1} из {total_pages}</b>\n"
        f"ID: #{content_id}\n"
        f"Видимость: {scope_info}\n"
        f"--------------------------\n\n"
        f"{text}"
    )
    markup = types.InlineKeyboardMarkup()
    nav_btns = []
    if total_pages > 1:
        nav_btns.append(types.InlineKeyboardButton("⬅️", callback_data=f"mycont_p_{page-1}"))
        nav_btns.append(types.InlineKeyboardButton("➡️", callback_data=f"mycont_p_{page+1}"))
    if nav_btns:
        markup.row(*nav_btns)
    markup.add(types.InlineKeyboardButton("Удалить этот пост ❌", callback_data=f"delete_content_{content_id}"))
    
    bot.send_message(user_id, response, reply_markup=markup, parse_mode='HTML')

def view_pending_requests(message):
    requests = get_pending_requests()
    if requests:
        response = "Ожидающие заявки: 👇\n"
        for req in requests:
            user_id, username = req
            response += f"- @{username} (ID: {user_id})\n"
        bot.send_message(message.chat.id, response)
    else:
        bot.send_message(message.chat.id, "Активных заявок нет. ✅")

def get_user_global_rank(user_id):
    """Получает глобальное место пользователя в рейтинге."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT rank FROM (
                SELECT user_id, RANK() OVER (ORDER BY hours DESC) as rank
                FROM users
                WHERE is_registered = 1 AND status != 'banned'
            ) AS ranked_users
            WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
    return result[0] if result else None

def get_user_regional_rank(user_id, region):
    """Получает региональное место пользователя в рейтинге."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT rank FROM (
                SELECT user_id, RANK() OVER (ORDER BY hours DESC) as rank
                FROM users
                WHERE is_registered = 1 AND status != 'banned' AND region = ?
            ) AS ranked_users
            WHERE user_id = ?
        ''', (region, user_id))
        result = cursor.fetchone()
    return result[0] if result else None

# №4: Реализация кнопок "Лишить прав"
def view_admin_list(message):
    admins = get_all_admins()
    if not admins: return
    res = "👥 <b>Список администрации:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    for user_id, username in admins:
        safe_username = html.escape(username if username else f"ID_{user_id}")
        if user_id == MAIN_ADMIN_ID:
            res += f"👑 @{safe_username} (Главный)\n"
        else:
            res += f"🔹 @{safe_username} (ID: <code>{user_id}</code>)\n" 
            if len(admins) < 10:
                markup.add(types.InlineKeyboardButton(f"❌ Лишить прав {username[:15]}...", callback_data=f"demote_{user_id}"))
    bot.send_message(message.chat.id, res, reply_markup=markup, parse_mode='HTML')

def get_user_id_by_username(username):
    """Безопасный поиск user_id без уязвимости к SQL-инъекциям."""
    clean_username = username.lstrip('@') 
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE username = ?', (clean_username,))
        result = cursor.fetchone()
    return result[0] if result else None

def process_mass_notification(message, scope):
    if is_interrupted(message): return
    admin_id = message.chat.id
    text = message.text
# 1. Защита на дурака (проверка текста)
    if message.content_type != 'text':
        bot.send_message(admin_id, "❌ Рассылка должна быть текстовой.")
        return
# 2. Получаем список только ЖИВЫХ (is_active=1) пользователей
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if scope == 'region':
            region = get_user_region(admin_id)
            cursor.execute('SELECT user_id FROM users WHERE region = ? AND is_active = 1 AND is_registered = 1', (region,))
        else:
            cursor.execute('SELECT user_id FROM users WHERE is_active = 1 AND is_registered = 1')
        user_ids = [row[0] for row in cursor.fetchall()]
    sent_count = 0
    blocked_count = 0
    start_time = time.time()
    bot.send_message(admin_id, f"🚀 Начинаю рассылку на {len(user_ids)} чел...")
    for target_id in user_ids:
        try:
            if target_id == admin_id: continue 
            bot.send_message(target_id, f"📣 <b>ОПОВЕЩЕНИЕ</b>\n\n{text}", parse_mode='HTML')
            sent_count += 1 
# ПУНКТ 2 (Оптимизация): Защита от Flood Control Telegram
            time.sleep(0.05) 
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 403 or e.error_code == 400:
                blocked_count += 1
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET is_active = 0 WHERE user_id = ?', (target_id,))
                    conn.commit()
            else:
                print(f"Ошибка при рассылке пользователю {target_id}: {e}")
        except Exception as e:
            print(f"Непредвиденная ошибка рассылки: {e}")
    duration = round(time.time() - start_time, 1)
# 3. Финальный отчет для админа
    report = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Доставлено: <code>{sent_count}</code>\n"
        f"🚫 Заблокировали бота: <code>{blocked_count}</code> (удалены из базы)\n"
        f"⏱ Время выполнения: <code>{duration} сек.</code>"
    )
    bot.send_message(admin_id, report, parse_mode='HTML')

def clear_temporary_memory():
    bot.user_data.clear()
    print("Временная память очищена.")

def process_admin_reply_step(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    user_data = bot.user_data.get(user_id, {})
    if not user_data.get('awaiting_admin_reply') or 'target_user_id' not in user_data:
        bot.send_message(user_id, "Ошибка сессии ответа. Попробуйте снова.")
        return 
    target_user_id = user_data['target_user_id']
    reply_text = message.text
    try:
        bot.send_message(target_user_id, f"<b>✉️ Ответ от администратора:</b>\n\n{reply_text}", parse_mode='HTML')
        bot.send_message(user_id, f"✅ Ответ успешно отправлен пользователю ID {target_user_id}.")
        safe_delete_message(user_id, message.message_id) 
    except Exception as e:
        bot.send_message(user_id, f"❌ Не удалось отправить ответ пользователю ID {target_user_id}.")
        print(f"Error sending admin reply: {e}")
    if user_id in bot.user_data:
        del bot.user_data[user_id]

def check_registration_leftovers():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE is_registered = 0 AND status = 'registering'")
        users = cursor.fetchall()
        for (u_id,) in users:
            try:
                bot.send_message(u_id, "💡 Заметили, что вы не закончили регистрацию. Нажмите /start, чтобы получить доступ к волонтерским часам!")
            except:
                pass

# --- 5. Обработка Inline кнопок (Одобрение/Отклонение/Лишение прав/Ответ/Удаление контента/Регистрация на ивент) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.message.chat.id
    data = call.data
    parts = data.split('_')
    action = parts[0]
    status = get_user_status(user_id)
    
    # 1. СИСТЕМА ОДОБРЕНИЯ ОТВЕТСТВЕННЫХ ЛИЦ (Только Главный Админ)
    if action in ['grant', 'deny'] and 'resp' in parts:
        if user_id != MAIN_ADMIN_ID:
            bot.answer_callback_query(call.id, "🚫 Только главный админ может одобрять роли!", show_alert=True)
            return
        target_id = int(parts[2])
        if action == 'grant':
            update_user_status(target_id, 'admin')
            update_registration_data_fixed_role(target_id, 'Ответственное лицо') 
            bot.send_message(target_id, "🎉 Ваша заявка одобрена! Вам выданы права Ответственного лица.")
            bot.edit_message_text(f"✅ Роль для ID {target_id} одобрена.", user_id, call.message.message_id)
        else:
            update_user_status(target_id, 'user')
            bot.send_message(target_id, "🔔 Ваша заявка на роль Ответственного лица была отклонена.")
            bot.edit_message_text(f"❌ В роли для ID {target_id} отказано.", user_id, call.message.message_id)
        return

    # 2. БЕЗОПАСНОСТЬ: Проверка на админ-действия
    admin_only_actions = ['moderate', 'delete', 'demote', 'admin']
    if any(x in action for x in admin_only_actions) and status != 'admin':
        bot.answer_callback_query(call.id, "🚫 Ошибка доступа: требуются права администратора.", show_alert=True)
        return
    bot.answer_callback_query(call.id) 

    # 3. ПАРСИНГ ID (Универсальный)
    target_id = int(parts[-1]) if parts[-1].isdigit() else None

    # --- ЛОГИКА МЕРОПРИЯТИЙ ---
    if action == 'view' and 'events' in parts:
        try:
            view_mode = parts[2] 
            region_index = int(parts[3]) 
            region_name = RUSSIAN_SUBJECTS[region_index] 
            display_events_list(call.message, region_name, view_mode)
        except Exception as e:
            print(f"Ошибка навигации мероприятий: {e}")
        
        # Логика удаления (из /manage_content и жалоб)
    if action == 'delete' and parts[1] == 'content':
        content_id = int(parts[2])
        delete_content_item(content_id)
        bot.answer_callback_query(call.id, "Пост удален")
        bot.edit_message_text(f"✅ Пост #{content_id} успешно удален.", user_id, call.message.message_id)

    elif action == 'register':
        # Здесь target_id — это event_id
        if target_id:
            execute_action(user_id, 'register', target_id, call.message)

        # --- ЛОГИКА МОДЕРАЦИИ КОНТЕНТА ---
    elif action == 'moderate':
        sub_action = parts[1]
        if sub_action == 'delete':
            content_id = int(parts[2]) 
            delete_content_and_reports(content_id)
            bot.edit_message_text(f"✅ Пост #{content_id} удален.", user_id, call.message.message_id)
        elif sub_action == 'dismiss':
            report_id = int(parts[2])
            update_report_status(report_id, 'dismissed')
            bot.edit_message_text(f"✅ Жалоба #{report_id} отклонена.", user_id, call.message.message_id)
    
    # Логика жалобы
    elif action == 'report' and parts[1] == 'content':
        content_id = int(parts[2])
        bot.answer_callback_query(call.id)
        msg = bot.send_message(user_id, "Опишите причину жалобы:")
        bot.user_data[user_id] = {'reporting_content_id': content_id}
        bot.register_next_step_handler(msg, process_report_reason)
    elif action == 'view' and 'original' in parts:
        content_id = int(parts[3]) 
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT text, author_id FROM content WHERE id = ?', (content_id,))
            content = cursor.fetchone()
        if content:
            text, author_id = content
            response_text = (
                f"<b>📖 Оригинал поста #{content_id}</b>\n"
                f"<b>Автор:</b> ID {author_id}\n"
                f"------------------------\n\n"
                f"{text}"
            )
            bot.send_message(user_id, response_text, parse_mode='HTML')
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, "❌ Пост не найден в базе данных.", show_alert=True)

    # 2.5 ЛОГИКА ПРОСМОТРА ВСЕХ ЖАЛОБ 
    if data == "admin_view_reports":
        if user_id == MAIN_ADMIN_ID or status == 'admin':
            bot.answer_callback_query(call.id)
            # Вызываем функцию, которую вы нашли ранее
            view_pending_reports_panel(call.message) 
        else:
            bot.answer_callback_query(call.id, "🚫 У вас нет прав админа", show_alert=True)
        return
    # --- ЛОГИКА ПАГИНАЦИИ ---
    elif action == 'content' and parts[1] == 'page':
        show_content_page(user_id, page=int(parts[2]))
        safe_delete_message(user_id, call.message.message_id)

    elif action == 'mycont' and 'p' in parts:
        show_my_content_page(user_id, page=target_id)
        safe_delete_message(user_id, call.message.message_id)

    # Логика сертификата
    elif data == 'get_cert':
        handle_get_certificate(call.message)

    elif action == 'send' and 'cert' in parts:
        try:
            target_user_id = int(parts[2])
            doc_msg_id = int(parts[3])
            bot.copy_message(target_user_id, user_id, doc_msg_id)
            bot.send_message(user_id, "✅ Сертификат отправлен пользователю.")
            safe_delete_message(user_id, call.message.message_id)
        except:
            bot.send_message(user_id, "❌ Ошибка пересылки.")

    # --- ЛОГИКА СВЯЗИ ---
    elif action == 'reply':
        if target_id:
            msg = bot.send_message(user_id, f"✍️ Введите текст ответа для пользователя ID {target_id}:")
            bot.user_data[user_id] = {'awaiting_admin_reply': True, 'target_user_id': target_id}
            bot.register_next_step_handler(msg, process_admin_reply_step)

    # --- ПОДТВЕРЖДЕНИЕ ДЕЙСТВИЙ (CONFIRM/DENY) ---
    elif type == 'confirm':
        real_action = parts[1]
        real_target = int(parts[2])
        execute_action(user_id, real_action, real_target, call.message)

    elif data == 'change_profile_data':
        prompt_change_data(call.message)

    elif action == 'deny':
        bot.edit_message_text("❌ Действие отменено.", user_id, call.message.message_id)

    elif action == 'select' and 'region' in parts:
        region_index = target_id
        if 0 <= region_index < len(RUSSIAN_SUBJECTS):
            region = RUSSIAN_SUBJECTS[region_index]
            finalize_region_selection(user_id, region, call.message.message_id)

def update_registration_data_fixed_role(user_id, new_role):
    """Специальная функция для ручного изменения текстовой роли пользователя. Используется главным админом при одобрении заявок."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET role = ? 
            WHERE user_id = ?
        ''', (new_role, user_id))
        conn.commit()

def process_set_user_role(message):
    if is_interrupted(message): return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2: 
             bot.send_message(message.chat.id, "❌ Неверный формат. Нужно: `ID Роль`")
             return
        target_id = int(parts[0])
        new_val = parts[1].strip()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if new_val in ['admin', 'user', 'pending', 'banned']:
                cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (new_val, target_id))
            else:
                cursor.execute('UPDATE users SET role = ? WHERE user_id = ?', (new_val, target_id))
            conn.commit() 
        bot.send_message(message.chat.id, f"✅ Данные ID {target_id} изменены на {new_val}")
        try:
            bot.send_message(target_id, f"🔔 Ваш статус/роль изменены на: **{new_val}**", parse_mode='Markdown')
        except: pass
    except ValueError:
        bot.send_message(message.chat.id, "Ошибка. Формат: `ID Роль` (ID должно быть числом)")

def export_users_to_csv(message):
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['ID', 'ФИО', 'Регион', 'Город', 'Часы', 'Роль'])
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, full_name, region, city, hours, role FROM users')
        for row in cursor:
            writer.writerow(row) 
    output.seek(0)
    byte_output = io.BytesIO(output.getvalue().encode('utf-8'))
    bot.send_document(message.chat.id, (f"users_26.csv", byte_output))

@bot.message_handler(commands=['top_global'])
def display_global_leaderboard(message):
    top_list = get_top_volunteers(region=None)
    if top_list:
        response = "🏆 <b>Глобальный топ 10 волонтеров</b>\n\n"
        for i, (username, hours) in enumerate(top_list, 1):
            name = username if username else f"Участник #{i}"
            response += f"{i}. {name} — <b>{hours}</b> ч.\n"
        bot.send_message(message.chat.id, response, parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, "Рейтинг пуст.")

def send_local_qr(user_id, qr_data, caption):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    bio.name = 'event_qr.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    bot.send_photo(user_id, bio, caption=caption, parse_mode='Markdown')

def clear_old_admin_limits():
    """Удаляет записи о лимитах за прошлые даты, чтобы освободить место и сбросить счетчики."""
    today = datetime.date.today().strftime('%Y-%m-%d')
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM admin_limits WHERE date < ?', (today,))
            conn.commit()
        print(f"[{datetime.datetime.now()}] Дневные лимиты успешно сброшены.")
    except Exception as e:
        print(f"Ошибка при очистке лимитов: {e}")

@bot.message_handler(commands=['set_role'])
def prompt_set_user_role(message):
    user_id = message.chat.id
    if get_user_status(user_id) != 'admin':
        bot.send_message(user_id, "У вас нет прав для выполнения этой команды.")
        return

    msg = bot.send_message(user_id, 
                           "Введите ID пользователя и новую роль через пробел.\n\n"
                           "Доступные роли: `Ученик (волонтер)`, `Куратор`, `Ответственное лицо`, `user` (для обычного статуса), `admin` (для статуса администратора). \n\n"
                           "Пример: `123456789 Куратор`",
                           parse_mode='Markdown')

    bot.register_next_step_handler(msg, process_set_user_role)

def process_send_message_to_responsible_person(message):
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    user_data = bot.user_data.get(user_id, {})
    if user_data.get('contacting_responsible_person') and 'responsible_person_id' in user_data:
        responsible_person_id = user_data['responsible_person_id']
        message_text = message.text
        username = message.from_user.username or f"ID: {user_id}"
        notification_message = (
            f"<b>✉️ НОВОЕ СООБЩЕНИЕ ОТВЕТСТВЕННОМУ ЛИЦУ ✉️</b>\n\n"
            f"От пользователя: @{username} (ID: {user_id})\n\n"
            f"<b>Сообщение:</b>\n{message_text}"
        )

        markup = types.InlineKeyboardMarkup()
        btn_reply = types.InlineKeyboardButton("Ответить пользователю", callback_data=f"reply_{user_id}") 
        markup.add(btn_reply)

        try:
            bot.send_message(responsible_person_id, notification_message, parse_mode='HTML', reply_markup=markup)
            bot.send_message(user_id, "✅ Ваше сообщение успешно отправлено ответственному лицу.")
        except Exception as e:
            bot.send_message(user_id, "❌ Произошла ошибка при отправке сообщения ответственному лицу. Возможно, он заблокировал бота.")
            print(f"Error sending message to responsible person {responsible_person_id}: {e}")
        finally:
            if user_id in bot.user_data:
                del bot.user_data[user_id]
    else:
        bot.send_message(user_id, "Произошла ошибка сессии. Начните снова через /profile -> Связаться с ответственным лицом.")
        if user_id in bot.user_data:
            del bot.user_data[user_id]

def confirm_action_prompt(message, action, target_id):
    """Отправляет сообщение с запросом подтверждения необратимого действия."""
    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton("✅ Да, выполнить", callback_data=f"confirm_{action}_{target_id}")
    btn_no = types.InlineKeyboardButton("❌ Нет, отменить", callback_data=f"deny_{action}_{target_id}")
    markup.add(btn_yes, btn_no)
    
    action_name = {
        'approve': 'одобрить заявку',
        'reject': 'отклонить заявку',
        'demote': 'лишить прав админа',
        'delete': 'удалить контент'
    }.get(action, 'выполнить действие')

    bot.send_message(message.chat.id, f"⚠️ Вы уверены, что хотите {action_name} (ID: {target_id})?", reply_markup=markup)

def execute_action(user_id, action, target_id, message_obj):
    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=message_obj.message_id, reply_markup=None)
    except Exception:
        pass 

    if action == 'approve':
        update_user_status(target_id, 'admin')
        bot.send_message(user_id, f"✅ Пользователь {target_id} назначен администратором.")
        try: bot.send_message(target_id, "🎉 Ваша заявка одобрена! Вы теперь администратор.")
        except: pass

    elif action == 'reject': 
        update_user_status(target_id, 'user') 
        bot.send_message(user_id, f"❌ Заявка пользователя {target_id} отклонена.")
        try: bot.send_message(target_id, "🔔 Ваша заявка на права администратора была отклонена.")
        except: pass

    elif action == 'demote':
        if target_id == MAIN_ADMIN_ID:
            bot.send_message(user_id, "❌ Невозможно лишить прав главного администратора!")
            return
        update_user_status(target_id, 'user')
        bot.send_message(user_id, f"✅ Пользователь {target_id} лишен прав.")
        try: bot.send_message(target_id, "🚨 Вы были лишены прав администратора.")
        except: pass

    elif action == 'delete':
        delete_content_item(target_id)
        bot.send_message(user_id, f"✅ Пост #{target_id} удален.")
        
    # --- Логика регистрации на ивент ---
    elif action == 'register':
        current_user_id = user_id
        if register_for_event(current_user_id, target_id):
            bot.send_message(current_user_id, f"🎉 Вы успешно записаны на мероприятие #{target_id}! Ждем вас!")
            bot.edit_message_reply_markup(chat_id=user_id, message_id=message_obj.message_id, reply_markup=None)
        else:
            bot.send_message(current_user_id, "Вы уже были записаны на это мероприятие ранее.")

# --- Функции профиля и изменения данных ---
def delete_event_registration(user_id, event_id):
    """Удаляет регистрацию пользователя на мероприятие."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM event_registrations WHERE user_id = ? AND event_id = ?', (user_id, event_id))
        conn.commit()
    return cursor.rowcount > 0

def format_date_26(date_obj):
    return date_obj.strftime("%d.%m.%y")
def parse_date_26(date_str):
    try:
        return datetime.datetime.strptime(date_str.strip(), "%d.%m.%y")
    except ValueError:
        return None

def get_user_details(user_id):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT username, region, city, role, status, hours, full_name, age 
                FROM users WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            return result
    except Exception as e:
        print(f"Ошибка БД в get_user_details: {e}")
        return None

@bot.message_handler(commands=['manage_reports'])
def view_pending_reports_panel(message):
    user_id = message.chat.id
    reports = get_pending_reports() 
    if not reports:
        bot.send_message(user_id, "Активных жалоб нет. ✅")
        return
    for report_id, content_id, report_text, reporter_id, author_id in reports:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Удалить пост ❌", callback_data=f"moderate_delete_{content_id}_{report_id}"))
        markup.add(types.InlineKeyboardButton("Отклонить жалобу ✅", callback_data=f"moderate_dismiss_{report_id}"))
        markup.add(types.InlineKeyboardButton("👁 Просмотреть оригинал", callback_data=f"view_original_post_{content_id}"))
        bot.send_message(
            user_id, 
            f"🚨 **Жалоба #{report_id}**\nПост: #{content_id}\nПричина: {report_text}\nАвтор поста: {author_id}",
            reply_markup=markup,
            parse_mode='Markdown'
        )

@bot.message_handler(commands=['checkin'])
def prompt_checkin_code(message):
    user_id = message.chat.id
    if not is_user_registered(user_id):
        enforce_registration(message)
        return
    msg = bot.send_message(user_id, "Введите **код участия** (6 символов), который вы получили на мероприятии:")
    bot.user_data[user_id] = {'awaiting_checkin_code': True}
    bot.register_next_step_handler(msg, process_checkin_code)

def parse_strict_date(text):
    """
    Проверяет строку на формат ДД.ММ.ГГ ЧЧ:ММ (напр. 06.01.26 15:30)
    """
    formats = ["%d.%m.%y %H:%M", "%d.%m.%y"] 
    now_moscow = datetime.datetime.now(timezone_spb)
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(text.strip(), fmt)
            dt = timezone_spb.localize(dt, is_dst=None) 
            if fmt == "%d.%m.%y":
                dt = dt.replace(hour=0, minute=0)
            if dt < now_moscow:
                continue 
            return dt
        except ValueError:
            continue
    return None

def get_progress_bar(hours):
    if hours is None: hours = 0
    levels = [10, 50, 150, 500, 1000]
    next_level = next((x for x in levels if x > hours), 1000)
    prev_level = levels[levels.index(next_level)-1] if hours >= 10 else 0
    total_segment = next_level - prev_level
    current_segment = hours - prev_level
    percent = min(max(int((current_segment / total_segment) * 10), 0), 10)
    bar = "🟩" * percent + "⬜" * (10 - percent)
    return f"{bar} {int((current_segment/total_segment)*100)}%"

@bot.message_handler(func=lambda message: message.text and ('Профиль' in message.text or message.text == '/profile'))
def view_profile(message):
    user_id = message.chat.id
    details = get_user_details(user_id) 
    if not details:
        bot.send_message(user_id, "❌ Профиль не найден. Нажмите /start")
        return
    username, region, city, role, status, hours, full_name, age = details
    full_name = full_name if full_name else "Не указано"
    hours = hours if hours is not None else 0
    rank = get_volunteer_rank(hours)
    progress = get_progress_bar(hours)
    response = (
        f"👤 <b>ПРОФИЛЬ ВОЛОНТЕРА</b>\n"
        f"--------------------------\n"
        f"<b>ФИО:</b> {full_name}\n"
        f"<b>Username:</b> @{username}\n"
        f"<b>Возраст:</b> {age if age else '?'}\n"
        f"<b>Регион:</b> {region}\n"
        f"<b>Город:</b> {city}\n"
        f"<b>Звание:</b> {rank}\n"
        f"<b>Часы:</b> {hours} ч.\n"
        f"<b>📊 Прогресс:</b> {progress}\n"
        f"--------------------------\n"
        f"<i>Роль: {role} | Статус: {status}</i>"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚙️ Изменить данные", callback_data="change_profile_data"))  
    if hours >= 100:
        markup.add(types.InlineKeyboardButton("📩 Запросить сертификат", callback_data="get_cert"))
    bot.send_message(user_id, response, parse_mode='HTML', reply_markup=markup)

def get_achievements(user_id):
    """Пример логики ачивок."""
    achievements = []
    hours = get_user_hours(user_id) 
    if hours >= 1: achievements.append("🥉 Первый шаг (1 час)")
    if hours >= 50: achievements.append("🥈 Опытный эколог (50 часов)")
    if hours >= 100: achievements.append("🥇 Эко-Герой (100 часов)")
    if hours >= 150: achievements.append("🏆 Эко-Халк (150 часов)")
    if hours >= 300: achievements.append("🌟🌳 Эко-Создатель (300 часов)")
    # Логика проверки участия в мероприятиях
    history = get_user_event_history(user_id)
    if len(history) >= 10: achievements.append("🥉⭐ Активист 3 уровня (10 мероприятий)")
    if len(history) >= 20: achievements.append("🥈⚡ Активист 2 уровня (20 мероприятий)")
    if len(history) >= 30: achievements.append("🥇🔥 Активист 1 уровня (30 мероприятий)")
    if len(history) >= 50: achievements.append("🏆👑 Активист-Легенда (50 мероприятий)")
    return achievements if achievements else ["Пока нет достижений"]

@bot.message_handler(commands=['award_hours'])
def prompt_award_hours(message):
    try:
        # 1. Сначала получаем ID, без него ничего не сработает
        u_id = message.chat.id 
        # 2. Сбрасываем старые обработчики
        bot.clear_step_handler_by_chat_id(u_id)
        # 3. Проверяем права через ваши функции
        u_status = get_user_status(u_id)
        u_details = get_user_details(u_id) 
        is_responsible_person = False
        if u_details and len(u_details) > 3:
            if u_details[3] == 'Ответственное лицо':
                is_responsible_person = True
        # Проверка прав: админ или ответственное лицо
        if u_status == 'admin' or is_responsible_person:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add('Использовать User ID (цифры) 🔢', 'Использовать Username (@логин) 👤')
            # Инициализируем данные в словаре
            if u_id not in bot.user_data:
                bot.user_data[u_id] = {}
            msg = bot.send_message(u_id, "Выберите способ ввода данных пользователя:", reply_markup=markup)
            bot.user_data[u_id]['awaiting_hours_method'] = True
            bot.register_next_step_handler(msg, choose_input_method_step)
        else:
            bot.send_message(u_id, "❌ У вас нет прав для начисления часов.")
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА в /award_hours: {e}")

def process_award_hoursts(message):
    user_id = message.chat.id
    if is_interrupted(message): 
        bot.send_message(user_id, "❌ Операция отменена.")
        return
    user_data = bot.user_data.get(user_id, {})
    input_method = user_data.get('method')
    if not input_method:
        bot.send_message(user_id, "❌ Ошибка сессии. Попробуйте снова: /award_hours")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2: raise ValueError
        identifier = parts[0]
        hours_to_add = int(parts[1])
    except (ValueError, IndexError):
        bot.send_message(user_id, "❌ Неверный формат. Пример: `123456789 10`", parse_mode='Markdown')
        bot.register_next_step_handler(message, process_award_hoursts)
        return
    # Определение target_user_id
    target_user_id = None
    if input_method == 'id':
        if identifier.isdigit(): target_user_id = int(identifier)
    else:
        target_user_id = get_user_id_by_username(identifier)
    if not target_user_id:
        bot.send_message(user_id, "❌ Пользователь не найден.")
        return
    if target_user_id == user_id:
        bot.send_message(user_id, "🚨 Нельзя начислять часы самому себе!")
        return
    # Проверка разового лимита
    if not (-20 <= hours_to_add <= 20):
        bot.send_message(user_id, "❌ Лимит одной операции: от -20 до 20 часов.")
        return
    if not check_and_update_admin_limit(user_id, hours_to_add):
        bot.send_message(user_id, "🚨 Вы исчерпали свой суммарный дневной лимит (150 часов).")
        return
    # Финальное начисление
    try:
        add_hours(target_user_id, hours_to_add)
        bot.send_message(user_id, f"✅ Успешно! Пользователю {target_user_id} изменено на {hours_to_add} ч.")
        # Уведомление пользователя (через try на случай, если бот заблокирован)
        try:
            bot.send_message(target_user_id, f"🎁 Ваш баланс часов изменен на: **{hours_to_add}** ч.!", parse_mode='Markdown')
        except: pass
    except Exception as e:
        bot.send_message(user_id, f"❌ Ошибка БД: {e}")
    if user_id in bot.user_data:
        del bot.user_data[user_id]

@bot.message_handler(commands=['cancel'])
@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def cancel_process(message):
    """Универсальная функция отмены действия."""
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id)
    if user_id in bot.user_data:
        keys_to_remove = ['awaiting_hours_method', 'adding_faq', 'creating_event', 'awaiting_checkin_code', 'scope', 'target_user_id']
        for key in keys_to_remove:
             bot.user_data[user_id].pop(key, None)
    status = get_user_status(user_id)
    bot.send_message(user_id, "❌ Действие отменено.")
    if status == 'admin':
        admin_panel(message) 
    else:
        bot.send_message(user_id, "Воспользуйтесь меню ниже.", reply_markup=user_keyboard)

@bot.message_handler(func=lambda message: message.text == '⚙️ Изменить данные' or message.text == '/change')
def prompt_change_data(message):
    user_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton('🗺 Изменить регион'), types.KeyboardButton('🏙 Изменить город'))
    markup.add(types.KeyboardButton('❌ Отмена'))
    bot.send_message(user_id, "Что именно вы хотите изменить?", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🗺 Изменить регион')
def btn_edit_region(message):
    # Убираем старую клавиатуру и запускаем ввод
    msg = bot.send_message(message.chat.id, "Введите новый регион:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_region_text_input)

@bot.message_handler(func=lambda message: message.text == '🏙 Изменить город')
def btn_edit_city(message):
    msg = bot.send_message(message.chat.id, "Введите новый город:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_new_city)

@bot.message_handler(commands=['edit_region'])
def edit_region_prompt(message):
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id)
    
    msg = bot.send_message(user_id, 
                           "Введите **название** вашего нового **региона** (можно ввести только первую букву или часть названия):", 
                           reply_markup=types.ReplyKeyboardRemove(),
                           parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_region_text_input)

@bot.message_handler(commands=['edit_city'])
def edit_city_prompt(message):
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id)
    
    msg = bot.send_message(user_id, "Введите новое название вашего **города/населенного пункта**:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_new_city)

def process_new_city(message):
    if is_command_and_cancel_process(message): return
    user_id = message.chat.id
    if message.content_type != 'text':
        msg = bot.send_message(user_id, "⚠️ Ошибка! Введите название города текстом:")
        bot.register_next_step_handler(msg, process_new_city)
        return
    city_name = message.text.strip()
    if city_name.isdigit():
        msg = bot.send_message(user_id, "❌ Название не может состоять только из цифр. Введите корректно:")
        bot.register_next_step_handler(msg, process_new_city)
        return
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET city = ? WHERE user_id = ?', (city_name, user_id))
        conn.commit()
    bot.send_message(user_id, f"✅ Город изменен на: **{city_name}**", parse_mode='Markdown')

def safe_delete_message(chat_id, message_id):
    """Безопасное удаление сообщений, с обработкой ошибок Telegram API."""
    try:
        bot.delete_message(chat_id, message_id)
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code not in [400, 403]: 
            print(f"Ошибка удаления сообщения: {e}")
    except Exception as e:
        print(f"Непредвиденная ошибка удаления: {e}")

def send_report_to_admin(message):
    user_id = message.chat.id
    if message.text == '/cancel' or message.text == '❌ Отмена':
        cancel_process(message) 
        return
    report_text = message.text
    username = message.from_user.username if message.from_user.username else f"ID: {user_id}"

    if MAIN_ADMIN_ID:
        report_message = (
            f"<b>🚨 НОВАЯ ЖАЛОБА/ВОПРОС 🚨</b>\n\n"
            f"От пользователя: @{username} (ID: {user_id})\n\n"
            f"<b>Сообщение:</b>\n{report_text}"
        )
        
        markup = types.InlineKeyboardMarkup()
        btn_reply = types.InlineKeyboardButton("Ответить пользователю", callback_data=f"reply_{user_id}") 
        markup.add(btn_reply)

        try:
            bot.send_message(MAIN_ADMIN_ID, report_message, parse_mode='HTML', reply_markup=markup)
            bot.send_message(user_id, "✅ Ваше сообщение отправлено главному администратору.")
        except Exception as e:
            bot.send_message(user_id, "Произошла ошибка при отправке сообщения администратору.")
            print(f"Error sending report to admin: {e}")
    else:
        bot.send_message(user_id, "Главный администратор в боте не настроен.")

def prompt_admin_reply(message, target_user_id):
    if message.text == '/cancel':
        cancel_process(message)
        return
    """Запрашивает у админа текст ответа пользователю."""
    reply_text = message.text

    try:
        bot.send_message(target_user_id, f"<b>✉️ Ответ от администратора:</b>\n\n{reply_text}", parse_mode='HTML')
        bot.send_message(message.chat.id, f"✅ Ответ успешно отправлен пользователю {target_user_id}.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Не удалось отправить ответ пользователю {target_user_id}. Возможно, он заблокировал бота.")
        print(f"Error sending admin reply: {e}")

# --- Дополнительные функции БД для управления контентом ---

def get_admin_content(author_id):
    """Получает список контента, созданного конкретным администратором."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, text, scope, region FROM content WHERE author_id = ? ORDER BY id DESC', (author_id,))
        results = cursor.fetchall()
    return results

def delete_content_item(content_id):
    """Удаляет контент по его ID."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM content WHERE id = ?', (content_id,))
        conn.commit()

# --- Обработчики управления контентом ---
@bot.message_handler(commands=['manage_content'])
def manage_content_prompt(message):
    user_id = message.chat.id
    if get_user_status(user_id) != 'admin':
        bot.send_message(user_id, "У вас нет прав администратора для управления контентом.")
        return

    content_list = get_admin_content(user_id)
    if not content_list:
        bot.send_message(user_id, "Вы еще не опубликовали ни одного поста.")
        return

    bot.send_message(user_id, "⬇️ **Ваши посты.** Нажмите кнопку, чтобы удалить пост:", parse_mode='Markdown')

    for content in content_list:
        content_id, text, scope, region = content
        scope_info = f"[{region} region only 🏠]" if scope == 'region' else "[For all 🌍]"
        display_text = text[:100] + ('...' if len(text) > 100 else '') # Обрезаем длинный текст для превью

        markup = types.InlineKeyboardMarkup()
        btn_delete = types.InlineKeyboardButton(f"Удалить пост #{content_id}", callback_data=f"delete_content_{content_id}")
        markup.add(btn_delete)
        
        bot.send_message(user_id, f"#{content_id} {scope_info}\n\n{display_text}", reply_markup=markup)

def check_disk_space():
    """Проверка свободного места и очистка логов """
    # Путь к лог-файлу на PythonAnywhere обычно такой:
    log_file = f"/home/ТВОЙ_ЛОГИН/var/log/ТВОЙ_ЛОГИН.pythonanywhere.com.error.log"
    if os.path.exists(log_file):
        size_mb = os.path.getsize(log_file) / (1024 * 1024)
        if size_mb > 10:  # Если файл логов больше 10 МБ
            with open(log_file, 'w') as f:
                f.write(f"--- Log cleaned at {datetime.datetime.now()} ---\n")
            print("Логи очищены, место освобождено.")

def weekly_backup():
    try:
        with open(DB_NAME, 'rb') as f:
            bot.send_document(MAIN_ADMIN_ID, f, caption=f"📦 Еженедельный бэкап ({datetime.date.today()})")
    except Exception as e:
        print(f"Ошибка бэкапа: {e}")

def optimize_db_size():
    """Сжатие базы данных для экономии места на PythonAnywhere"""
    try:
        with get_db_connection() as conn:
            conn.execute('VACUUM')
        print("База данных оптимизирована и сжата.")
    except Exception as e:
        print(f"Ошибка оптимизации БД: {e}")

# --- 6. Функция для установки стандартного меню команд ---
def set_default_commands():
    commands = [
        types.BotCommand('start', 'Запустить бота'),
        types.BotCommand('help', 'Список команд'),
        types.BotCommand('profile', 'Мой профиль'),
        types.BotCommand('view_content', 'Посмотреть посты'),
        types.BotCommand('view_events', 'Посмотреть мероприятия'),
        types.BotCommand('eco_faq', 'Полезная информация'),
        types.BotCommand('my_rating', 'Мой рейтинг'),
        types.BotCommand('top_volunteers', 'Топ волонтеров региона'),
        types.BotCommand('request_admin', 'Подать заявку на админа'),
        types.BotCommand('report_admin', 'Пожаловаться')
    ]
    bot.set_my_commands(commands) 

@bot.message_handler(content_types=['photo', 'video', 'audio', 'document', 'sticker', 'voice', 'location', 'contact'])
def handle_unsupported_media(message):
    user_id = message.chat.id
    if get_user_status(user_id) == 'banned':
        return
    if user_id in bot.user_data and bot.user_data[user_id] != {}:
        bot.send_message(user_id, "Извините, в данный момент бот ожидает от вас **текстовый ввод**. Фотографии, видео и другие медиафайлы сейчас не поддерживаются. Пожалуйста, введите текст или используйте команду /cancel для отмены действия.", parse_mode='Markdown')

    else:
        bot.send_message(user_id, "Извините, этот бот пока не поддерживает отправку фотографий, видео или других медиафайлов в обычном режиме. Воспользуйтесь командами меню /help.")

@bot.message_handler(func=lambda message: True)
def handle_unknown_messages(message):
    buttons = ['Ученик (волонтер)', 'Куратор', 'Ответственное лицо', '📖 Посты', '🌳 Мероприятия', '👤 Профиль', '📚 FAQ', '📜 Все команды', '❌ Отмена', 'Лишить прав админа ❌', 'Написать напрямую ✉️', 'Глобальный (для всех) 🌍', 'Только для моего региона 🏠', 'Выдать сертификат ✅', '✅ Отправить пользователю', '❌ Оставить у себя', 'Разрешить ✅', 'Отказать ❌', 'Одобрить ✅', 'Отклонить ❌', '⬅️ Назад', 'Вперед ➡️', '🚨 Пожаловаться', '👥 Таблица волонтеров', '📝 Таблица постов', '🌳 Таблица мероприятий', '🚨 Нарушения админов', '⏱ Текущие лимиты', 'Опубликовать для всех 🌍', 'Опубликовать только для моего региона 🏠', 'Посмотреть в панели', 'Актуальные (Новые) 🌳', 'Прошедшие (Старые) ⏳', '📝 Записаться', 'Посмотреть заявки на админа 👀', 'Список администраторов 👥', 'Добавить контент ✍️', 'Отправить оповещение 📣', 'Мои посты 📝', '🗺 Изменить регион', '🏙 Изменить город', '🏠 Только мой регион', '🌍 Для всех пользователей', '⬅️', '➡️', 'Удалить этот пост ❌', '❌ Лишить прав', 'Ответить пользователю', '✅ Да, выполнить', '❌ Нет, отменить', 'Удалить пост ❌', 'Отклонить жалобу ✅', '👁 Просмотреть оригинал', '⚙️ Изменить данные', '📩 Запросить сертификат', 'Использовать User ID (цифры) 🔢', 'Использовать Username (@логин) 👤', '']
    if message.text:
        if message.text.startswith('/') or any(b in message.text for b in buttons):
            return      
    bot.send_message(message.chat.id, "❓ Я не понимаю эту команду. Используйте меню или /help.")

# --- 7. Старт бота ---
if __name__ == '__main__':
    print("Старт процесса...")
    init_db()
    print("Бот готов к работе")
    set_default_commands()
    print("Команды установлены")
    setup_scheduler()
    print("Бот и планировщик запущены. Режим: Production Polling")
    try:
        bot.infinity_polling(
            timeout=90, 
            long_polling_timeout=5, 
            skip_pending=True,
            interval=1 
        )
    except Exception as e:
        print(f"Критическая ошибка запуска бота: {e}")
