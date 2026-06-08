"""
Marzban panel integration (اختیاری).
وقتی PANEL_ENABLED=true باشد، هنگام تایید سفارش به‌صورت خودکار
کاربر در پنل ساخته می‌شود و لینک‌ها برگردانده می‌شوند.
"""
import logging
import httpx
from datetime import datetime, timedelta
from config import PANEL_URL, PANEL_USERNAME, PANEL_PASSWORD, PANEL_INBOUND_TAG, PANEL_DEFAULT_DAYS

logger = logging.getLogger(__name__)


class MarzbanClient:
    def __init__(self):
        self._token: str | None = None
        self._expires: datetime | None = None

    async def _auth(self) -> str:
        if self._token and self._expires and datetime.now() < self._expires:
            return self._token
        async with httpx.AsyncClient(verify=False, timeout=15) as c:
            r = await c.post(
                f"{PANEL_URL}/api/admin/token",
                data={"username": PANEL_USERNAME, "password": PANEL_PASSWORD},
            )
            r.raise_for_status()
            self._token = r.json()["access_token"]
            self._expires = datetime.now() + timedelta(minutes=50)
            return self._token

    async def create_user(self, username: str, gb: int, days: int = None) -> dict:
        """
        کاربر جدید در پنل Marzban می‌سازد.
        برمی‌گرداند: {"config": "vless://...", "sub_link": "https://..."}
        """
        days = days or PANEL_DEFAULT_DAYS
        token = await self._auth()
        expire_ts = int((datetime.now() + timedelta(days=days)).timestamp())

        payload = {
            "username": username,
            "proxies": {"vless": {"flow": "xtls-rprx-vision"}},
            "inbounds": {"vless": [PANEL_INBOUND_TAG]},
            "expire": expire_ts,
            "data_limit": gb * 1_073_741_824,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
        }
        async with httpx.AsyncClient(verify=False, timeout=15) as c:
            r = await c.post(
                f"{PANEL_URL}/api/user",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            data = r.json()

        links = data.get("links", [])
        vless_config = next((l for l in links if l.startswith("vless://")), links[0] if links else "")
        sub_link = f"{PANEL_URL}/sub/{data.get('subscription_url','').lstrip('/')}"
        return {
            "config":       vless_config,
            "sub_link":     sub_link,
            "panel_user":   data.get("username"),
            "expiry_date":  (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d"),
        }

    async def get_user_usage(self, username: str) -> dict | None:
        try:
            token = await self._auth()
            async with httpx.AsyncClient(verify=False, timeout=10) as c:
                r = await c.get(
                    f"{PANEL_URL}/api/user/{username}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                r.raise_for_status()
                d = r.json()
                used = d.get("used_traffic", 0)
                total = d.get("data_limit", 0)
                remaining = max(0, total - used)
                return {
                    "used_gb":      round(used / 1_073_741_824, 2),
                    "total_gb":     round(total / 1_073_741_824, 2),
                    "remaining_gb": round(remaining / 1_073_741_824, 2),
                    "status":       d.get("status"),
                    "expire":       d.get("expire"),
                }
        except Exception as e:
            logger.error("Panel get_user_usage error: %s", e)
            return None

    async def delete_user(self, username: str) -> bool:
        try:
            token = await self._auth()
            async with httpx.AsyncClient(verify=False, timeout=10) as c:
                r = await c.delete(
                    f"{PANEL_URL}/api/user/{username}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                return r.status_code == 200
        except Exception as e:
            logger.error("Panel delete_user error: %s", e)
            return False


marzban = MarzbanClient()
