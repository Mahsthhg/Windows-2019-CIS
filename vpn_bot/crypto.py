"""USDT TRC20 payment monitoring via TronGrid API."""
import aiohttp
import logging
import time

logger = logging.getLogger(__name__)

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # USDT TRC20 mainnet
TRONGRID_URL  = "https://api.trongrid.io"


async def get_recent_usdt_transfers(address: str, since_ms: int) -> list:
    """Fetch TRC20 USDT transfers TO `address` since `since_ms` epoch milliseconds."""
    url = f"{TRONGRID_URL}/v1/accounts/{address}/transactions/trc20"
    params = {
        "only_to":          "true",
        "contract_address": USDT_CONTRACT,
        "min_timestamp":    since_ms,
        "limit":            50,
    }
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15))
            data = await r.json(content_type=None)
        return data.get("data", [])
    except Exception as e:
        logger.error("TronGrid fetch error: %s", e)
        return []


def usdt_amount_from_transfer(tx: dict) -> float:
    """Extract USDT amount (float, 6 decimals) from TronGrid tx dict."""
    try:
        return int(tx.get("value", "0")) / 1_000_000
    except Exception:
        return 0.0
