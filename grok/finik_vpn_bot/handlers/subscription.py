from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from config import YUKASSA_SHOP_ID, YUKASSA_SECRET_KEY, DATABASE_URL
from utils.db import extend_subscription, get_user_status, save_vpn_key, activate_referral_bonus, db_pool
from utils.marzban import get_marzban_token, enable_vpn_user, get_available_inbounds, create_vpn_user, get_vpn_user, delete_vpn_user
import uuid
import aiohttp
import base64
import logging
import asyncio
import asyncpg

logger = logging.getLogger(__name__)
router = Router()
_processed_payments = set()

@router.message(F.text == "💳 Купить")
async def buy_handler(message: Message):
    user_id = message.from_user.id
    logging_extra = {"user_id": user_id}
    logger.info("Нажата кнопка 'Купить'", extra=logging_extra)
    await message.delete()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 149 ₽ - 1 месяц", callback_data="buy_30")],
        [InlineKeyboardButton(text="💰 370 ₽ - 3 месяца", callback_data="buy_90")],
        [InlineKeyboardButton(text="💰 625 ₽ - 6 месяцев", callback_data="buy_180")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="clear_message")]
    ])
    await message.answer("Выберите подписку:", reply_markup=keyboard)

async def generate_payment_url(user_id: int, amount: int, days: int, order_id: str) -> tuple[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Idempotence-Key": order_id,
        "Authorization": f"Basic {base64.b64encode(f'{YUKASSA_SHOP_ID}:{YUKASSA_SECRET_KEY}'.encode()).decode()}"
    }
    payload = {
        "amount": {"value": f"{amount}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/finik_vpn_bot"},
        "capture": True,
        "description": f"Подписка на {days} дней для user_{user_id}",
        "metadata": {"user_id": str(user_id), "days": str(days), "order_id": order_id},
        "receipt": {
            "customer": {"email": "support@finik.online"},
            "items": [
                {
                    "description": f"Подписка на {days} дней",
                    "quantity": "1.00",
                    "amount": {"value": f"{amount}.00", "currency": "RUB"},
                    "vat_code": 1,
                    "payment_subject": "service",
                    "payment_mode": "full_payment"
                }
            ]
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.yookassa.ru/v3/payments", json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data["confirmation"]["confirmation_url"], data["id"]
            logger.error(f"Ошибка создания платежа: {await response.text()}", extra={"user_id": user_id})
            return None, None

async def check_payment(order_id: str) -> bool:
    headers = {
        "Authorization": f"Basic {base64.b64encode(f'{YUKASSA_SHOP_ID}:{YUKASSA_SECRET_KEY}'.encode()).decode()}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.yookassa.ru/v3/payments/{order_id}", headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                status = data.get("status")
                logger.info(f"Статус платежа {order_id}: {status}")
                return status == "succeeded"
            logger.error(f"Ошибка проверки платежа: {await response.text()}")
            return False

@router.callback_query(F.data == "buy_30")
async def buy_30_days(callback: CallbackQuery):
    user_id = callback.from_user.id
    logging_extra = {"user_id": user_id}
    logger.info("Выбрана подписка на 30 дней", extra=logging_extra)
    await callback.message.delete()

    order_id = str(uuid.uuid4())
    payment_url, payment_id = await generate_payment_url(user_id, 149, 30, order_id)
    if not payment_url:
        await callback.message.answer("❌ Ошибка создания платежа. Попробуйте позже.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"confirm_payment_{payment_id}_30")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_subscriptions")]
    ])
    await callback.message.answer("Оплата 30 дней: 149 рублей", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "buy_90")
async def buy_90_days(callback: CallbackQuery):
    user_id = callback.from_user.id
    logging_extra = {"user_id": user_id}
    logger.info("Выбрана подписка на 90 дней", extra=logging_extra)
    await callback.message.delete()

    order_id = str(uuid.uuid4())
    payment_url, payment_id = await generate_payment_url(user_id, 370, 90, order_id)
    if not payment_url:
        await callback.message.answer("❌ Ошибка создания платежа. Попробуйте позже.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"confirm_payment_{payment_id}_90")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_subscriptions")]
    ])
    await callback.message.answer("Оплата 90 дней: 370 рублей", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "buy_180")
async def buy_180_days(callback: CallbackQuery):
    user_id = callback.from_user.id
    logging_extra = {"user_id": user_id}
    logger.info("Выбрана подписка на 180 дней", extra=logging_extra)
    await callback.message.delete()

    order_id = str(uuid.uuid4())
    payment_url, payment_id = await generate_payment_url(user_id, 625, 180, order_id)
    if not payment_url:
        await callback.message.answer("❌ Ошибка создания платежа. Попробуйте позже.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"confirm_payment_{payment_id}_180")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_subscriptions")]
    ])
    await callback.message.answer("Оплата 180 дней: 625 рублей", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "back_to_subscriptions")
async def back_to_subscriptions(callback: CallbackQuery):
    user_id = callback.from_user.id
    logging_extra = {"user_id": user_id}
    logger.info("Нажата кнопка 'Назад'", extra=logging_extra)
    await callback.message.delete()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 149 ₽ - 1 месяц", callback_data="buy_30")],
        [InlineKeyboardButton(text="💰 370 ₽ - 3 месяца", callback_data="buy_90")],
        [InlineKeyboardButton(text="💰 625 ₽ - 6 месяцев", callback_data="buy_180")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="clear_message")]
    ])
    await callback.message.answer("Выберите подписку:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "clear_message")
async def clear_message(callback: CallbackQuery):
    user_id = callback.from_user.id
    logging_extra = {"user_id": user_id}
    logger.info("Нажата кнопка 'Назад'", extra=logging_extra)
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment(callback: CallbackQuery):
    parts = callback.data.split("_")
    payment_id = parts[2]
    days = int(parts[3])
    user_id = callback.from_user.id
    logging_extra = {"user_id": user_id}
    logger.info(f"Проверка оплаты payment_id={payment_id}, days={days}", extra=logging_extra)

    if payment_id in _processed_payments:
        await callback.answer("Оплата уже обработана!")
        return
    if await check_payment(payment_id):
        _processed_payments.add(payment_id)
        await extend_subscription(user_id, days)
        status = await get_user_status(user_id)
        token = await get_marzban_token()
        if token:
            username = f"user_{user_id}"
            if not status["vpn_key"]:
                user_data = await get_vpn_user(token, username)
                if user_data:
                    delete_result = await delete_vpn_user(token, username)
                    if not delete_result:
                        await callback.message.answer("❌ Ошибка сервера. Обратитесь в техподдержку.")
                        return
                    await asyncio.sleep(1)

                inbounds = await get_available_inbounds(token)
                if not inbounds:
                    await callback.message.answer("❌ Ошибка сервера. Обратитесь в техподдержку.")
                    return
                vpn_key = await create_vpn_user(token, username, inbounds)
                if not vpn_key or not vpn_key.get("subscription_url"):
                    await callback.message.answer("❌ Ошибка создания ключа. Обратитесь в техподдержку.")
                    return
                await save_vpn_key(user_id, vpn_key["subscription_url"])
                status = await get_user_status(user_id)
            await enable_vpn_user(token, username)

            async with db_pool.acquire() as conn:
                referrers = await conn.fetch(
                    "SELECT referrer_id FROM invited_users WHERE invited_user_id = $1 AND bonus_activated = FALSE",
                    user_id
                )
            for referrer in referrers:
                referrer_id = referrer["referrer_id"]
                bonus_activated = await activate_referral_bonus(referrer_id, user_id)
                if bonus_activated:
                    try:
                        await callback.message.bot.send_message(
                            referrer_id,
                            f"🎉 Пользователь, которого вы пригласили, активировал подписку! Вам добавлено 3 дня."
                        )
                    except Exception as e:
                        logger.error(f"Ошибка уведомления referrer_id={referrer_id}: {str(e)}", extra=logging_extra)

        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.message.answer(
            f"✅ Оплата прошла успешно! Доступ продлён до {status['subscription_end']} (МСК).\n"
            f"Теперь выберите устройство в меню 'Установить'."
        )
    else:
        await callback.message.answer("❌ Оплата ещё не подтверждена. Убедитесь, что вы завершили оплату.")
    await callback.answer()

def setup_subscription_handlers(dp: Router):
    dp.include_router(router)