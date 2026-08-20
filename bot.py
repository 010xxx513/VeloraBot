import asyncio
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

# Ссылка на опубликованный магазин Velora
SHOP_URL = "https://010xxx513.github.io/Velora/"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# КОМАНДЫ БОТА
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


@dp.message(Command("help"))
async def help_handler(message):
    await message.answer(
        "🖤 <b>Velora — помощь</b>\n\n"
        "🛍 Открыть магазин — нажми кнопку «Открыть Velora».\n"
        "📦 Для оформления заказа выбери товар, размер и заполни данные.\n\n"
        "Если возникли вопросы — напиши нам.",
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
            {"ok": False, "error": str(error)},
            status=500,
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )


async def options_handler(request):
    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )


# Проверка, что сервер работает
async def health_handler(request):
    return web.json_response({
        "ok": True,
        "service": "VeloraBot"
    })


async def start_web_server():
    app = web.Application()

    app.router.add_get("/", health_handler)
    app.router.add_post("/api/order", order_handler)
    app.router.add_options("/api/order", options_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    # Render передаёт порт через переменную PORT
    port = int(os.getenv("PORT", 8000))

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    print(f"Сервер заказов запущен на порту {port}")


# =========================
# ЗАПУСК
# =========================

async def main():
    await start_web_server()

    print("Velora Bot запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
