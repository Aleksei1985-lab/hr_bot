![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Aiogram](https://img.shields.io/badge/aiogram-3.x-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
The HR Telegram Bot
# HR Telegram Bot 🤖

[Русская версия ниже](#русская-версия)

## 📝 Description

A Telegram bot for HR agencies to collect candidate applications, store them in Google Sheets and database, with resume upload functionality.

## ✨ Features

- Multi-language support (English/Russian)
- Application form with validation
- Resume upload (PDF/DOCX)
- Google Sheets integration
- SQL database storage
- HR notifications
- Docker support

## 🛠 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/hr-telegram-bot.git
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (copy `.env.example` to `.env` and fill your data)

4. Run with Docker:
```bash
docker-compose up --build
```

## ⚙ Configuration

Required environment variables:
- `TELEGRAM_BOT_TOKEN` - Your bot token from @BotFather
- `SPREADSHEET_ID` - Google Sheets ID
- `HR_NOTIFICATION_CHAT_ID` - Chat ID for HR notifications
- `GOOGLE_SHEETS_CREDENTIALS` - Path to Google service account JSON

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

# Русская версия

## 📝 Описание

Telegram бот для HR-агентств для сбора заявок от кандидатов с сохранением в Google Таблицы и базу данных, с функцией загрузки резюме.

## ✨ Возможности

- Поддержка двух языков (Английский/Русский)
- Анкета с валидацией данных
- Загрузка резюме (PDF/DOCX)
- Интеграция с Google Таблицами
- Хранение в SQL базе данных
- Уведомления для HR
- Поддержка Docker

## 🛠 Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/hr-telegram-bot.git
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Настройте переменные окружения (скопируйте `.env.example` в `.env` и заполните данные)

4. Запуск через Docker:
```bash
docker-compose up --build
```

## ⚙ Конфигурация

Необходимые переменные окружения:
- `TELEGRAM_BOT_TOKEN` - Токен бота от @BotFather
- `SPREADSHEET_ID` - ID Google таблицы
- `HR_NOTIFICATION_CHAT_ID` - ID чата для уведомлений HR
- `GOOGLE_SHEETS_CREDENTIALS` - Путь к JSON файлу сервисного аккаунта Google

## 📄 Лицензия

Проект лицензирован под MIT License - подробности в файле [LICENSE](LICENSE).
