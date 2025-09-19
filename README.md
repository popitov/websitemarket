# Webshop (Flask) — Витрина для сети Telegram-магазинов

Полностью рабочий MVP веб‑витрины на Python/Flask + HTML/CSS/JS, интегрируется с общей базой `shop.db`, 
поддерживает оплату через Platega (СБП), выдачу доступа в каналы (через Redis-ключи auto-approve, как в Handler-боте), 
личный кабинет «Мой доступ» и простую админ‑панель (категории, товары, длительности, бандлы).

## Быстрый старт

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. (Опционально для QR через СБП) Установите браузеры Playwright:
   ```bash
   python -m playwright install
   ```

3. Создайте `.env` файл (или отредактируйте `config.py`) со своими значениями:
   ```env
   SHOP_DB=/absolute/path/to/shop.db
   REDIS_URL=redis://localhost:6379/0
   PLATEGA_MERCHANT_ID=...        # тестовый мерчант
   PLATEGA_API_KEY=...            # тестовый ключ
   SITE_URL=http://localhost:5000
   TELEGRAM_LOGIN_BOT=YourLoginBot
   TELEGRAM_LOGIN_TOKEN=123456:ABC-DEF....
   ADMINS=111111111,222222222
   ```

4. Запустите приложение:
   ```bash
   flask --app app.py run --debug
   ```
   или
   ```bash
   python app.py
   ```

## Важные замечания

- **База `shop.db`**: используется существующая схема проекта ботов. Код только читает товары/категории/каналы и создаёт покупки/платежи по факту оплаты.
- **Идентификация пользователя**: 
  - Для доступа в **канал** требуется Telegram‑логин (виджет Telegram Login) — нужен `tg_id`, чтобы выставить ключ в Redis для авто-апрува Handler‑ботом.
  - Для **текстовых** товаров покупка возможна и без Telegram‑логина; такие покупки сохраняются в сессии браузера (раздел «Мой доступ» покажет их, пока не очищены cookie).
- **Platega / QR**: страница оплаты показывает QR СБП. Для его автопарсинга (как в боте) задействуется Playwright — он открывает редирект-страницу Platega и извлекает ссылку `qr.nspk.ru`. Если Playwright не установлен/не запускается, на странице будет кнопка «Открыть страницу оплаты».
- **Handler‑бот**: сайт не создаёт новые каналы и не копирует контент. Он лишь выдаёт join‑request ссылки из таблицы `channels`/`tariff_channels` и ставит Redis‑ключ `auto:<channel_id>:<tg_id>` на TTL покупки — дальше Handler‑бот автоматически одобрит Join Request.
- **Админ‑панель**: простые CRUD по категориям/товарам/длительностям/бандлам. Для привязки каналов к тарифам по-прежнему удобно пользоваться Telegram‑админ‑ботом (веб‑панель может быть расширена под это при необходимости).

## Структура

```
webshop/
├── app.py
├── config.py
├── db.py
├── routes_main.py
├── routes_admin.py
├── requirements.txt
├── README.md
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
└── templates/
    ├── base.html
    ├── index.html
    ├── category.html
    ├── product_detail.html
    ├── cart.html
    ├── payment.html
    ├── account.html
    ├── admin_base.html
    ├── admin_categories.html
    ├── admin_category_edit.html
    ├── admin_tariffs.html
    └── admin_tariff_edit.html
```

## Примечание по совместимости

- Код рассчитан на Python 3.10+.
- Если в вашей `shop.db` отсутствуют некоторые таблицы (например, `promocodes`), соответствующие разделы просто не будут активны (код проверяет наличие таблиц/колонок перед запросами).
