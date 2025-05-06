import gspread_asyncio
from google.oauth2.service_account import Credentials
from config import settings
from datetime import datetime
import logging
from localization import TEXTS
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

def get_column_headers(language="ru"):
    """Возвращает заголовки столбцов на выбранном языке"""
    return [
        TEXTS[language].get("vacancy_column", "Вакансия"),
        TEXTS[language].get("name_column", "Имя"),
        TEXTS[language].get("surname_column", "Фамилия"),
        TEXTS[language].get("phone_column", "Телефон"),
        TEXTS[language].get("age_column", "Возраст"),
        TEXTS[language].get("gender_column", "Пол"),
        TEXTS[language].get("education_column", "Образование"),
        "Telegram ID",
        "Telegram Username",
        TEXTS[language].get("date_column", "Дата и время"),
        TEXTS[language].get("language_column", "Язык"),
        TEXTS[language].get("resume_column", "Резюме"),
        TEXTS[language].get("resume_filename_column", "Имя файла резюме"),
    ]

async def init_google_sheets(default_language="ru"):
    """Инициализирует подключение к Google Sheets и создает заголовки"""
    try:
        creds = Credentials.from_service_account_file(
            settings.google_sheets_credentials,
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/drive.file",
            ],
        )
        client = gspread_asyncio.AsyncioGspreadClientManager(lambda: creds)
        spreadsheet = await (await client.authorize()).open_by_key(settings.spreadsheet_id)
        
        try:
            worksheet = await spreadsheet.get_worksheet(0)
        except Exception as e:
            logger.info("Worksheet not found, creating a new one")
            worksheet = await spreadsheet.add_worksheet(
                title="Candidates", 
                rows=100, 
                cols=len(get_column_headers())
            )
        
        headers = get_column_headers(default_language)
        existing_data = await worksheet.get_all_values()
        
        if not existing_data:
            await worksheet.append_row(headers)
            logger.info("Added new column headers")
        elif existing_data[0] != headers:
            await worksheet.insert_row(headers, 1)
            logger.info("Inserted missing column headers")
            
        return worksheet
    except Exception as e:
        logger.error(f"Google Sheets initialization failed: {e}")
        raise

def upload_to_drive(file_path: str, filename: str, creds):
    """Загружает файл в Google Drive и возвращает общедоступную ссылку"""
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        file_metadata = {
            'name': filename,
            'mimeType': 'application/pdf' if filename.endswith('.pdf') else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }
        media = MediaFileUpload(file_path)
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        # Делаем файл общедоступным
        drive_service.permissions().create(
            fileId=file.get('id'),
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        # Получаем ссылку
        file_url = f"https://drive.google.com/file/d/{file.get('id')}/view"
        return file_url
    except Exception as e:
        logger.error(f"Error uploading to Google Drive: {e}")
        raise

async def append_to_sheets(worksheet, data: dict):
    """Добавляет данные в Google Sheets с гиперссылкой на файл в Google Drive или локальный файл"""
    try:
        if not worksheet:
            raise Exception("Worksheet not initialized")
        
        phone_number = data.get("phone", "")
        # Добавляем одинарную кавычку, чтобы предотвратить интерпретацию как формулу
        if phone_number and phone_number.startswith("+"):
            phone_number = f"'{phone_number}"
        # Формируем данные для строки
        row_data = [
            data.get("vacancy_title", ""),
            data.get("name", ""),
            data.get("surname", ""),
            phone_number,  # Номер телефона
            data.get("age", ""),
            data.get("gender", ""),
            data.get("education", ""),
            str(data.get("telegram_id", "")),
            data.get("telegram_username", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("language", "ru"),
            "Yes" if data.get("resume_file_id") else "No",
        ]

        logger.info(f"Appending row_data: {row_data}")  # Отладка

        # Добавляем гиперссылку на файл
        if data.get("resume_file_id") and data.get("resume_filename"):
            resume_filename = data.get("resume_filename", "resume")
            # Используем Google Drive для гиперссылки
            file_path = os.path.join("C:\\Dev\\hr_bot\\resumes", resume_filename)
            if not os.path.exists(file_path):
                logger.error(f"Resume file not found at {file_path}")
                row_data.append("No resume (file not found)")
            else:
                try:
                    creds = Credentials.from_service_account_file(
                        settings.google_sheets_credentials,
                        scopes=["https://www.googleapis.com/auth/drive.file"],
                    )
                    file_url = upload_to_drive(file_path, resume_filename, creds)
                    hyperlink_formula = f'=HYPERLINK("{file_url}"; "{resume_filename}")'
                    row_data.append(hyperlink_formula)
                except Exception as e:
                    logger.error(f"Failed to upload resume to Google Drive: {e}")
                    # В качестве запасного варианта используем локальный путь
                    file_path = file_path.replace("\\", "/")
                    hyperlink_formula = f'=HYPERLINK("file:///{file_path}"; "{resume_filename}")'
                    row_data.append(hyperlink_formula)
        else:
            row_data.append("No resume")

        logger.info(f"Final row_data: {row_data}")  # Отладка

        # Проверяем, что количество элементов соответствует заголовкам
        headers = get_column_headers(data.get("language", "ru"))
        if len(row_data) != len(headers):
            logger.error(f"Row data length ({len(row_data)}) does not match headers length ({len(headers)})")
            raise ValueError("Incorrect number of columns in row_data")

        # Добавляем строку в Google Sheets
        await worksheet.append_row(row_data, value_input_option="USER_ENTERED")
        logger.info("Data successfully appended to Google Sheets")
        return True
    except Exception as e:
        logger.error(f"Error appending to sheets: {e}")
        return False