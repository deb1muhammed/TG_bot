import os
import json
import logging
import shutil
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Загрузка переменных окружения из файла config.txt
load_dotenv("config.txt")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = [int(id) for id in os.getenv("ADMINS", "").split(",") if id.isdigit()]

# Проверка обязательных переменных
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set in config file")

# Настройка логирования
log_dir = "logs"
if os.path.exists(log_dir) and not os.path.isdir(log_dir):
    os.remove(log_dir)  # Удаляем файл, если он существует вместо папки
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
logging.basicConfig(
    filename=os.path.join(log_dir, "bot.log"),
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Функции для работы с данными
def create_backup(file_path: str) -> None:
    """Создает резервную копию файла с ограничением на количество бэкапов."""
    try:
        if not os.path.exists("backups"):
            os.makedirs("backups")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backups/{os.path.basename(file_path)}_{timestamp}"
        shutil.copy2(file_path, backup_path)

        backups = sorted(
            [f for f in os.listdir("backups") if f.startswith(os.path.basename(file_path))]
        )
        if len(backups) > 10:
            os.remove(os.path.join("backups", backups[0]))
    except Exception as e:
        logger.error(f"Failed to create backup for {file_path}: {e}")

def load_data(file_path: str, default: Any = None) -> Dict:
    """Загружает данные из JSON-файла."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load {file_path}: {e}")
        return default if default is not None else {}

def save_data(file_path: str, data: Dict) -> None:
    """Сохраняет данные в JSON-файл с созданием бэкапа."""
    try:
        if os.path.exists(file_path):
            create_backup(file_path)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {file_path}: {e}")

# Главное меню
def get_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    """Возвращает главное меню с учетом прав администратора."""
    keyboard = [
        [KeyboardButton("📚 Теория")],
        [KeyboardButton("❓ Теоретические вопросы")],
        [KeyboardButton("📝 Тесты")],
        [KeyboardButton("🖼️ Тесты по изображениям")],
        [KeyboardButton("🧩 Ситуационные задачи")],
    ]
    if user_id in ADMINS:
        keyboard.append([KeyboardButton("👑 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Админ-панель меню
def get_admin_panel_menu() -> ReplyKeyboardMarkup:
    """Возвращает меню админ-панели."""
    keyboard = [
        [KeyboardButton("Добавить элемент")],
        [KeyboardButton("Редактировать элемент")],
        [KeyboardButton("Удалить элемент")],
        [KeyboardButton("🔙 Главное меню")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start. Показывает главное меню."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")
    context.user_data.clear()  # Очищаем все состояния
    context.user_data["state"] = "main_menu"
    await update.message.reply_text(
        "Добро пожаловать в бот по дерматовенерологии!\nВыберите раздел:",
        reply_markup=get_main_menu(user_id),
    )

# Обработчик главного меню
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выбор пунктов главного меню."""
    user_message = update.message.text
    user_id = update.effective_user.id
    current_state = context.user_data.get("state", "main_menu")

    logger.info(f"handle_menu: User {user_id}, state: {current_state}, message: {user_message}")

    if current_state == "admin_panel":
        return  # Пропускаем, если пользователь в админ-панели

    main_menu = get_main_menu(user_id)

    sections = {
        "📚 Теория": ("theory", "topics", "topics", "Выберите тему"),
        "❓ Теоретические вопросы": ("questions", "questions", "questions", "Выберите вопрос"),
        "📝 Тесты": ("tests", "tests", "tests", "Выберите тест"),
        "🖼️ Тесты по изображениям": ("image_tests", "image_tests", "image_tests", "Выберите тест по изображениям"),
        "🧩 Ситуационные задачи": ("tasks", "tasks", "tasks", "Выберите задачу"),
    }

    if user_message in sections:
        section, key, display_key, prompt = sections[user_message]
        data = load_data(f"data/{section}/structure.json", {key: []})[key]
        if not data:
            await update.message.reply_text(
                f"{prompt.split()[1]} пока нет.", reply_markup=main_menu
            )
        else:
            context.user_data["state"] = section
            keyboard = [[KeyboardButton(f"{item['name']}")] for item in data] + [
                [KeyboardButton("🔙 Главное меню")]
            ]
            await update.message.reply_text(
                f"{prompt}:\n" + "\n".join([f"{item['id']}. {item['name']}" for item in data]),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            )
    elif user_message == "👑 Админ-панель" and user_id in ADMINS:
        context.user_data["state"] = "admin_panel"
        context.user_data["admin_state"] = None
        await update.message.reply_text(
            "Вы в админ-панели. Выберите действие:",
            reply_markup=get_admin_panel_menu(),
        )
    elif user_message == "🔙 Главное меню":
        context.user_data["state"] = "main_menu"
        context.user_data["admin_state"] = None
        await update.message.reply_text("Выберите раздел:", reply_markup=main_menu)
    else:
        await update.message.reply_text(
            "Неизвестная команда. Выберите раздел:", reply_markup=main_menu
        )

# Обработчик админ-панели
async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает действия в админ-панели."""
    user_message = update.message.text
    user_id = update.effective_user.id
    current_state = context.user_data.get("state", "main_menu")
    admin_state = context.user_data.get("admin_state")

    logger.info(f"handle_admin_panel: User {user_id}, state: {current_state}, admin_state: {admin_state}, message: {user_message}")

    if current_state != "admin_panel" or admin_state:
        return  # Пропускаем, если не в админ-панели или уже в процессе ввода

    if user_id not in ADMINS:
        context.user_data["state"] = "main_menu"
        context.user_data["admin_state"] = None
        await update.message.reply_text(
            "Доступ запрещен.",
            reply_markup=get_main_menu(user_id),
        )
        return

    main_menu = get_main_menu(user_id)
    admin_panel_menu = get_admin_panel_menu()

    sections = {
        "Теория": ("theory", "topics"),
        "Теоретические вопросы": ("questions", "questions"),
        "Тесты": ("tests", "tests"),
        "Тесты по изображениям": ("image_tests", "image_tests"),
        "Ситуационные задачи": ("tasks", "tasks"),
    }

    if user_message == "Добавить элемент":
        context.user_data["admin_state"] = "waiting_add_section"
        keyboard = [[KeyboardButton(section)] for section in sections.keys()] + [
            [KeyboardButton("Отмена")]
        ]
        await update.message.reply_text(
            "Выберите раздел для добавления элемента:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
    elif user_message == "Редактировать элемент":
        context.user_data["admin_state"] = "waiting_edit_section"
        keyboard = [[KeyboardButton(section)] for section in sections.keys()] + [
            [KeyboardButton("Отмена")]
        ]
        await update.message.reply_text(
            "Выберите раздел для редактирования элемента:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
    elif user_message == "Удалить элемент":
        context.user_data["admin_state"] = "waiting_delete_section"
        keyboard = [[KeyboardButton(section)] for section in sections.keys()] + [
            [KeyboardButton("Отмена")]
        ]
        await update.message.reply_text(
            "Выберите раздел для удаления элемента:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
    elif user_message == "🔙 Главное меню":
        context.user_data["state"] = "main_menu"
        context.user_data["admin_state"] = None
        await update.message.reply_text(
            "Выберите раздел:",
            reply_markup=main_menu,
        )
    else:
        await update.message.reply_text(
            "Неизвестная команда. Выберите действие:",
            reply_markup=admin_panel_menu,
        )

# Обработчик ввода данных в админ-панели
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод данных в админ-панели."""
    user_message = update.message.text
    user_id = update.effective_user.id
    current_state = context.user_data.get("state", "main_menu")
    admin_state = context.user_data.get("admin_state")

    logger.info(f"handle_admin_input: User {user_id}, state: {current_state}, admin_state: {admin_state}, message: {user_message}")

    if current_state != "admin_panel" or not admin_state:
        return  # Пропускаем, если не в админ-панели или нет admin_state

    if user_id not in ADMINS:
        context.user_data["state"] = "main_menu"
        context.user_data["admin_state"] = None
        await update.message.reply_text(
            "Доступ запрещен.",
            reply_markup=get_main_menu(user_id),
        )
        return

    main_menu = get_main_menu(user_id)
    admin_panel_menu = get_admin_panel_menu()

    sections = {
        "Теория": ("theory", "topics"),
        "Теоретические вопросы": ("questions", "questions"),
        "Тесты": ("tests", "tests"),
        "Тесты по изображениям": ("image_tests", "image_tests"),
        "Ситуационные задачи": ("tasks", "tasks"),
    }

    try:
        if admin_state == "waiting_add_section":
            if user_message in sections:
                context.user_data["admin_section"] = user_message
                context.user_data["admin_state"] = "waiting_add_item"
                await update.message.reply_text(
                    f"Введите данные для нового элемента в разделе '{user_message}'.\n"
                    "Для 'Теория' используйте формат: section|theme_name (например: theory|Инфекции кожи).\n"
                    "Для других разделов просто название (например: Что такое экзема?).",
                    reply_markup=ReplyKeyboardMarkup(
                        [[KeyboardButton("Отмена")]], resize_keyboard=True
                    ),
                )
            else:
                context.user_data["admin_state"] = None
                await update.message.reply_text(
                    "Неверный раздел. Выберите действие:",
                    reply_markup=admin_panel_menu,
                )
        elif admin_state == "waiting_add_item":
            section_name = context.user_data["admin_section"]
            section, key = sections[section_name]
            if section_name == "Теория":
                section_part, item_name = user_message.split("|")
                item_name = item_name.strip()
            else:
                item_name = user_message.strip()
            path = f"data/{section}/structure.json"
            data = load_data(path, {key: []})
            new_id = str(len(data[key]) + 1)
            data[key].append({"id": new_id, "name": item_name})
            save_data(path, data)
            logger.info(f"User {user_id} added {key[:-1]} '{item_name}' to '{section}'")
            await update.message.reply_text(
                f"Элемент '{item_name}' добавлен в раздел '{section_name}'.",
                reply_markup=admin_panel_menu,
            )
            context.user_data["admin_state"] = None
            context.user_data["admin_section"] = None
        elif admin_state == "waiting_edit_section":
            if user_message in sections:
                context.user_data["admin_section"] = user_message
                context.user_data["admin_state"] = "waiting_edit_item_list"
                section, key = sections[user_message]
                data = load_data(f"data/{section}/structure.json", {key: []})[key]
                if not data:
                    context.user_data["admin_state"] = None
                    await update.message.reply_text(
                        f"В разделе '{user_message}' нет элементов для редактирования.",
                        reply_markup=admin_panel_menu,
                    )
                else:
                    keyboard = [[KeyboardButton(f"{item['name']}")] for item in data] + [
                        [KeyboardButton("Отмена")]
                    ]
                    await update.message.reply_text(
                        f"Выберите элемент для редактирования в разделе '{user_message}':\n"
                        + "\n".join([f"{item['id']}. {item['name']}" for item in data]),
                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                    )
            else:
                context.user_data["admin_state"] = None
                await update.message.reply_text(
                    "Неверный раздел. Выберите действие:",
                    reply_markup=admin_panel_menu,
                )
        elif admin_state == "waiting_edit_item_list":
            section_name = context.user_data["admin_section"]
            section, key = sections[section_name]
            data = load_data(f"data/{section}/structure.json", {key: []})[key]
            selected_item = next((item for item in data if item["name"] == user_message), None)
            if selected_item:
                context.user_data["admin_selected_item"] = selected_item
                context.user_data["admin_state"] = "waiting_edit_item"
                await update.message.reply_text(
                    f"Введите новое название для '{selected_item['name']}':",
                    reply_markup=ReplyKeyboardMarkup(
                        [[KeyboardButton("Отмена")]], resize_keyboard=True
                    ),
                )
            else:
                context.user_data["admin_state"] = None
                await update.message.reply_text(
                    "Элемент не найден. Выберите действие:",
                    reply_markup=admin_panel_menu,
                )
        elif admin_state == "waiting_edit_item":
            new_name = user_message.strip()
            section_name = context.user_data["admin_section"]
            section, key = sections[section_name]
            data = load_data(f"data/{section}/structure.json", {key: []})
            selected_item = context.user_data["admin_selected_item"]
            selected_item["name"] = new_name
            save_data(f"data/{section}/structure.json", data)
            logger.info(f"User {user_id} edited {key[:-1]} to '{new_name}' in '{section}'")
            await update.message.reply_text(
                f"Элемент переименован в '{new_name}'.",
                reply_markup=admin_panel_menu,
            )
            context.user_data["admin_state"] = None
            context.user_data["admin_section"] = None
            context.user_data["admin_selected_item"] = None
        elif admin_state == "waiting_delete_section":
            if user_message in sections:
                context.user_data["admin_section"] = user_message
                context.user_data["admin_state"] = "waiting_delete_item_list"
                section, key = sections[user_message]
                data = load_data(f"data/{section}/structure.json", {key: []})[key]
                if not data:
                    context.user_data["admin_state"] = None
                    await update.message.reply_text(
                        f"В разделе '{user_message}' нет элементов для удаления.",
                        reply_markup=admin_panel_menu,
                    )
                else:
                    keyboard = [[KeyboardButton(f"{item['name']}")] for item in data] + [
                        [KeyboardButton("Отмена")]
                    ]
                    await update.message.reply_text(
                        f"Выберите элемент для удаления в разделе '{user_message}':\n"
                        + "\n".join([f"{item['id']}. {item['name']}" for item in data]),
                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                    )
            else:
                context.user_data["admin_state"] = None
                await update.message.reply_text(
                    "Неверный раздел. Выберите действие:",
                    reply_markup=admin_panel_menu,
                )
        elif admin_state == "waiting_delete_item_list":
            section_name = context.user_data["admin_section"]
            section, key = sections[section_name]
            data = load_data(f"data/{section}/structure.json", {key: []})
            selected_item = next((item for item in data[key] if item["name"] == user_message), None)
            if selected_item:
                data[key] = [item for item in data[key] if item != selected_item]
                save_data(f"data/{section}/structure.json", data)
                logger.info(f"User {user_id} deleted {key[:-1]} '{selected_item['name']}' from '{section}'")
                await update.message.reply_text(
                    f"Элемент '{selected_item['name']}' удален.",
                    reply_markup=admin_panel_menu,
                )
            else:
                context.user_data["admin_state"] = None
                await update.message.reply_text(
                    "Элемент не найден. Выберите действие:",
                    reply_markup=admin_panel_menu,
                )
            context.user_data["admin_state"] = None
            context.user_data["admin_section"] = None
        elif user_message == "Отмена":
            context.user_data["admin_state"] = None
            context.user_data["admin_section"] = None
            context.user_data["admin_selected_item"] = None
            await update.message.reply_text(
                "Действие отменено. Выберите действие:",
                reply_markup=admin_panel_menu,
            )
    except ValueError as e:
        await update.message.reply_text(
            f"Ошибка: {e}. Попробуйте снова или выберите 'Отмена'.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Отмена")]], resize_keyboard=True
            ),
        )
    except Exception as e:
        logger.error(f"Error in admin input: {e}")
        await update.message.reply_text(
            f"Произошла ошибка: {e}",
            reply_markup=admin_panel_menu,
        )
        context.user_data["admin_state"] = None
        context.user_data["admin_section"] = None
        context.user_data["admin_selected_item"] = None

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ошибки."""
    logger.error(f"Update {update} caused error: {context.error}")
    if update and update.message:
        await update.message.reply_text("Произошла ошибка. Попробуйте снова.")

# Запуск бота
def main() -> None:
    """Запускает бота."""
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_panel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))
    app.add_error_handler(error_handler)
    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()