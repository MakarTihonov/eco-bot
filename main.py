import telebot
from telebot import types
import sqlite3
import time


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
        conn.commit()

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
        # Выбираем контент либо для всех ('all'), либо только для региона пользователя
        cursor.execute('SELECT text, region, scope FROM content WHERE scope = "all" OR (scope = "region" AND region = ?)', (user_region,))
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
    bot.send_message(message.chat.id, "Привет, вот, что я умею: \n" \
    "\n"
    "/view_content - посмотреть посты, которые доступны для вас. \n"
    "/admin - доступные команды для администратора. \n"
    "/request_admin - для заявки на должность админимстратора. \n"
    "/report_admin - для жалобы на администратора или контент. \n"
    "/change - изменить информацию профиля. \n"
    "/profile - чтобы посмотреть свой профиль \n") 

@bot.message_handler(commands=['admin'])
def admin(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    if status == 'admin':
        bot.send_message(message.chat.id, "Команды для админа: "
        "/add_content \n"
        "/admin_panel \n" 
        "/manage_content \n" \
        "")
    else:
        bot.send_message(message.chat.id, "Вы не являетесь администратором!")


# Шаг 1: Получение региона
def process_region_step(message):
    user_id = message.chat.id
    if message.content_type != 'text' or message.text.startswith('/'):
        msg = bot.send_message(user_id, "Пожалуйста, введите корректное название региона текстом.")
        bot.register_next_step_handler(msg, process_region_step)
        return

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
    content_list = get_all_content_for_user(message.chat.id)
    if content_list:
        response = "Последние записи (доступные вам): 👇\n\n"
        for content in content_list:
            text, region, scope = content
            scope_info = f"[{region} region only 🏠]" if scope == 'region' else "[For all 🌍]"
            response += f"- {text} {scope_info}\n"
        bot.send_message(message.chat.id, response)
    else:
        bot.send_message(message.chat.id, "К сожалению, пока нет ни одной записи, доступной для вашего региона или всех пользователей.")

@bot.message_handler(commands=['add_content'])
def prompt_add_content(message):
    user_id = message.chat.id
    status = get_user_status(user_id)
    
    if status == 'admin':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('Опубликовать для всех 🌍', 'Опубликовать только для моего региона 🏠')
        msg = bot.send_message(user_id, "Отправьте текст, который вы хотите опубликовать, а затем выберите область видимости:", reply_markup=markup)
        # Сохраняем состояние, что пользователь начал процесс добавления контента
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

# --- 5. Обработка Inline кнопок (Одобрение/Отклонение/Лишение прав/Ответ/Удаление контента) ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    admin_id = call.message.chat.id
    bot.answer_callback_query(call.id, "Обработка запроса...")

    try:
        data_parts = call.data.split('_')
        action = data_parts[0] 
        target_id_str = data_parts[-1]
        target_id = int(target_id_str) 
    except (IndexError, ValueError):
        bot.send_message(admin_id, "Произошла ошибка при обработке запроса (парсинг данных).")
        return

    status = get_user_status(admin_id)

    # --- Логика модерации админов (approve, reject, demote, reply) ---
    if action in ['approve', 'reject', 'demote', 'reply'] and status != 'admin' and admin_id != MAIN_ADMIN_ID:
         bot.send_message(admin_id, "У вас нет прав для выполнения этого действия.")
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
        if target_id == MAIN_ADMIN_ID: bot.send_message(admin_id, "Невозможно лишить прав главного администратора!"); return
        if admin_id != MAIN_ADMIN_ID: bot.send_message(admin_id, "Только главный администратор может лишать других прав. 🚫"); return
        update_user_status(target_id, 'user')
        try: bot.send_message(target_id, "🚨 Внимание! Вы были лишены прав администратора главным администратором.")
        except: pass
        bot.edit_message_text(f"Пользователь (ID: {target_id}) лишен прав администратора.", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='HTML')
    
    elif action == 'reply':
        if admin_id != MAIN_ADMIN_ID: bot.send_message(admin_id, "Это действие доступно только главному администратору."); return
        msg = bot.send_message(admin_id, f"Введите ответ для пользователя {target_id}:")
        bot.register_next_step_handler(msg, prompt_admin_reply, target_id)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)

    # --- Логика удаления контента ---
    elif action == 'delete' and data_parts[1] == 'content':
        content_id = target_id
        # Проверяем, что удаляет свой контент (опционально, но безопасно)
        content_list = get_admin_content(admin_id)
        if any(item[0] == content_id for item in content_list):
            delete_content_item(content_id)
            bot.edit_message_text(f"✅ Пост #{content_id} удален.", 
                                  chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        else:
            bot.send_message(admin_id, "Вы можете удалить только свой контент!")


# --- Функции профиля и изменения данных ---

def get_user_details(user_id):
    """Получает полную информацию о пользователе из БД."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username, region, city, role, status FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    return result

@bot.message_handler(commands=['profile'])
def view_profile(message):
    user_id = message.chat.id
    details = get_user_details(user_id)
    if details:
        username, region, city, role, status = details
        response = (
            f"👤 Ваш профиль:\n"
            f"--------------------------\n"
            f"Ник: @{username}\n"
            f"Статус: {status}\n"
            f"Роль: {role}\n"
            f"Регион: {region}\n"
            f"Город: {city}\n"
            f"--------------------------\n"
            f"Чтобы изменить данные: /change"
        )
        bot.send_message(user_id, response)
    else:
        bot.send_message(user_id, "Произошла ошибка при получении данных профиля. Попробуйте /start.")

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


# --- 6. Запуск бота ---

if __name__ == '__main__':
    init_db()
    print("Бот запускается...")
    bot.polling(none_stop=True)
