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
    WebAppInfo
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
                total NUMERIC,
                delivery TEXT,
                items JSONB,
                status TEXT DEFAULT 'Принят',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    print("PostgreSQL подключён")
    print("Таблица orders готова")


# =========================
# ПРОВЕРКА АДМИНА
# =========================

def is_admin(message):
    return message.chat.id == ADMIN_CHAT_ID


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
# ТОЛЬКО ДЛЯ АДМИНА
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

    text += "\nЧтобы открыть заказ подробнее:\n"
    text += "<code>/order НОМЕР</code>"

    await message.answer(
        text,
        parse_mode="HTML"
    )


# =========================
# /ORDER НОМЕР
# ТОЛЬКО ДЛЯ АДМИНА
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

    async with db_pool.acquire() as connection:
        order = await connection.fetchrow(
            """
            SELECT
                order_number,
                name,
                telegram,
                total,
                delivery,
                items,
                status,
                created_at
            FROM orders
            WHERE order_number = $1
            """,
            order_number
        )

    if not order:
        await message.answer(
            f"❌ Заказ №{order_number} не найден."
        )
        return

    items = order["items"] or []

    items_text = ""

    for item in items:
        items_text += (
            f"• {item.get('name', 'Товар')} — "
            f"{item.get('size', '—')} × "
            f"{item.get('quantity', 1)}\n"
        )

    text = (
        f"🛍 <b>Заказ №{order['order_number']}</b>\n\n"
        f"👤 <b>Имя:</b> {order['name'] or '—'}\n"
        f"💬 <b>Telegram:</b> {order['telegram'] or '—'}\n\n"
        f"📦 <b>Товары:</b>\n"
        f"{items_text or '—'}\n"
        f"💰 <b>Сумма:</b> {order['total']} ₽\n"
        f"🚚 <b>Получение:</b> {order['delivery'] or '—'}\n"
        f"🟢 <b>Статус:</b> {order['status']}\n"
    )

    await message.answer(
        text,
        parse_mode="HTML"
    )


# =========================
# СЕРВЕР ЗАКАЗОВ
# =========================

async def order_handler(request):
    try:
        data = await request.json()

        order_number = data.get("number")
        name = data.get("name")
        telegram = data.get("telegram")
        total = data.get("total")
        delivery = data.get("delivery")
        items = data.get("items", [])

        # Сохраняем заказ в PostgreSQL
        async with db_pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO orders (
                    order_number,
                    name,
                    telegram,
                    total,
                    delivery,
                    items,
                    status
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                ON CONFLICT (order_number) DO NOTHING
                """,
                str(order_number),
                name,
                telegram,
                total,
                delivery,
                json.dumps(items, ensure_ascii=False),
                "Принят"
            )

        # Формируем сообщение администратору
        items_text = ""

        for item in items:
            items_text += (
                f"• {item.get('name')} — "
                f"{item.get('size')} × {item.get('quantity')}\n"
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
            {"ok": True},
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
# ПРОВЕРКА СЕРВЕРА
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
