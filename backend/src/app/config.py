from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "SparklAI"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///../local.db"
    database_echo: bool = False

    # Sessions (signed `creator_session` cookie, replaces the old raw-id cookie)
    session_secret: str = "change-me"
    session_cookie_name: str = "creator_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 365  # 1 year, matches previous cookie maxAge

    # Chat / LLM (OpenAI-compatible endpoint, e.g. LM Studio/Ollama/vLLM)
    chat_url: str = "http://127.0.0.1:1234/v1/"
    chat_model: str = ""
    chat_api_key: str = "no-key"

    # Stable Diffusion (Automatic1111 or ComfyUI — see `app/services/sd/`). `sd_url` is the base
    # URL for whichever backend is selected: an Automatic1111 `.../sdapi/v1/` root, or a bare
    # ComfyUI server root (e.g. `http://host:8188/`).
    sd_url: str = "http://127.0.0.1:7860/sdapi/v1/"
    sd_backend: str = "automatic1111"
    sd_photo_model: str = ""
    sd_photo_prompt: str = ""
    sd_photo_negative_prompt: str = ""
    sd_drawing_model: str = ""
    sd_drawing_prompt: str = ""
    sd_drawing_negative_prompt: str = ""
    sd_stylized_model: str = ""
    sd_stylized_prompt: str = ""
    sd_stylized_negative_prompt: str = ""
    sd_sdxl_model: str = ""
    sd_sdxl_prompt: str = ""
    sd_sdxl_negative_prompt: str = ""
    sd_comfy_poll_interval_ms: int = 1500
    sd_comfy_timeout_ms: int = 180000

    # Static SPA build output, mounted by main.py in production
    static_dir: str = "../build"

    # Logging
    log_level: str = "INFO"


settings = Settings()
