import os
import logging
import re
import phonenumbers
import logging.handlers
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode, ChatType
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
from config import Settings
from database import get_db, init_db
from models import Candidate, VacancyPost
from sheets import init_google_sheets, append_to_sheets
from localization import TEXTS
import urllib.parse
from aiogram.types import Message


settings=Settings()
# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler("bot.log", maxBytes=5*1024*1024, backupCount=3),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# States
class ApplicationForm(StatesGroup):
    Language = State()
    Name = State()
    Surname = State()
    Phone = State()
    Age = State()
    Gender = State()
    Education = State()
    Resume = State()
    Confirmation = State()

# Bot initialization
bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Global sheets client
worksheet = None

async def notify_hr(data: dict, language: str = "ru"):
    text = (
        "🚀 Новый кандидат!\n\n"
        f"Вакансия: {data['vacancy_title']}\n"
        f"Имя: {data['name']} {data['surname']}\n"
        f"Телефон: {data['phone']}\n"
        f"Возраст: {data['age']}\n"
        f"Пол: {data['gender']}\n"
        f"Образование: {data['education']}\n"
        f"Резюме: {'Да' if data.get('resume_file_id') else 'Нет'}\n"
        f"Username: @{data.get('telegram_username', 'нет')}\n"
        f"ID: {data['telegram_id']}\n"
    )
    try:
        await bot.send_message(settings.hr_notification_chat_id, text)
    except Exception as e:
        logger.error(f"Failed to notify HR: {e}")

async def save_to_database(data: dict, language: str):
    try:
        with get_db() as db:
            # Если вакансии нет в БД, создаем запись
            if 'vacancy_id' not in data:
                vacancy = VacancyPost(
                    title=data["vacancy_title"],
                    description=f"Вакансия из ссылки: {data['vacancy_title']}",
                    timestamp=datetime.now()  # Используем datetime объект
                )
                db.add(vacancy)
                db.commit()
                db.refresh(vacancy)
                data['vacancy_id'] = vacancy.id

            candidate = Candidate(
                vacancy_id=data["vacancy_id"],
                vacancy_title=data["vacancy_title"],
                name=data["name"],
                surname=data["surname"],
                phone=data["phone"],
                age=data["age"],
                gender=data["gender"],
                education=data["education"],
                telegram_id=data["telegram_id"],
                telegram_username=data.get("telegram_username", ""),
                timestamp=datetime.now(),  # Используем datetime объект
                language=language,
                resume_file_id=data.get("resume_file_id"),
                resume_filename=data.get("resume_filename"),
            )
            db.add(candidate)
            db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise


async def handle_channel_post(message: types.Message):
    if not message.text:
        return

    title = "Неизвестная вакансия"
    if "Вакансия:" in message.text:
        title = message.text.split("Вакансия:")[1].split("\n")[0].strip()[:200]

    try:
        with get_db() as db:
            # Проверяем, существует ли вакансия с таким телом
            existing_vacancy = db.query(VacancyPost).filter_by(body=message.text).first()
            if existing_vacancy:
                logger.info(f"Vacancy already exists: {title}, ID: {existing_vacancy.id}")
                return

            vacancy = VacancyPost(
                title=title,
                description=message.text,
                body=message.text,  # Сохраняем тело для проверки уникальности
                timestamp=datetime.now().isoformat(),
                channel_message_id=message.message_id,
                channel_id=message.chat.id
            )
            db.add(vacancy)
            db.commit()
            db.refresh(vacancy)

            # Формируем ссылку с названием вакансии
            encoded_title = urllib.parse.quote(title)
            markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton(
                    "Откликнуться",
                    url=f"https://t.me/{(await bot.get_me()).username}?start={encoded_title}",
                )
            )
            await message.edit_reply_markup(markup)
            logger.info(f"Added button to vacancy: {title}, ID: {vacancy.id}")
    except Exception as e:
        logger.error(f"Error handling channel post: {e}")

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    logger.info(f"Start command received: {message.text}")
    try:
        args = message.text.split(maxsplit=1)
        vacancy_title = "Неизвестная вакансия"
        
        if len(args) > 1:
            # Декодируем URL-encoded строку
            arg = urllib.parse.unquote(args[1])
            
            # Если есть start=, берем часть после него
            if "start=" in arg:
                arg = arg.split("start=")[1]
            
            # Заменяем подчеркивания на пробелы
            vacancy_title = arg.replace('_', ' ')
            
            # Проверяем, что название не пустое
            if not vacancy_title.strip():
                vacancy_title = "Неизвестная вакансия"

        # Сохраняем данные
        user_data = {
            'vacancy_title': vacancy_title,
            'telegram_id': message.from_user.id,
            'telegram_username': message.from_user.username or ""
        }
        
        # Если вакансия не "Неизвестная", ищем в БД
        if vacancy_title != "Неизвестная вакансия":
            with get_db() as db:
                vacancy = db.query(VacancyPost).filter_by(title=vacancy_title).first()
                if vacancy:
                    user_data['vacancy_id'] = vacancy.id
                else:
                    # Создаем новую вакансию
                    vacancy = VacancyPost(
                        title=vacancy_title,
                        description=f"Вакансия из ссылки: {vacancy_title}",
                        timestamp=datetime.now()
                    )
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                    user_data['vacancy_id'] = vacancy.id
        
        await state.update_data(**user_data)
        
        # Продолжаем стандартный процесс
        buttons = [
            [InlineKeyboardButton(text="Русский", callback_data="ru")],
            [InlineKeyboardButton(text="English", callback_data="en")]
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(
            f"Вы откликаетесь на вакансию: {vacancy_title}",
            reply_markup=markup
        )
        await state.set_state(ApplicationForm.Language)
        
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.message(CommandStart(["start"]))
async def start_default(message: Message):
    await message.answer("Старт без аргумента")

@dp.message(F.text.startswith("/start"))
async def handle_start_text(message: types.Message, state: FSMContext):
    """Обрабатывает текстовые сообщения, начинающиеся с /start, если команда не сработала"""
    logger.info(f"Handling text as start command: {message.text}")
    await start(message, state)

@dp.message(F.chat_type == ChatType.PRIVATE)
async def handle_any_message(message: types.Message, state: FSMContext):
    """Обрабатывает любые сообщения в приватном чате для инициирования start"""
    current_state = await state.get_state()
    if current_state is None:  # Если пользователь не в процессе заполнения формы
        logger.info(f"Initiating start for message: {message.text}")
        await start(message, state)
    else:
        logger.info(f"Ignoring message, user in state: {current_state}")

@dp.callback_query(StateFilter(ApplicationForm.Language))
async def set_language(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    language = callback.data
    await state.update_data(language=language)

    data = await state.get_data()
    await callback.message.edit_text(
        TEXTS[language]["start"].format(vacancy=data["vacancy_title"])
    )
    await callback.message.answer(TEXTS[language]["ask_name"])
    await state.set_state(ApplicationForm.Name)

@dp.message(StateFilter(ApplicationForm.Name))
async def name(message: types.Message, state: FSMContext):
    language = (await state.get_data())["language"]
    name = message.text.strip()

    if not re.match(r"^[a-zA-Zа-яА-ЯёЁ\s-]+$", name):
        await message.answer(TEXTS[language]["invalid_name"])
        return

    await state.update_data(name=name)
    await message.answer(TEXTS[language]["ask_surname"])
    await state.set_state(ApplicationForm.Surname)

@dp.message(StateFilter(ApplicationForm.Surname))
async def surname(message: types.Message, state: FSMContext):
    language = (await state.get_data())["language"]
    surname = message.text.strip()
    if not re.match(r"^[a-zA-Zа-яА-ЯёЁ\s-]+$", surname):
        await message.answer(TEXTS[language]["invalid_name"])
        return
    await state.update_data(surname=surname)
    # Исправленная клавиатура для запроса телефона
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TEXTS[language]["share_phone"], request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        TEXTS[language]["ask_phone"],
        reply_markup=markup,
        input_field_placeholder=TEXTS[language]["phone_placeholder"],
    )
    await state.set_state(ApplicationForm.Phone)

@dp.message(StateFilter(ApplicationForm.Phone), F.content_type.in_({'contact', 'text'}))
async def phone(message: types.Message, state: FSMContext):
    language = (await state.get_data())["language"]
    
    if message.contact:
        phone_number = message.contact.phone_number
    elif message.text:
        phone_number = message.text.strip()
    else:
        await message.answer(TEXTS[language]["invalid_phone"])
        return

    try:
        parsed = phonenumbers.parse(phone_number, None)
        if parsed.country_code != 7 or not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        phone_number = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        if not phone_number.startswith("+7") or len(str(parsed.national_number)) != 10:
            raise ValueError("Phone number must be in +7 format with 10 digits")
    except Exception as e:
        logger.error(f"Phone validation error: {e}")
        await message.answer(TEXTS[language]["invalid_phone"])
        return

    await state.update_data(phone=phone_number)
    logger.info(f"Phone number saved: {phone_number}")  # Отладка
    await message.answer(TEXTS[language]["ask_age"], reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(ApplicationForm.Age)


@dp.message(StateFilter(ApplicationForm.Age))
async def age(message: types.Message, state: FSMContext):
    language = (await state.get_data())["language"]
    try:
        age = int(message.text.strip())
        if not 14 <= age <= 99:
            raise ValueError
    except ValueError:
        await message.answer(TEXTS[language]["invalid_age"])
        return

    await state.update_data(age=age)
    
    # Исправленная клавиатура для выбора пола
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=TEXTS[language]["male"]),
                KeyboardButton(text=TEXTS[language]["female"])
            ],
            [
                KeyboardButton(text=TEXTS[language]["other_gender"])
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(TEXTS[language]["ask_gender"], reply_markup=markup)
    await state.set_state(ApplicationForm.Gender)

@dp.message(StateFilter(ApplicationForm.Gender))
async def gender(message: types.Message, state: FSMContext):
    language = (await state.get_data())["language"]
    await state.update_data(gender=message.text)

    # Исправленная клавиатура для образования
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=TEXTS[language]["secondary"]),
                KeyboardButton(text=TEXTS[language]["vocational"])
            ],
            [
                KeyboardButton(text=TEXTS[language]["higher"]),
                KeyboardButton(text=TEXTS[language]["incomplete_higher"])
            ],
            [
                KeyboardButton(text=TEXTS[language]["other_education"])
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(TEXTS[language]["ask_education"], reply_markup=markup)
    await state.set_state(ApplicationForm.Education)

@dp.message(StateFilter(ApplicationForm.Education))
async def education(message: types.Message, state: FSMContext):
    language = (await state.get_data())["language"]
    await state.update_data(education=message.text)

    # Исправленная inline клавиатура для резюме
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[language]["skip_resume"], callback_data="skip_resume")]
        ]
    )
    
    await message.answer(
        TEXTS[language]["ask_resume"],
        reply_markup=markup,
        input_field_placeholder="PDF или DOCX",
    )
    await state.set_state(ApplicationForm.Resume)



async def download_resume(file_id: str, filename: str):
    try:
        os.makedirs("/app/resumes", exist_ok=True)  # Изменено для Docker
        file_path = os.path.join("/app/resumes", filename)
        
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, file_path)
        logger.info(f"Resume downloaded to: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error downloading resume: {e}")
        raise

async def show_confirmation(message: types.Message, state: FSMContext):
    language = (await state.get_data())["language"]
    data = await state.get_data()

    confirmation_text = TEXTS[language]["confirmation"].format(
        vacancy=data["vacancy_title"],
        name=data["name"],
        surname=data["surname"],
        phone=data["phone"],
        age=data["age"],
        gender=data["gender"],
        education=data["education"],
        resume="Да" if data.get("resume_file_id") else "Нет",
    )

    # Исправленное создание клавиатуры
    buttons = [
        [
            InlineKeyboardButton(text=TEXTS[language]["terms"], url="https://example.com/terms"),
            InlineKeyboardButton(text=TEXTS[language]["privacy"], url="https://example.com/privacy")
        ],
        [InlineKeyboardButton(text=TEXTS[language]["submit"], callback_data="submit")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(confirmation_text, reply_markup=markup)
    await state.set_state(ApplicationForm.Confirmation)

@dp.message(StateFilter(ApplicationForm.Resume), F.document)
async def handle_resume(message: types.Message, state: FSMContext):
    language = (await state.get_data())["language"]
    document = message.document
    
    # Проверяем формат файла
    if document.mime_type not in ["application/pdf", 
                                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        await message.answer(TEXTS[language]["invalid_resume"])
        return
    
    # Генерируем уникальное имя файла: telegramid_originalname
    user_data = await state.get_data()
    new_filename = f"{user_data['telegram_id']}_{document.file_name}"
    
    # Сохраняем информацию о резюме
    await state.update_data(
        resume_file_id=document.file_id,
        resume_filename=new_filename
    )
    
    logger.info(f"Resume saved in state: file_id={document.file_id}, filename={new_filename}")  # Отладка
    await show_confirmation(message, state)

@dp.callback_query(lambda c: c.data == "submit", StateFilter(ApplicationForm.Confirmation))
async def confirmation(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    language = (await state.get_data())["language"]
    data = await state.get_data()
    
    try:
        # Логируем данные для отладки
        logger.info(f"Confirmation data: {data}")

        # Сохраняем резюме (если есть)
        if data.get("resume_file_id"):
            try:
                os.makedirs("C:\\Dev\\hr_bot\\resumes", exist_ok=True)
                file_path = await download_resume(
                    data["resume_file_id"],
                    data.get("resume_filename", f"resume_{data['telegram_id']}")
                )
                logger.info(f"Resume saved to: {file_path}")
            except Exception as e:
                logger.error(f"Error saving resume: {e}")
                # Продолжаем, даже если не удалось сохранить резюме

        # Сохраняем в Google Sheets
        # Временно отключаем Google Sheets
        # try:
        #     if worksheet:
        #         success = await append_to_sheets(worksheet, data)
        #         if not success:
        #             raise Exception("Failed to append to Google Sheets")
        #         logger.info("Data saved to Google Sheets")
        # except Exception as e:
        #     logger.error(f"Google Sheets error: {e}")
        #     await callback.message.answer(TEXTS[language]["error"] + " (Google Sheets)")
        #     return

        # Сохраняем в базу данных
        try:
            await save_to_database(data, language)
            logger.info("Data saved to database")
        except Exception as e:
            logger.error(f"Database error: {e}")
            await callback.message.answer(TEXTS[language]["error"] + " (Database)")
            return

        # Уведомляем HR
        try:
            await notify_hr(data, language)
        except Exception as e:
            logger.error(f"HR notification error: {e}")

        await callback.message.edit_text(TEXTS[language]["success"])
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await callback.message.edit_text(TEXTS[language]["error"])
    finally:
        await state.clear()

@dp.message(Command("cancel"), StateFilter("*"))
async def cancel(message: types.Message, state: FSMContext):
    language = (await state.get_data()).get("language", "ru")
    await state.clear()
    await message.answer(TEXTS[language]["cancel"], reply_markup=types.ReplyKeyboardRemove())

async def main():
    global worksheet
    try:
        init_db()
        # worksheet = await init_google_sheets()  # Временно отключено
        logger.info("Starting bot...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())