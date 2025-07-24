
import os
import logging
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования для отладки
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Словарь для хранения настроек каждого пользователя
# Ключ: user_id, Значение: словарь с настройками
user_settings = {}

# --- Функции для создания клавиатуры и генерации пароля ---

def get_default_settings():
    """Возвращает стандартные настройки генерации."""
    return {
        "length": 16,
        "use_upper": True,
        "use_lower": True,
        "use_digits": True,
        "use_symbols": True,
    }

def generate_password(settings: dict) -> str:
    """Генерирует пароль на основе предоставленных настроек."""
    length = settings["length"]
    character_pool = []
    guaranteed_chars = []

    if settings["use_lower"]:
        character_pool.extend(string.ascii_lowercase)
        guaranteed_chars.append(random.choice(string.ascii_lowercase))
    if settings["use_upper"]:
        character_pool.extend(string.ascii_uppercase)
        guaranteed_chars.append(random.choice(string.ascii_uppercase))
    if settings["use_digits"]:
        character_pool.extend(string.digits)
        guaranteed_chars.append(random.choice(string.digits))
    if settings["use_symbols"]:
        # Можно добавить больше символов при желании
        symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        character_pool.extend(symbols)
        guaranteed_chars.append(random.choice(symbols))

    if not character_pool:
        return "Ошибка: Выберите хотя бы один тип символов!"

    # Заполняем оставшуюся часть пароля случайными символами из всего пула
    remaining_length = length - len(guaranteed_chars)
    password_list = guaranteed_chars + [random.choice(character_pool) for _ in range(remaining_length)]

    # Перемешиваем, чтобы гарантированные символы не стояли в начале
    random.shuffle(password_list)

    return "".join(password_list)


async def build_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Строит и отправляет интерактивное меню."""
    user_id = update.effective_user.id
    if user_id not in user_settings:
        user_settings[user_id] = get_default_settings()

    s = user_settings[user_id]
    
    # ✅ или ❌ для наглядности
    upper_icon = "✅" if s["use_upper"] else "❌"
    lower_icon = "✅" if s["use_lower"] else "❌"
    digits_icon = "✅" if s["use_digits"] else "❌"
    symbols_icon = "✅" if s["use_symbols"] else "❌"

    keyboard = [
        [
            InlineKeyboardButton("➖", callback_data="len_decr"),
            InlineKeyboardButton(f"Длина: {s['length']}", callback_data="len_info"),
            InlineKeyboardButton("➕", callback_data="len_incr"),
        ],
        [
            InlineKeyboardButton(f"{upper_icon} Заглавные", callback_data="toggle_upper"),
            InlineKeyboardButton(f"{lower_icon} Строчные", callback_data="toggle_lower"),
        ],
        [
            InlineKeyboardButton(f"{digits_icon} Цифры", callback_data="toggle_digits"),
            InlineKeyboardButton(f"{symbols_icon} Символы", callback_data="toggle_symbols"),
        ],
        [
            InlineKeyboardButton("🔑 Сгенерировать пароль 🔑", callback_data="generate"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Если сообщение новое - отправляем, если старое - редактируем
    if update.callback_query:
        await update.callback_query.edit_message_text(text=message_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text=message_text, reply_markup=reply_markup, parse_mode='Markdown')

# --- Обработчики команд и кнопок ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    welcome_message = (
        "👋 *Привет! Я бот для генерации паролей.*

"
        "Используйте кнопки ниже, чтобы настроить параметры и сгенерировать пароль."
    )
    await build_menu(update, context, welcome_message)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия на все inline-кнопки."""
    query = update.callback_query
    await query.answer()  # Обязательно, чтобы убрать "часики" на кнопке

    user_id = query.from_user.id
    if user_id not in user_settings:
        user_settings[user_id] = get_default_settings()

    action = query.data
    settings = user_settings[user_id]

    if action == "len_incr":
        settings["length"] = min(64, settings["length"] + 1)
    elif action == "len_decr":
        settings["length"] = max(4, settings["length"] - 1)
    elif action == "toggle_upper":
        settings["use_upper"] = not settings["use_upper"]
    elif action == "toggle_lower":
        settings["use_lower"] = not settings["use_lower"]
    elif action == "toggle_digits":
        settings["use_digits"] = not settings["use_digits"]
    elif action == "toggle_symbols":
        settings["use_symbols"] = not settings["use_symbols"]
    elif action == "generate":
        password = generate_password(settings)
        # Отправляем пароль в сообщении, которое можно легко скопировать
        await context.bot.send_message(
            chat_id=query.effective_chat.id,
            text=f"Ваш новый пароль:
`{password}`

Нажмите на него, чтобы скопировать.",
            parse_mode='Markdown'
        )
        # После генерации снова показываем меню для удобства
        await build_menu(update, context, "⚙️ *Новые настройки для следующего пароля:*")
        return # Выходим, чтобы не перерисовывать меню дважды
    
    # После изменения настроек, перерисовываем меню
    await build_menu(update, context, "⚙️ *Настройки изменены:*")


def main() -> None:
    """Основная функция для запуска бота."""
    # Важно! Получаем токен из переменной окружения
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("Ошибка: Токен не найден. Пожалуйста, установите переменную окружения TELEGRAM_BOT_TOKEN")
        return

    application = Application.builder().token(token).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Бот запущен...")
    # Запускаем бота
    application.run_polling()


if __name__ == "__main__":
    main()
