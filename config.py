from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os

class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    spreadsheet_id: str = Field(..., env="SPREADSHEET_ID")
    hr_notification_chat_id: str = Field(..., env="HR_NOTIFICATION_CHAT_ID")
    database_url: str = Field(default="sqlite:///candidates.db", env="DATABASE_URL")
    vacancy_channel_id: str = Field(..., env="VACANCY_CHANNEL_ID")
    channel_username: str = Field(..., env="CHANNEL_USERNAME") 
    google_sheets_credentials: str = Field(
        default="hr-bot-458309-172165e27a72.json", 
        env="GOOGLE_SHEETS_CREDENTIALS"
    )

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8"
    )

settings = Settings()