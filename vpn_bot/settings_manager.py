"""تنظیمات پویا — ذخیره در DB، قابل تغییر از پنل ادمین بدون ریستارت."""
import json
import sqlite3
from config import DB_PATH

_cache: dict = {}


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_settings() -> None:
    db = _conn()
    db.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    db.commit()
    rows = db.execute("SELECT key, value FROM bot_settings").fetchall()
    for row in rows:
        try:
            _cache[row['key']] = json.loads(row['value'])
        except (json.JSONDecodeError, TypeError):
            _cache[row['key']] = row['value']
    db.close()


def get(key: str, default=None):
    return _cache.get(key, default)


def set_val(key: str, value) -> None:
    _cache[key] = value
    db = _conn()
    db.execute(
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
        (key, json.dumps(value, ensure_ascii=False)),
    )
    db.commit()
    db.close()


def delete(key: str) -> None:
    _cache.pop(key, None)
    db = _conn()
    db.execute("DELETE FROM bot_settings WHERE key=?", (key,))
    db.commit()
    db.close()


def all_settings() -> dict:
    return dict(_cache)


# ─── Typed accessors ──────────────────────────────────────────────────────────

def price_per_gb() -> int:
    from config import PRICE_PER_GB
    return int(get('price_per_gb', PRICE_PER_GB))


def min_gb() -> int:
    from config import MIN_GB
    return int(get('min_gb', MIN_GB))


def max_gb() -> int:
    from config import MAX_GB
    return int(get('max_gb', MAX_GB))


def gb_packages() -> list:
    from config import GB_PACKAGES
    v = get('gb_packages', None)
    return list(v) if v is not None else list(GB_PACKAGES)


def card_number() -> str:
    from config import CARD_NUMBER
    return str(get('card_number', CARD_NUMBER))


def card_holder() -> str:
    from config import CARD_HOLDER
    return str(get('card_holder', CARD_HOLDER))


def bank_name() -> str:
    from config import BANK_NAME
    return str(get('bank_name', BANK_NAME))


def support_username() -> str:
    from config import SUPPORT_USERNAME
    return str(get('support_username', SUPPORT_USERNAME))


def bot_channel() -> str:
    from config import BOT_CHANNEL
    return str(get('bot_channel', BOT_CHANNEL))


def wallet_min_charge() -> int:
    from config import WALLET_MIN_CHARGE
    return int(get('wallet_min_charge', WALLET_MIN_CHARGE))


def referral_bonus_mb() -> int:
    from config import REFERRAL_BONUS_MB
    return int(get('referral_bonus_mb', REFERRAL_BONUS_MB))


def referral_bonus_toman() -> int:
    from config import REFERRAL_BONUS_TOMAN
    return int(get('referral_bonus_toman', REFERRAL_BONUS_TOMAN))


def referral_min_purchases() -> int:
    """حداقل تعداد خرید موفق زیرمجموعه برای دریافت جایزه."""
    return int(get('referral_min_purchases', 1))


def free_trial_enabled() -> bool:
    from config import FREE_TRIAL_ENABLED
    v = get('free_trial_enabled', FREE_TRIAL_ENABLED)
    return bool(v)


def free_trial_gb() -> int:
    from config import FREE_TRIAL_GB
    return int(get('free_trial_gb', FREE_TRIAL_GB))


def force_join_enabled() -> bool:
    from config import FORCE_JOIN_ENABLED
    v = get('force_join_enabled', FORCE_JOIN_ENABLED)
    return bool(v)


def force_join_channels() -> list:
    from config import FORCE_JOIN_CHANNELS
    v = get('force_join_channels', None)
    if v is None:
        return list(FORCE_JOIN_CHANNELS)
    return list(v) if isinstance(v, list) else []


def rate_limit_per_minute() -> int:
    from config import RATE_LIMIT_PER_MINUTE
    return int(get('rate_limit_per_minute', RATE_LIMIT_PER_MINUTE))


def captcha_enabled() -> bool:
    from config import CAPTCHA_ENABLED
    v = get('captcha_enabled', CAPTCHA_ENABLED)
    return bool(v)
