"""ZarinPal payment gateway integration."""
import aiohttp
import logging

logger = logging.getLogger(__name__)

SANDBOX_BASE = "https://sandbox.zarinpal.com/pg"
LIVE_BASE    = "https://api.zarinpal.com/pg"


async def request_payment(merchant_id: str, amount_toman: int, description: str,
                           callback_url: str, sandbox: bool = False) -> dict:
    """Create payment request. Returns {'authority': str, 'url': str}."""
    base = SANDBOX_BASE if sandbox else LIVE_BASE
    payload = {
        "merchant_id":   merchant_id,
        "amount":        amount_toman * 10,  # ZarinPal uses Rials
        "description":   description,
        "callback_url":  callback_url,
    }
    async with aiohttp.ClientSession() as s:
        r = await s.post(f"{base}/v4/payment/request.json", json=payload, timeout=aiohttp.ClientTimeout(total=15))
        data = await r.json(content_type=None)
    code = data.get("data", {}).get("code")
    if code == 100:
        authority = data["data"]["authority"]
        gate = f"{'https://sandbox.zarinpal.com/pg' if sandbox else 'https://www.zarinpal.com/pg'}/StartPay/{authority}"
        return {"authority": authority, "url": gate}
    raise Exception(f"ZarinPal request failed: {data.get('errors', data)}")


async def verify_payment(merchant_id: str, amount_toman: int, authority: str,
                          sandbox: bool = False) -> dict:
    """Verify payment after user pays. Returns {'ref_id': str}."""
    base = SANDBOX_BASE if sandbox else LIVE_BASE
    payload = {
        "merchant_id": merchant_id,
        "amount":      amount_toman * 10,
        "authority":   authority,
    }
    async with aiohttp.ClientSession() as s:
        r = await s.post(f"{base}/v4/payment/verify.json", json=payload, timeout=aiohttp.ClientTimeout(total=15))
        data = await r.json(content_type=None)
    code = data.get("data", {}).get("code")
    if code in (100, 101):
        return {
            "ref_id":           str(data["data"].get("ref_id", "")),
            "already_verified": code == 101,
        }
    raise Exception(f"ZarinPal verify failed: {data.get('errors', data)}")
