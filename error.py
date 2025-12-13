import telebot
from telebot import types
from apscheduler.schedulers.blocking import BlockingScheduler
import sqlite3
import random
import string
import datetime
import pytz
import threading

# --- Константы  ---
TOKEN = '8595755361:AAEa-Qjsqq-2AolWWrbEdy0CnSqpM_Vla4g' 
MAIN_ADMIN_ID =  1961128598
DB_NAME = 'bot_data.db'
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
user_keyboard.add(btn_content, btn_events, btn_profile, btn_faq)

bot = telebot.TeleBot(TOKEN)
# Инициализируем user_data для хранения временных данных
if not hasattr(bot, 'user_data'):
    bot.user_data = {}

# --- 2. Функции для работы с базой данных (Улучшены с помощью 'with') ---

def init_db():
    """Инициализация базы данных и создание таблиц, если их нет."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей (user_id, status, username, region, city, role, is_registered, points)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                username TEXT,
                region TEXT,
                city TEXT,
                role TEXT,
                is_registered INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0 
            )
        ''')
        
        # Таблица для хранения контента (id, text, author_id, scope ('all' или 'region'), created_at)
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
                FOREIGN KEY (event_id) REFERENCES events(id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id INTEGER NOT NULL,
                reporter_user_id INTEGER NOT NULL,
                report_text TEXT,
                status TEXT NOT NULL DEFAULT 'pending', -- pending, resolved, dismissed
                reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (content_id) REFERENCES content(id),
                FOREIGN KEY (reporter_user_id) REFERENCES users(user_id)
            )
        ''')
        # Таблица для отслеживания дневного лимита баллов админов (admin_id, date, points_awarded)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_limits (
                admin_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                points_awarded INTEGER NOT NULL DEFAULT 0,
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

        conn.commit()
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
    user_region = get_user_region(user_id) # Это должен быть ваш текущий регион
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT text, region, scope, id FROM content WHERE scope = "all" OR (scope = "region" AND region = ?)', (user_region,))
        results = cursor.fetchall()
    return results


def get_events_for_region(region, view_mode='new'):
    """Получает активные (новые) или старые мероприятия для указанного региона."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        today_date = datetime.date.today().strftime('%Y-%m-%d')
        if view_mode == 'new':
            sql_query = '''
                SELECT id, title, description, event_date, location FROM events 
                WHERE region = ? AND event_date >= ?
                ORDER BY event_date ASC
            '''
        elif view_mode == 'old':
             sql_query = '''
                SELECT id, title, description, event_date, location FROM events 
                WHERE region = ? AND event_date < ?
                ORDER BY event_date DESC
            '''
        else:
            sql_query = '''
                SELECT id, title, description, event_date, location FROM events 
                WHERE region = ?
                ORDER BY event_date DESC
            '''

        cursor.execute(sql_query, (region, today_date))
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


def add_points(user_id, points_to_add):
    """Начисляет или снимает баллы пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET points = points + ? 
            WHERE user_id = ?
        ''', (points_to_add, user_id))
        conn.commit()

def get_user_points(user_id):
    """Получает текущее количество баллов пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT points FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    return result[0] if result else 0

def check_and_update_admin_limit(admin_id, points_to_add, daily_limit=150):
    """
    Проверяет дневной лимит администратора, обновляет его и регистрирует нарушение.
    """
    today_date = datetime.date.today().strftime('%Y-%m-%d')
    month_year = datetime.date.today().strftime('%Y-%m')

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT points_awarded FROM admin_limits WHERE admin_id = ? AND date = ?
        ''', (admin_id, today_date))
        result = cursor.fetchone()

        current_points = result[0] if result else 0
        new_total_points = current_points + points_to_add

        if new_total_points <= daily_limit:
            # Обновляем или вставляем запись о начисленных баллах
            cursor.execute('''
                INSERT INTO admin_limits (admin_id, date, points_awarded) 
                VALUES (?, ?, ?)
                ON CONFLICT(admin_id, date) DO UPDATE SET points_awarded = ?
            ''', (admin_id, today_date, new_total_points, new_total_points))
            conn.commit()
            return True
        else:
            # !!! РЕГИСТРИРУЕМ ФАКТ НАРУШЕНИЯ !!!
            cursor.execute('''
                INSERT INTO admin_violations (admin_id, violation_date, month_year)
                VALUES (?, ?, ?)
            ''', (admin_id, today_date, month_year))
            conn.commit()
            return False # Лимит превышен

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

def get_curators_in_region(region):
    """Получает user_id всех кураторов в определенном регионе."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Ищем пользователей со статусом 'admin' или ролью 'Куратор' в указанном регионе
        cursor.execute('''
            SELECT user_id, username FROM users 
            WHERE (status = "admin" OR role = "Куратор") AND region = ?
        ''', (region,))
        results = cursor.fetchall()
    return results # Возвращаем список кортежей (user_id, username)

def send_monthly_violation_report():
    """
    Отправляет ежемесячный отчет главному администратору о злостных нарушителях лимита.
    """
    # Получаем данные за прошлый месяц
    today = datetime.date.today()
    # Просто меняем день на 1, чтобы получить корректный месяц/год
    first_of_month = today.replace(day=1) 
    last_month = first_of_month - datetime.timedelta(days=1)
    target_month_year = last_month.strftime('%Y-%m')

    violations = get_monthly_violations_report(target_month_year)
    
    if not violations:
        # Если нарушений нет, можно ничего не отправлять или отправить сообщение об отсутствии нарушений
        # bot.send_message(MAIN_ADMIN_ID, f"Отчет о нарушениях за {target_month_year}: нарушений не зафиксировано.")
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
        
        # Отправляем сообщение по частям, чтобы прикрепить разные кнопки к разным админам
        bot.send_message(MAIN_ADMIN_ID, report_text, reply_markup=markup, parse_mode='HTML')
        report_text = "" # Очищаем текст для следующего админа


@bot.message_handler(func=lambda message: message.text == '📖 Посты' or message.text == 'Посты')
def handle_view_content_button(message):
    view_content(message)

@bot.message_handler(func=lambda message: message.text == '🌳 Мероприятия' or message.text == 'Мероприятия')
def handle_view_events_button(message):
    # Вызываем функцию выбора режима просмотра (нов. или стар.)
    prompt_view_events_choice(message) 

@bot.message_handler(func=lambda message: message.text == '👤 Профиль' or message.text == 'Профиль')
def handle_view_profile_button(message):
    view_profile(message)

@bot.message_handler(func=lambda message: message.text == '📚 FAQ' or message.text == 'FAQ')
def handle_view_faq_button(message):
    view_faq(message)

def get_top_volunteers(region=None, limit=10):
    """Получает список лучших волонтеров (по региону или глобально)."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        if region:
            cursor.execute('''
                SELECT username, points FROM users 
                WHERE region = ? AND is_registered = 1 
                ORDER BY points DESC LIMIT ?
            ''', (region, limit))
        else:
            cursor.execute('''
                SELECT username, points FROM users 
                WHERE is_registered = 1 
                ORDER BY points DESC LIMIT ?
            ''', (limit,))
        results = cursor.fetchall()
    return results

def get_user_id_by_username(username):
    """Получает user_id по username."""
    # Убеждаемся, что username не содержит символ '@' в начале при поиске в БД
    clean_username = username.lstrip('@') 
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Поиск без учета регистра
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
            # Пользователь уже зарегистрирован (если добавить UNIQUE constraint, что полезно)
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
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    # Возвращаем статус или 'new', если пользователь не найден
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

# Функция для разбана пользователя
def unban_user_in_db(user_id):
    update_user_status(user_id, 'user') # Возвращаем к стандартному статусу пользователя

def get_monthly_violations_report_current(month_year):
    """
    Получает список всех нарушений за текущий месяц для команды /view_violations.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Возвращаем все записи, не только те, где > 35 нарушений
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
        
        return users_count, admins_count, content_count, events_count

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
    """Добавляет нового пользователя в БД."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO users (user_id, username, status, is_registered) VALUES (?, ?, ?, ?)', 
                       (user_id, username, status, 0))
        conn.commit()

def update_registration_data(user_id, region, city, role):
    """Завершает регистрацию, обновляя данные пользователя и устанавливая is_registered в 1."""
    with sqlite3.connect(DB_NAME) as conn:
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

def add_content(text, author_id, scope, region=None):
    """Добавляет новый контент в БД с указанием области видимости (scope)."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO content (text, author_id, scope, region) VALUES (?, ?, ?, ?)', 
                       (text, author_id, scope, region))
        conn.commit()

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
    return [row[0] for row in results] # Возвращаем только IDшники

@bot.message_handler(content_types=['photo', 'video', 'audio', 'document', 'sticker', 'voice', 'location', 'contact'])
def handle_unsupported_media(message):
    user_id = message.chat.id

    if get_user_status(user_id) == 'banned':
        # Просто игнорируем или отправляем сообщение о бане, если возможно
        return
    if user_id in bot.user_data and bot.user_data[user_id] != {}:
        # Если ожидали текст, а получили медиафайл
        bot.send_message(user_id, "Извините, в данный момент бот ожидает от вас **текстовый ввод**. Фотографии, видео и другие медиафайлы сейчас не поддерживаются. Пожалуйста, введите текст или используйте команду /cancel для отмены действия.", parse_mode='Markdown')

    else:
        bot.send_message(user_id, "Извините, этот бот пока не поддерживает отправку фотографий, видео или других медиафайлов в обычном режиме. Воспользуйтесь командами меню /help.")

# --- 3. Обработчики команд и процесс регистрации ---

@bot.message_handler(commands=['my_rating'])
def display_my_rating(message):
    user_id = message.chat.id
    if not is_user_registered(user_id):
        enforce_registration(message)
        return

    points = get_user_points(user_id)
    bot.send_message(user_id, f"🌟 Ваш текущий рейтинг: **{points} баллов**.", parse_mode='Markdown')

@bot.message_handler(func=lambda message: get_user_status(message.chat.id) == 'banned')
def handle_banned_users(message):
    # Просто ничего не делаем или отправляем одно сообщение о бане
    bot.send_message(message.chat.id, "Вы забанены и не можете использовать бота.")
    pass 


@bot.message_handler(commands=['eco_faq'])
def view_faq(message):
    user_id = message.chat.id
    user_region = get_user_region(user_id)
    
    if not user_region:
        user_region = 'N/A' 

    faq_items = get_faq_for_user_region(user_region)

    if faq_items:
        # !!! ИЗМЕНЕНО: Используем HTML <b> и <i> !!!
        response = f"📚 <b>Экологический FAQ</b> (для региона {user_region}):\n\n"
        current_scope = None
        for question, answer, region_scope in faq_items:
            if region_scope != current_scope:
                scope_title = "Общие вопросы 🌍" if region_scope == 'all' else f"Вопросы по вашему региону 🏠"
                # Используем <i> для курсива
                response += f"\n--- <i>{scope_title}</i> ---\n"
                current_scope = region_scope
            # Используем <b> для вопроса
            response += f"❓ <b>{question}</b>\n➡️ {answer}\n\n"
        
        # !!! Добавляем parse_mode='HTML' !!!
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

def process_faq_question(message):
    if message.text == '/cancel':
        cancel_process(message)
        return
    user_id = message.chat.id
    if user_id not in bot.user_data or 'scope' not in bot.user_data[user_id]: return
    
    bot.user_data[user_id]['question'] = message.text
    # !!! ДОБАВЛЯЕМ parse_mode='Markdown' сюда, чтобы следующий ввод сохранял разметку !!!
    msg = bot.send_message(user_id, "Теперь введите **ответ** на этот вопрос:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_faq_answer)

def process_faq_answer(message):
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    if user_id not in bot.user_data or 'question' not in bot.user_data[user_id]: return

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
        bot.send_message(user_id, "Чтобы увидеть региональный рейтинг, укажите свой регион в /change. Показываю глобальный рейтинг вместо него /leaderboard_global.")
        return

    top_list = get_top_volunteers(region=region)
    title = f"🏆 Топ 10 волонтеров ({region})"

    if top_list:
        response = f"{title}:\n\n"
        for i, (username, points) in enumerate(top_list, 1):
            response += f"{i}. @{username}: {points} баллов\n"
        
        # Проверяем, есть ли пользователь в топ-10 региона
        is_in_top_10_regional = any(user_id == get_user_id_by_username(u) for u, p in top_list)

        if not is_in_top_10_regional:
            # Если нет в топ-10, показываем его личное региональное место
            user_rank = get_user_regional_rank(user_id, region)
            if user_rank is not None:
                response += f"\n--------------------------\n"
                response += f"👤 Ваше место: **#{user_rank}** в регионе"
        
        bot.send_message(user_id, response, parse_mode='Markdown')
    else:
        bot.send_message(user_id, f"В этом регионе пока нет волонтеров или баллов для рейтинга.")


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    username = message.from_user.username if message.from_user.username else 'Пользователь'
    
    if not is_user_registered(user_id):
        add_new_user(user_id, username, status='registering')
        
        # ИЗМЕНЕНО: Сразу запрашиваем текстовый ввод и регистрируем следующий шаг
        msg = bot.send_message(user_id, "Здравствуйте! Для начала работы, пожалуйста, введите **название** вашего **региона** (можно ввести только первую букву или часть названия):", 
                               reply_markup=types.ReplyKeyboardRemove(), # Убираем любые Reply-клавиатуры
                               parse_mode='Markdown')
        # Регистрируем следующий шаг для обработки текстового ввода
        bot.register_next_step_handler(msg, process_region_text_input)

    else:
        # ... (логика для зарегистрированных пользователей остается прежней) ...
        status = get_user_status(user_id)
        welcome_text = f"Привет, {username}! Твой текущий статус: {status}."
        if user_id == MAIN_ADMIN_ID:
            welcome_text += "\nТы главный администратор. 👑 \nЧтобы посмотреть все мои команды: /help"
        bot.send_message(user_id, welcome_text, reply_markup=user_keyboard) 
        if status == 'admin':
            admin_panel(message)


# команда help
@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.chat.id, "Привет, вот, что я умею: \n" 
    "\n"
    "/view_content - посмотреть посты, которые доступны для вас. \n" 
    "/view_events - для просмотра и записи на доступные мероприятия. \n"
    "/admin - доступные команды для администратора. \n"
    "/request_admin - для заявки на должность админимстратора. \n"
    "/report_admin - для жалобы на администратора или контент. \n"
    "/change - изменить информацию профиля. \n"
    "/profile - чтобы посмотреть свой профиль. \n"
    "/my_rating - посмотреть свой рейтинг. \n"
    "/top_volunteers - рейтинг пользователей по региону. \n" \
    "/top_global - рейтинг пользователей по стране. \n"
    "/eco_faq - Посмотреть полезную информацию и ответы на вопросы. \n" 
    "/checkin - Для проверки на регистрацию. \n"
    "/cancel - отмена действия. ") 

@bot.message_handler(commands=['admin'])
def admin(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    if status == 'admin':
        bot.send_message(message.chat.id, "Команды для админа: \n" 
        " \n"
        "/add_content - добавить контент. \n"
        "/admin_panel - панель администратора. \n" 
        "/manage_content - удалить и посмотреть контент.\n" 
        "/award_points - добавить баллы. \n" 
        "/create_event - создать мероприятие. \n" 
        "/view_violations - посмотреть нарушения. \n" 
        "/stats - посмотреть статистику бота. \n" 
        "/unban - разбанить пользователя. \n" 
        "/ban - забанить пользователя. \n" 
        "/set_role - изменить роль пользовател. \n")
    else:
        bot.send_message(message.chat.id, "Вы не являетесь администратором!")

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
    if get_user_status(user_id) not in ['admin', 'Куратор', 'Ответственное лицо']:
         bot.send_message(user_id, "У вас нет прав для просмотра статистики.")
         return

    users_count, admins_count, content_count, events_count = get_stats_from_db()
    
    response = (
        f"📊 **Статистика бота:**\n\n"
        f"👤 Всего пользователей: **{users_count}**\n"
        f"👑 Администраторов: **{admins_count}**\n"
        f"📝 Всего постов: **{content_count}**\n"
        f"🌳 Всего мероприятий: **{events_count}**\n"
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
             report_text += f"👤 **Админ**: @{username} (ID: {admin_id})\n"
             current_admin = admin_id
        
        report_text += f"— Нарушение: {violation_date}\n"

    bot.send_message(MAIN_ADMIN_ID, report_text, parse_mode='HTML')

# Шаг 1: Получение региона
def process_region_text_input(message):
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
            # !!! ИСПРАВЛЕНИЕ ЗДЕСЬ: Извлекаем строку из списка (suggestions[0]) !!!
            region_name = suggestions[0] 
            finalize_region_selection(user_id, region_name, None)
        else:
            # Предлагаем список вариантов через Inline кнопки
            markup = types.InlineKeyboardMarkup()
            for region in suggestions:
                region_index = RUSSIAN_SUBJECTS.index(region)
                markup.add(types.InlineKeyboardButton(region, callback_data=f"select_region_{region_index}"))
            
            bot.send_message(user_id, f"Найдено {len(suggestions)} вариантов. Выберите ваш регион из списка ниже или введите более точное название:", reply_markup=markup)
            bot.register_next_step_handler(message, process_region_text_input)

    else:
        # Если ничего не найдено
        msg = bot.send_message(user_id, "Регион не найден. Пожалуйста, проверьте название или введите другую букву. Чтобы попробовать снова, введите название или /cancel.")
        bot.register_next_step_handler(msg, process_region_text_input)


# --- Новая вспомогательная функция для завершения выбора региона ---
def finalize_region_selection(user_id, region_name, message_id=None):
    """
    Общая логика после выбора региона (текстом или кнопкой).
    Теперь умеет отличать процесс регистрации от изменения данных (/change).
    """
    # !!! ИСПРАВЛЕНИЕ: УБРАНО clear_step_handler_by_chat_id ОТСЮДА !!!
    
    # Определяем, находимся ли мы в процессе регистрации или просто меняем регион
    # Эта проверка должна быть надежной, даже если user_data[user_id] только что создан
    is_registration = get_user_status(user_id) == 'registering'
    
    if user_id not in bot.user_data: 
        bot.user_data[user_id] = {}
        
    bot.user_data[user_id]['region'] = region_name
    
    if message_id:
         bot.edit_message_text(f"✅ Выбран регион: **{region_name}**", user_id, message_id, parse_mode='Markdown')

    if is_registration:
        # Если это регистрация, переходим к вводу города
        msg = bot.send_message(user_id, "Спасибо. Теперь введите название вашего **города или населенного пункта**.")
        bot.register_next_step_handler(msg, process_city_step)
    else:
        # Если это просто изменение данных через /change, обновляем БД и завершаем
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET region = ? WHERE user_id = ?', (region_name, user_id))
            conn.commit()
        bot.send_message(user_id, f"✅ Ваш регион успешно изменен на: **{region_name}**", parse_mode='Markdown', reply_markup=user_keyboard)
        
        # !!! ИСПРАВЛЕНИЕ: СБРАСЫВАЕМ ОБРАБОТЧИКИ ТОЛЬКО ЗДЕСЬ, В КОНЦЕ ПРОЦЕССА !!!
        bot.clear_step_handler_by_chat_id(user_id)

        # Очищаем временные данные, так как процесс завершен
        if user_id in bot.user_data:
            del bot.user_data[user_id]

# --- Обработчик выбора региона через Inline кнопки 

# Шаг 2: Получение города/населенного пункта
def process_city_step(message):
    user_id = message.chat.id
    # !!! ДОБАВЛЕНО ИСПРАВЛЕНИЕ: СБРАСЫВАЕМ ВСЕ ОЖИДАНИЯ ПЕРЕД ОБРАБОТКОЙ !!!
    bot.clear_step_handler_by_chat_id(user_id) 

    if message.text == '/cancel': 
        cancel_process(message)
        return
        
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название города текстом.")
        bot.register_next_step_handler(msg, process_city_step)
        return
        
    bot.user_data[user_id]['city'] = message.text
    
    msg = bot.send_message(user_id, "И последний шаг: пожалуйста, выберите **вашу должность** с помощью кнопок ниже:", reply_markup=role_keyboard)

@bot.message_handler(func=lambda message: message.text in ['Ученик (волонтер)', 'Куратор', 'Ответственное лицо'])
def handle_role_selection_button(message):
    process_role_step(message)

# Шаг 3: Получение должности и завершение регистрации
def process_role_step(message):
    user_id = message.chat.id
    # !!! ДОБАВЛЕНО ИСПРАВЛЕНИЕ: СБРАСЫВАЕМ ВСЕ ОЖИДАНИЯ ПЕРЕД ОБРАБОТКОЙ !!!
    bot.clear_step_handler_by_chat_id(user_id) 

    if message.text == '/cancel':
        cancel_process(message)
        return
        
    role = message.text
    
    if role not in ['Ученик (волонтер)', 'Куратор', 'Ответственное лицо']:
        msg = bot.send_message(user_id, "Пожалуйста, выберите должность, используя кнопки.", reply_markup=role_keyboard)
        # Если неверный ввод, мы снова ждем корректный ввод роли
        bot.register_next_step_handler(msg, process_role_step) 
        return

    user_data = bot.user_data.get(user_id, {})
    if 'region' not in user_data or 'city' not in user_data:
         bot.send_message(user_id, "Произошла ошибка регистрации. Пожалуйста, начните заново: /start", reply_markup=types.ReplyKeyboardRemove())
         return

    update_registration_data(
        user_id=user_id,
        region=user_data['region'],
        city=user_data['city'],
        role=role
    )
    
    if user_id in bot.user_data:
        del bot.user_data[user_id]
        
    # Используем user_keyboard
    bot.send_message(user_id, "Спасибо, регистрация завершена! 🎉 Теперь вам доступны основные функции бота. \nЧтобы посмотреть все мои команды: /help", reply_markup=user_keyboard)

@bot.message_handler(func=lambda message: message.content_type == 'text' and not message.text.startswith('/start') and not is_user_registered(message.chat.id))
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
        # Убедимся, что главный админ существует и может принять сообщение
        if MAIN_ADMIN_ID:
            bot.send_message(MAIN_ADMIN_ID, notification_text, reply_markup=markup)
    elif status == 'pending':
        bot.send_message(user_id, "Ваша заявка уже находится на рассмотрении. 👀")
    elif status == 'admin':
        bot.send_message(user_id, "У вас уже есть права администратора. ✅")

@bot.message_handler(commands=['view_content'])
def view_content(message):
    user_id = message.chat.id
    content_list = get_all_content_for_user(user_id) 
    if content_list:
        bot.send_message(user_id, "Последние записи (доступные вам): 👇", reply_markup=types.ReplyKeyboardRemove())

        for content in content_list:
            # ИСПРАВЛЕНИЕ: Ожидаем 4 значения, а не 5
            text, region, scope, content_id = content 
            scope_info = f"[{region} region only 🏠]" if scope == 'region' else "[For all 🌍]"
            
            markup = types.InlineKeyboardMarkup()
            btn_report = types.InlineKeyboardButton("Пожаловаться", callback_data=f"report_content_{content_id}")
            markup.add(btn_report)

            response_text = f"<b>{text}</b> <code>{scope_info}</code>"

            # Отправляем просто текст, без проверки photo_url
            bot.send_message(user_id, response_text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(user_id, "К сожалению, пока нет ни одной записи, доступной для вашего региона или всех пользователей.")


@bot.message_handler(commands=['add_content'])
def prompt_add_content(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    
    if status == 'admin':
        bot.clear_step_handler_by_chat_id(user_id) # Сброс обработчиков (это мы оставим)

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('Опубликовать для всех 🌍', 'Опубликовать только для моего региона 🏠')
        
        msg = bot.send_message(user_id, "Выберите область видимости, затем отправьте текст:", reply_markup=markup, parse_mode='Markdown')
        
        if user_id not in bot.user_data:
            bot.user_data[user_id] = {}
        bot.user_data[user_id]['adding_content'] = True
        
        # Переходим сразу к выбору области видимости, а потом к вводу текста
        bot.register_next_step_handler(msg, process_content_scope_step)
    else:
        bot.send_message(user_id, "У вас нет прав для добавления контента. 🚫")

# --- Команды для работы с мероприятиями ---
def process_content_scope_step(message):
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id) # Сбросим обработчик

    # --- ИСПРАВЛЕНИЕ ОШИБКИ KeyError: Проверка наличия временных данных ---
    if user_id not in bot.user_data or not bot.user_data[user_id].get('adding_content'):
        bot.send_message(user_id, "Данные о предыдущем действии утеряны. Пожалуйста, начните добавление контента заново: /add_content")
        # Очищаем временные данные, чтобы пользователь мог начать заново
        if user_id in bot.user_data: del bot.user_data[user_id]
        return
    # ---------------------------------------------------------------------

    scope_choice_text = message.text.lower()
    
    if 'для всех' in scope_choice_text:
        scope = 'all'
    elif 'моего региона' in scope_choice_text:
        scope = 'region'
    else:
        msg = bot.send_message(user_id, "Неверный выбор. Пожалуйста, используйте кнопки.")
        # Перерегистрируем тот же шаг, чтобы пользователь мог выбрать снова
        bot.register_next_step_handler(msg, process_content_scope_step) 
        return

    bot.user_data[user_id]['scope'] = scope
    
    # !!! ВОЗВРАЩАЕМСЯ К СТАРОЙ ЛОГИКЕ !!!
    msg = bot.send_message(user_id, f"Вы выбрали '{message.text}'. Теперь отправьте сам текст контента.", reply_markup=types.ReplyKeyboardRemove())
    # Регистрируем следующий шаг: process_content_step
    bot.register_next_step_handler(msg, process_content_step)

def get_event_by_code(code):
    """Получает детали мероприятия по коду регистрации."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Ищем активное мероприятие с таким кодом
        # (в идеале тут нужна проверка на дату, но пока просто ищем код)
        cursor.execute('SELECT id, title FROM events WHERE check_in_code = ?', (code,))
        result = cursor.fetchone()
    return result

def has_user_checked_in(user_id, event_id):
    """Проверяет, получил ли пользователь уже баллы за это мероприятие."""
    # Мы используем таблицу event_registrations для двойной проверки.
    # Если пользователь записан, мы считаем, что он может подтвердить участие.
    # Чтобы предотвратить двойное начисление баллов, мы могли бы создать новую таблицу 'checkins',
    # но пока будем считать, что регистрация + ввод кода = баллы.
    # Реальная защита от двойного начисления баллов сложнее и требует дополнительных проверок.
    pass # Пока оставим эту логику внутри process_checkin_code

def process_checkin_code(message):
    user_id = message.chat.id

    # >>> ИСПРАВЛЕНИЕ: Проверяем команду отмены <<<
    if message.text == '/cancel':
        # Вызываем вашу существующую функцию отмены
        cancel_process(message) 
        # Важно: cancel_process уже очистит bot.user_data[user_id], 
        # поэтому здесь мы просто выходим из функции.
        return
        
    if user_id not in bot.user_data or not bot.user_data[user_id].get('awaiting_checkin_code'): 
        # Если данные уже очищены функцией cancel_process, просто выходим
        return
    
    code = message.text.strip().upper() # Приводим код к верхнему регистру для сравнения

    event_data = get_event_by_code(code)

    if not event_data:
        bot.send_message(user_id, "❌ Неверный или устаревший код участия. Попробуйте еще раз или введите /cancel.")
        # Оставляем next_step_handler активным, чтобы пользователь мог попробовать снова
        bot.register_next_step_handler(message, process_checkin_code)
        return

    # ... (остальная логика проверки регистрации и начисления баллов остается прежней) ...

    event_id, event_title = event_data

    # УСЛОВИЕ 1: Пользователь должен быть зарегистрирован на мероприятие
    if not is_user_registered_for_event(user_id, event_id):
        bot.send_message(user_id, f"❌ Вы не зарегистрированы на мероприятие «{event_title}». Пожалуйста, сначала запишитесь через /view_events.")
        del bot.user_data[user_id]
        return

    # УСЛОВИЕ 2: Начисление баллов
    POINTS_FOR_CHECKIN = 3
    add_points(user_id, POINTS_FOR_CHECKIN)

    bot.send_message(user_id, 
                     f"🎉 Успешная регистрация на месте! Вы получили **{POINTS_FOR_CHECKIN} баллов** за участие в «{event_title}».",
                     parse_mode='Markdown')
    
    del bot.user_data[user_id]

def add_content_report(content_id, reporter_user_id, report_text):
    """Регистрирует новую жалобу на контент и возвращает ID отчета."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO content_reports (content_id, reporter_user_id, report_text) 
            VALUES (?, ?, ?)
        ''', (content_id, reporter_user_id, report_text))
        conn.commit()
        return cursor.lastrowid # Возвращаем ID новой записи


def process_event_title(message):
    user_id = message.chat.id
    # Не забываем про сброс обработчиков, который мы внедрили ранее
    bot.clear_step_handler_by_chat_id(user_id) 

    if user_id not in bot.user_data or not bot.user_data[user_id].get('creating_event'): return
    
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название текстом.")
        bot.register_next_step_handler(msg, process_event_title)
        return

    bot.user_data[user_id]['title'] = message.text
    msg = bot.send_message(user_id, "Введите **описание** мероприятия:")
    bot.register_next_step_handler(msg, process_event_description)


@bot.message_handler(commands=['create_event'])
def prompt_create_event(message):
    user_id = message.chat.id
    if get_user_status(user_id) != 'admin':
        bot.send_message(user_id, "У вас нет прав администратора для создания мероприятий.")
        return

    region = get_user_region(user_id)
    if not region:
        bot.send_message(user_id, "Не удалось определить ваш регион. Обновите профиль через /change")
        return
    
    bot.clear_step_handler_by_chat_id(user_id) # Сброс обработчиков

    # Сохраняем регион в user_data для следующих шагов
    bot.user_data[user_id] = {'creating_event': True, 'region': region}
    
    # Сразу просим ввести название, без запроса фото
    msg = bot.send_message(user_id, f"Начинаем создание мероприятия для региона **{region}**. Введите **название/заголовок** мероприятия:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_event_title)

def process_event_description(message):
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
        # Также достаем ID автора контента для удобства
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
    """Удаляет контент и все связанные с ним жалобы."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM content WHERE id = ?', (content_id,))
        cursor.execute('DELETE FROM content_reports WHERE content_id = ?', (content_id,))
        conn.commit()

def process_report_reason(message):
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id) # Сброс обработчика

    if user_id not in bot.user_data or 'reporting_content_id' not in bot.user_data[user_id]:
        bot.send_message(user_id, "Произошла ошибка при подаче жалобы. Попробуйте снова /view_content.")
        return

    content_id = bot.user_data[user_id]['reporting_content_id']
    report_text = message.text
    reporter_username = message.from_user.username or f"ID: {user_id}"

    # Сохраняем жалобу в БД и получаем ее ID
    report_id = add_content_report(content_id, user_id, report_text)

    bot.send_message(user_id, "✅ Ваша жалоба принята и отправлена на рассмотрение модераторам.")

    # >>> УВЕДОМЛЕНИЕ ГЛАВНОГО АДМИНИСТРАТОРА <<<
    if MAIN_ADMIN_ID:
        notification_message = (
            f"<b>🚨 НОВАЯ ЖАЛОБА #{report_id} НА КОНТЕНТ #{content_id} 🚨</b>\n\n"
            f"От пользователя: @{reporter_username}\n"
            f"Причина: {report_text}\n"
        )
        
        markup = types.InlineKeyboardMarkup()
        # Кнопки для модерации в админ-панели
        btn_view = types.InlineKeyboardButton("Посмотреть в панели", callback_data="admin_view_reports")
        markup.add(btn_view)

        try:
            bot.send_message(MAIN_ADMIN_ID, notification_message, parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            print(f"Ошибка при отправке уведомления админу {MAIN_ADMIN_ID}: {e}")

    # Очищаем данные пользователя
    del bot.user_data[user_id]

def process_event_date(message):
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    if user_id not in bot.user_data: return
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректную дату/время текстом.")
        bot.register_next_step_handler(msg, process_event_date)
        return

    bot.user_data[user_id]['date'] = message.text
    msg = bot.send_message(user_id, "Введите **место проведения** (адрес или координаты):")
    bot.register_next_step_handler(msg, process_event_location)

def generate_check_in_code(length=6):
    """Генерирует случайный 6-значный буквенно-цифровой код."""
    # Используем только заглавные буквы и цифры для легкости ввода
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for i in range(length))

def process_event_location(message):
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    user_data = bot.user_data[user_id]
    
    check_in_code = generate_check_in_code()
    # Проверка, что данные существуют и это текст, не команда
    if user_id not in bot.user_data or message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Неверный ввод. Введите **место проведения** текстом.")
        if user_id in bot.user_data:
             if 'date' not in bot.user_data[user_id]:
                  bot.send_message(user_id, "Ошибка в предыдущих данных, начните заново: /create_event")
                  del bot.user_data[user_id]
                  return
             bot.register_next_step_handler(msg, process_event_location)
        return
        
    bot.user_data[user_id]['location'] = message.text 
    user_data = bot.user_data[user_id]
    
    # >>>>> НОВОЕ: ГЕНЕРИРУЕМ КОД ПРОВЕРКИ <<<<<
    check_in_code = generate_check_in_code()

    create_event(
        title=user_data['title'],
        description=user_data['description'],
        region=user_data['region'],
        event_date=user_data['date'],
        location=user_data['location'],
        creator_id=user_id,
        check_in_code=check_in_code
    )

    bot.send_message(user_id, 
                     f"🎉 Мероприятие успешно создано и доступно пользователям в вашем регионе!\n\n"
                     f"🔑 **КОД ПРОВЕРКИ УЧАСТИЯ:** `{check_in_code}`\n\n"
                     f"Сообщите этот код участникам на мероприятии, чтобы они могли получить баллы через команду /checkin",
                     parse_mode='Markdown')
                     
    del bot.user_data[user_id]

@bot.message_handler(commands=['view_events'])
def prompt_view_events_choice(message):
    user_id = message.chat.id
    region = get_user_region(user_id)

    if not region:
        bot.send_message(user_id, "Чтобы просматривать мероприятия, пожалуйста, укажите свой регион в /start или /change.")
        return
        
    markup = types.InlineKeyboardMarkup()
    btn_new = types.InlineKeyboardButton("Актуальные (Новые) 🌳", callback_data=f"view_events_new_{region}")
    btn_old = types.InlineKeyboardButton("Прошедшие (Старые) ⏳", callback_data=f"view_events_old_{region}")
    markup.add(btn_new, btn_old)

    bot.send_message(user_id, f"В регионе {region}. Какие мероприятия показать?", reply_markup=markup)

# >>>>> НОВЫЙ ОБРАБОТЧИК CALLBACK ДЛЯ КНОПОК ВЫБОРА <<<<<
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_events_'))
def display_events_list(user_id, region, view_mode):
    events_list = get_events_for_region(region, view_mode)
    title_text = "Актуальные мероприятия" if view_mode == 'new' else "Прошедшие мероприятия"
    if events_list:
        bot.send_message(user_id, f"🌳 {title_text} в вашем регионе ({region}):", reply_markup=types.ReplyKeyboardRemove())
        for event in events_list:
            event_id, title, description, date, location = event
            response = (f"**{title}**\n\n"f"🗓️ **Дата/Время:** {date}\n"f"📍 **Место:** {location}\n\n"f"{description[:200]}...")
            markup = types.InlineKeyboardMarkup()
            if view_mode == 'new':
                 if not is_user_registered_for_event(user_id, event_id):
                    btn_register = types.InlineKeyboardButton("Я пойду! Записаться ✅", callback_data=f"register_event_{event_id}")
                    markup.add(btn_register)
                 else:
                    btn_cancel = types.InlineKeyboardButton("Отменить запись ❌", callback_data=f"cancel_event_registration_{event_id}")
                    markup.add(btn_cancel)
            else:
                 btn_info = types.InlineKeyboardButton("Мероприятие завершено 🚫", callback_data="ignore")
                 markup.add(btn_info)
            bot.send_message(user_id, response, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(user_id, f"К сожалению, {title_text.lower()} в регионе {region} пока нет.")


def choose_input_method_step(message):
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    if user_id not in bot.user_data or not bot.user_data[user_id].get('awaiting_points_method'): return

    if 'id' in message.text.lower():
        method = 'id'
        prompt_text = "Вы выбрали ввод по ID. Введите ID пользователя и баллы (пример: `123456789 50`):"
    elif 'username' in message.text.lower():
        method = 'username'
        prompt_text = "Вы выбрали ввод по Username. Введите Username и баллы (пример: `@username 50`):"
    else:
        msg = bot.send_message(user_id, "Неверный выбор. Пожалуйста, используйте кнопки.")
        bot.register_next_step_handler(msg, choose_input_method_step)
        return

    bot.user_data[user_id]['method'] = method
    msg = bot.send_message(user_id, prompt_text, reply_markup=types.ReplyKeyboardRemove(), parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_award_points)


def process_content_step(message):
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return

    # --- ИСПРАВЛЕНИЕ ОШИБКИ KeyError: Проверка наличия временных данных ---
    if user_id not in bot.user_data or 'scope' not in bot.user_data[user_id]:
        bot.send_message(user_id, "Данные о предыдущем действии утеряны. Пожалуйста, начните добавление контента заново: /add_content")
        # Очищаем временные данные, чтобы пользователь мог начать заново
        if user_id in bot.user_data: del bot.user_data[user_id]
        return
    
    if not is_user_registered(message.chat.id):
         bot.send_message(message.chat.id, "Пожалуйста, завершите регистрацию: /start")
         if user_id in bot.user_data: del bot.user_data[user_id]
         return
         
    content_text = message.text
    author_id = message.chat.id
    
    scope = bot.user_data[author_id]['scope']
    region = get_user_region(author_id) if scope == 'region' else None

    add_content(content_text, author_id, scope, region)
    bot.send_message(author_id, "Контент успешно добавлен и теперь доступен пользователям. ✅", reply_markup=types.ReplyKeyboardRemove())
    
    # Очищаем данные пользователя полностью после завершения процесса
    if user_id in bot.user_data:
        del bot.user_data[user_id]

# --- 4. Обработчики команд администратора (ИСПРАВЛЕНО) ---

@bot.message_handler(commands=['admin_panel'])
def admin_panel(message):
    user_id = message.chat.id
    status = get_user_status(user_id)

    if status == 'admin':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_requests = types.KeyboardButton('Посмотреть заявки на админа 👀')
        btn_list_admins = types.KeyboardButton('Список администраторов 👥')
        btn_add_content = types.KeyboardButton('Добавить контент ✍️')
        btn_send_notification = types.KeyboardButton('Отправить оповещение по региону 📣')
        btn_add_faq = types.KeyboardButton('Добавить вопрос в FAQ ❓')
        markup.add(btn_add_faq) # Добавьте кнопку в клавиатуру
        markup.add(btn_requests, btn_list_admins, btn_add_content, btn_send_notification)
        bot.send_message(user_id, "Добро пожаловать в админ-панель: 👇", reply_markup=markup)
    else:
        bot.send_message(user_id, "У вас нет доступа к админ-панели. 🚫")

@bot.message_handler(commands=['send_notification', 'send'])
def prompt_send_notification(message):
    user_id = message.chat.id
    if get_user_status(user_id) != 'admin':
        bot.send_message(user_id, "У вас нет прав для рассылки уведомлений. 🚫")
        return
    
    region = get_user_region(user_id)
    if not region:
        bot.send_message(user_id, "Не удалось определить ваш регион для рассылки. 🏠")
        return

    msg = bot.send_message(user_id, f"Вы будете отправлять сообщение пользователям в регионе **{region}**. Введите текст оповещения:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_send_notification_step, region)

def process_send_notification_step(message, region):
    notification_text = message.text
    user_ids = get_users_in_region(region)
    
    if not user_ids:
        bot.send_message(message.chat.id, f"В регионе {region} нет пользователей, которым можно отправить оповещение.")
        return
        
    sent_count = 0
    for target_user_id in user_ids:
        try:
            # Не отправляем самому себе
            if target_user_id == message.chat.id:
                continue
            bot.send_message(target_user_id, f"**[Уведомление из вашего региона - {region}]**\n\n{notification_text}", parse_mode='Markdown')
            sent_count += 1
        except Exception as e:
            print(f"Ошибка при отправке пользователю {target_user_id}: {e}")
            
    bot.send_message(message.chat.id, f"Оповещение отправлено {sent_count} пользователям в регионе {region}. ✅")

# ИСПРАВЛЕНИЕ ОШИБКИ #1 & #2: Заменяем универсальный admin_text_handler на точечные обработчики кнопок
@bot.message_handler(func=lambda message: message.text == 'Посмотреть заявки на админа 👀' and get_user_status(message.chat.id) == 'admin')
def handle_view_pending_requests_button(message):
    view_pending_requests(message)

@bot.message_handler(func=lambda message: message.text == 'Список администраторов 👥' and get_user_status(message.chat.id) == 'admin')
def handle_view_admin_list_button(message):
    view_admin_list(message)

@bot.message_handler(func=lambda message: message.text == 'Добавить контент ✍️' and get_user_status(message.chat.id) == 'admin')
def handle_add_content_button(message):
    # Вызываем уже существующую функцию
    prompt_add_content(message)

@bot.message_handler(func=lambda message: message.text == 'Отправить оповещение по региону 📣' and get_user_status(message.chat.id) == 'admin')
def handle_send_notification_button(message):
    # Вызываем уже существующую функцию
    prompt_send_notification(message)

@bot.message_handler(func=lambda message: message.text == 'Добавить вопрос в FAQ ❓' and get_user_status(message.chat.id) == 'admin')
def handle_add_faq_button(message):
    prompt_add_faq(message)

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
        # Сложный SQL-запрос для определения позиции в рейтинге
        cursor.execute('''
            SELECT rank FROM (
                SELECT user_id, RANK() OVER (ORDER BY points DESC) as rank
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
                SELECT user_id, RANK() OVER (ORDER BY points DESC) as rank
                FROM users
                WHERE is_registered = 1 AND status != 'banned' AND region = ?
            ) AS ranked_users
            WHERE user_id = ?
        ''', (region, user_id))
        result = cursor.fetchone()
    return result[0] if result else None


# ИСПРАВЛЕНИЕ ОШИБКИ #4: Реализация кнопок "Лишить прав"
def view_admin_list(message):
    admins = get_all_admins()
    if admins:
        bot.send_message(message.chat.id, "Текущие администраторы: 👥", reply_markup=types.ReplyKeyboardRemove())
        for admin in admins:
            user_id, username = admin
            if user_id != MAIN_ADMIN_ID:
                markup = types.InlineKeyboardMarkup()
                btn_demote = types.InlineKeyboardButton(f"Лишить прав {username} ❌", callback_data=f"demote_{user_id}")
                markup.add(btn_demote)
                bot.send_message(message.chat.id, f"- @{username} (ID: {user_id})", reply_markup=markup)
            else:
                 bot.send_message(message.chat.id, f"- @{username} (ID: {user_id}) (Главный админ 👑)")
    else:
        bot.send_message(message.chat.id, "Кроме вас, администраторов нет.")

def get_user_id_by_username(username):
    """Получает user_id по username."""
    clean_username = username.lstrip('@') 
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE username LIKE ?', (clean_username,))
        result = cursor.fetchone()
    return result # result будет None или кортеж, например (12345,)

def process_admin_reply_step(message):
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

    # Используем вашу функцию отправки ответа, которую вы уже определили ранее
    # (Она называлась send_report_to_admin или prompt_admin_reply в ваших предыдущих частях)
    # Предполагаю, что ваша функция называется prompt_admin_reply:
    # prompt_admin_reply(message, target_user_id) # Это был бы вызов

    # Или напрямую вызываем логику отправки:
    try:
        bot.send_message(target_user_id, f"<b>✉️ Ответ от администратора:</b>\n\n{reply_text}", parse_mode='HTML')
        bot.send_message(user_id, f"✅ Ответ успешно отправлен пользователю ID {target_user_id}.")
    except Exception as e:
        bot.send_message(user_id, f"❌ Не удалось отправить ответ пользователю ID {target_user_id}.")
        print(f"Error sending admin reply: {e}")
        
    # Очищаем временные данные
    if user_id in bot.user_data:
        del bot.user_data[user_id]


# --- 5. Обработка Inline кнопок (Одобрение/Отклонение/Лишение прав/Ответ/Удаление контента/Регистрация на ивент) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id, "Обработка запроса...") 
    
    # --- ЛОГИКА СВЯЗИ С КУРАТОРОМ ---
    if call.data.startswith('contact_curator_'):
        try:
            data_parts = call.data.split('_')
            curator_id = int(data_parts[-1]) 
            msg = bot.send_message(user_id, f"Вы собираетесь написать куратору. Введите ваше сообщение:")
            bot.user_data[user_id] = {'contacting_curator': True, 'curator_id': curator_id}
            bot.register_next_step_handler(msg, process_send_message_to_curator)
        except (IndexError, ValueError):
            bot.send_message(user_id, "Произошла ошибка при определении куратора.")
        return

    # >>>>> ДОБАВИТЬ ЭТОТ БЛОК ДЛЯ ПРОСМОТРА МЕРОПРИЯТИЙ <<<<<
    if call.data.startswith('view_events_'):
        try:
            parts = call.data.split('_')
            view_mode = parts
            # region_name может содержать пробелы, поэтому нужно объединить оставшиеся части
            region_name = '_'.join(parts)

            # Вызываем существующую функцию display_events_list
            display_events_list(user_id, region_name, view_mode)
            
        except (IndexError, ValueError):
            bot.send_message(user_id, "Произошла ошибка при обработке запроса мероприятий.")
        return # Выходим из хэндлера
    if call.data.startswith('select_region_'):
        try:
            region_index = int(call.data.split('_')) 
            if 0 <= region_index < len(RUSSIAN_SUBJECTS):
                region = RUSSIAN_SUBJECTS[region_index]
                finalize_region_selection(user_id, region, call.message.message_id)
            else:
                bot.send_message(user_id, "Извините, ошибка при выборе региона.")
        except (IndexError, ValueError):
            bot.send_message(user_id, "Произошла ошибка при обработке выбора региона.")
        return # Выходим из хэндлера
    
    # --- ЛОГИКА ОТВЕТА АДМИНА/КУРАТОРА ---
    if call.data.startswith('reply_'):
        try:
            data_parts = call.data.split('_')
            target_user_id = int(data_parts[-1])
            msg = bot.send_message(user_id, f"Вы отвечаете пользователю ID {target_user_id}. Введите текст сообщения:")
            bot.user_data[user_id] = {'awaiting_admin_reply': True, 'target_user_id': target_user_id}
            bot.register_next_step_handler(msg, process_admin_reply_step)
        except (IndexError, ValueError):
            bot.send_message(user_id, "Произошла ошибка при подготовке ответа.")
        return

    # --- ЛОГИКА ПОДТВЕРЖДЕНИЯ ДЕЙСТВИЯ (confirm_ / deny_) ---
    if call.data.startswith('confirm_'):
        parts = call.data.split('_')
        action_type = parts[1]
        target_id = int(parts[2]) 
        execute_action(user_id, action_type, target_id, call.message)
        return

    elif call.data.startswith('deny_'):
        bot.edit_message_text(f"{call.message.text}\n\n❌ Действие отменено администратором.", 
                              chat_id=user_id, message_id=call.message.message_id, reply_markup=None)
        return

    # --- (Весь остальной код callback_handler) ---
    try:
        data_parts = call.data.split('_')
        action_type = data_parts[0] 
        target_id = int(data_parts[-1]) 
    except (IndexError, ValueError):
        return

    # --- Логика жалоб на контент ---
    if action_type == 'report' and len(data_parts) > 1 and data_parts[1] == 'content':
        content_id = target_id
        reporter_id = call.message.chat.id
        msg = bot.send_message(reporter_id, "Опишите причину вашей жалобы на этот пост:")
        bot.user_data[reporter_id] = {'reporting_content_id': content_id}
        bot.register_next_step_handler(msg, process_report_reason)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)

    # --- Логика регистрации на ивент / отмены записи ---
    elif action_type == 'register' and len(data_parts) > 1 and data_parts[1] == 'event':
        execute_action(user_id, action_type, target_id, call.message)
        
    elif action_type == 'cancel' and len(data_parts) > 2 and data_parts[1] == 'event' and data_parts[2] == 'registration':
        event_id = target_id
        current_user_id = call.message.chat.id
        if delete_event_registration(current_user_id, event_id):
            bot.send_message(current_user_id, f"❌ Ваша запись на мероприятие #{event_id} отменена.")
            bot.edit_message_reply_markup(chat_id=current_user_id, message_id=call.message.message_id, reply_markup=None)
        else:
            bot.send_message(current_user_id, "Произошла ошибка при отмене записи или вы не были записаны.")    
            
    elif action_type == 'ignore':
        pass 
        
    # --- Логика модерации админом (удаление контента) ---
    elif call.data.startswith('moderate_delete_'):
        parts = call.data.split('_')
        content_id = int(parts)
        report_id = int(parts)
        delete_content_and_reports(content_id)
        bot.edit_message_text(f"{call.message.text}\n\n✅ Контент и связанные жалобы удалены.", chat_id=user_id, message_id=call.message.message_id, reply_markup=None, parse_mode='Markdown')

    # --- Логика модерации админом (отклонение жалобы) ---
    elif call.data.startswith('moderate_dismiss_'):
        parts = call.data.split('_')
        report_id = int(parts) 
        update_report_status(report_id, 'dismissed')
        bot.edit_message_text(f"{call.message.text}\n\n✅ Жалоба отклонена (статус обновлен).", chat_id=user_id, message_id=call.message.message_id, reply_markup=None, parse_mode='Markdown')
    
    # --- Просмотр оригинала поста из админ-панели ---
    elif call.data.startswith('view_original_post_'):
        bot.send_message(user_id, f"Здесь будет логика просмотра оригинального поста #{target_id}")

    # --- Открытие панели отчетов из уведомления ---
    elif call.data == 'admin_view_reports':
        view_pending_reports_panel(call.message)

def process_set_user_role(message):
    user_id = message.chat.id
    
    if message.text == '/cancel':
        cancel_process(message)
        return
        
    try:
        parts = message.text.split(maxsplit=1)
        target_user_id_str = parts[0]
        new_role_or_status = parts[1].strip()
        target_user_id = int(target_user_id_str)
    except (ValueError, IndexError):
        bot.send_message(user_id, "Неверный формат ввода. Используйте формат: `ID_ПОЛЬЗОВАТЕЛЯ Новая_роль`")
        bot.register_next_step_handler(message, process_set_user_role)
        return
    
    # >>>>> ВАЖНАЯ ПРОВЕРКА: Не даем менять роль главному админу <<<<<
    if target_user_id == MAIN_ADMIN_ID and user_id != MAIN_ADMIN_ID:
        bot.send_message(user_id, "Вы не можете изменить роль или статус главного администратора!")
        bot.clear_step_handler_by_chat_id(user_id)
        return

    # Список допустимых ролей и статусов, которые можно менять этой командой
    allowed_roles = ['Ученик (волонтер)', 'Куратор', 'Ответственное лицо']
    allowed_statuses = ['user', 'admin']

    if new_role_or_status in allowed_roles:
        # Обновляем именно колонку 'role' в таблице users
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET role = ? WHERE user_id = ?', (new_role_or_status, target_user_id))
            conn.commit()
        
        bot.send_message(user_id, f"✅ Роль пользователя ID {target_user_id} успешно обновлена на **{new_role_or_status}**.", parse_mode='Markdown')
        try:
            bot.send_message(target_user_id, f"👤 Ваш статус был изменен администратором на: **{new_role_or_status}**.", parse_mode='Markdown')
        except: pass

    elif new_role_or_status in allowed_statuses:
        # Обновляем именно колонку 'status'
        update_user_status(target_user_id, new_role_or_status)

        bot.send_message(user_id, f"✅ Статус пользователя ID {target_user_id} успешно обновлен на **{new_role_or_status}**.", parse_mode='Markdown')
        try:
            bot.send_message(target_user_id, f"👤 Ваш статус был изменен администратором на: **{new_role_or_status}**.", parse_mode='Markdown')
        except: pass
    
    else:
        bot.send_message(user_id, "Неверная или недопустимая роль/статус.")

    bot.clear_step_handler_by_chat_id(user_id)

@bot.message_handler(commands=['leaderboard_global', 'top_global'])
def display_global_leaderboard(message):
    user_id = message.chat.id
    if not is_user_registered(user_id):
        enforce_registration(message)
        return

    top_list = get_top_volunteers(region=None) # Получаем глобальный топ-10
    
    if top_list:
        response = "🏆 **Топ 10 волонтеров (Глобальный рейтинг)**:\n\n"
        for i, (username, points) in enumerate(top_list, 1):
            response += f"{i}. @{username}: {points} баллов\n"
        
        # Проверяем, есть ли пользователь в топ-10
        is_in_top_10 = any(user_id == get_user_id_by_username(u) for u, p in top_list)
        
        if not is_in_top_10:
            # Если нет в топ-10, показываем его личное место
            user_rank = get_user_global_rank(user_id)
            if user_rank is not None:
                response += f"\n--------------------------\n"
                response += f"👤 Ваше место: **#{user_rank}**"

        bot.send_message(user_id, response, parse_mode='Markdown')
    else:
        bot.send_message(user_id, "Глобальный рейтинг пока пуст.")


@bot.message_handler(commands=['set_role'])
def prompt_set_user_role(message):
    user_id = message.chat.id
    # Проверяем, что у пользователя статус 'admin'
    if get_user_status(user_id) != 'admin':
        bot.send_message(user_id, "У вас нет прав для выполнения этой команды.")
        return

    msg = bot.send_message(user_id, 
                           "Введите ID пользователя и новую роль через пробел.\n\n"
                           "Доступные роли: `Ученик (волонтер)`, `Куратор`, `Ответственное лицо`, `user` (для обычного статуса), `admin` (для статуса администратора). \n\n"
                           "Пример: `123456789 Куратор`",
                           parse_mode='Markdown')

    bot.register_next_step_handler(msg, process_set_user_role)

def process_send_message_to_curator(message):
    user_id = message.chat.id

    if message.text == '/cancel':
        cancel_process(message)
        return

    user_data = bot.user_data.get(user_id, {})
    
    # >>>>> ПЕРЕНОСИМ ВСЮ ЛОГИКУ ВНУТРЬ ЭТОГО БЛОКА <<<<<
    if user_data.get('contacting_curator') and 'curator_id' in user_data:
        curator_id = user_data['curator_id']
        message_text = message.text
        username = message.from_user.username or f"ID: {user_id}"

        # Отправляем сообщение куратору (переменная message_text теперь определена)
        notification_message = (
            f"<b>✉️ НОВОЕ СООБЩЕНИЕ КУРАТОРУ ✉️</b>\n\n"
            f"От пользователя: @{username} (ID: {user_id})\n\n"
            f"<b>Сообщение:</b>\n{message_text}"
        )

        markup = types.InlineKeyboardMarkup()
        btn_reply = types.InlineKeyboardButton("Ответить пользователю", callback_data=f"reply_{user_id}") 
        markup.add(btn_reply)

        try:
            bot.send_message(curator_id, notification_message, parse_mode='HTML', reply_markup=markup)
            bot.send_message(user_id, "✅ Ваше сообщение успешно отправлено куратору.")
        except Exception as e:
            bot.send_message(user_id, "❌ Произошла ошибка при отправке сообщения куратору. Возможно, он заблокировал бота.")
            print(f"Error sending message to curator {curator_id}: {e}")
        finally:
            # Очищаем временные данные
            if user_id in bot.user_data:
                del bot.user_data[user_id]
                
    else:
        # Если условие не выполнилось, просто сообщаем об ошибке и выходим
        bot.send_message(user_id, "Произошла ошибка сессии. Начните снова через /profile -> Связаться с куратором.")
        if user_id in bot.user_data:
            del bot.user_data[user_id]




def confirm_action_prompt(message, action, target_id):
    """Отправляет сообщение с запросом подтверждения необратимого действия."""
    markup = types.InlineKeyboardMarkup()
    # Callback data теперь содержит префикс confirm_ или deny_, чтобы callback_handler знал, что делать
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
    print(f"!!! execute_action CALLED !!! User: {user_id}, Action: {action}, Target: {target_id}") # Отладочное сообщение
    
    # Убираем кнопки подтверждения из предыдущего сообщения
    bot.edit_message_reply_markup(chat_id=user_id, message_id=message_obj.message_id, reply_markup=None)
    

    if action == 'approve':
        update_user_status(target_id, 'admin')
        try: bot.send_message(target_id, "🎉 Поздравляем! Ваша заявка одобрена, вы получили права администратора.")
        except: pass
        bot.send_message(user_id, f"✅ Заявка ID {target_id} одобрена.")
        # !!! ДОБАВЛЕНО: Удаляем оригинальное сообщение с запросом !!!
        bot.delete_message(user_id, message_obj.message_id)
    
    elif action == 'reject':
        update_user_status(target_id, 'user')
        try: bot.send_message(target_id, "❌ К сожалению, ваша заявка на администрирование была отклонена.")
        except: pass
        bot.send_message(user_id, f"❌ Отклонено.")
        # !!! ДОБАВЛЕНО: Удаляем оригинальное сообщение с запросом !!!
        bot.delete_message(user_id, message_obj.message_id)
    
    elif action == 'demote':
        if target_id == MAIN_ADMIN_ID: bot.send_message(user_id, "Невозможно лишить прав главного администратора!"); return
        if user_id != MAIN_ADMIN_ID: bot.send_message(user_id, "Только главный администратор может лишать других прав. 🚫"); return
        update_user_status(target_id, 'user')
        try: bot.send_message(target_id, "🚨 Внимание! Вы были лишены прав администратора главным администратором.")
        except: pass
        bot.send_message(user_id, f"✅ Пользователь ID {target_id} лишен прав администратора.")

    # --- Логика удаления контента ---
    elif action == 'delete' and get_user_status(user_id) == 'admin':
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
    # Проверяем, были ли удалены строки
    return cursor.rowcount > 0

def get_user_details(user_id):
    """Получает полную информацию о пользователе из БД."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username, region, city, role, status FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    return result

@bot.message_handler(commands=['manage_reports'])
def view_pending_reports_panel(message):
    user_id = message.chat.id
    if get_user_status(user_id) != 'admin': return
    
    reports = get_pending_reports()
    if not reports:
        bot.send_message(user_id, "Активных жалоб на контент нет. ✅")
        return

    bot.send_message(user_id, f"⬇️ **Ожидающие жалобы ({len(reports)} шт.):**", parse_mode='Markdown')

    for report_id, content_id, report_text, reporter_id, author_id in reports:
        markup = types.InlineKeyboardMarkup()
        btn_delete_content = types.InlineKeyboardButton("Удалить контент ❌", callback_data=f"moderate_delete_{content_id}_{report_id}")
        btn_dismiss_report = types.InlineKeyboardButton("Отклонить жалобу ✅", callback_data=f"moderate_dismiss_{report_id}")
        btn_view_original = types.InlineKeyboardButton("Посмотреть оригинал поста", callback_data=f"view_original_post_{content_id}")
        markup.add(btn_delete_content, btn_dismiss_report)
        markup.add(btn_view_original)

        bot.send_message(user_id, 
                         f"**Жалоба #{report_id}** (на пост #{content_id})\n"
                         f"Причина: {report_text}\n"
                         f"От: {reporter_id} | Автор поста: {author_id}", 
                         reply_markup=markup, parse_mode='Markdown')


@bot.message_handler(commands=['checkin'])
def prompt_checkin_code(message):
    user_id = message.chat.id
    if not is_user_registered(user_id):
        enforce_registration(message)
        return
        
    msg = bot.send_message(user_id, "Введите **код участия** мероприятия, который вам предоставил организатор:")
    # Сохраняем состояние, что пользователь ожидает ввода кода
    bot.user_data[user_id] = {'awaiting_checkin_code': True}
    bot.register_next_step_handler(msg, process_checkin_code)

@bot.message_handler(commands=['profile'])
def view_profile(message):
    user_id = message.chat.id
    details = get_user_details(user_id)
    
    if details:
        username, region, city, role, status = details
        points = get_user_points(user_id)
        
        # Получаем историю мероприятий
        history = get_user_event_history(user_id, limit=3)

        response = (
            f"👤 Ваш профиль:\n"
            f"--------------------------\n"
            f"ID: <code>{user_id}</code>\n"
            f"Ник: @{username}\n"
            f"Статус: {status}\n"
            f"Роль: {role}\n"
            f"Регион: {region}\n"
            f"Город: {city}\n"
            f"<b>Баллы:</b> {points}\n"
            f"--------------------------\n"
        )
        
        if history:
            response += f"\n🗓️ <b>Последние мероприятия:</b>\n"
            for title, date in history:
                response += f"— <i>{title}</i> ({date})\n"
        else:
            response += f"\n🗓️ Вы пока не участвовали ни в одном мероприятии.\n"

        response += f"\nЧтобы изменить данные: /change"

        # >>>>> НОВОЕ: Добавляем кнопку связи с куратором <<<<<
        markup = types.InlineKeyboardMarkup() # Инициализируем markup здесь
        if region:
            curators_list = get_curators_in_region(region)
            if curators_list:
                # !!! ИСПРАВЛЕНИЕ ЗДЕСЬ !!!
                # first_curator_id теперь содержит числовой ID пользователя
                first_curator_id = curators_list[0][0] 
                # Используем first_curator_id в callback_data
                btn_curator = types.InlineKeyboardButton("✉️ Связаться с куратором", callback_data=f"contact_curator_{first_curator_id}")
                markup.add(btn_curator)
            
        # Отправляем сообщение с кнопкой, если она была добавлена
        bot.send_message(user_id, response, parse_mode='HTML', reply_markup=markup if markup.keyboard else None)
    
    else:
        bot.send_message(user_id, "Произошла ошибка при получении данных профиля. Попробуйте /start.")


@bot.message_handler(commands=['award_points'])
def prompt_award_points(message):
    user_id = message.chat.id
    status = get_user_status(user_id)

    # Проверяем права администратора/куратора
    if status == 'admin' or (get_user_details(user_id) and get_user_details(user_id)[3] == 'Куратор'): 
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('Использовать User ID (цифры) 🔢', 'Использовать Username (@логин) 👤')
        
        msg = bot.send_message(user_id, "Выберите способ ввода данных пользователя:", reply_markup=markup)
        
        # Сохраняем состояние для следующего шага
        bot.user_data[user_id] = {'awaiting_points_method': True}
        bot.register_next_step_handler(msg, choose_input_method_step)
    else:
        bot.send_message(user_id, "У вас нет прав для начисления или списания баллов.")


def process_award_points(message):
    user_id = message.chat.id # ID администратора, который начисляет баллы
    user_data = bot.user_data.get(user_id, {})
    input_method = user_data.get('method')

    if not input_method:
        bot.send_message(user_id, "Произошла ошибка, начните заново: /award_points")
        if user_id in bot.user_data: del bot.user_data[user_id]
        return

    try:
        parts = message.text.split()
        identifier = parts[0]
        points_to_add = int(parts[1])
    except (ValueError, IndexError):
        bot.send_message(user_id, "Неверный формат ввода. Попробуйте снова: /award_points")
        bot.register_next_step_handler(message, process_award_points)
        return
    
    # --- ДОБАВЛЕНО ОГРАНИЧЕНИЕ 1: Максимум 20 баллов за раз ---
    if points_to_add > 20 or points_to_add < -20:
        bot.send_message(user_id, "❌ Невозможно начислить или списать более 20 баллов за одну операцию.")
        if user_id in bot.user_data: del bot.user_data[user_id]
        return
    
    # Определяем ID пользователя в зависимости от метода ввода
    target_user_id = None
    if input_method == 'id':
        try: target_user_id = int(identifier)
        except ValueError:
            bot.send_message(user_id, "Неверный формат ID. Попробуйте снова: /award_points"); return
    elif input_method == 'username':
        user_record = get_user_id_by_username(identifier)
        if user_record: target_user_id = user_record[0]
    
    if not target_user_id or get_user_status(target_user_id) == 'new':
        bot.send_message(user_id, f"Пользователь с указанным ID/Username не найден или не зарегистрирован.")
        if user_id in bot.user_data: del bot.user_data[user_id]
        return

    # --- ДОБАВЛЕНО ОГРАНИЧЕНИЕ 2: Проверка дневного лимита админа ---
    # Мы проверяем лимит только если баллы начисляются (положительное число)
    if points_to_add > 0:
        if not check_and_update_admin_limit(user_id, points_to_add):
            bot.send_message(user_id, f"❌ Извините, вы превысили свой дневной лимит (150 баллов) на начисление баллов сегодня.")
            if user_id in bot.user_data: del bot.user_data[user_id]
            return

    # Если все проверки пройдены:
    add_points(target_user_id, points_to_add)
    
    if points_to_add >= 0:
        bot.send_message(user_id, f"✅ Пользователю {identifier} (ID: {target_user_id}) начислено {points_to_add} баллов.")
        notification_message = f"🎉 Вам начислено {points_to_add} баллов за вашу активность!"
    else:
        bot.send_message(user_id, f"✅ У пользователя {identifier} (ID: {target_user_id}) списано {abs(points_to_add)} баллов.")
        notification_message = f"💸 С вашего счета списано {abs(points_to_add)} баллов."
    
    try:
        bot.send_message(target_user_id, notification_message)
    except Exception as e:
        print(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
        
    if user_id in bot.user_data: del bot.user_data[user_id]


@bot.message_handler(commands=['cancel'])
def cancel_process(message):
    user_id = message.chat.id

    # Проверяем, находится ли пользователь в каком-либо многоступенчатом процессе
    if user_id in bot.user_data:
        # Очищаем все временные данные для этого пользователя
        del bot.user_data[user_id]
        
        bot.send_message(user_id, "❌ Текущее действие отменено. Вы вернулись в основное меню.", 
                         reply_markup=types.ReplyKeyboardRemove())
        
        # Если пользователь был админом, можно сразу показать админ-панель
        status = get_user_status(user_id)
        if status == 'admin':
            admin_panel(message)
    else:
        bot.send_message(user_id, "Вы сейчас не выполняете ни одну команду, которую можно отменить.")


@bot.message_handler(commands=['change'])
def prompt_change_data(message):
    user_id = message.chat.id
    if not is_user_registered(user_id):
        enforce_registration(message)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_region = types.KeyboardButton('/edit_region Изменить регион')
    btn_city = types.KeyboardButton('/edit_city Изменить город')
    markup.add(btn_region, btn_city)
    bot.send_message(user_id, "Что вы хотите изменить?", reply_markup=markup)

@bot.message_handler(commands=['edit_region'])
def edit_region_prompt(message):
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id)
    
    msg = bot.send_message(user_id, 
                           "Введите **название** вашего нового **региона** (можно ввести только первую букву или часть названия):", 
                           reply_markup=types.ReplyKeyboardRemove(),
                           parse_mode='Markdown')
                           
    # Используем ту же функцию обработки, что и при регистрации
    bot.register_next_step_handler(msg, process_region_text_input)


@bot.message_handler(commands=['edit_city'])
def edit_city_prompt(message):
    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id)
    
    msg = bot.send_message(user_id, "Введите новое название вашего **города/населенного пункта**:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_new_city)


def process_new_city(message):
    user_id = message.chat.id
    # !!! ДОБАВЛЕНО ИСПРАВЛЕНИЕ: СБРАСЫВАЕМ ВСЕ ОЖИДАНИЯ !!!
    bot.clear_step_handler_by_chat_id(user_id)

    if message.text == '/cancel':
        cancel_process(message)
        return

    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название города текстом.")
        bot.register_next_step_handler(msg, process_new_city)
        return

    new_city = message.text
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET city = ? WHERE user_id = ?', (new_city, user_id))
        conn.commit()
    bot.send_message(user_id, f"✅ Ваш город успешно изменен на: **{new_city}**", parse_mode='Markdown')

# --- Функция жалоб главному админу ---
@bot.message_handler(commands=['report_admin'])
def report_to_admin_prompt(message):
    user_id = message.chat.id
    msg = bot.send_message(user_id, "Опишите вашу жалобу или вопрос главному администратору. Будьте вежливы и информативны.")
    bot.register_next_step_handler(msg, send_report_to_admin)

def send_report_to_admin(message):
    user_id = message.chat.id
    if message.text == '/cancel':
        cancel_process(message)
        return
    report_text = message.text
    username = message.from_user.username if message.from_user.username else f"ID: {user_id}"

    if MAIN_ADMIN_ID:
        # Используем HTML-форматирование, оно более устойчиво к случайным символам
        report_message = (
            f"<b>🚨 НОВАЯ ЖАЛОБА/ВОПРОС 🚨</b>\n\n"
            f"От пользователя: @{username} (ID: {user_id})\n\n"
            f"<b>Сообщение:</b>\n{report_text}"
        )
        
        markup = types.InlineKeyboardMarkup()
        # ИСПРАВЛЕНО: callback_data изменена на 'reply_'
        btn_reply = types.InlineKeyboardButton("Ответить пользователю", callback_data=f"reply_{user_id}") 
        markup.add(btn_reply)

        try:
            # Обязательно указываем parse_mode='HTML'
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
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Добавляем сортировку по убыванию даты создания, чтобы новые посты были вверху
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


# --- 6. Функция для установки стандартного меню команд ---

def set_default_commands():
    """Отправляет список команд в Telegram API для отображения в меню."""
    commands = [
        ('start', 'Запустить бота'),
        ('help', 'Список команд'),
        ('profile', 'Мой профиль'),
        ('view_content', 'Посмотреть посты'),
        ('view_events', 'Посмотреть мероприятия'),
        ('eco_faq', 'Полезная информация'),
        ('my_rating', 'Мой рейтинг'),
        ('top_volunteers', 'Топ волонтеров региона'),
        ('request_admin', 'Подать заявку на админа'),
        ('report_admin', 'Пожаловаться')
    ]
    try:
        # Устанавливаем команды глобально для всех пользователей
        bot.set_my_commands(commands, scope=types.BotCommandScopeDefault(), language_code='ru')
        print("Стандартные команды Telegram меню успешно установлены.")
    except Exception as e:
        print(f"Ошибка при установке команд меню Telegram: {e}")

# --- 7. Запуск бота ---

if __name__ == '__main__':
    init_db()
    set_default_commands() 
    print("Бот запускается...")

    # Определяем ваш часовой пояс с помощью pytz
    # Я предполагаю, что вы находитесь в Самаре (GMT+4), но вы можете заменить 'Europe/Moscow' на свой
    # Найдите свой пояс тут: gist.github.com
    timezone_spb = pytz.timezone('Europe/Moscow') 

    # Инициализация планировщика с указанием часового пояса
    scheduler = BlockingScheduler(timezone=timezone_spb)
    # Запускаем функцию send_monthly_violation_report на 1-е число каждого месяца в 00:01
    scheduler.add_job(send_monthly_violation_report, 'cron', day=1, hour=0, minute=1)
    # scheduler.start() # Мы не запускаем его здесь, мы используем threading для бота

    # Используем threading для параллельного запуска бота и планировщика
    bot_thread = threading.Thread(target=bot.polling, kwargs={"none_stop": True})
    bot_thread.start()
    
    # Запускаем scheduler после bot.polling в основном потоке (или наоборот)
    scheduler.start() 
