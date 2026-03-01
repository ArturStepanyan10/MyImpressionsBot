from dataclasses import dataclass

from environs import Env


@dataclass
class TgBot:
    token: str         # Токен для доступа к телеграм-боту


@dataclass
class Config:
    bot: TgBot


def load_config(path: str | None = None) -> Config:
    env: Env = Env()
    env.read_env(path)

    return Config(
        bot=TgBot(
            token=env("BOT_TOKEN")
        )
    )
