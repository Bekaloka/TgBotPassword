
import os
import logging
import random
import string
import json
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Настройка ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

SETTINGS_FILE = Path("user_settings.json")

# --- Константы для Callback Query ---
# Это предотвращает ошибки из-за опечаток в строках
LEN_INCR = "len_incr"
LEN_DECR = "len_decr"
LEN_INFO = "len_info"
TOGGLE_UPPER = "toggle_upper"
TOGGLE_LOWER = "toggle_lower"
TOGGLE_DIGITS = "toggle_digits"
TOGGLE_SYMBOLS = "toggle_symbols"
GENERATE = "generate"


# --- Управление настройками пользователей ---
def load_user_settings() -> dict:
    """Загружает настройки пользователей из файла JSON."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON из {SETTINGS_FILE}: {e}")
        return {}

def save_user_settings(settings: dict):
    """Сохраняет настройки пользователей в файл JSON."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Ошибка записи в файл {SETTINGS_FILE}: {e}")

# --- Функции для создания клавиатуры и генерации пароля ---

def get_default_settings() -> dict:
    """Возвращает стандартные настройки генерации."""
    return {
        "length": 16,
        "use_upper": True,
        "use_lower": True,
        "use_digits": True,
        "use_symbols": True,
    }

# Загружаем настройки при старте
user_settings = load_user_settings()

def get_user_config(user_id: int) -> dict:
    """Возвращает настройки для конкретного пользователя, создавая их при необходимости."""
    # Мы используем строковые ключи в JSON, поэтому конвертируем user_id
    user_id_str = str(user_id)
    if user_id_str not in user_settings:
        user_settings[user_id_str] = get_default_settings()
    return user_settings[user_id_str]


def generate_password(settings: dict) -> str:
    """
    Генерирует пароль, гарантируя наличие хотя бы одного символа
    каждого выбранного типа для повышения надежности.
    """
    length = settings["length"]
    character_pool = []
    guaranteed_chars = []

    if settings.get("use_lower", False):
        character_pool.extend(string.ascii_lowercase)
        guaranteed_chars.append(random.choice(string.ascii_lowercase))
    if settings.get("use_upper", False):
        character_pool.extend(string.ascii_uppercase)
        guaranteed_chars.append(random.choice(string.ascii_uppercase))
    if settings.get("use_digits", False):
        character_pool.extend(string.digits)
        guaranteed_chars.append(random.choice(string.digits))
    if settings.get("use_symbols", False):
        symbols = "!@#$%^&*()_+-=[]{}|;:,.<>"
        character_pool.extend(symbols)
        guaranteed_chars.append(random.choice(symbols))

    if not character_pool:
        return "Ошибка: Выберите хотя бы один тип символов!"

    # Если требуемая длина меньше, чем количество гарантированных символов,
    # просто вернем перемешанный набор гарантированных символов.
    if length < len(guaranteed_chars):
        random.shuffle(guaranteed_chars)
        return "".join(guaranteed_chars[:length])

    # Заполняем оставшуюся часть пароля случайными символами из всего пула
    remaining_length = length - len(guaranteed_chars)
    password_list = guaranteed_chars + [random.choice(character_pool) for _ in range(remaining_length)]

    # Финальное перемешивание, чтобы гарантированные символы не стояли в начале
    random.shuffle(password_list)

    return "".join(password_list)


async def build_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Строит и отправляет интерактивное меню настроек."""
    config = get_user_config(update.effective_user.id)

    # Иконки для наглядности
    upper_icon = "✅" if config["use_upper"] else "❌"
    lower_icon = "✅" if config["use_lower"] else "❌"
    digits_icon = "✅" if config["use_digits"] else "❌"
    symbols_icon = "✅" if config["use_symbols"] else "❌"

    keyboard = [
        [
            InlineKeyboardButton("➖", callback_data=LEN_DECR),
            InlineKeyboardButton(f'Длина: {config["length"]}', callback_data=LEN_INFO),
            InlineKeyboardButton("➕", callback_data=LEN_INCR),
        ],
        [
            InlineKeyboardButton(f"{upper_icon} Заглавные", callback_data=TOGGLE_UPPER),
            InlineKeyboardButton(f"{lower_icon} Строчные", callback_data=TOGGLE_LOWER),
        ],
        [
            InlineKeyboardButton(f"{digits_icon} Цифры", callback_data=TOGGLE_DIGITS),
            InlineKeyboardButton(f"{symbols_icon} Символы", callback_data=TOGGLE_SYMBOLS),
        ],
        [
            InlineKeyboardButton("🔑 Сгенерировать пароль 🔑", callback_data=GENERATE),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение или отправляем новое
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=message_text, reply_markup=reply_markup, parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text=message_text, reply_markup=reply_markup, parse_mode='Markdown'
        )

# --- Обработчики Telegram ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start. Приветствует пользователя и показывает меню."""
    welcome_message = """
👋 *Привет! Я бот для генерации паролей.*

Используйте кнопки ниже, чтобы настроить параметры и сгенерировать пароль.
"""
    await build_menu(update, context, welcome_message)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает все нажатия на inline-кнопки."""
    query = update.callback_query
    await query.answer()  # Убираем "часики" на кнопке

    action = query.data
    user_id = query.from_user.id
    config = get_user_config(user_id)
    
    needs_update = True
    message = "⚙️ *Настройки изменены:*"

    if action == LEN_INCR:
        config["length"] = min(64, config["length"] + 1)
    elif action == LEN_DECR:
        config["length"] = max(4, config["length"] - 1)
    elif action == TOGGLE_UPPER:
        config["use_upper"] = not config["use_upper"]
    elif action == TOGGLE_LOWER:
        config["use_lower"] = not config["use_lower"]
    elif action == TOGGLE_DIGITS:
        config["use_digits"] = not config["use_digits"]
    elif action == TOGGLE_SYMBOLS:
        config["use_symbols"] = not config["use_symbols"]
    elif action == GENERATE:
        password = generate_password(config)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"""Ваш новый пароль:
`{password}`

Нажмите на него, чтобы скопировать.""",
            parse_mode='Markdown'
        )
        message = "⚙️ *Новые настройки для следующего пароля:*"
    else:
        needs_update = False

    if needs_update:
        save_user_settings(user_settings) # Сохраняем изменения на диск
        await build_menu(update, context, message)


def main() -> None:
    """Основная функция для запуска бота."""
    logger.info("Запуск бота...")

    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.critical("Токен не найден! Установите переменную окружения BOT_TOKEN.")
        return

    application = Application.builder().token(token).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Бот успешно запущен и готов к работе.")
    application.run_polling()


if __name__ == "__main__":
    main()
