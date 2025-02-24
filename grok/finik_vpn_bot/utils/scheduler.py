from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from utils.db import get_user_status, save_vpn_key, db_pool
from utils.marzban import disable_vpn_user, enable_vpn_user, get_marzban_token, create_vpn_user, get_available_inbounds, delete_vpn_user, get_vpn_user
from aiogram import Bot
from config import TELEGRAM_BOT_TOKEN
import asyncio
import logging
from aiojobs import Scheduler as JobScheduler

scheduler = AsyncIOScheduler()
job_scheduler = JobScheduler()
bot = Bot(token=TELEGRAM_BOT_TOKEN)
logger = logging.getLogger(__name__)

async def process_user(user, token):
    user_id = user["user_id"]
    sub_end = user["subscription_end"]
    status = await get_user_status(user_id)
    username = f"user_{user_id}"
    current_time = datetime.now()

    user_data = await get_vpn_user(token, username)
    inbounds = await get_available_inbounds(token)
    if not inbounds:
        logger.error(f"Не удалось получить inbounds для user_id={user_id}")
        return

    if user_data:
        online_at = user_data.get("online_at")
        created_at = user_data.get("created_at")
        last_active = online_at or created_at
        if last_active:
            last_active_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
            if (current_time - last_active_dt).days >= 15 and not status["active"]:
                await delete_vpn_user(token, username)
                await save_vpn_key(user_id, None)
                user_data = None

    if not user_data or not status["vpn_key"]:
        vpn_key = await create_vpn_user(token, username, inbounds)
        if not vpn_key or not vpn_key.get("subscription_url"):
            logger.error(f"Не удалось создать пользователя {username}")
            return
        await save_vpn_key(user_id, vpn_key["subscription_url"])

    if not status["active"]:
        await disable_vpn_user(token, username)
    elif status["active"]:
        await enable_vpn_user(token, username)
    if status["days_left"] == 3:
        await bot.send_message(user_id, "⚠️ Ваша подписка истекает через 3 дня! Продлите доступ в меню 'Купить'.")

async def check_subscriptions():
    logger.info("Запуск проверки подписок")
    current_time = datetime.now()
    token = await get_marzban_token()
    if not token:
        logger.error("Не удалось получить токен Marzban")
        return

    async with db_pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT user_id, subscription_end FROM users WHERE subscription_end <= $1",
            current_time + timedelta(days=3)
        )

    batch_size = 50
    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        for user in batch:
            await job_scheduler.spawn(process_user(user, token))
        await asyncio.sleep(1)

async def setup_scheduler():
    logger.info("Настройка scheduler")
    scheduler.add_job(check_subscriptions, "interval", minutes=20)
    scheduler.start()