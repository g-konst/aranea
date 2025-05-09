from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class BrowserConfig(BaseModel):
    timeout: int = 30000
    max_retries: int = 3
    retry_delay: int = 1000
    max_pages: int = 10
    launch_timeout: int = 30000
    close_timeout: int = 5000
    humanize: bool = True
    headless: bool = True
    locale: str = "en-US"
    block_webrtc: bool = True
    geoip: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    rotation: str = "1 day"
    retention: str = "7 days"
    compression: str = "zip"
    enqueue: bool = True
    backtrace: bool = True
    diagnose: bool = True
    sink: str = "logs/app.log"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000

    manager_address: str = "localhost:50050"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    @classmethod
    def settings_customise_sources(
        cls, settings_cls: type[BaseSettings], **kwargs
    ):
        return (
            YamlConfigSettingsSource(
                settings_cls,
                yaml_file=(
                    "config.example.yaml",  # load example config first
                    "config.yaml",
                ),
            ),
        )


settings = Settings()
