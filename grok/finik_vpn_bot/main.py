from aiohttp import web
import hmac
import hashlib
from config import YUKASSA_SECRET_KEY


async def yookassa_webhook(request):
    data = await request.json()
    signature = request.headers.get("X-Signature")

    # Валидация подписи (простой пример, уточните у документации YooKassa)
    computed_signature = hmac.new(
        YUKASSA_SECRET_KEY.encode(),
        json.dumps(data).encode(),
        hashlib.sha256
    ).hexdigest()

    if signature != computed_signature:
        return web.Response(status=401, text="Invalid signature")

    # Обработка платежа (например, обновление статуса в базе данных)
    payment_id = data.get("object", {}).get("id")
    if payment_id and data.get("event") == "payment.succeeded":
        # Здесь можно вызвать check_payment или обновить статус в базе
        logger.info(f"YooKassa payment {payment_id} succeeded")
        return web.Response(status=200, text="OK")

    return web.Response(status=200, text="OK")


async def on_startup(app):
    await init_db()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    app['bot'] = bot
    app['dp'] = dp

    setup_start_handlers(dp)
    setup_status_handlers(dp)
    setup_subscription_handlers(dp)

    await setup_scheduler()
    await bot.set_webhook("https://webhook.finik.online/webhook")
    logger.info("Webhook установлен")


async def handle_webhook(request):
    bot = request.app['bot']
    dp = request.app['dp']
    update = await request.json()
    await dp.feed_update(bot, update)
    return web.Response()


async def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.add_routes([
        web.post('/webhook', handle_webhook),
        web.post('/yookassa-webhook', yookassa_webhook)  # Новый маршрут для YooKassa
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8443)
    await site.start()
    logger.info("Сервер запущен на порту 8443")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())