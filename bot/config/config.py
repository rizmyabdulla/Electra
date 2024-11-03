from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str


    REF_LINK: str = "https://t.me/ElectraAppBot/dex?startapp=lbIgsm9M"

    DELAY_EACH_ACCOUNT: list[int] = [20, 30]

    USE_PROXY_FROM_FILE: bool = False

    BTC_PRICE_GUESS: str = "random"


settings = Settings()

