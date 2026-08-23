import asyncio
import json
import os

import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    CallbackQuery
)
from dotenv import load_dotenv


# =========================
# НАСТРОЙКИ
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

SHOP_URL = "https://010xxx513.github.io/Velora/"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db_pool = None


# =========================
# БАЗА ДАННЫХ
# =========================

async def init_database():
    global db_pool

    db_pool = await asyncpg.create_pool(DATABASE_URL)

    async with db_pool.acquire() as connection:

        await connection.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                order_number TEXT UNIQUE NOT NULL,
                name TEXT,
                telegram TEXT,
                telegram_id BIGINT,
                total NUMERIC,
                delivery TEXT,
                items JSONB,
                status TEXT DEFAULT 'Принят',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Если таблица orders уже существовала раньше,
        # добавляем новую колонку без удаления старых данных.
        await connection.execute("""
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS telegram_id BIGINT
        """)

    print("PostgreSQL подключён")
    print("Таблица orders готова")


# =========================
# ПРОВЕРКА АДМИНА
# =========================

def is_admin(message):
    return message.chat.id == ADMIN_CHAT_ID


# =========================
# КНОПКИ СТАТУСОВ
# =========================

def status_keyboard(order_number):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟡 В обработке",
                    callback_data=f"status|{order_number}|В обработке"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟢 Подтверждён",
                    callback_data=f"status|{order_number}|Подтверждён"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📦 Готов к выдаче",
                    callback_data=f"status|{order_number}|Готов к выдаче"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Выполнен",
                    callback_data=f"status|{order_number}|Выполнен"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменён",
                    callback_data=f"status|{order_number}|Отменён"
                )
            ]
        ]
    )


# =========================
# УВЕДОМЛЕНИЕ КЛИЕНТА
# =========================

async def notify_customer(telegram_id, order_number, status):

    if not telegram_id:
        print(
            f"У заказа №{order_number} нет Telegram ID клиента. "
            f"Уведомление не отправлено."
        )
        return

    messages = {
        "В обработке": (
            f"🛍 <b>Velora</b>\n\n"
            f"Ваш заказ №{order_number} взят в обработку. 🟡\n\n"
            f"Мы уже занимаемся вашим заказом."
        ),

        "Подтверждён": (
            f"🛍 <b>Velora</b>\n\n"
            f"Ваш заказ №{order_number} подтверждён! 🟢\n\n"
            f"Спасибо за заказ 🖤"
        ),

        "Готов к выдаче": (
            f"🛍 <b>Velora</b>\n\n"
            f"Ваш заказ №{order_number} готов к выдаче! 📦\n\n"
            f"Скоро вы сможете его забрать."
        ),

        "Выполнен": (
            f"🛍 <b>Velora</b>\n\n"
            f"Ваш заказ №{order_number} выполнен! ✅\n\n"
            f"Спасибо, что выбрали Velora 🖤"
        ),

        "Отменён": (
            f"🛍 <b>Velora</b>\n\n"
            f"Ваш заказ №{order_number} отменён. ❌\n\n"
            f"Если у вас есть вопросы, свяжитесь с нами."
        )
    }

    text = messages.get(status)

    if not text:
        return

    try:
        await bot.send_message(
            chat_id=int(telegram_id),
            text=text,
            parse_mode="HTML"
        )

        print(
            f"Уведомление отправлено клиенту "
            f"{telegram_id} по заказу №{order_number}"
        )

    except Exception as error:
        print(
            f"Не удалось отправить уведомление клиенту "
            f"{telegram_id}: {error}"
        )


# =========================
# /START
# =========================

@dp.message(CommandStart())
async def start_handler(message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛍 Открыть Velora",
                    web_app=WebAppInfo(url=SHOP_URL)
                )
            ]
        ]
    )

    await message.answer(
        "Привет! 👋\n\n"
        "Добро пожаловать в <b>Velora</b> — онлайн-магазин одежды и обуви.\n\n"
        "Выбирай товар, оформляй заказ и наслаждайся покупкой 🖤",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =========================
# /HELP
# =========================

@dp.message(Command("help"))
async def help_handler(message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛍 Открыть Velora",
                    web_app=WebAppInfo(url=SHOP_URL)
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Связаться с нами",
                    url="https://t.me/velllorrra"
                )
            ]
        ]
    )

    await message.answer(
        "🖤 <b>Velora — помощь</b>\n\n"
        "🛍 <b>Магазин</b>\n"
        "Нажми «Открыть Velora», чтобы посмотреть каталог и оформить заказ.\n\n"
        "📦 <b>Как оформить заказ</b>\n"
        "Выбери товар → размер → добавь его в корзину → "
        "укажи данные → подтверди заказ.\n\n"
        "🚚 <b>Получение</b>\n"
        "После оформления с тобой свяжется менеджер для подтверждения заказа "
        "и деталей получения.\n\n"
        "💬 <b>Поддержка</b>\n"
        "Есть вопросы по товару или заказу? Напиши нам — поможем.\n\n"
        "<b>Команды:</b>\n"
        "/start — открыть Velora\n"
        "/help — помощь",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =========================
# /ORDERS
# =========================

@dp.message(Command("orders"))
async def orders_handler(message):

    if not is_admin(message):
        return

    async with db_pool.acquire() as connection:
        orders = await connection.fetch("""
            SELECT
                order_number,
                total,
                status,
                created_at
            FROM orders
            ORDER BY id DESC
            LIMIT 20
        """)

    if not orders:
        await message.answer("📦 Заказов пока нет.")
        return

    text = "📦 <b>Последние заказы</b>\n\n"

    for order in orders:
        text += (
            f"№{order['order_number']} — "
            f"{order['total']} ₽ — "
            f"{order['status']}\n"
        )

    text += (
        "\nЧтобы открыть заказ подробнее:\n"
        "<code>/order 1</code>"
    )

    await message.answer(
        text,
        parse_mode="HTML"
    )


# =========================
# /ORDER
# =========================

@dp.message(Command("order"))
async def order_details_handler(message):

    if not is_admin(message):
        return

    command_parts = message.text.split(maxsplit=1)

    if len(command_parts) < 2:
        await message.answer(
            "Использование:\n"
            "<code>/order 1</code>",
            parse_mode="HTML"
        )
        return

    order_number = command_parts[1].strip()

    clean_order_number = (
        order_number
        .replace("№", "")
        .replace(" ", "")
        .strip()
    )

    async with db_pool.acquire() as connection:
        order = await connection.fetchrow(
            """
            SELECT
                order_number,
                name,
                telegram,
                telegram_id,
                total,
                delivery,
                items,
                status,
                created_at
            FROM orders
            WHERE REPLACE(REPLACE(order_number, '№', ''), ' ', '') = $1
            """,
            clean_order_number
        )

    if not order:
        await message.answer(
            f"❌ Заказ №{clean_order_number} не найден."
        )
        return

    items = order["items"] or []

    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            items = []

    items_text = ""

    if isinstance(items, list):
        for item in items:

            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except json.JSONDecodeError:
                    continue

            if isinstance(item, dict):
                items_text += (
                    f"• {item.get('name', 'Товар')} — "
                    f"{item.get('size', '—')} × "
                    f"{item.get('quantity', 1)}\n"
                )

    if not items_text:
        items_text = "—\n"

    text = (
        f"🛍 <b>Заказ №{clean_order_number}</b>\n\n"
        f"👤 <b>Имя:</b> {order['name'] or '—'}\n"
        f"💬 <b>Telegram:</b> {order['telegram'] or '—'}\n\n"
        f"📦 <b>Товары:</b>\n"
        f"{items_text}\n"
        f"💰 <b>Сумма:</b> {order['total']} ₽\n"
        f"🚚 <b>Получение:</b> {order['delivery'] or '—'}\n"
        f"🟢 <b>Статус:</b> {order['status']}\n"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=status_keyboard(clean_order_number)
    )


# =========================
# ИЗМЕНЕНИЕ СТАТУСА
# =========================

@dp.callback_query()
async def status_callback(callback: CallbackQuery):

    if callback.message.chat.id != ADMIN_CHAT_ID:
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True
        )
        return

    data = callback.data

    if not data.startswith("status|"):
        await callback.answer()
        return

    parts = data.split("|", 2)

    if len(parts) != 3:
        await callback.answer(
            "Ошибка",
            show_alert=True
        )
        return

    _, order_number, new_status = parts

    async with db_pool.acquire() as connection:

        order = await connection.fetchrow(
            """
            SELECT
                order_number,
                name,
                telegram,
                telegram_id,
                total,
                delivery,
                items,
                status
            FROM orders
            WHERE REPLACE(REPLACE(order_number, '№', ''), ' ', '') = $1
            """,
            order_number
        )

        if not order:
            await callback.answer(
                "Заказ не найден",
                show_alert=True
            )
            return

        old_status = order["status"]

        await connection.execute(
            """
            UPDATE orders
            SET status = $1
            WHERE REPLACE(REPLACE(order_number, '№', ''), ' ', '') = $2
            """,
            new_status,
            order_number
        )

    await callback.answer(
        f"Статус изменён: {new_status}"
    )

    # Если статус действительно изменился —
    # отправляем уведомление клиенту.
    if old_status != new_status:
        await notify_customer(
            telegram_id=order["telegram_id"],
            order_number=order_number,
            status=new_status
        )

    # =========================
    # ОБНОВЛЯЕМ СООБЩЕНИЕ АДМИНА
    # =========================

    items = order["items"] or []

    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            items = []

    items_text = ""

    if isinstance(items, list):
        for item in items:

            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except json.JSONDecodeError:
                    continue

            if isinstance(item, dict):
                items_text += (
                    f"• {item.get('name', 'Товар')} — "
                    f"{item.get('size', '—')} × "
                    f"{item.get('quantity', 1)}\n"
                )

    if not items_text:
        items_text = "—\n"

    text = (
        f"🛍 <b>Заказ №{order_number}</b>\n\n"
        f"👤 <b>Имя:</b> {order['name'] or '—'}\n"
        f"💬 <b>Telegram:</b> {order['telegram'] or '—'}\n\n"
        f"📦 <b>Товары:</b>\n"
        f"{items_text}\n"
        f"💰 <b>Сумма:</b> {order['total']} ₽\n"
        f"🚚 <b>Получение:</b> {order['delivery'] or '—'}\n"
        f"🟢 <b>Статус:</b> {new_status}\n"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=status_keyboard(order_number)
    )


# =========================
# СЕРВЕР ЗАКАЗОВ
# =========================

async def order_handler(request):

    try:
        data = await request.json()

        # Номер заказа НЕ принимаем от Mini App.
        # Его выдаём здесь, в PostgreSQL, чтобы номера были уникальными
        # и не зависели от localStorage браузера.
        name = data.get("name")
        telegram = data.get("telegram")
        telegram_id = data.get("telegram_id")
        total = data.get("total")
        delivery = data.get("delivery")
        items = data.get("items", [])
        date = data.get("date")

        # Приводим Telegram ID к числу.
        if telegram_id:
            try:
                telegram_id = int(telegram_id)
            except (ValueError, TypeError):
                telegram_id = None

        # Создаём номер заказа атомарно на стороне PostgreSQL.
        # pg_advisory_xact_lock не позволяет двум одновременным заказам
        # получить один и тот же следующий номер.
        async with db_pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT pg_advisory_xact_lock($1)",
                    918273645
                )

                row = await connection.fetchrow(
                    """
                    SELECT COALESCE(
                        MAX(
                            CASE
                                WHEN order_number ~ '^[0-9]+$'
                                THEN order_number::BIGINT
                            END
                        ),
                        0
                    ) + 1 AS next_number
                    FROM orders
                    """
                )

                order_number = str(row["next_number"])

                await connection.execute(
                    """
                    INSERT INTO orders (
                        order_number,
                        name,
                        telegram,
                        telegram_id,
                        total,
                        delivery,
                        items,
                        status
                    )
                    VALUES (
                        $1,
                        $2,
                        $3,
                        $4,
                        $5,
                        $6,
                        $7::jsonb,
                        $8
                    )
                    """,
                    order_number,
                    name,
                    telegram,
                    telegram_id,
                    total,
                    delivery,
                    json.dumps(items, ensure_ascii=False),
                    "Принят"
                )

        # =========================
        # СООБЩЕНИЕ АДМИНУ
        # =========================

        items_text = ""

        for item in items:

            items_text += (
                f"• {item.get('name')} — "
                f"{item.get('size')} × "
                f"{item.get('quantity')}\n"
            )

        text = (
            f"🛍 <b>Новый заказ Velora №{order_number}</b>\n\n"
            f"👤 <b>Имя:</b> {name}\n"
            f"💬 <b>Telegram:</b> {telegram}\n\n"
            f"📦 <b>Товары:</b>\n"
            f"{items_text}\n"
            f"💰 <b>Сумма:</b> {total} ₽\n"
            f"🚚 <b>Получение:</b> {delivery}\n\n"
            f"🟢 <b>Статус:</b> Принят"
        )

        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            parse_mode="HTML"
        )

        return web.json_response(
            {
                "ok": True,
                "number": order_number,
                "date": date
            },
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )

    except Exception as error:

        print("Ошибка заказа:", error)

        return web.json_response(
            {
                "ok": False,
                "error": str(error)
            },
            status=500,
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )


# =========================
# CORS
# =========================

async def options_handler(request):

    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )


# =========================
# HEALTH CHECK
# =========================

async def health_handler(request):

    return web.json_response({
        "status": "ok",
        "service": "VeloraBot"
    })


# =========================
# WEB-СЕРВЕР
# =========================

async def start_web_server():

    app = web.Application()

    app.router.add_get("/", health_handler)
    app.router.add_post("/api/order", order_handler)
    app.router.add_options("/api/order", options_handler)

    runner = web.AppRunner(app)

    await runner.setup()

    port = int(os.getenv("PORT", 8000))

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    print(f"Web-сервер запущен на порту {port}")


# =========================
# ЗАПУСК
# =========================

async def main():

    await init_database()
    await start_web_server()

    print("Velora Bot запущен!")

    try:
        await dp.start_polling(bot)

    finally:

        if db_pool:
            await db_pool.close()


# =========================
# START
# =========================

if __name__ == "__main__":
    asyncio.run(main())
