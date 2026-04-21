# -<b>- coding: utf-8 -</b>-
import re
import telebot
import requests
import random
import time
import datetime
import sqlite3
import threading
import logging
from telebot import types
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = '8289373453:AAEcMeZuN9RzPA8Bcg129BBA15CFUJ9JM6A'
bot = telebot.TeleBot(TOKEN)
bot.skip_pending = True

ADMIN_ID = 8727723180
YOUR_USERNAME = "@ubmuh"
REQUIRED_CHANNEL = "@krectbII"
CHANNEL_LINK = "https://t.me/krectbII"
SELLER_USERNAME = "@ubmuh"

vowels = 'aeiouy'
consonants = 'bcdfghklmnprstvw'
all_letters = 'abcdefghijklmnopqrstuvwxyz'
BASE_SEARCHES = 5
SEARCH_ATTEMPTS = 40
FILTER_ATTEMPTS = 40
REQUEST_TIMEOUT = 1

patterns_5 = ['CVCVC', 'VCVCV', 'CVCCV', 'VCCVC']
patterns_6 = ['CVCVCV', 'VCVCVC', 'CVCCVC', 'VCCVCC']

PREMIUM_PRICES = {1: 49, 3: 120, 7: 210, 30: 450}
REFERRAL_REWARDS = {5: 1, 8: 3, 12: 7, 20: 30}
SEARCH_PACKAGE_PRICE = 1
CRYPTO_BOT_TOKEN = "559739:AALFf0i5EFhsnAiXQ2CCrKtWVf2MZFfMmTz"

EMOJI = {
    'search': '🔍', 'found': '✅', 'error': '❌', 'premium': '💎',
    'profile': '👤', 'stats': '📊', 'info': 'ℹ️', 'referral': '👥',
    'top': '🏆', 'trap': '🎯', 'filter': '🔎', 'channel': '📢',
    'admin': '⚙️', 'star': '⭐', 'crown': '👑', 'fire': '🔥',
    'rocket': '🚀', 'zap': '⚡', 'lock': '🔒', 'time': '⏱️'
}

conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()
db_lock = threading.RLock()

user_actions = defaultdict(list)
blocked_users = {}
ACTION_COOLDOWN = 3
START_LIMIT = 3
START_WINDOW = 5
BLOCK_DURATION = 300

def migrate_database():
    logger.info("🔄 Проверка миграций БД...")
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    required_columns = {
        'trial_used': 'INTEGER DEFAULT 0',
        'search_packages': 'INTEGER DEFAULT 0',
        'casino_balance': 'INTEGER DEFAULT 0',
        'market_balance': 'INTEGER DEFAULT 0'
    }
    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                conn.commit()
                logger.info(f"✅ Добавлена колонка: {column_name}")
            except Exception as e:
                logger.error(f"❌ Ошибка добавления колонки {column_name}: {e}")
    try:
        cursor.execute("PRAGMA table_info(user_ratings)")
        rating_columns = {row[1] for row in cursor.fetchall()}
        if 'review_text' not in rating_columns:
            cursor.execute("ALTER TABLE user_ratings ADD COLUMN review_text TEXT")
            conn.commit()
            logger.info("✅ Добавлена колонка review_text в user_ratings")
    except Exception as e:
        logger.debug(f"Миграция user_ratings: {e}")
    logger.info("✅ Миграция БД завершена")

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    referrer_id INTEGER,
    referrals_count INTEGER DEFAULT 0,
    subscription_end TEXT,
    searches_today INTEGER DEFAULT 0,
    last_search_date TEXT,
    created_date TEXT,
    total_searches INTEGER DEFAULT 0,
    found_count INTEGER DEFAULT 0,
    subscribed INTEGER DEFAULT 0,
    referral_activated INTEGER DEFAULT 0
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS found (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    length INTEGER,
    price INTEGER,
    found_date TEXT,
    finder_id INTEGER
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS traps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    target_username TEXT,
    status TEXT DEFAULT 'active',
    created_date TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS saved_masks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    mask_name TEXT,
    filter_type TEXT,
    filter_value TEXT,
    created_date TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS gifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER,
    receiver_id INTEGER,
    days INTEGER,
    payment_method TEXT,
    created_date TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS casino_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    game_type TEXT,
    bet INTEGER,
    result INTEGER,
    balance_after INTEGER,
    created_date TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS market_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER,
    username TEXT,
    price INTEGER,
    description TEXT,
    created_date TEXT,
    sold INTEGER DEFAULT 0,
    buyer_id INTEGER DEFAULT NULL
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS user_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_id INTEGER,
    rated_id INTEGER,
    rating INTEGER,
    review_text TEXT,
    created_date TEXT,
    UNIQUE(rater_id, rated_id)
)''')

conn.commit()
migrate_database()

def get_user(user_id):
    with db_lock:
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return {
                'user_id': row[0], 'username': row[1], 'referrer_id': row[2],
                'referrals_count': row[3] or 0, 'subscription_end': row[4],
                'searches_today': row[5] or 0, 'last_search_date': row[6],
                'created_date': row[7], 'total_searches': row[8] or 0,
                'found_count': row[9] or 0, 'subscribed': row[10] or 0,
                'referral_activated': row[11] or 0, 'trial_used': row[12] or 0,
                'search_packages': row[13] or 0, 'casino_balance': row[14] or 0,
                'market_balance': row[15] or 0
            }
        return None

def create_user(user_id, username=None, referrer_id=None):
    with db_lock:
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            return get_user(user_id), False
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO users (user_id, username, referrer_id, created_date) VALUES (?, ?, ?, ?)',
                       (user_id, username, referrer_id, now))
        conn.commit()
        return get_user(user_id), True

def update_user(user_id, **kwargs):
    allowed_fields = {
        'username', 'referrer_id', 'referrals_count', 'subscription_end',
        'searches_today', 'last_search_date', 'total_searches',
        'found_count', 'subscribed', 'referral_activated', 'trial_used',
        'search_packages', 'casino_balance'
    }
    with db_lock:
        for key, val in kwargs.items():
            if key in allowed_fields:
                cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (val, user_id))
        conn.commit()

def check_rate_limit(user_id, action_type='general'):
    current_time = time.time()
    if user_id in blocked_users:
        if current_time < blocked_users[user_id]:
            return False, f"{EMOJI['error']} <b>Вы заблокированы!</b>"
        else:
            del blocked_users[user_id]
            user_actions[user_id] = []
    actions = user_actions[user_id]
    if action_type == 'start':
        actions[:] = [t for t in actions if current_time - t < START_WINDOW]
        if len(actions) >= START_LIMIT:
            blocked_users[user_id] = current_time + BLOCK_DURATION
            user_actions[user_id] = []
            return False, f"{EMOJI['error']} <b>Вы заблокированы на 5 минут!</b>"
        actions.append(current_time)
        return True, None
    else:
        actions[:] = [t for t in actions if current_time - t < ACTION_COOLDOWN]
        if actions and (current_time - actions[-1]) < ACTION_COOLDOWN:
            return False, f"{EMOJI['time']} <b>Подожди немного</b>"
        actions.append(current_time)
        return True, None

def validate_username(username):
    if not username:
        return False, "Пустой username"
    username = username.strip().lower().replace('@', '')
    if len(username) < 5 or len(username) > 32:
        return False, "Username должен быть от 5 до 32 символов"
    if not re.match(r'^[a-z0-9_]+$', username):
        return False, "Только латиница, цифры и _"
    return True, username

def validate_mask(mask):
    if not mask:
        return False, "Пустая маска"
    mask = mask.strip().lower()
    if len(mask) < 5 or len(mask) > 6:
        return False, "Маска должна быть 5-6 символов"
    if not re.match(r'^[a-z?]+$', mask):
        return False, "Только латиница и символ ?"
    return True, mask

def save_mask(user_id, mask_name, filter_type, filter_value):
    with db_lock:
        cursor.execute("INSERT INTO saved_masks (user_id, mask_name, filter_type, filter_value, created_date) VALUES (?, ?, ?, ?, ?)",
                       (user_id, mask_name, filter_type, filter_value, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

def get_user_masks(user_id):
    with db_lock:
        cursor.execute("SELECT * FROM saved_masks WHERE user_id = ?", (user_id,))
        return cursor.fetchall()

def delete_mask(mask_id, user_id):
    with db_lock:
        cursor.execute("DELETE FROM saved_masks WHERE id = ? AND user_id = ?", (mask_id, user_id))
        conn.commit()

def add_search_packages(user_id, amount):
    user = get_user(user_id)
    current = user.get('search_packages', 0) if user else 0
    update_user(user_id, search_packages=current + amount)

def add_casino_balance(user_id, amount):
    user = get_user(user_id)
    current = user.get('casino_balance', 0) if user else 0
    update_user(user_id, casino_balance=current + amount)

def create_gift(sender_id, receiver_id, days, payment_method):
    with db_lock:
        cursor.execute("INSERT INTO gifts (sender_id, receiver_id, days, payment_method, created_date) VALUES (?, ?, ?, ?, ?)",
                       (sender_id, receiver_id, days, payment_method, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

def check_crypto_payment(invoice_id):
    try:
        response = requests.get("https://pay.crypt.bot/api/getInvoices",
                                headers={"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN},
                                params={"invoice_ids": invoice_id}, timeout=10)
        data = response.json()
        if data.get('ok') and data.get('result'):
            invoice = data['result']['items'][0] if data['result'].get('items') else None
            if invoice and invoice.get('status') == 'paid':
                return True
    except:
        pass
    return False

def activate_referral(user_id):
    user = get_user(user_id)
    logger.info(f"activate_referral({user_id}): user={user is not None}, activated={user.get('referral_activated') if user else 'N/A'}, referrer={user.get('referrer_id') if user else 'N/A'}")
    if not user or user['referral_activated']:
        logger.info(f"activate_referral({user_id}): skipped (no user or already activated)")
        return False
    referrer_id = user['referrer_id']
    if not referrer_id or referrer_id == user_id:
        logger.info(f"activate_referral({user_id}): skipped (no referrer or self-ref)")
        return False
    with db_lock:
        cursor.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referrer_id,))
        cursor.execute("UPDATE users SET referral_activated = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        cursor.execute("SELECT referrals_count FROM users WHERE user_id = ?", (referrer_id,))
        ref_count = cursor.fetchone()[0]
    logger.info(f"activate_referral({user_id}): SUCCESS! referrer={referrer_id} now has {ref_count} refs")
    check_referral_rewards(referrer_id, ref_count)
    try:
        bot.send_message(referrer_id, f"{EMOJI['fire']} По твоей ссылке зарегистрировался новый пользователь!\n\n👥 Всего рефералов: {ref_count}")
    except:
        pass
    return True

def check_referral_rewards(user_id, ref_count):
    user = get_user(user_id)
    if not user:
        return
    for need_refs, days in sorted(REFERRAL_REWARDS.items()):
        if ref_count >= need_refs:
            add_premium(user_id, days, from_ref=True)

def check_fragment(username):
    try:
        r = requests.get(f"https://fragment.com/username/{username}", timeout=5, allow_redirects=True)
        text = r.text.lower()
        if "query=" in r.url:
            return False
        if "auction" in text or "make an offer" in text or "for sale" in text:
            return True
        return False
    except:
        return False

def check_telegram(username):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(f"https://t.me/{username}", headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            if 'tgme_page_title' in r.text.lower():
                return False, f"{EMOJI['error']} Занят"
            else:
                return True, f"{EMOJI['found']} Свободен"
        return True, f"{EMOJI['found']} Свободен"
    except:
        return False, f"{EMOJI['error']} Ошибка"

def check_username_full(username):
    is_free_tg, status_tg = check_telegram(username)
    if not is_free_tg:
        return False, status_tg
    if check_fragment(username):
        return False, f"{EMOJI['error']} На Fragment"
    return True, f"{EMOJI['found']} Свободен"

def generate_from_pattern(pattern):
    result = ''
    for ch in pattern:
        if ch == 'C':
            result += random.choice(consonants)
        else:
            result += random.choice(vowels)
    return result

def generate_from_mask(mask):
    result = ''
    for ch in mask:
        if ch == '?':
            result += random.choice(all_letters)
        else:
            result += ch
    return result

def estimate_price(username):
    return random.randint(50, 200) if len(username) == 5 else random.randint(10, 50)

def error_handler(func):
    def wrapper(message):
        try:
            return func(message)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            try:
                bot.send_message(message.from_user.id, f"{EMOJI['error']} Ошибка. Попробуй позже.")
            except:
                pass
    return wrapper

def check_subscription(user_id):
    try:
        status = bot.get_chat_member(REQUIRED_CHANNEL, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return True

def subscription_required(func):
    def wrapper(message):
        if check_subscription(message.from_user.id):
            return func(message)
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"{EMOJI['channel']} Подписаться", url=CHANNEL_LINK))
            bot.send_message(message.from_user.id, f"{EMOJI['lock']} <b>Подпишись на канал</b>\n\n{CHANNEL_LINK}", parse_mode='HTML', reply_markup=markup)
    return wrapper

def has_premium(user_id):
    user = get_user(user_id)
    if not user or not user['subscription_end']:
        return False
    try:
        return datetime.datetime.now() < datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S')
    except:
        return False

def get_available_searches(user_id):
    user = get_user(user_id)
    if not user:
        return BASE_SEARCHES
    if user['subscription_end']:
        try:
            if datetime.datetime.now() < datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S'):
                return 999
        except:
            pass
    packages = user.get('search_packages', 0)
    if packages > 0:
        return packages
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    if user['last_search_date'] != today:
        update_user(user_id, searches_today=0, last_search_date=today)
        return BASE_SEARCHES
    return max(BASE_SEARCHES - (user['searches_today'] or 0), 0)

def use_search(user_id):
    user = get_user(user_id)
    if user:
        packages = user.get('search_packages', 0)
        if packages > 0:
            update_user(user_id, search_packages=packages - 1, total_searches=(user['total_searches'] or 0) + 1)
        else:
            update_user(user_id, searches_today=(user['searches_today'] or 0) + 1, total_searches=(user['total_searches'] or 0) + 1)

def add_found(user_id):
    user = get_user(user_id)
    if user:
        update_user(user_id, found_count=(user['found_count'] or 0) + 1)

def add_premium(user_id, days, from_ref=False):
    user = get_user(user_id)
    if not user:
        return
    now = datetime.datetime.now()
    new_end = now + datetime.timedelta(days=days)
    if user['subscription_end']:
        try:
            old = datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S')
            if old > now:
                new_end = old + datetime.timedelta(days=days)
        except:
            pass
    update_user(user_id, subscription_end=new_end.strftime('%Y-%m-%d %H:%M:%S'))
    try:
        text = f"{EMOJI['premium']} <b>ПРЕМИУМ АКТИВИРОВАН</b>\n\n📅 До: {new_end.strftime('%d.%m.%Y')}"
        if from_ref:
            text = f"{EMOJI['fire']} <b>НАГРАДА ЗА РЕФЕРАЛОВ</b>\n\n{text}"
        bot.send_message(user_id, text, parse_mode='HTML')
    except:
        pass

def get_user_rating(user_id):
    with db_lock:
        cursor.execute("SELECT AVG(rating), COUNT(*) FROM user_ratings WHERE rated_id = ?", (user_id,))
        result = cursor.fetchone()
        avg = result[0] or 0
        count = result[1] or 0
        return round(avg, 1), count

def format_rating_stars(avg, count):
    full = int(avg)
    empty = 5 - full
    stars = "★" * full + "☆" * empty
    return f"{stars} ({count})"

def add_market_listing(seller_id, username, price, description):
    with db_lock:
        cursor.execute("INSERT INTO market_listings (seller_id, username, price, description, created_date) VALUES (?, ?, ?, ?, datetime('now'))",
                       (seller_id, username, price, description or ''))
        conn.commit()
        return cursor.lastrowid

def get_market_listings(page=0, per_page=6):
    offset = page * per_page
    with db_lock:
        cursor.execute("SELECT id, seller_id, username, price, description, created_date FROM market_listings WHERE sold = 0 ORDER BY created_date DESC LIMIT ? OFFSET ?", (per_page, offset))
        return cursor.fetchall()

def get_market_count():
    with db_lock:
        cursor.execute("SELECT COUNT(*) FROM market_listings WHERE sold = 0")
        return cursor.fetchone()[0]

def get_user_listings(user_id):
    with db_lock:
        cursor.execute("SELECT id, username, price, description, sold, created_date FROM market_listings WHERE seller_id = ? ORDER BY created_date DESC", (user_id,))
        return cursor.fetchall()

def get_listing_by_id(listing_id):
    with db_lock:
        cursor.execute("SELECT id, seller_id, username, price, description, sold, buyer_id, created_date FROM market_listings WHERE id = ?", (listing_id,))
        return cursor.fetchone()

def cancel_listing(listing_id, user_id):
    listing = get_listing_by_id(listing_id)
    if not listing:
        return False, "Лот не найден"
    if listing[1] != user_id:
        return False, "Это не ваш лот"
    if listing[5] == 1:
        return False, "Лот уже продан"
    with db_lock:
        cursor.execute("DELETE FROM market_listings WHERE id = ?", (listing_id,))
        conn.commit()
    return True, "Лот удален"

def get_user_reviews(user_id):
    with db_lock:
        cursor.execute("SELECT rater_id, rating, review_text, created_date FROM user_ratings WHERE rated_id = ? ORDER BY created_date DESC", (user_id,))
        return cursor.fetchall()

def add_review(rater_id, rated_id, rating, review_text):
    if rater_id == rated_id:
        return False, "Нельзя оставить отзыв себе"
    if rating < 1 or rating > 5:
        return False, "Оценка от 1 до 5"
    with db_lock:
        cursor.execute("SELECT id FROM user_ratings WHERE rater_id = ? AND rated_id = ?", (rater_id, rated_id))
        if cursor.fetchone():
            return False, "Вы уже оставляли отзыв этому продавцу"
        cursor.execute("INSERT INTO user_ratings (rater_id, rated_id, rating, review_text, created_date) VALUES (?, ?, ?, ?, datetime('now'))",
                       (rater_id, rated_id, rating, review_text))
        conn.commit()
        return True, "Отзыв добавлен"

def get_main_keyboard(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton(f"Поиск"),
        types.KeyboardButton(f"Статистика (бота)"),
        types.KeyboardButton(f"Профиль"),
        types.KeyboardButton(f"Премиум")
    ]
    if user_id == ADMIN_ID:
        buttons.append(types.KeyboardButton(f"{EMOJI['admin']} АДМИН"))
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['start'])
@error_handler
def start(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id, 'start')
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    username = message.from_user.username
    referrer_id = None
    if len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1])
            if referrer_id == user_id:
                referrer_id = None
        except:
            pass

    # Капча для новых
    user, is_new = create_user(user_id, username, referrer_id)
    if is_new:
        # Простая капча-заглушка 
        bot.send_message(user_id, "<tg-emoji emoji-id='6082635604896520956'>🚀</tg-emoji> Проходим проверку...", parse_mode='HTML')
        time.sleep(1)
        trial_end = datetime.datetime.now() + datetime.timedelta(minutes=15)
        update_user(user_id, subscription_end=trial_end.strftime('%Y-%m-%d %H:%M:%S'), trial_used=1)
        
    # Активация реферала при подписке на канал
    if check_subscription(user_id):
        # Всегда пытаемся активировать реферал (функция сама проверит условия)
        activate_referral(user_id)
        welcome = (f"<tg-emoji emoji-id='4918354603281482671'>⭐</tg-emoji> ДОБРО ПОЖАЛОВАТЬ!\n\n"
                  f"<tg-emoji emoji-id='4906943755644306322'>⭐</tg-emoji> У нас можно:\n"
                  f"<tg-emoji emoji-id='4902524693858222969'>⭐</tg-emoji> Поиск 5-6 букв\n"
                  f"<tg-emoji emoji-id='4902524693858222969'>⭐</tg-emoji> Поиск по слову\n"
                  f"<tg-emoji emoji-id='4902524693858222969'>⭐</tg-emoji> Поиск по фильтру\n\n"
                  f"<tg-emoji emoji-id='4916105371858240403'>⭐</tg-emoji> Бот иногда может выдавать юзернеймы которые заблокированы в ТГ или стоят на продаже")
        bot.send_photo(user_id, photo="https://i.postimg.cc/nhbMgpRy/1775474714965.png", caption=welcome, parse_mode='HTML', reply_markup=get_main_keyboard(user_id))
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Подписаться на канал", url=CHANNEL_LINK))
        bot.send_message(user_id, "Сначала подпишись на наш канал", parse_mode='HTML', reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "Поиск")
@subscription_required
@error_handler
def search_menu_handler(message):
    user_id = message.from_user.id
    text = (f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Режим Буквы — поиск свободных юзернеймов по количеству букв.\n\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Слово — Вводите основу (например, style), и бот найдет свободные ники вроде @username, @user. Вам дадут похожий не занятый юзернейм.\n\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Фильтр — поиск по маске от 5 до 15 символов. Например, маска a?s?a?a может дать результат вроде aasaaza. Знак ? означает случайную букву.\n\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Ловушка — вы указываете нужный юзернейм, и как только он освободится, вы сразу получите уведомление.")
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("5 букв", callback_data="search_mode_5"),
        types.InlineKeyboardButton("6 букв", callback_data="search_mode_6"),
        types.InlineKeyboardButton("Фильтр", callback_data="search_mode_filter"),
        types.InlineKeyboardButton("Ловушка", callback_data="search_mode_trap"),
        types.InlineKeyboardButton("Слово", callback_data="search_mode_word"),
        types.InlineKeyboardButton("Закрыть", callback_data="search_close")
    )
    bot.send_message(user_id, text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "search_close")
def search_close_handler(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "search_mode_5")
@subscription_required
@error_handler
def search_5_handler(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    if get_available_searches(user_id) <= 0:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Лимит исчерпан!</b>\n\nКупите премиум", parse_mode='HTML')
        return
    msg = bot.send_message(user_id, f"{EMOJI['search']} <b>Ищу 5-буквенный ник...</b>", parse_mode='HTML')
    for i in range(SEARCH_ATTEMPTS):
        username = generate_from_pattern(random.choice(patterns_5))
        is_free, status = check_username_full(username)
        if is_free:
            use_search(user_id)
            price = estimate_price(username)
            add_found(user_id)
            try:
                with db_lock:
                    cursor.execute("INSERT INTO found (username, length, price, found_date, finder_id) VALUES (?, ?, ?, datetime('now'), ?)", (username, 5, price, user_id))
                    conn.commit()
            except:
                pass
            try:
                bot.delete_message(user_id, msg.message_id)
            except:
                pass
            
            searches_left = get_available_searches(user_id)
            win_text = (f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> НИК НАЙДЕН!\n\n"
                        f"<tg-emoji emoji-id='5084979757905347540'>⭐</tg-emoji> Ник: @{username}\n"
                        f"<tg-emoji emoji-id='5084923566848213749'>⭐</tg-emoji> Букв: 5 букв\n"
                        f"<tg-emoji emoji-id='5134438483867206614'>⭐</tg-emoji> Примерная стоимость: {price} Stars\n\n"
                        f"Осталось поисков: {'Безлимит (Премиум)' if has_premium(user_id) else searches_left}\n"
                        f"<tg-emoji emoji-id='4911656069207426158'>⭐</tg-emoji> Наш канал: {REQUIRED_CHANNEL}")
            
            search_markup = types.InlineKeyboardMarkup()
            search_markup.add(types.InlineKeyboardButton("Найти другой", callback_data="search_mode_5"))
            bot.send_message(user_id, win_text, parse_mode='HTML', reply_markup=search_markup)
            return
            
        time.sleep(REQUEST_TIMEOUT)
    bot.edit_message_text(f"{EMOJI['error']} <b>Не удалось найти свободный ник. Попробуйте еще раз!</b>", user_id, msg.message_id, parse_mode='HTML')

# ========== 5 БУКВ ==========
@bot.message_handler(func=lambda m: m.text == f"{EMOJI['search']} 5 БУКВ")
@subscription_required
@error_handler
def search_5_old(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    if get_available_searches(user_id) <= 0:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Лимит исчерпан!</b>\n\n{EMOJI['premium']} Купи премиум: {SELLER_USERNAME}", parse_mode='HTML')
        return
    msg = bot.send_message(user_id, f"{EMOJI['search']} <b>Ищу 5-буквенный ник...</b>", parse_mode='HTML')
    for i in range(SEARCH_ATTEMPTS):
        username = generate_from_pattern(random.choice(patterns_5))
        is_free, status = check_username_full(username)
        if is_free:
            use_search(user_id)
            price = estimate_price(username)
            add_found(user_id)
            try:
                with db_lock:
                    cursor.execute("INSERT INTO found (username, length, price, found_date, finder_id) VALUES (?, ?, ?, datetime('now'), ?)", (username, 5, price, user_id))
                    conn.commit()
            except:
                pass
            try:
                bot.delete_message(user_id, msg.message_id)
            except:
                pass
            clickable_nick = f"<a href='https://t.me/{username}'>{username}</a>"
            bot.send_message(user_id, f"{EMOJI['found']} <b>НИК НАЙДЕН ✅</b>\n\n<b>Ваш ник:</b> @{username} ~ {clickable_nick}\n<b>Кол-во символов:</b> {len(username)}\n<b>Ценность:</b> {price} ⭐\n<b>Статус:</b> Свободен\n\n🔗 https://t.me/{username}", parse_mode='HTML', link_preview_options=types.LinkPreviewOptions(url="https://i.postimg.cc/nhbMgpRy/1775474714965.png", show_above_text=True))
            return
        if i % 3 == 0:
            bot.edit_message_text(f"{EMOJI['search']} <b>Поиск...</b> {i+1}/{SEARCH_ATTEMPTS}", user_id, msg.message_id, parse_mode='HTML')
    bot.edit_message_text(f"{EMOJI['error']} <b>Ничего не найдено</b>\nПопробуй еще раз!", user_id, msg.message_id, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == "search_mode_6")
@subscription_required
@error_handler
def search_6_handler(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    if get_available_searches(user_id) <= 0:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Лимит исчерпан!</b>\n\nКупите премиум", parse_mode='HTML')
        return
    msg = bot.send_message(user_id, f"{EMOJI['search']} <b>Ищу 6-буквенный ник...</b>", parse_mode='HTML')
    for i in range(SEARCH_ATTEMPTS):
        username = generate_from_pattern(random.choice(patterns_6))
        is_free, status = check_username_full(username)
        if is_free:
            use_search(user_id)
            price = estimate_price(username)
            add_found(user_id)
            try:
                with db_lock:
                    cursor.execute("INSERT INTO found (username, length, price, found_date, finder_id) VALUES (?, ?, ?, datetime('now'), ?)", (username, 6, price, user_id))
                    conn.commit()
            except:
                pass
            try:
                bot.delete_message(user_id, msg.message_id)
            except:
                pass
            
            searches_left = get_available_searches(user_id)
            win_text = (f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> НИК НАЙДЕН!\n\n"
                        f"<tg-emoji emoji-id='5084979757905347540'>⭐</tg-emoji> Ник: @{username}\n"
                        f"<tg-emoji emoji-id='5084923566848213749'>⭐</tg-emoji> Букв: 6 букв\n"
                        f"<tg-emoji emoji-id='5134438483867206614'>⭐</tg-emoji> Примерная стоимость: {price} Stars\n\n"
                        f"Осталось поисков: {'Безлимит (Премиум)' if has_premium(user_id) else searches_left}\n"
                        f"<tg-emoji emoji-id='4911656069207426158'>⭐</tg-emoji> Наш канал: {REQUIRED_CHANNEL}")
            
            search_markup = types.InlineKeyboardMarkup()
            search_markup.add(types.InlineKeyboardButton("Найти другой", callback_data="search_mode_6"))
            bot.send_message(user_id, win_text, parse_mode='HTML', reply_markup=search_markup)
            return
            
        if i % 3 == 0:
            bot.edit_message_text(f"{EMOJI['search']} <b>Поиск...</b> {i+1}/{SEARCH_ATTEMPTS}", user_id, msg.message_id, parse_mode='HTML')
        time.sleep(REQUEST_TIMEOUT)
    bot.edit_message_text(f"{EMOJI['error']} <b>Не удалось найти свободный ник. Попробуйте еще раз!</b>", user_id, msg.message_id, parse_mode='HTML')

# ========== 6 БУКВ ==========
@bot.message_handler(func=lambda m: m.text == f"{EMOJI['search']} 6 БУКВ")
@subscription_required
@error_handler
def search_6_old(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    if get_available_searches(user_id) <= 0:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Лимит исчерпан!</b>\n\n{EMOJI['premium']} Купи премиум: {SELLER_USERNAME}", parse_mode='HTML')
        return
    msg = bot.send_message(user_id, f"{EMOJI['search']} <b>Ищу 6-буквенный ник...</b>", parse_mode='HTML')
    for i in range(SEARCH_ATTEMPTS):
        username = generate_from_pattern(random.choice(patterns_6))
        is_free, status = check_username_full(username)
        if is_free:
            use_search(user_id)
            price = estimate_price(username)
            add_found(user_id)
            try:
                with db_lock:
                    cursor.execute("INSERT INTO found (username, length, price, found_date, finder_id) VALUES (?, ?, ?, datetime('now'), ?)", (username, 6, price, user_id))
                    conn.commit()
            except:
                pass
            try:
                bot.delete_message(user_id, msg.message_id)
            except:
                pass
            clickable_nick = f"<a href='https://t.me/{username}'>{username}</a>"
            bot.send_message(user_id, f"{EMOJI['found']} <b>НИК НАЙДЕН ✅</b>\n\n<b>Ваш ник:</b> @{username} ~ {clickable_nick}\n<b>Кол-во символов:</b> {len(username)}\n<b>Ценность:</b> {price} ⭐\n<b>Статус:</b> Свободен\n\n🔗 https://t.me/{username}", parse_mode='HTML', link_preview_options=types.LinkPreviewOptions(url="https://i.postimg.cc/nhbMgpRy/1775474714965.png", show_above_text=True))
            return
        if i % 3 == 0:
            bot.edit_message_text(f"{EMOJI['search']} <b>Поиск...</b> {i+1}/{SEARCH_ATTEMPTS}", user_id, msg.message_id, parse_mode='HTML')
    bot.edit_message_text(f"{EMOJI['error']} <b>Ничего не найдено</b>\nПопробуй еще раз!", user_id, msg.message_id, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == "search_mode_filter")
@subscription_required
def filter_menu_handler(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    user = get_user(user_id)
    is_premium = False
    if user and user['subscription_end']:
        try:
            if datetime.datetime.now() < datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S'):
                is_premium = True
        except:
            pass
    if not is_premium:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Фильтр только для Premium!</b>\n\n{EMOJI['premium']} Купить премиум", parse_mode='HTML')
        return
    
    filter_text = (f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> ФИЛЬТР\n\n"
                   f"Введите маску (5-15 символов)\n"
                   f"Знак <code>?</code> — любая случайная буква.\n\n"
                   f"Пример: <code>a?s?a?a</code> → результат <code>aasaaza</code>")
                   
    msg = bot.send_photo(user_id, photo="https://i.postimg.cc/nhbMgpRy/1775474714965.png", caption=filter_text, parse_mode='HTML')
    bot.register_next_step_handler(msg, process_filter_new)

def process_filter_new(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    
    mask_input = message.text.strip().lower()
    if not mask_input or len(mask_input) < 5 or len(mask_input) > 15:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Маска должна быть от 5 до 15 символов!</b>", parse_mode='HTML')
        return
        
    # Преобразуем введенную маску к нужному формату `?` = любая буква
    # Ранее `?` это была согласная (C), а `!` гласная (V).
    # Теперь `?` это просто рандом буква, так что перепишем генератор
    
    msg = bot.send_message(user_id, f"{EMOJI['search']} <b>Ищу по маске '{mask_input}'...</b>", parse_mode='HTML')
    checked = 0
    for i in range(FILTER_ATTEMPTS):
        username = ""
        for ch in mask_input:
            if ch == '?':
                username += random.choice(all_letters)
            elif ch.isalpha():
                username += ch
            else:
                bot.edit_message_text(f"{EMOJI['error']} <b>Разрешены только буквы и знак ?</b>", user_id, msg.message_id, parse_mode='HTML')
                return
                
        # Если юзернейм слишком длинный или короткий отпадает сам в цикл:
        if len(username) < 5 or len(username) > 32:
            continue
            
        checked += 1
        is_free, status = check_username_full(username)
        if is_free:
            use_search(user_id)
            price = estimate_price(username)
            add_found(user_id)
            try:
                bot.delete_message(user_id, msg.message_id)
            except:
                pass
                
            searches_left = get_available_searches(user_id)
            win_text = (f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> НИК НАЙДЕН!\n\n"
                        f"<tg-emoji emoji-id='5084979757905347540'>⭐</tg-emoji> Ник: @{username}\n"
                        f"<tg-emoji emoji-id='5084923566848213749'>⭐</tg-emoji> Символов: {len(username)}\n"
                        f"<tg-emoji emoji-id='5134438483867206614'>⭐</tg-emoji> Примерная стоимость: {price} Stars\n\n"
                        f"Осталось поисков: Безлимит (Премиум)\n"
                        f"<tg-emoji emoji-id='4911656069207426158'>⭐</tg-emoji> Наш канал: {REQUIRED_CHANNEL}")
            
            # Поскольку маска может быть разной, кнопка будет просто вызывать filter заново
            search_markup = types.InlineKeyboardMarkup()
            search_markup.add(types.InlineKeyboardButton("Найти другой", callback_data="search_mode_filter"))
            bot.send_message(user_id, win_text, parse_mode='HTML', reply_markup=search_markup)
            return

        if i % 5 == 0:
            try:
                bot.edit_message_text(f"{EMOJI['search']} <b>Поиск...</b> {checked}/{FILTER_ATTEMPTS}", user_id, msg.message_id, parse_mode='HTML')
            except:
                pass
        time.sleep(REQUEST_TIMEOUT)
    bot.edit_message_text(f"{EMOJI['error']} <b>Ничего не найдено</b>\nПопробуй другую маску!", user_id, msg.message_id, parse_mode='HTML')


# ========== ФИЛЬТР ==========
@bot.message_handler(func=lambda m: m.text == f"{EMOJI['filter']} ФИЛЬТР {EMOJI['premium']}")
@subscription_required
def filter_menu_old(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    user = get_user(user_id)
    is_premium = False
    if user and user['subscription_end']:
        try:
            if datetime.datetime.now() < datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S'):
                is_premium = True
        except:
            pass
    if not is_premium:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Фильтр только для Premium!</b>\n\n{EMOJI['premium']} Купить: {SELLER_USERNAME}", parse_mode='HTML')
        return
    filter_text = f"{EMOJI['filter']} <b>ФИЛЬТР</b>\n\nВведите фильтр (5-6 символов)\nСогласная буква - <code>?</code>\nГласная буква - <code>!</code>\n\nПримеры: <code>k!y?a</code> | <code>ee?!?a</code> | <code>?iebxu</code>"
    bot.send_photo(user_id, photo="https://i.postimg.cc/nhbMgpRy/1775474714965.png", caption=filter_text, parse_mode='HTML')
    bot.register_next_step_handler(message, process_filter)

def process_filter(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    mask_input = message.text.strip().lower()
    if not mask_input or len(mask_input) < 5 or len(mask_input) > 6:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Маска должна быть 5-6 символов!</b>", parse_mode='HTML')
        return
    converted_mask = ""
    for ch in mask_input:
        if ch == '?':
            converted_mask += 'C'
        elif ch == '!':
            converted_mask += 'V'
        elif ch.isalpha():
            converted_mask += ch
        else:
            bot.send_message(user_id, f"{EMOJI['error']} <b>Разрешены только буквы, ? и !</b>", parse_mode='HTML')
            return
    mask = converted_mask
    is_pattern = all(ch in 'CV' for ch in mask.upper())
    msg = bot.send_message(user_id, f"{EMOJI['filter']} <b>Поиск...</b>", parse_mode='HTML')
    for i in range(FILTER_ATTEMPTS):
        if is_pattern:
            username = generate_from_pattern(mask.upper())
        else:
            username = generate_from_mask(mask)
        is_free, status = check_username_full(username)
        if is_free:
            price = estimate_price(username)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"💾 Сохранить эту маску", callback_data=f"save_mask_{mask}"))
            try:
                bot.delete_message(user_id, msg.message_id)
            except:
                pass
            clickable_nick = f"<a href='https://t.me/{username}'>{username}</a>"
            bot.send_message(user_id, f"{EMOJI['found']} <b>НИК НАЙДЕН ✅</b>\n\n<b>Ваш ник:</b> @{username} ~ {clickable_nick}\n<b>Кол-во символов:</b> {len(username)}\n<b>Ценность:</b> {price} ⭐\n<b>Статус:</b> Свободен\n\n🔗 https://t.me/{username}", parse_mode='HTML', reply_markup=markup, link_preview_options=types.LinkPreviewOptions(url="https://i.postimg.cc/nhbMgpRy/1775474714965.png", show_above_text=True))
            return
        if i % 3 == 0:
            bot.edit_message_text(f"{EMOJI['filter']} <b>Поиск...</b> {i+1}/{FILTER_ATTEMPTS}", user_id, msg.message_id, parse_mode='HTML')
    bot.edit_message_text(f"{EMOJI['error']} <b>Ничего не найдено</b>", user_id, msg.message_id, parse_mode='HTML')

# ========== ЛОВУШКА ==========
@bot.callback_query_handler(func=lambda call: call.data == "search_mode_trap")
@subscription_required
def trap_menu_handler(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    user = get_user(user_id)
    is_premium = False
    if user and user['subscription_end']:
        try:
            if datetime.datetime.now() < datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S'):
                is_premium = True
        except:
            pass
    if not is_premium:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Ловушка только для Premium!</b>\n\nКупить премиум", parse_mode='HTML')
        return
    msg = bot.send_photo(user_id, photo="https://i.postimg.cc/nhbMgpRy/1775474714965.png", caption=f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> ЛОВУШКА\n\nВы указываете нужный юзернейм, и как только он освободится, вы сразу получите уведомление.\n\nВведи ник, обязательно без @, например <code>tergut</code>", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_trap)

def process_trap(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    is_valid, result = validate_username(message.text)
    if not is_valid:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Ошибка:</b> {result}", parse_mode='HTML')
        return
    target = result
    with db_lock:
        cursor.execute("SELECT COUNT(*) FROM traps WHERE user_id = ? AND status = 'active'", (user_id,))
        if cursor.fetchone()[0] >= 3:
            bot.send_message(user_id, f"{EMOJI['error']} <b>Максимум 3 ловушки!</b>", parse_mode='HTML')
            return
    is_free, status = check_username_full(target)
    if is_free:
        clickable_nick = f"<a href='https://t.me/{target}'>{target}</a>"
        bot.send_message(user_id, f"{EMOJI['found']} <b>НИК УЖЕ СВОБОДЕН ✅</b>\n\n<b>Ваш ник:</b> {clickable_nick} - @{target}\n<b>Статус:</b> Свободен\n\n🔗 https://t.me/{target}", parse_mode='HTML', link_preview_options=types.LinkPreviewOptions(url="https://i.postimg.cc/nhbMgpRy/1775474714965.png", show_above_text=True))
        return
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with db_lock:
        cursor.execute("INSERT INTO traps (user_id, target_username, status, created_date) VALUES (?, ?, 'active', ?)", (user_id, target, now))
        conn.commit()
    bot.send_message(user_id, f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> ЛОВУШКА УСТАНОВЛЕНА!\n\n🎯 @{target}\n{EMOJI['time']} Сообщу, когда освободится", parse_mode='HTML', link_preview_options=types.LinkPreviewOptions(url="https://i.postimg.cc/nhbMgpRy/1775474714965.png", show_above_text=True))

def check_traps():
    while True:
        try:
            time.sleep(30)
            with db_lock:
                cursor.execute("SELECT id, user_id, target_username FROM traps WHERE status = 'active'")
                traps = cursor.fetchall()
            for trap_id, user_id, target in traps:
                is_free, status = check_username_full(target)
                if is_free:
                    with db_lock:
                        cursor.execute("UPDATE traps SET status = 'completed' WHERE id = ?", (trap_id,))
                        conn.commit()
                    try:
                        clickable_nick = f"<a href='https://t.me/{target}'>{target}</a>"
                        bot.send_message(user_id, f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> ЛОВУШКА СРАБОТАЛА!\n\n✅ <b>Ваш ник:</b> {clickable_nick} - @{target}\n✅ {target} теперь свободен!\n\n🔗 https://t.me/{target}", parse_mode='HTML', link_preview_options=types.LinkPreviewOptions(url="https://i.postimg.cc/nhbMgpRy/1775474714965.png", show_above_text=True))
                    except:
                        pass
        except:
            pass

threading.Thread(target=check_traps, daemon=True).start()

@bot.callback_query_handler(func=lambda call: call.data == "search_mode_word")
@subscription_required
def word_search_menu_handler(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    user = get_user(user_id)
    has_premium = False
    if user and user['subscription_end']:
        try:
            if datetime.datetime.now() < datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S'):
                has_premium = True
        except:
            pass
    if not has_premium:
        bot.send_message(user_id, f"{EMOJI['error']} <b>СЛОВО только для Premium!</b>\n\nКупить премиум можно в профиле", parse_mode='HTML')
        return
    bot.send_photo(user_id, photo="https://i.postimg.cc/nhbMgpRy/1775474714965.png", caption=f"🔤 <b>СЛОВО</b>\n\nВведите основу (например: <code>style</code>)\nБот найдет свободные ники с этим корнем\nМинимум 3 буквы, максимум 10 букв", parse_mode='HTML')
    bot.register_next_step_handler(call.message, process_word_search_new)

def process_word_search_new(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    word = message.text.strip().lower()
    if len(word) < 3 or len(word) > 10 or not word.isalpha():
        bot.send_message(user_id, f"{EMOJI['error']} <b>Слово должно быть 3-10 букв!</b>", parse_mode='HTML')
        return
        
    use_search(user_id)
    
    msg = bot.send_message(user_id, f"🔤 <b>Поиск ников со словом '{word}'...</b>", parse_mode='HTML')
    suffixes = ['vk', 'mx', 'x', 'z', 'qq', 'top', 'pro', 'new', 'live', 'tv', 'net', 'me', 'girl', 'boy', 'god', 'king', 'queen', 'star', 'moon', 'sun', 'fire', 'ice', 'dark', 'light']
    prefixes = ['i', 'my', 'the', 'real', 'just', 'mr', 'miss', 'best', 'super', 'pro', 'top', 'x', 'z', 'v', 'k', 'j', 'd', 'r', 'f', 'g', 't', 'm', 'l', 's', 'p', 'q', 'y', 'h', 'b', 'c', 'n', 'o', 'e', 'u', 'a']
    attempts = 200
    checked = 0
    for i in range(attempts):
        username = word + random.choice(suffixes) if i % 2 == 0 else random.choice(prefixes) + word
        if len(username) < 5 or len(username) > 32:
            continue
        checked += 1
        is_free, status = check_username_full(username)
        if is_free:
            price = estimate_price(username)
            add_found(user_id)
            try:
                bot.delete_message(user_id, msg.message_id)
            except:
                pass
                
            searches_left = get_available_searches(user_id)
            win_text = (f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> НИК НАЙДЕН!\n\n"
                        f"<tg-emoji emoji-id='5084979757905347540'>⭐</tg-emoji> Ник: @{username}\n"
                        f"<tg-emoji emoji-id='5084923566848213749'>⭐</tg-emoji> Букв: {len(username)} букв\n"
                        f"<tg-emoji emoji-id='5134438483867206614'>⭐</tg-emoji> Примерная стоимость: {price} Stars\n\n"
                        f"Осталось поисков: {'Безлимит (Премиум)' if has_premium(user_id) else searches_left}\n"
                        f"<tg-emoji emoji-id='4911656069207426158'>⭐</tg-emoji> Наш канал: {REQUIRED_CHANNEL}")
            
            search_markup = types.InlineKeyboardMarkup()
            search_markup.add(types.InlineKeyboardButton("Найти другой", callback_data="search_mode_word"))
            bot.send_message(user_id, win_text, parse_mode='HTML', reply_markup=search_markup)
            return
            
        if checked % 10 == 0:
            try:
                bot.edit_message_text(f"🔤 <b>Поиск...</b> Проверено: {checked}/{attempts}", user_id, msg.message_id, parse_mode='HTML')
            except:
                pass
        time.sleep(REQUEST_TIMEOUT)
    bot.edit_message_text(f"{EMOJI['error']} <b>Ничего не найдено</b>\n\nПопробуй другое слово!", user_id, msg.message_id, parse_mode='HTML')

# ========== СЛОВО ==========
@bot.message_handler(func=lambda m: m.text == f"СЛОВО {EMOJI['premium']}")
@subscription_required
def word_search_menu(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    user = get_user(user_id)
    has_premium = False
    if user and user['subscription_end']:
        try:
            if datetime.datetime.now() < datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S'):
                has_premium = True
        except:
            pass
    if not has_premium:
        bot.send_message(user_id, f"{EMOJI['error']} <b>СЛОВО только для Premium!</b>\n\nКупить премиум можно в кнопке {EMOJI['premium']} ПРЕМИУМ", parse_mode='HTML')
        return
    bot.send_photo(user_id, photo="https://i.postimg.cc/nhbMgpRy/1775474714965.png", caption=f"🔤 <b>СЛОВО {EMOJI['premium']}</b>\n\nВведите слово (например: <code>light</code>)\nБот найдет свободные ники с этим словом\nМинимум 3 буквы, максимум 10 букв", parse_mode='HTML')
    bot.register_next_step_handler(message, process_word_search)

def process_word_search(message):
    user_id = message.from_user.id
    allowed, error_msg = check_rate_limit(user_id)
    if not allowed:
        bot.send_message(user_id, error_msg, parse_mode='HTML')
        return
    word = message.text.strip().lower()
    if len(word) < 3 or len(word) > 10 or not word.isalpha():
        bot.send_message(user_id, f"{EMOJI['error']} <b>Слово должно быть 3-10 букв!</b>", parse_mode='HTML')
        return
    user = get_user(user_id)
    packages = user.get('search_packages', 0) if user else 0
    searches_today = user.get('searches_today', 0) if user else 0
    if searches_today >= BASE_SEARCHES and packages <= 0:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Недостаточно поисков!</b>\n\nКупите пакеты поисков через кнопку ПОИСКИ", parse_mode='HTML')
        return
    if searches_today < BASE_SEARCHES:
        use_search(user_id)
    else:
        add_search_packages(user_id, -1)
    msg = bot.send_message(user_id, f"🔤 <b>Поиск ников со словом '{word}'...</b>", parse_mode='HTML')
    suffixes = ['vk', 'mx', 'x', 'z', 'qq', 'top', 'pro', 'new', 'live', 'tv', 'net', 'me', 'girl', 'boy', 'god', 'king', 'queen', 'star', 'moon', 'sun', 'fire', 'ice', 'dark', 'light']
    prefixes = ['i', 'my', 'the', 'real', 'just', 'mr', 'miss', 'best', 'super', 'pro', 'top', 'x', 'z', 'v', 'k', 'j', 'd', 'r', 'f', 'g', 't', 'm', 'l', 's', 'p', 'q', 'y', 'h', 'b', 'c', 'n', 'o', 'e', 'u', 'a']
    attempts = 200
    checked = 0
    for i in range(attempts):
        username = word + random.choice(suffixes) if i % 2 == 0 else random.choice(prefixes) + word
        if len(username) < 5 or len(username) > 32:
            continue
        checked += 1
        is_free, status = check_username_full(username)
        if is_free:
            price = estimate_price(username)
            add_found(user_id)
            try:
                bot.delete_message(user_id, msg.message_id)
            except:
                pass
            clickable_nick = f"<a href='https://t.me/{username}'>{username}</a>"
            bot.send_message(user_id, f"{EMOJI['found']} <b>НИК НАЙДЕН ✅</b>\n\n<b>Ваш ник:</b> @{username} ~ {clickable_nick}\n<b>Кол-во символов:</b> {len(username)}\n<b>Ценность:</b> {price} ⭐\n<b>Статус:</b> Свободен\n\n🔗 https://t.me/{username}\n\n🔤 Слово: <code>{word}</code>", parse_mode='HTML', link_preview_options=types.LinkPreviewOptions(url="https://i.postimg.cc/nhbMgpRy/1775474714965.png", show_above_text=True))
            return
        if checked % 5 == 0:
            try:
                bot.edit_message_text(f"🔤 <b>Поиск...</b> Проверено: {checked}/{attempts}", user_id, msg.message_id, parse_mode='HTML')
            except:
                pass
    bot.edit_message_text(f"{EMOJI['error']} <b>Ничего не найдено</b>\n\nПопробуй другое слово!", user_id, msg.message_id, parse_mode='HTML')

# ========== ПРОФИЛЬ ==========
@bot.message_handler(func=lambda m: m.text == "Профиль")
def profile(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        user, _ = create_user(user_id, message.from_user.username)
        user = get_user(user_id)
        
    prem_status = "<tg-emoji emoji-id='5121063440311386962'>❌</tg-emoji> Нет"
    if user['subscription_end']:
        try:
            end = datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.now() < end:
                prem_status = f"<tg-emoji emoji-id='5123163417326126159'>✅</tg-emoji> есть до {end.strftime('%d.%m.%Y')}"
        except:
            pass
            
    with db_lock:
        cursor.execute("SELECT COUNT(*) FROM traps WHERE user_id = ? AND status = 'active'", (user_id,))
        traps_active = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM traps WHERE user_id = ? AND status = 'completed'", (user_id,))
        traps_completed = cursor.fetchone()[0]
        
    registration_date = user.get('created_date', 'Неизвестно')
    if registration_date and registration_date != 'Неизвестно':
        try:
            date_obj = datetime.datetime.strptime(registration_date, '%Y-%m-%d %H:%M:%S')
            registration_date = date_obj.strftime('%d.%m.%Y %H:%M')
        except:
            pass
            
    username_text = f"@{user['username']}" if user['username'] else "Нет"
    searches_today = user.get('searches_today', 0)
    total_searches = user.get('total_searches', 0)
    found_count = user.get('found_count', 0)
    refs_count = user.get('referrals_count', 0)

    text = (f"<tg-emoji emoji-id='4904848288345228262'>⭐</tg-emoji> ПРОФИЛЬ\n\n"
            f"<tg-emoji emoji-id='5116512467194741904'>⭐</tg-emoji> ID: <code>{user_id}</code>\n"
            f"<tg-emoji emoji-id='5116512467194741904'>⭐</tg-emoji> Юзернейм: {username_text}\n\n"
            f"<tg-emoji emoji-id='5116175844837950263'>⭐</tg-emoji> Премиум: {prem_status}\n"
            f"<tg-emoji emoji-id='5104960787579929462'>⭐</tg-emoji> Сегодня: {searches_today}/3\n"
            f"<tg-emoji emoji-id='5122933683820430249'>⭐</tg-emoji> Всего поисков: {total_searches}\n"
            f"<tg-emoji emoji-id='5116298753917060171'>⭐</tg-emoji> Найдено ников: {found_count}\n"
            f"<tg-emoji emoji-id='4916086774649848789'>⭐</tg-emoji> Ловушек: {traps_active} активных / {traps_completed} сработало\n"
            f"<tg-emoji emoji-id='4916086774649848789'>⭐</tg-emoji> Рефералов: {refs_count} человека\n\n"
            f"<tg-emoji emoji-id='5118357331742032622'>⭐</tg-emoji> Регистрация: {registration_date}")
            
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Рефералка", callback_data="profile_referral"),
        types.InlineKeyboardButton("🏆 Топ", callback_data="profile_top")
    )
    
    bot.send_photo(user_id, photo="https://i.postimg.cc/nhbMgpRy/1775474714965.png", caption=text, parse_mode='HTML', reply_markup=markup)

# ========== РЕФЕРАЛЫ (CALLBACK) ==========
@bot.callback_query_handler(func=lambda call: call.data == "profile_referral")
def referral_callback(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user:
        user, _ = create_user(user_id, call.from_user.username)
        user = get_user(user_id)
        
    link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    total_refs = user['referrals_count'] if user else 0
    active_refs = user['referrals_count'] if user else 0 # Заглушка, так как пока нет отдельного поля на активированных
    
    next_reward_text = "5 реф - 1 дн Premium"
    if total_refs >= 20: next_reward_text = "Макс. награда достигнута"
    elif total_refs >= 12: next_reward_text = "20 реф - 25 дн Premium"
    elif total_refs >= 8: next_reward_text = "12 реф - 7 дн Premium"
    elif total_refs >= 5: next_reward_text = "8 реф - 3 дн Premium"

    text = (f"<tg-emoji emoji-id='5123237479742178762'>⭐</tg-emoji> РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
            f"<tg-emoji emoji-id='4916086774649848789'>⭐</tg-emoji> Твоя ссылка: <code>{link}</code>\n\n"
            f"<tg-emoji emoji-id='4906943755644306322'>⭐</tg-emoji> Статистика:\n"
            f"<tg-emoji emoji-id='4918087434840834979'>⭐</tg-emoji> Приглашено: {total_refs}\n"
            f"<tg-emoji emoji-id='4918087434840834979'>⭐</tg-emoji> Активировано: {active_refs}\n\n"
            f"<tg-emoji emoji-id='4916105371858240403'>⭐</tg-emoji> НАГРАДЫ:\n"
            f"5 рефералов - 1 дн Premium\n"
            f"8 рефералов - 3 дн Premium\n"
            f"12 рефералов - 7 дн Premium\n"
            f"20 рефералов - 25 дн Premium\n"
            f"<tg-emoji emoji-id='5134202243486057363'>⭐</tg-emoji> Следующая награда: {next_reward_text}\n\n"
            f"<tg-emoji emoji-id='5116275208906343429'>⭐</tg-emoji> Реферал засчитывается после подписки на группу!")
            
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="profile_back"))
    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "profile_top")
def top_callback(call):
    with db_lock:
        cursor.execute("SELECT username, user_id, referrals_count FROM users WHERE referrals_count > 0 ORDER BY referrals_count DESC LIMIT 10")
        top_users = cursor.fetchall()
        
    text = f"<tg-emoji emoji-id='4904973211763999824'>⭐</tg-emoji> ТОП РЕФЕРАЛОВ <tg-emoji emoji-id='4904832912362309275'>🏆</tg-emoji>\n\n"
    if not top_users:
        text += "Пока нет участников"
    else:
        for i, (username, uid, refs) in enumerate(top_users, 1):
            name = f"@{username}" if username else f"ID {uid}"
            text += f"<tg-emoji emoji-id='4904848288345228262'>⭐</tg-emoji> {i}. {name} — {refs} реф.\n"
            
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="profile_back"))
    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "profile_back")
def profile_back_callback(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user: return
    
    prem_status = "<tg-emoji emoji-id='5121063440311386962'>❌</tg-emoji> Нет"
    if user['subscription_end']:
        try:
            end = datetime.datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.now() < end:
                prem_status = f"<tg-emoji emoji-id='5123163417326126159'>✅</tg-emoji> есть до {end.strftime('%d.%m.%Y')}"
        except:
            pass
            
    with db_lock:
        cursor.execute("SELECT COUNT(*) FROM traps WHERE user_id = ? AND status = 'active'", (user_id,))
        traps_active = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM traps WHERE user_id = ? AND status = 'completed'", (user_id,))
        traps_completed = cursor.fetchone()[0]
        
    registration_date = user.get('created_date', 'Неизвестно')
    if registration_date and registration_date != 'Неизвестно':
        try:
            date_obj = datetime.datetime.strptime(registration_date, '%Y-%m-%d %H:%M:%S')
            registration_date = date_obj.strftime('%d.%m.%Y %H:%M')
        except:
            pass
            
    username_text = f"@{user['username']}" if user['username'] else "Нет"
    searches_today = user.get('searches_today', 0)
    total_searches = user.get('total_searches', 0)
    found_count = user.get('found_count', 0)
    refs_count = user.get('referrals_count', 0)

    text = (f"<tg-emoji emoji-id='4904848288345228262'>⭐</tg-emoji> ПРОФИЛЬ\n\n"
            f"<tg-emoji emoji-id='5116512467194741904'>⭐</tg-emoji> ID: <code>{user_id}</code>\n"
            f"<tg-emoji emoji-id='5116512467194741904'>⭐</tg-emoji> Юзернейм: {username_text}\n\n"
            f"<tg-emoji emoji-id='5116175844837950263'>⭐</tg-emoji> Премиум: {prem_status}\n"
            f"<tg-emoji emoji-id='5104960787579929462'>⭐</tg-emoji> Сегодня: {searches_today}/3\n"
            f"<tg-emoji emoji-id='5122933683820430249'>⭐</tg-emoji> Всего поисков: {total_searches}\n"
            f"<tg-emoji emoji-id='5116298753917060171'>⭐</tg-emoji> Найдено ников: {found_count}\n"
            f"<tg-emoji emoji-id='4916086774649848789'>⭐</tg-emoji> Ловушек: {traps_active} активных / {traps_completed} сработало\n"
            f"<tg-emoji emoji-id='4916086774649848789'>⭐</tg-emoji> Рефералов: {refs_count} человека\n\n"
            f"<tg-emoji emoji-id='5118357331742032622'>⭐</tg-emoji> Регистрация: {registration_date}")
            
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Рефералка", callback_data="profile_referral"),
        types.InlineKeyboardButton("Топ", callback_data="profile_top")
    )
    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, parse_mode='HTML', reply_markup=markup)



# ========== МАРКЕТ ==========
@bot.message_handler(func=lambda m: m.text == "МАРКЕТ")
@subscription_required
def market_menu(message):
    user_id = message.from_user.id
    avg_rating, rating_count = get_user_rating(user_id)
    rating_str = format_rating_stars(avg_rating, rating_count)
    text = f"🏪 <b>МАРКЕТ</b>\n\n⭐ Рейтинг: {rating_str}\n"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 Купить", callback_data="market_list_0"),
        types.InlineKeyboardButton("💰 Продать", callback_data="market_sell"),
        types.InlineKeyboardButton("📦 Мои посты", callback_data="market_my")
    )
    bot.send_message(user_id, text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('market_list_'))
def market_list_callback(call):
    user_id = call.from_user.id
    page = int(call.data.split('_')[-1])
    listings = get_market_listings(page, 6)
    total = get_market_count()
    total_pages = max(1, (total + 5) // 6)
    if not listings:
        text = "🛒 <b>ЮЗЕРНЕЙМЫ НА ПРОДАЖУ</b>\n\nПока нет лотов"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="market_back"))
        bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML', reply_markup=markup)
        return
    text = f"🛒 <b>ЮЗЕРНЕЙМЫ НА ПРОДАЖУ</b>\n\n📊 Всего лотов: {total}\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for listing in listings:
        lid, seller_id, username, price, desc, created = listing
        seller = get_user(seller_id)
        seller_name = f"@{seller['username']}" if seller and seller['username'] else f"ID {seller_id}"
        avg, cnt = get_user_rating(seller_id)
        rating_str = "🆕" if cnt == 0 else f"{avg}/5⭐"
        text += f"🏷 @{username} — {price}⭐\n👤 {seller_name} • {rating_str}\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    for listing in listings:
        lid, seller_id, username, price, desc, created = listing
        markup.add(types.InlineKeyboardButton(f"@{username} — {price}⭐", callback_data=f"market_item_{lid}"))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"market_list_{page-1}"))
    nav_buttons.append(types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"market_list_{page+1}"))
    markup.row(*nav_buttons)
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="market_back"))
    bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('market_item_'))
def market_item_callback(call):
    user_id = call.from_user.id
    listing_id = int(call.data.split('_')[-1])
    listing = get_listing_by_id(listing_id)
    if not listing:
        bot.answer_callback_query(call.id, "❌ Лот не найден", show_alert=True)
        return
    lid, seller_id, username, price, desc, sold, buyer_id, created_date = listing
    if sold:
        bot.answer_callback_query(call.id, "❌ Лот уже продан", show_alert=True)
        return
    seller = get_user(seller_id)
    seller_name = f"@{seller['username']}" if seller and seller['username'] else f"ID {seller_id}"
    avg, cnt = get_user_rating(seller_id)
    rating_str = "🆕 (0 отзывов)" if cnt == 0 else f"{avg}/5 ({cnt} отзывов)"
    date_str = created_date[:16] if created_date else "?"
    price_rub = int(price * 1.25)
    text = f"📦 Лот #{lid}\n━━━━━━━━━━━━━━━━━━━━━━━\n\n👤 Юзернейм\n🏷 @{username}\n"
    if desc:
        text += f"📝 {desc}\n"
    text += f"\n💰 Цена: {price}⭐ ({price_rub}₽)\n\n👤 {seller_name}\n⭐ {rating_str}\n📅 {date_str}"
    markup = types.InlineKeyboardMarkup(row_width=1)
    if seller and seller['username']:
        markup.add(types.InlineKeyboardButton(f"💰 Купить за {price}⭐", url=f"https://t.me/{seller['username']}"))
    markup.add(types.InlineKeyboardButton(f"⭐ Отзывы ({cnt})", callback_data=f"market_reviews_{seller_id}"))
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="market_list_0"))
    bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('market_reviews_'))
def market_reviews_callback(call):
    user_id = call.from_user.id
    seller_id = int(call.data.split('_')[-1])
    seller = get_user(seller_id)
    seller_name = f"@{seller['username']}" if seller and seller['username'] else f"ID {seller_id}"
    avg, cnt = get_user_rating(seller_id)
    reviews = get_user_reviews(seller_id)
    text = f"⭐ <b>ОТЗЫВЫ О {seller_name}</b>\n━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 Рейтинг: {avg}/5⭐ ({cnt} отзывов)\n\n"
    if reviews:
        for i, (rater_id, rating, review_text, created) in enumerate(reviews[:10], 1):
            rater = get_user(rater_id)
            rater_name = f"@{rater['username']}" if rater and rater['username'] else f"ID {rater_id}"
            stars = "⭐" * rating
            date_str = created[:10] if created else "?"
            text += f"{i}. {stars} ({rating}/5)\n👤 {rater_name} • 📅 {date_str}\n"
            if review_text:
                text += f"💬 {review_text[:150]}{'...' if len(review_text or '') > 150 else ''}\n"
            text += "\n"
    else:
        text += "Пока нет отзывов 🤷‍♂️\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("✍️ Оставить отзыв", callback_data=f"market_addreview_{seller_id}"))
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="market_list_0"))
    bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('market_addreview_'))
def market_addreview_callback(call):
    user_id = call.from_user.id
    seller_id = int(call.data.split('_')[-1])
    if user_id == seller_id:
        bot.answer_callback_query(call.id, "❌ Нельзя оставить отзыв себе", show_alert=True)
        return
    with db_lock:
        cursor.execute("SELECT id FROM user_ratings WHERE rater_id = ? AND rated_id = ?", (user_id, seller_id))
        if cursor.fetchone():
            bot.answer_callback_query(call.id, "❌ Вы уже оставляли отзыв этому продавцу", show_alert=True)
            return
    text = "✍️ <b>ОСТАВИТЬ ОТЗЫВ</b>\n\nВыберите оценку:"
    markup = types.InlineKeyboardMarkup(row_width=5)
    markup.add(
        types.InlineKeyboardButton("1⭐", callback_data=f"market_rate_{seller_id}_1"),
        types.InlineKeyboardButton("2⭐", callback_data=f"market_rate_{seller_id}_2"),
        types.InlineKeyboardButton("3⭐", callback_data=f"market_rate_{seller_id}_3"),
        types.InlineKeyboardButton("4⭐", callback_data=f"market_rate_{seller_id}_4"),
        types.InlineKeyboardButton("5⭐", callback_data=f"market_rate_{seller_id}_5")
    )
    markup.add(types.InlineKeyboardButton("◀️ Отмена", callback_data=f"market_reviews_{seller_id}"))
    bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('market_rate_'))
def market_rate_callback(call):
    user_id = call.from_user.id
    parts = call.data.split('_')
    seller_id = int(parts[2])
    rating = int(parts[3])
    text = f"✍️ <b>ОСТАВИТЬ ОТЗЫВ</b>\n\nОценка: {'⭐' * rating}\n\nНапишите текст отзыва (или отправьте - чтобы пропустить):"
    bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML')
    bot.register_next_step_handler(call.message, lambda m: process_review_text(m, seller_id, rating))

def process_review_text(message, seller_id, rating):
    user_id = message.from_user.id
    review_text = message.text.strip() if message.text.strip() != '-' else ''
    if len(review_text) > 500:
        review_text = review_text[:500]
    success, msg = add_review(user_id, seller_id, rating, review_text)
    if success:
        text = f"✅ <b>Отзыв добавлен!</b>\n\nОценка: {'⭐' * rating}"
        if review_text:
            text += f"\n💬 {review_text}"
    else:
        text = f"❌ <b>Ошибка:</b> {msg}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ К отзывам", callback_data=f"market_reviews_{seller_id}"))
    bot.send_message(user_id, text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'market_back')
def market_back_callback(call):
    user_id = call.from_user.id
    avg_rating, rating_count = get_user_rating(user_id)
    rating_str = format_rating_stars(avg_rating, rating_count)
    text = f"🏪 <b>МАРКЕТ</b>\n\n⭐ Рейтинг: {rating_str}\n"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 Юзернеймы", callback_data="market_list_0"),
        types.InlineKeyboardButton("💰 Продать", callback_data="market_sell"),
        types.InlineKeyboardButton("📦 Мои лоты", callback_data="market_my")
    )
    bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'market_sell')
def market_sell_callback(call):
    user_id = call.from_user.id
    text = "💰 <b>ПРОДАТЬ ЮЗЕРНЕЙМ</b>\n\nВведите юзернейм (без @):"
    bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML')
    bot.register_next_step_handler(call.message, process_sell_username)

def process_sell_username(message):
    user_id = message.from_user.id
    username = message.text.strip().lstrip('@').lower()
    if len(username) < 5 or len(username) > 32:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Юзернейм должен быть от 5 до 32 символов</b>", parse_mode='HTML')
        return
    if not all(c.isalnum() or c == '_' for c in username):
        bot.send_message(user_id, f"{EMOJI['error']} <b>Юзернейм содержит недопустимые символы</b>", parse_mode='HTML')
        return
    msg = bot.send_message(user_id, "💵 <b>Введите цену в звездах:</b>", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_sell_price(m, username))

def process_sell_price(message, username):
    user_id = message.from_user.id
    try:
        price = int(message.text.strip())
        if price < 1 or price > 100000:
            bot.send_message(user_id, f"{EMOJI['error']} <b>Цена от 1 до 100000⭐</b>", parse_mode='HTML')
            return
    except:
        bot.send_message(user_id, f"{EMOJI['error']} <b>Введите число</b>", parse_mode='HTML')
        return
    msg = bot.send_message(user_id, "📝 <b>Введите описание</b> (или отправьте - чтобы пропустить):", parse_mode='HTML')
    bot.register_next_step_handler(msg, lambda m: process_sell_description(m, username, price))

def process_sell_description(message, username, price):
    user_id = message.from_user.id
    description = message.text.strip() if message.text.strip() != '-' else ''
    if len(description) > 200:
        description = description[:200]
    add_market_listing(user_id, username, price, description)
    text = f"✅ <b>ЛОТ СОЗДАН!</b>\n\n@{username} — {price}⭐\n"
    if description:
        text += f"📝 {description}\n"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ В маркет", callback_data="market_back"))
    bot.send_message(user_id, text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'market_my')
def market_my_callback(call):
    user_id = call.from_user.id
    listings = get_user_listings(user_id)
    if not listings:
        text = "📦 <b>МОИ ЛОТЫ</b>\n\nУ вас нет активных лотов"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="market_back"))
        bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML', reply_markup=markup)
        return
    text = "📦 <b>МОИ ЛОТЫ</b>\n\n"
    active = [l for l in listings if l[4] == 0]
    sold = [l for l in listings if l[4] == 1]
    markup = types.InlineKeyboardMarkup(row_width=1)
    if active:
        text += "🟢 <b>Активные:</b>\n"
        for lid, username, price, desc, is_sold, created in active:
            text += f"@{username} — {price}⭐\n"
            markup.add(types.InlineKeyboardButton(f"❌ Удалить @{username}", callback_data=f"market_cancel_{lid}"))
    if sold:
        text += "\n✅ <b>Проданные:</b>\n"
        for lid, username, price, desc, is_sold, created in sold[:5]:
            text += f"@{username} — {price}⭐\n"
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="market_back"))
    bot.edit_message_text(text, user_id, call.message.message_id, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('market_cancel_'))
def market_cancel_callback(call):
    user_id = call.from_user.id
    listing_id = int(call.data.split('_')[-1])
    success, msg = cancel_listing(listing_id, user_id)
    if success:
        bot.answer_callback_query(call.id, "✅ Лот удален", show_alert=True)
        market_my_callback(call)
    else:
        bot.answer_callback_query(call.id, f"❌ {msg}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'noop')
def noop_callback(call):
    bot.answer_callback_query(call.id)

# ========== ТОП ==========
@bot.message_handler(func=lambda m: m.text == f"{EMOJI['top']} ТОП")
def top(message):
    with db_lock:
        cursor.execute("SELECT username, user_id, referrals_count FROM users WHERE referrals_count > 0 ORDER BY referrals_count DESC LIMIT 10")
        top_users = cursor.fetchall()
    text = f"{EMOJI['top']} <b>ТОП РЕФЕРАЛОВ</b>\n\n"
    if not top_users:
        text += "Пока нет участников 🏆"
    else:
        for i, (username, uid, refs) in enumerate(top_users, 1):
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else "👤"
            name = f"@{username}" if username else f"ID {uid}"
            text += f"{medal} {i}. {name} — {refs} реф.\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

# ========== СТАТИСТИКА ==========
@bot.message_handler(func=lambda m: m.text == "Статистика (бота)")
def stats(message):
    with db_lock:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_end > datetime('now')")
        premium_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM found")
        found_nicks = cursor.fetchone()[0]
        # Заглушка, если нет слов в бд
        found_words = 0
        try:
            cursor.execute("SELECT SUM(total_searches) FROM users")
            total_searches = cursor.fetchone()[0] or 0
        except:
            total_searches = 0
            
        cursor.execute("SELECT COUNT(*) FROM traps WHERE status = 'active'")
        active_traps = cursor.fetchone()[0]
        
    text = (f"<tg-emoji emoji-id='4906943755644306322'>⭐</tg-emoji> СТАТИСТИКА БОТА\n\n"
            f"<tg-emoji emoji-id='4904848288345228262'>⭐</tg-emoji> Пользователей: {total_users}\n"
            f"<tg-emoji emoji-id='4913497231492908158'>⭐</tg-emoji> Премиум: {premium_users}\n"
            f"<tg-emoji emoji-id='5084923566848213749'>⭐</tg-emoji> Найдено ников: {found_nicks}\n"
            f"<tg-emoji emoji-id='5116574228824458340'>⭐</tg-emoji> Найдено Слов: {found_words}\n"
            f"<tg-emoji emoji-id='5098094273039959279'>⭐</tg-emoji> Активных ловушек: {active_traps}\n"
            f"<tg-emoji emoji-id='5116414868357907335'>⭐</tg-emoji> Всего поисков: {total_searches}")
    bot.send_message(message.chat.id, text, parse_mode='HTML')

# ========== ИНФО ==========
@bot.message_handler(func=lambda m: m.text == f"{EMOJI['info']} ИНФО")
def info(message):
    text = f"{EMOJI['info']} <b>ИНФОРМАЦИЯ</b>\n\n🤖 <b>NICK FINDER BOT</b>\nВерсия: 10.0\n\n{EMOJI['crown']} Админ: {YOUR_USERNAME}\n{EMOJI['channel']} Канал: {REQUIRED_CHANNEL}\n{EMOJI['premium']} Premium: {SELLER_USERNAME}\n\n{EMOJI['fire']} Рефералы: 5→1д | 8→3д | 12→7д | 20→30д"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

# ========== ПРЕМИУМ ==========
@bot.message_handler(func=lambda m: m.text == "Премиум")
def premium(message):
    text = (f"<tg-emoji emoji-id='4918203446202467778'>⭐</tg-emoji> ПРЕМИУМ ПОДПИСКА\n\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> ФУНКЦИИ:\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Фильтр по маске\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Ловушка на ник\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Слово\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Безлимитный поиск")
            
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"1 день", callback_data="premium_sel_1"),
        types.InlineKeyboardButton(f"3 дня", callback_data="premium_sel_3"),
        types.InlineKeyboardButton(f"7 дней", callback_data="premium_sel_7"),
        types.InlineKeyboardButton(f"30 дней", callback_data="premium_sel_30")
    )
    bot.send_photo(message.chat.id, photo="https://i.postimg.cc/nhbMgpRy/1775474714965.png", caption=text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('premium_sel_'))
def premium_selection_callback(call):
    days = int(call.data.split('_')[-1])
    price_stars = PREMIUM_PRICES[days]
    prices_crypto = {1: 0.74, 3: 1.80, 7: 3.15, 30: 6.75}
    price_usd = prices_crypto[days]
    
    text = (f"<tg-emoji emoji-id='5116093437300442328'>⭐</tg-emoji> Способ оплаты\n\n"
            f"Вы выбрали:\n"
            f"Тариф: {days} дн.\n"
            f"Цена: {price_stars} ⭐ / ${price_usd}")
            
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("Stars", callback_data=f"premium_stars_{days}"),
        types.InlineKeyboardButton("Ton", callback_data=f"premium_crypto_ton_{days}"),
        types.InlineKeyboardButton("Usdt", callback_data=f"premium_crypto_usdt_{days}")
    )
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="premium_back"))
    
    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "premium_back")
def premium_back_callback(call):
    text = (f"<tg-emoji emoji-id='4918203446202467778'>⭐</tg-emoji> ПРЕМИУМ ПОДПИСКА\n\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> ФУНКЦИИ:\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Фильтр по маске\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Ловушка на ник\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Слово\n"
            f"<tg-emoji emoji-id='5134122666331996794'>⭐</tg-emoji> Безлимитный поиск")
            
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"1 день", callback_data="premium_sel_1"),
        types.InlineKeyboardButton(f"3 дня", callback_data="premium_sel_3"),
        types.InlineKeyboardButton(f"7 дней", callback_data="premium_sel_7"),
        types.InlineKeyboardButton(f"30 дней", callback_data="premium_sel_30")
    )
    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=text, parse_mode='HTML', reply_markup=markup)

# ========== ПОИСКИ ==========
@bot.message_handler(func=lambda m: m.text == "ПОИСКИ")
def buy_searches_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    packages = user.get('search_packages', 0) if user else 0
    text = f"📦 <b>ПАКЕТЫ ПОИСКОВ</b>\n\n💰 У вас: {packages} поисков\n\n💵 <b>ЦЕНЫ:</b>\n10 поисков — 10⭐ / $0.15\n50 поисков — 50⭐ / $0.75\n100 поисков — 100⭐ / $1.50\n\nВыберите способ оплаты:"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⭐ 10 поисков (Stars)", callback_data="search_stars_10"),
        types.InlineKeyboardButton("💳 10 поисков (USDT)", callback_data="search_crypto_10"),
        types.InlineKeyboardButton("⭐ 50 поисков (Stars)", callback_data="search_stars_50"),
        types.InlineKeyboardButton("💳 50 поисков (USDT)", callback_data="search_crypto_50"),
        types.InlineKeyboardButton("⭐ 100 поисков (Stars)", callback_data="search_stars_100"),
        types.InlineKeyboardButton("💳 100 поисков (USDT)", callback_data="search_crypto_100")
    )
    bot.send_message(user_id, text, parse_mode='HTML', reply_markup=markup)

# ========== CALLBACK HANDLERS ДЛЯ ПРЕМИУМ ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('premium_stars_'))
def premium_stars_callback(call):
    user_id = call.from_user.id
    try:
        days = int(call.data.split('_')[-1])
        price = PREMIUM_PRICES[days]
        bot.answer_callback_query(call.id)
        
        bot.send_invoice(
            chat_id=user_id,
            title=f"Premium на {days} дней",
            description=f"Оплата премиум-подписки на {days} дней",
            invoice_payload=f"premium_stars_{user_id}_{days}",
            provider_token="",
            currency="XTR",
            prices=[types.LabeledPrice(label=f"Premium {days} дн", amount=price)]
        )
    except Exception as e:
        logger.error(f"Error handling stars callback: {e}")

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("premium_stars_"):
        parts = payload.split('_')
        user_id = int(parts[2])
        days = int(parts[3])
        add_premium(user_id, days)
        bot.send_message(user_id, f"🎉 <b>Оплата прошла успешно!</b>\n\nВы получили Premium на {days} дней.\nСпасибо за поддержку!", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('premium_crypto_'))
def premium_crypto_callback(call):
    user_id = call.from_user.id
    
    # Извлечём количество дней безопасно (последний элемент в split, если это число)
    parts = call.data.split('_')
    days_str = parts[-1]
    asset_pref = parts[-2]
    
    if not days_str.isdigit():
        bot.answer_callback_query(call.id, "Ошибка!", show_alert=True)
        return
        
    days = int(days_str)
    prices = {1: 0.74, 3: 1.80, 7: 3.15, 30: 6.75}
    price = prices[days]
    bot.answer_callback_query(call.id)
    
    # Для CryptoBot задаем валюту оплаты, если выбрали usdt - можно передать asset,
    # Но так как оплата идет в фиате USD, CryptoBot сам предложит выбрать крипту
    try:
        req_json = {
            "amount": price,
            "currency_type": "fiat",
            "fiat": "USD",
            "description": f"Premium {days} days",
            "payload": f"premium_{user_id}_{days}"
        }
        
        # Если нужно форснуть конкретный ассет для оплаты, можно добавить строку "accepted_assets": "TON" или "USDT"
        if asset_pref.lower() == "ton":
            req_json["accepted_assets"] = "TON"
        elif asset_pref.lower() == "usdt":
            req_json["accepted_assets"] = "USDT"
            
        response = requests.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN},
            json=req_json,
            timeout=10
        )
        data = response.json()
        if data.get('ok'):
            invoice_url = data['result']['bot_invoice_url']
            invoice_id = data['result']['invoice_id']
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(f"💳 Оплатить ${price}", url=invoice_url),
                types.InlineKeyboardButton(f"✅ Проверить оплату", callback_data=f"check_premium_crypto_{invoice_id}_{days}")
            )
            bot.send_message(user_id, f"💳 <b>ОПЛАТА КРИПТОЙ (USDT)</b>\n\n💰 Сумма: ${price}\n📦 Пакет: {days} дней\n\nНажмите кнопку ниже для оплаты:", parse_mode='HTML', reply_markup=markup)
        else:
            bot.send_message(user_id, "❌ Ошибка создания платежа. Попробуйте позже.", parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка создания CryptoBot инвойса: {e}")
        bot.send_message(user_id, "❌ Ошибка создания платежа. Попробуйте позже.", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_premium_crypto_'))
def check_premium_crypto_callback(call):
    user_id = call.from_user.id
    parts = call.data.split('_')
    invoice_id = parts[3]
    days = int(parts[4])
    
    if check_crypto_payment(invoice_id):
        add_premium(user_id, days)
        bot.answer_callback_query(call.id, f"✅ Премиум активирован на {days} дней!", show_alert=True)
        bot.edit_message_text(f"✅ <b>ПРЕМИУМ АКТИВИРОВАН</b>\n\n📅 На {days} дней", user_id, call.message.message_id, parse_mode='HTML')
    else:
        bot.answer_callback_query(call.id, "⏳ Оплата не найдена. Попробуйте позже", show_alert=True)

# ========== CALLBACK HANDLERS ДЛЯ ПОИСКОВ ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('search_stars_'))
def search_stars_callback(call):
    user_id = call.from_user.id
    amount = int(call.data.split('_')[-1])
    bot.answer_callback_query(call.id)
    bot.send_message(user_id, f"⭐ <b>ПОКУПКА ПОИСКОВ (STARS)</b>\n\nКоличество: {amount}\nЦена: {amount}⭐\n\n📩 Для оплаты напишите {SELLER_USERNAME}", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('search_crypto_'))
def search_crypto_callback(call):
    user_id = call.from_user.id
    amount = int(call.data.split('_')[-1])
    price_usd = round(amount * 0.015, 2)
    bot.answer_callback_query(call.id)
    
    try:
        response = requests.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN},
            json={
                "amount": price_usd,
                "currency_type": "fiat",
                "fiat": "USD",
                "description": f"Search package {amount} searches",
                "payload": f"searches_{user_id}_{amount}"
            },
            timeout=10
        )
        data = response.json()
        if data.get('ok'):
            invoice_url = data['result']['bot_invoice_url']
            invoice_id = data['result']['invoice_id']
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(f"💳 Оплатить ${price_usd}", url=invoice_url),
                types.InlineKeyboardButton(f"✅ Проверить оплату", callback_data=f"check_search_crypto_{invoice_id}_{amount}")
            )
            bot.send_message(user_id, f"💳 <b>ПОКУПКА ПОИСКОВ (USDT)</b>\n\n💰 Сумма: ${price_usd}\n📦 Пакет: {amount} поисков\n\nНажмите кнопку ниже для оплаты:", parse_mode='HTML', reply_markup=markup)
        else:
            bot.send_message(user_id, "❌ Ошибка создания платежа. Попробуйте позже.", parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка создания CryptoBot инвойса: {e}")
        bot.send_message(user_id, "❌ Ошибка создания платежа. Попробуйте позже.", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_search_crypto_'))
def check_search_crypto_callback(call):
    user_id = call.from_user.id
    parts = call.data.split('_')
    invoice_id = parts[3]
    amount = int(parts[4])
    
    if check_crypto_payment(invoice_id):
        add_search_packages(user_id, amount)
        bot.answer_callback_query(call.id, f"✅ {amount} поисков активировано!", show_alert=True)
        bot.edit_message_text(f"✅ <b>ПАКЕТ АКТИВИРОВАН</b>\n\n📦 +{amount} поисков", user_id, call.message.message_id, parse_mode='HTML')
    else:
        bot.answer_callback_query(call.id, "⏳ Оплата не найдена. Попробуйте позже", show_alert=True)

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет доступа к админ-панели")
        return
    text = f"{EMOJI['admin']} <b>АДМИН ПАНЕЛЬ</b>\n\n📊 <code>/stats</code> - полная статистика\n👥 <code>/users</code> - список пользователей\n💎 <code>/give ID ДНИ</code> - выдать Premium\n📦 <code>/give_searches ID КОЛ-ВО</code> - выдать пакеты поисков\n🎁 <code>/gift ID ДНИ</code> - подарить премиум\n📢 <code>/broadcast ТЕКСТ</code> - рассылка\n🔄 <code>/restart</code> - перезапуск"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    with db_lock:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_end > datetime('now')")
        premium_users = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(total_searches) FROM users")
        total_searches = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(found_count) FROM users")
        total_found = cursor.fetchone()[0] or 0
    text = f"📊 <b>ПОЛНАЯ СТАТИСТИКА</b>\n\n👥 Всего users: {total_users}\n💎 Premium: {premium_users}\n🔍 Поисков: {total_searches}\n✅ Найдено: {total_found}"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

@bot.message_handler(commands=['users'])
def admin_users(message):
    if message.from_user.id != ADMIN_ID:
        return
    with db_lock:
        cursor.execute("SELECT user_id, username, referrals_count, subscription_end FROM users ORDER BY created_date DESC LIMIT 50")
        users = cursor.fetchall()
    if not users:
        bot.reply_to(message, "Нет пользователей")
        return
    text = "👥 <b>ПОСЛЕДНИЕ 50 ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
    for uid, username, refs, sub_end in users:
        name = f"@{username}" if username else f"ID {uid}"
        prem = "💎" if sub_end and sub_end > datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') else ""
        text += f"{name} — {refs} реф {prem}\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

@bot.message_handler(commands=['give'])
def admin_give(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "❌ /give ID ДНИ\nПример: /give 123456789 7")
            return
        identifier = parts[1]
        days = int(parts[2])
        if identifier.startswith('@'):
            username = identifier[1:].lower()
            with db_lock:
                cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (username,))
                row = cursor.fetchone()
                if not row:
                    bot.reply_to(message, f"❌ Пользователь {identifier} не найден")
                    return
                user_id = row[0]
        else:
            user_id = int(identifier)
        add_premium(user_id, days)
        user = get_user(user_id)
        name = f"@{user['username']}" if user and user['username'] else f"ID {user_id}"
        bot.reply_to(message, f"✅ Premium {days}дн выдан {name}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['give_searches'])
def admin_give_searches(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "❌ /give_searches ID КОЛИЧЕСТВО\nПример: /give_searches 123456789 50")
            return
        identifier = parts[1]
        amount = int(parts[2])
        if identifier.startswith('@'):
            username = identifier[1:].lower()
            with db_lock:
                cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (username,))
                row = cursor.fetchone()
                if not row:
                    bot.reply_to(message, f"❌ Пользователь {identifier} не найден")
                    return
                user_id = row[0]
        else:
            user_id = int(identifier)
        add_search_packages(user_id, amount)
        user = get_user(user_id)
        name = f"@{user['username']}" if user and user['username'] else f"ID {user_id}"
        bot.reply_to(message, f"✅ {amount} поисков выдано {name}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['gift'])
def admin_gift(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "❌ /gift ID ДНИ\nПример: /gift 123456789 7")
            return
        receiver_id = int(parts[1])
        days = int(parts[2])
        add_premium(receiver_id, days)
        create_gift(ADMIN_ID, receiver_id, days, "admin")
        user = get_user(receiver_id)
        name = f"@{user['username']}" if user and user['username'] else f"ID {receiver_id}"
        bot.reply_to(message, f"✅ Подарен Premium {days}дн {name}")
        try:
            bot.send_message(receiver_id, f"🎁 <b>ВАМ ПОДАРИЛИ ПРЕМИУМ!</b>\n\n⏱️ Срок: {days} дней\nОт: Администратор", parse_mode='HTML')
        except:
            pass
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['broadcast'])
def admin_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.replace('/broadcast', '', 1).strip()
    if not text:
        bot.reply_to(message, "❌ /broadcast ТЕКСТ")
        return
    with db_lock:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
    success = 0
    failed = 0
    status_msg = bot.reply_to(message, f"📢 Рассылка началась...\n👥 Всего: {len(users)}")
    for user_id, in users:
        try:
            bot.send_message(user_id, text, parse_mode='HTML')
            success += 1
            time.sleep(0.05)
        except:
            failed += 1
        if success % 10 == 0:
            try:
                bot.edit_message_text(f"📢 Рассылка...\n✅ Отправлено: {success}\n❌ Ошибок: {failed}", message.chat.id, status_msg.message_id)
            except:
                pass
    bot.edit_message_text(f"✅ РАССЫЛКА ЗАВЕРШЕНА\n\n👥 Всего: {len(users)}\n✅ Отправлено: {success}\n❌ Ошибок: {failed}", message.chat.id, status_msg.message_id)

@bot.message_handler(commands=['restart'])
def admin_restart(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, "🔄 Перезапуск бота...")
    time.sleep(1)
    os._exit(0)

@bot.message_handler(func=lambda m: m.text == f"{EMOJI['admin']} АДМИН")
def admin_button(message):
    if message.from_user.id == ADMIN_ID:
        admin_panel(message)
    else:
        bot.send_message(message.chat.id, "❌ У вас нет доступа к админ-панели")

@bot.message_handler(func=lambda message: True)
def unknown_command(message):
    user_id = message.from_user.id
    logger.warning(f"Неизвестная команда от {user_id}: {message.text}")

if __name__ == "__main__":
    import os
    print("=" * 60)
    print("🚀 NICK FINDER БОТ ЗАПУЩЕН")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 60)
    bot.infinity_polling(timeout=60)
