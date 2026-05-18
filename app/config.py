from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./bot.db"
    redis_url: str | None = None
    admin_ids: str = ""
    closed_channel_url: str = "https://t.me/"
    final_video_note_file_id: str | None = None
    # TG message effect on the final card. Default = 🎉 confetti.
    # Other IDs: 🔥 5104841245755180586 · ❤️ 5159385139981059251 · 👍 5107584321108051014
    # Set to empty string in .env to disable.
    final_effect_id: str | None = "5046509860389126442"

    # Google Sheets (real-time export). Leave both empty to disable.
    google_sheet_id: str | None = None
    google_credentials_path: str | None = None

    @property
    def admin_id_list(self) -> list[int]:
        return [int(x) for x in self.admin_ids.split(",") if x.strip()]


settings = Settings()
