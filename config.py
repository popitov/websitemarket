import os
from dotenv import load_dotenv

load_dotenv()

# Путь к общей базе проекта ботов (SQLite)
SHOP_DB = os.getenv("SHOP_DB", "shop.db")

# Подключение к Redis (для автоапрува join-request)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Платёжка Platega (тестовые/боевые параметры)
PLATEGA_MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID", "TEST_MERCHANT_ID")
PLATEGA_API_KEY = os.getenv("PLATEGA_API_KEY", "TEST_SECRET_KEY")
PLATEGA_CREATE_URL = os.getenv("PLATEGA_CREATE_URL", "https://app.platega.io/transaction/process")
PLATEGA_STATUS_URL = os.getenv("PLATEGA_STATUS_URL", "https://app.platega.io/transaction/{payment_id}")

# Базовый URL сайта (для возвратов из Platega)
SITE_URL = os.getenv("SITE_URL", "http://localhost:5000")

# Telegram Login Widget (для авторизации пользователей)
TELEGRAM_LOGIN_BOT = os.getenv("TELEGRAM_LOGIN_BOT", "")         # @username бота
TELEGRAM_LOGIN_TOKEN = os.getenv("TELEGRAM_LOGIN_TOKEN", "")     # токен бота (для верификации подписи)

# Ссылка на статус-бота (опционально, для товаров типа 'status')
STATUS_BOT_LINK = os.getenv("STATUS_BOT_LINK", "")

# Админы по tg_id (через запятую)
def _parse_admins(raw: str):
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except:
            pass
    return out

ADMINS = _parse_admins(os.getenv("ADMINS", ""))

# Безопасный ключ Flask-сессии
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_SECRET")

# Тайминги ожидания оплаты/пула
PAYMENT_POLL_INTERVAL = int(os.getenv("PAYMENT_POLL_INTERVAL", "4"))   # секунды
PAYMENT_POLL_ATTEMPTS = int(os.getenv("PAYMENT_POLL_ATTEMPTS", "45"))  # попыток (около 3 минут)
