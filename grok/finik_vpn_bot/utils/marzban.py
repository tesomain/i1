import aiohttp
import logging
from config import MARZBAN_URL, ADMIN_USERNAME, ADMIN_PASSWORD
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_token_cache = {"token": None, "expires_at": None}
_inbounds_cache = None

async def get_marzban_token():
    current_time = datetime.now()
    if _token_cache["token"] and _token_cache["expires_at"] > current_time:
        return _token_cache["token"]

    payload = {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{MARZBAN_URL}/api/admin/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            ssl=False
        ) as response:
            if response.status == 200:
                data = await response.json()
                _token_cache["token"] = data["access_token"]
                _token_cache["expires_at"] = current_time + timedelta(hours=1)  # Предполагаем TTL 1 час
                return _token_cache["token"]
            logger.error(f"Ошибка получения токена: {await response.text()}")
            return None

async def get_available_inbounds(token):
    global _inbounds_cache
    if _inbounds_cache:
        return _inbounds_cache
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{MARZBAN_URL}/api/inbounds",
            headers={"Authorization": f"Bearer {token}"},
            ssl=False
        ) as response:
            if response.status == 200:
                _inbounds_cache = await response.json()
                return _inbounds_cache
            logger.error(f"Ошибка получения inbounds: {await response.text()}")
            return None

async def get_vpn_user(token, username):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{MARZBAN_URL}/api/user/{username}",
            headers={"Authorization": f"Bearer {token}"},
            ssl=False
        ) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 404:
                return None
            logger.error(f"Ошибка получения данных пользователя {username}: {await response.text()}")
            return None

async def create_vpn_user(token, username, inbounds):
    if not inbounds or "vless" not in inbounds or not inbounds["vless"]:
        logger.error(f"Нет доступных vless inbound'ов для {username}")
        return None
    inbound_tag = inbounds["vless"][0]["tag"]
    inbound = {"vless": [inbound_tag]}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{MARZBAN_URL}/api/user",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": username, "proxies": {"vless": {}}, "inbounds": inbound},
            ssl=False
        ) as response:
            if response.status == 200:
                return await response.json()
            logger.error(f"Ошибка создания пользователя {username}: {await response.text()}")
            return None

async def delete_vpn_user(token, username):
    async with aiohttp.ClientSession() as session:
        async with session.delete(
            f"{MARZBAN_URL}/api/user/{username}",
            headers={"Authorization": f"Bearer {token}"},
            ssl=False
        ) as response:
            if response.status in (200, 204):
                return True
            elif response.status == 404:
                return True
            logger.error(f"Ошибка удаления пользователя {username}: {await response.text()}")
            return False

async def disable_vpn_user(token, username):
    async with aiohttp.ClientSession() as session:
        async with session.put(
            f"{MARZBAN_URL}/api/user/{username}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "disabled"},
            ssl=False
        ) as response:
            if response.status == 200:
                return True
            logger.error(f"Ошибка отключения ключа {username}: {await response.text()}")
            return False

async def enable_vpn_user(token, username):
    async with aiohttp.ClientSession() as session:
        async with session.put(
            f"{MARZBAN_URL}/api/user/{username}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "active"},
            ssl=False
        ) as response:
            if response.status == 200:
                return True
            logger.error(f"Ошибка включения ключа {username}: {await response.text()}")
            return False