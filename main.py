import telebot
from telebot import types
import sqlite3
import random
import string
import datetime

# --- Константы  ---
TOKEN = '' 
MAIN_ADMIN_ID = 123456789 
DB_NAME = 'bot_data.db'

# --- Клавиатуры ---
role_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
btn1 = types.KeyboardButton('Ученик (волонтер)')
btn2 = types.KeyboardButton('Куратор')
btn3 = types.KeyboardButton('Ответственное лицо')
role_keyboard.add(btn1, btn2, btn3)

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
        
        conn.commit()


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

def add_content_report(content_id, reporter_user_id, report_text):
    """Регистрирует новую жалобу на контент."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO content_reports (content_id, reporter_user_id, report_text) 
            VALUES (?, ?, ?)
        ''', (content_id, reporter_user_id, report_text))
        conn.commit()


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


# >>>>> ИЗМЕНЕНО: Добавлен параметр check_in_code <<<<<
def create_event(title, description, region, event_date, location, creator_id, check_in_code=None):
    """Создает новое мероприятие в БД."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO events (title, description, region, event_date, location, creator_id, check_in_code) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, region, event_date, location, creator_id, check_in_code))
        conn.commit()

def get_events_for_region(region, view_mode='new'):
    """
    Получает активные (новые) или старые мероприятия для указанного региона.
    view_mode: 'new' (default) or 'old'
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Получаем текущую дату в том же формате 'YYYY-MM-DD', в котором она хранится
        today_date = datetime.date.today().strftime('%Y-%m-%d')
        
        if view_mode == 'new':
            # Выбираем мероприятия, дата которых больше или равна сегодняшней
            sql_query = '''
                SELECT id, title, description, event_date, location FROM events 
                WHERE region = ? AND event_date >= ?
                ORDER BY event_date ASC
            '''
        elif view_mode == 'old':
            # Выбираем мероприятия, дата которых строго меньше сегодняшней
             sql_query = '''
                SELECT id, title, description, event_date, location FROM events 
                WHERE region = ? AND event_date < ?
                ORDER BY event_date DESC
            '''
        else:
            # По умолчанию показываем все, если режим не указан корректно
            sql_query = '''
                SELECT id, title, description, event_date, location FROM events 
                WHERE region = ?
                ORDER BY event_date DESC
            '''

        cursor.execute(sql_query, (region, today_date))
        results = cursor.fetchall()
    return results


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
    # Возвращаем регион или None
    return result[0] if result else None

def get_all_content_for_user(user_id):
    """Получает контент, доступный конкретному пользователю (глобальный или региональный)."""
    user_region = get_user_region(user_id)
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # !!! УБЕДИТЕСЬ, ЧТО ЗДЕСЬ ВЫБИРАЕТСЯ ID !!!
        cursor.execute('SELECT text, region, scope, id FROM content WHERE scope = "all" OR (scope = "region" AND region = ?)', (user_region,))
        results = cursor.fetchall()
    return results


def get_users_in_region(region):
    """Получает user_id всех пользователей в определенном регионе."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE region = ?', (region,))
        results = cursor.fetchall()
    return [row[0] for row in results] # Возвращаем только IDшники

# --- 3. Обработчики команд и процесс регистрации ---

@bot.message_handler(commands=['my_rating'])
def display_my_rating(message):
    user_id = message.chat.id
    if not is_user_registered(user_id):
        enforce_registration(message)
        return

    points = get_user_points(user_id)
    bot.send_message(user_id, f"🌟 Ваш текущий рейтинг: **{points} баллов**.", parse_mode='Markdown')

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
    user_id = message.chat.id
    if user_id not in bot.user_data or 'scope' not in bot.user_data[user_id]: return
    
    bot.user_data[user_id]['question'] = message.text
    # !!! ДОБАВЛЯЕМ parse_mode='Markdown' сюда, чтобы следующий ввод сохранял разметку !!!
    msg = bot.send_message(user_id, "Теперь введите **ответ** на этот вопрос:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_faq_answer)

def process_faq_answer(message):
    user_id = message.chat.id
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
        bot.send_message(user_id, "Чтобы увидеть региональный рейтинг, укажите свой регион в /change.")
        # Показываем глобальный рейтинг вместо регионального, если регион не указан
        top_list = get_top_volunteers(region=None) 
        title = "🏆 Топ 10 волонтеров (Глобальный рейтинг)"
    else:
        top_list = get_top_volunteers(region=region)
        title = f"🏆 Топ 10 волонтеров ({region})"

    if top_list:
        response = f"{title}:\n\n"
        for i, (username, points) in enumerate(top_list, 1):
            response += f"{i}. @{username}: {points} баллов\n"
        bot.send_message(user_id, response)
    else:
        bot.send_message(user_id, f"В этом регионе пока нет волонтеров или баллов для рейтинга.")


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    username = message.from_user.username if message.from_user.username else 'Пользователь'
    
    if not is_user_registered(user_id):
        add_new_user(user_id, username, status='registering')
        msg = bot.send_message(user_id, "Здравствуйте! Для начала работы, пожалуйста, пройдите небольшую регистрацию. Введите название вашего **региона**.")
        bot.register_next_step_handler(msg, process_region_step)
    else:
        status = get_user_status(user_id)
        welcome_text = f"Привет, {username}! Твой текущий статус: {status}."
        if user_id == MAIN_ADMIN_ID:
            welcome_text += "\nТы главный администратор. 👑 \nЧтобы посмотреть все мои команды: /help"
        bot.send_message(user_id, welcome_text, reply_markup=types.ReplyKeyboardRemove())
        if status == 'admin':
            admin_panel(message) # Сразу показываем админ-панель после /start если админ

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
    "/top_volunteers - рейтинг пользователей по региону. \n"
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
        "/create_event - создать мероприятие. \n")
    else:
        bot.send_message(message.chat.id, "Вы не являетесь администратором!")


# Шаг 1: Получение региона
def process_region_step(message):
    user_id = message.chat.id
    
    # >>>>> ДОБАВЛЕНА ПРОВЕРКА НА ОТМЕНУ <<<<<
    if message.text == '/cancel':
        cancel_process(message)
        return
        
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название региона текстом.")
        bot.register_next_step_handler(msg, process_region_step)
        return
    # ... (остальная логика) ...


    bot.user_data[user_id] = {'region': message.text}
    
    msg = bot.send_message(user_id, "Спасибо. Теперь введите название вашего **города или населенного пункта**.")
    bot.register_next_step_handler(msg, process_city_step)

# Шаг 2: Получение города/населенного пункта
def process_city_step(message):
    user_id = message.chat.id
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название города текстом.")
        bot.register_next_step_handler(msg, process_city_step)
        return
        
    bot.user_data[user_id]['city'] = message.text
    
    msg = bot.send_message(user_id, "И последний шаг: пожалуйста, выберите **вашу должность** с помощью кнопок ниже:", reply_markup=role_keyboard)
    bot.register_next_step_handler(msg, process_role_step)

# Шаг 3: Получение должности и завершение регистрации
def process_role_step(message):
    user_id = message.chat.id
    role = message.text
    
    if role not in ['Ученик (волонтер)', 'Куратор', 'Ответственное лицо']:
        msg = bot.send_message(user_id, "Пожалуйста, выберите должность, используя кнопки.", reply_markup=role_keyboard)
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
        
    bot.send_message(user_id, "Спасибо, регистрация завершена! 🎉 Теперь вам доступны основные функции бота. \nЧтобы посмотреть все мои команды: /help", reply_markup=types.ReplyKeyboardRemove())
    # Не вызываем send_welcome(message) здесь повторно, чтобы избежать зацикливания next_step_handler
    # Вместо этого пользователь увидит сообщение выше и может вручную нажать /start или воспользоваться функциями.


# Middleware: Проверяет регистрацию перед обработкой любой другой команды, кроме /start
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
    # Убедитесь, что get_all_content_for_user возвращает ID
    content_list = get_all_content_for_user(user_id) 
    if content_list:
        bot.send_message(user_id, "Последние записи (доступные вам): 👇", reply_markup=types.ReplyKeyboardRemove())

        for content in content_list:
            # Получаем ID из функции БД
            text, region, scope, content_id = content 
            scope_info = f"[{region} region only 🏠]" if scope == 'region' else "[For all 🌍]"
            
            markup = types.InlineKeyboardMarkup()
            # Убраны иероглифы по вашему желанию
            btn_report = types.InlineKeyboardButton("Пожаловаться", callback_data=f"report_content_{content_id}")
            markup.add(btn_report)

            # !!! ИЗМЕНЕНО ФОРМАТИРОВАНИЕ: Используем HTML <b> для жирного заголовка !!!
            # Используем <code> для scope_info, чтобы он не конфликтовал с HTML
            response_text = f"<b>{text}</b> <code>{scope_info}</code>"

            # !!! Добавляем parse_mode='HTML' !!!
            bot.send_message(user_id, response_text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(user_id, "К сожалению, пока нет ни одной записи, доступной для вашего региона или всех пользователей.")


@bot.message_handler(commands=['add_content'])
def prompt_add_content(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    
    if status == 'admin':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('Опубликовать для всех 🌍', 'Опубликовать только для моего региона 🏠')
        
        # !!! ДОБАВЛЯЕМ parse_mode='Markdown' сюда, чтобы следующий ввод сохранял разметку !!!
        msg = bot.send_message(user_id, "Отправьте текст, который вы хотите опубликовать, а затем выберите область видимости:", reply_markup=markup, parse_mode='Markdown')
        
        if user_id not in bot.user_data:
            bot.user_data[user_id] = {}
        bot.user_data[user_id]['adding_content'] = True
        bot.register_next_step_handler(msg, process_content_scope_step)
    else:
        bot.send_message(user_id, "У вас нет прав для добавления контента. 🚫")

def process_content_scope_step(message):
    user_id = message.chat.id
    
    # --- ИСПРАВЛЕНИЕ ОШИБКИ KeyError: Проверка наличия временных данных ---
    if user_id not in bot.user_data or not bot.user_data[user_id].get('adding_content'):
        bot.send_message(user_id, "Данные о предыдущем действии утеряны. Пожалуйста, начните добавление контента заново: /add_content")
        return
    # ---------------------------------------------------------------------

    scope_choice_text = message.text.lower()
    
    # ИСПРАВЛЕНИЕ ОШИБКИ #3: Надежная проверка текста кнопок
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
    
    msg = bot.send_message(user_id, f"Вы выбрали '{message.text}'. Теперь отправьте сам текст контента.", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_content_step)

# --- Команды для работы с мероприятиями ---

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
    
    # Сохраняем регион в user_data для следующих шагов
    bot.user_data[user_id] = {'creating_event': True, 'region': region}
    msg = bot.send_message(user_id, f"Начинаем создание мероприятия для региона **{region}**. Введите **название/заголовок** мероприятия:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_event_title)

def process_event_title(message):
    user_id = message.chat.id
    if user_id not in bot.user_data or not bot.user_data[user_id].get('creating_event'): return
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название текстом.")
        bot.register_next_step_handler(msg, process_event_title)
        return

    bot.user_data[user_id]['title'] = message.text
    msg = bot.send_message(user_id, "Введите **описание** мероприятия:")
    bot.register_next_step_handler(msg, process_event_description)

def process_event_description(message):
    user_id = message.chat.id
    if user_id not in bot.user_data: return
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное описание текстом.")
        bot.register_next_step_handler(msg, process_event_description)
        return
        
    bot.user_data[user_id]['description'] = message.text
    msg = bot.send_message(user_id, "Введите **дату и время** мероприятия (например, '25.12 в 14:00'):")
    bot.register_next_step_handler(msg, process_event_date)

def process_report_reason(message):
    user_id = message.chat.id
    if user_id not in bot.user_data or 'reporting_content_id' not in bot.user_data[user_id]:
        bot.send_message(user_id, "Произошла ошибка при подаче жалобы. Попробуйте снова /view_content.")
        return

    content_id = bot.user_data[user_id]['reporting_content_id']
    report_text = message.text
    reporter_username = message.from_user.username or f"ID: {user_id}"

    # Сохраняем жалобу в БД
    add_content_report(content_id, user_id, report_text)

    bot.send_message(user_id, "✅ Ваша жалоба принята и отправлена на рассмотрение модераторам.")

    # >>> УВЕДОМЛЕНИЕ АДМИНИСТРАТОРОВ <<<
    # Нужно получить список всех администраторов, чтобы отправить им уведомление
    admins = get_all_admins()
    if not admins:
        # Если админов нет, отправляем главному админу
        if MAIN_ADMIN_ID:
            admins = [(MAIN_ADMIN_ID, 'MainAdmin')]

    notification_message = (
        f"<b>🚨 НОВАЯ ЖАЛОБА НА КОНТЕНТ #{content_id} 🚨</b>\n\n"
        f"От пользователя: @{reporter_username}\n"
        f"Причина: {report_text}\n\n"
        f"Чтобы посмотреть контент: /view_content \n"
        f"Чтобы удалить контент: /manage_content"
    )
    
    # Отправляем уведомление каждому администратору
    for admin_id, _ in admins:
        try:
            # Не отправляем самому себе, если админ сам подал жалобу (хотя это маловероятно)
            if admin_id != user_id:
                bot.send_message(admin_id, notification_message, parse_mode='HTML')
        except Exception as e:
            print(f"Ошибка при отправке уведомления админу {admin_id}: {e}")

    # Очищаем данные пользователя
    del bot.user_data[user_id]


def process_event_date(message):
    user_id = message.chat.id
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
        check_in_code=check_in_code # Передаем код в функцию создания
    )

    # >>>>> НОВОЕ: СООБЩАЕМ АДМИНУ КОД <<<<<
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
def handle_view_events_callback(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    
    # call.data будет иметь формат: "view_events_new_RegionName"
    parts = call.data.split('_')
    # parts[0] = 'view'
    # parts[1] = 'events'
    # parts[2] = 'new' (или 'old')
    # parts[3] = 'RegionName'
    
    view_mode = parts[2]
    region_name = parts[3]

    display_events_list(user_id, region_name, view_mode)


# >>>>> НОВАЯ ФУНКЦИЯ ДЛЯ ОТОБРАЖЕНИЯ СПИСКА МЕРОПРИЯТИЙ <<<<<
def display_events_list(user_id, region, view_mode):
    events_list = get_events_for_region(region, view_mode)
    
    title_text = "Актуальные мероприятия" if view_mode == 'new' else "Прошедшие мероприятия"

    if events_list:
        bot.send_message(user_id, f"🌳 {title_text} в вашем регионе ({region}):", reply_markup=types.ReplyKeyboardRemove())
        for event in events_list:
            event_id, title, description, date, location = event
            response = (
                f"**{title}**\n\n"
                f"🗓️ **Дата/Время:** {date}\n"
                f"📍 **Место:** {location}\n\n"
                f"{description[:200]}..."
            )
            
            markup = types.InlineKeyboardMarkup()
            # Кнопка записи нужна только для новых мероприятий
            if view_mode == 'new':
                 if not is_user_registered_for_event(user_id, event_id):
                    btn_register = types.InlineKeyboardButton("Я пойду! Записаться ✅", callback_data=f"register_event_{event_id}")
                    markup.add(btn_register)
                 else:
                    btn_registered = types.InlineKeyboardButton("Вы уже записаны 👍", callback_data="ignore")
                    markup.add(btn_registered)
            else:
                 # Для старых мероприятий просто информационная кнопка
                 btn_info = types.InlineKeyboardButton("Мероприятие завершено 🚫", callback_data="ignore")
                 markup.add(btn_info)


            bot.send_message(user_id, response, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(user_id, f"К сожалению, {title_text.lower()} в регионе {region} пока нет.")



def choose_input_method_step(message):
    user_id = message.chat.id
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

    # --- ИСПРАВЛЕНИЕ ОШИБКИ KeyError: Проверка наличия временных данных ---
    if user_id not in bot.user_data or 'scope' not in bot.user_data[user_id]:
        bot.send_message(user_id, "Данные о предыдущем действии утеряны. Пожалуйста, начните добавление контента заново: /add_content")
        # Очищаем временные данные, чтобы пользователь мог начать заново
        if user_id in bot.user_data: del bot.user_data[user_id]
        return
    # ---------------------------------------------------------------------

    # Эта проверка тут лишняя, так как middleware должна ее перехватить раньше,
    # но как дополнительная мера безопасности:
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


# --- 5. Обработка Inline кнопок (Одобрение/Отклонение/Лишение прав/Ответ/Удаление контента/Регистрация на ивент) ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    # Получаем ID пользователя, который нажал кнопку (это админ в большинстве случаев)
    user_id = call.message.chat.id 
    bot.answer_callback_query(call.id, "Обработка запроса...")

    try:
        # call.data может быть "approve_12345" или "delete_content_5" или "register_event_10"
        data_parts = call.data.split('_')
        action = data_parts[0] 
        # Target ID обычно находится в конце строки
        target_id_str = data_parts[-1] 
        target_id = int(target_id_str) 
    except (IndexError, ValueError):
        bot.send_message(user_id, "Произошла ошибка при обработке запроса (парсинг данных).")
        return

    # --- Логика модерации админов (approve, reject, demote, reply) ---
    # Проверяем права только для админских действий, не для записи на ивент
    if action in ['approve', 'reject', 'demote', 'reply']:
        status = get_user_status(user_id)
        if status != 'admin' and user_id != MAIN_ADMIN_ID:
             bot.send_message(user_id, "У вас нет прав для выполнения этого действия.")
             return
    
    if action == 'approve':
        update_user_status(target_id, 'admin')
        try: bot.send_message(target_id, "🎉 Поздравляем! Ваша заявка одобрена, вы получили права администратора.")
        except: pass
        bot.edit_message_text(f"{call.message.text}\n\n✅ Одобрено.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='HTML')
    
    elif action == 'reject':
        update_user_status(target_id, 'user')
        try: bot.send_message(target_id, "❌ К сожалению, ваша заявка на администрирование была отклонена.")
        except: pass
        bot.edit_message_text(f"{call.message.text}\n\n❌ Отклонено.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='HTML')
    
    elif action == 'demote':
        if target_id == MAIN_ADMIN_ID: bot.send_message(user_id, "Невозможно лишить прав главного администратора!"); return
        if user_id != MAIN_ADMIN_ID: bot.send_message(user_id, "Только главный администратор может лишать других прав. 🚫"); return
        update_user_status(target_id, 'user')
        try: bot.send_message(target_id, "🚨 Внимание! Вы были лишены прав администратора главным администратором.")
        except: pass
        bot.edit_message_text(f"Пользователь (ID: {target_id}) лишен прав администратора.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='HTML')
    
    # --- Логика жалоб на контент ---
    elif action == 'report' and data_parts[1] == 'content':
        content_id = target_id # target_id из парсинга в начале функции callback_handler
        reporter_id = call.message.chat.id
        
        # Запрашиваем у пользователя причину жалобы
        msg = bot.send_message(reporter_id, "Опишите причину вашей жалобы на этот пост:")
        
        # Сохраняем content_id во временных данных и регистрируем следующий шаг
        bot.user_data[reporter_id] = {'reporting_content_id': content_id}
        bot.register_next_step_handler(msg, process_report_reason)
        
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None) # Убираем кнопку "Пожаловаться" после нажатия

    elif action == 'reply':
        if user_id != MAIN_ADMIN_ID: bot.send_message(user_id, "Это действие доступно только главному администратору."); return
        msg = bot.send_message(user_id, f"Введите ответ для пользователя {target_id}:")
        bot.register_next_step_handler(msg, prompt_admin_reply, target_id)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)

    # --- Логика удаления контента ---
    elif action == 'delete' and data_parts[1] == 'content':
        content_id = target_id
        # Проверяем, что удаляет свой контент (опционально, но безопасно)
        content_list = get_admin_content(user_id)
        if any(item[0] == content_id for item in content_list):
            delete_content_item(content_id)
            bot.edit_message_text(f"✅ Пост #{content_id} удален.", 
                                  chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        else:
            bot.send_message(user_id, "Вы можете удалить только свой контент!")

    # --- НОВАЯ ЛОГИКА ДЛЯ РЕГИСТРАЦИИ НА ЭКО-ИВЕНТЫ ---
    elif action == 'register' and data_parts[1] == 'event':
        event_id = target_id
        current_user_id = call.message.chat.id # ID пользователя, который жмет кнопку "Я пойду"
        
        if register_for_event(current_user_id, event_id):
            # Заменяем кнопку "Я пойду" на "Вы записаны", чтобы не спамить регистрациями
            bot.edit_message_text(f"{call.message.text}\n\n✅ Вы успешно записаны!", 
                                  chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode='Markdown')
            bot.send_message(current_user_id, f"🎉 Вы успешно записаны на мероприятие #{event_id}! Ждем вас!")
        else:
            bot.send_message(current_user_id, "Вы уже были записаны на это мероприятие ранее.")
            
    elif action == 'ignore':
        bot.answer_callback_query(call.id, "Это просто информационная кнопка.")



# --- Функции профиля и изменения данных ---

def get_user_details(user_id):
    """Получает полную информацию о пользователе из БД."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username, region, city, role, status FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    return result

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
        
        # >>>>> ДОБАВЛЯЕМ ИСТОРИЮ ВЫВОДА <<<<<
        if history:
            response += f"\n🗓️ <b>Последние мероприятия:</b>\n"
            for title, date in history:
                response += f"— <i>{title}</i> ({date})\n"
        else:
            response += f"\n🗓️ Вы пока не участвовали ни в одном мероприятии.\n"
        # ------------------------------------

        response += f"\nЧтобы изменить данные: /change"

        # Обязательно указываем parse_mode='HTML'
        bot.send_message(user_id, response, parse_mode='HTML') 
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
    user_id = message.chat.id
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
        bot.register_next_step_handler(message, process_award_points) # Повторяем шаг, чтобы не потерять метод
        return
    
    # Определяем ID пользователя в зависимости от метода ввода
    target_user_id = None
    if input_method == 'id':
        try:
            target_user_id = int(identifier)
        except ValueError:
            bot.send_message(user_id, "Неверный формат ID. Попробуйте снова: /award_points")
            return
    elif input_method == 'username':
        # Используем функцию get_user_id_by_username, которую мы создали ранее
        user_record = get_user_id_by_username(identifier)
        if user_record:
            target_user_id = user_record[0] # get_user_id_by_username возвращает кортеж, берем первый элемент
    
    if not target_user_id or get_user_status(target_user_id) == 'new':
        bot.send_message(user_id, f"Пользователь с указанным ID/Username не найден или не зарегистрирован.")
        if user_id in bot.user_data: del bot.user_data[user_id]
        return

    add_points(target_user_id, points_to_add)
    
    # ... (логика уведомлений остается прежней) ...
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
        
    # Очищаем данные после завершения
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
    msg = bot.send_message(user_id, "Введите новое название вашего **региона**:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_new_region)

def process_new_region(message):
    user_id = message.chat.id
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название региона текстом.")
        bot.register_next_step_handler(msg, process_new_region)
        return
    
    new_region = message.text
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET region = ? WHERE user_id = ?', (new_region, user_id))
        conn.commit()
    bot.send_message(user_id, f"✅ Ваш регион успешно изменен на: **{new_region}**", parse_mode='Markdown')

@bot.message_handler(commands=['edit_city'])
def edit_city_prompt(message):
    user_id = message.chat.id
    msg = bot.send_message(user_id, "Введите новое название вашего **города/населенного пункта**:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_new_city)

def process_new_city(message):
    user_id = message.chat.id
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
    bot.polling(none_stop=True)
