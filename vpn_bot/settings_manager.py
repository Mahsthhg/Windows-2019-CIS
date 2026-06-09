"""تنظیمات پویا — ذخیره در DB، قابل تغییر از پنل ادمین بدون ریستارت."""
import json, sqlite3
from config import DB_PATH

def _db():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_settings():
    defaults = {
        "price_per_gb":           "5000",
        "min_gb":                 "20",
        "max_gb":                 "500",
        "gb_packages":            json.dumps([20, 50, 100, 200]),
        "card_number":            "6037-XXXX-XXXX-XXXX",
        "card_holder":            "نام صاحب کارت",
        "bank_name":              "بانک ملت",
        "support_username":       "@support",
        "bot_channel":            "@channel",
        "wallet_min_charge":      "50000",
        "referral_bonus_mb":      "1024",
        "referral_bonus_toman":   "0",
        "referral_min_purchases": "1",
        "free_trial_enabled":     "false",
        "free_trial_gb":          "1",
        "captcha_enabled":        "true",
        "force_join_enabled":     "false",
        "force_join_channels":    json.dumps([]),
        "rate_limit_per_minute":  "20",
        "points_per_10k":         "1",
        "points_to_toman":        "100",
        "server_selection":       "auto",
        "payment_timeout_min":    "15",
        "daily_report_enabled":   "true",
        "multi_card_enabled":     "false",
        "card_numbers":           json.dumps([]),
    }
    c = _db()
    try:
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO bot_settings(key,value) VALUES(?,?)", (k, v))
        c.commit()
    finally:
        c.close()

def get(key, default=None):
    c = _db()
    try:
        r = c.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
        return r[0] if r else default
    finally:
        c.close()

def set_val(key, value):
    v = json.dumps(value) if isinstance(value, (list, dict, bool)) else str(value)
    c = _db()
    try:
        c.execute("INSERT OR REPLACE INTO bot_settings(key,value,updated_at) VALUES(?,?,datetime('now','localtime'))", (key, v))
        c.commit()
    finally:
        c.close()

def _int(key, default=0) -> int:
    try: return int(get(key, default))
    except: return default

def _bool(key, default=False) -> bool:
    v = get(key, str(default)).lower()
    return v in ("true", "1", "yes")

def _list(key, default=None) -> list:
    try: return json.loads(get(key, "[]"))
    except: return default or []

# ─── Typed accessors ──────────────────────────────────────────────────────────

def price_per_gb() -> int:       return _int("price_per_gb", 5000)
def min_gb() -> int:             return _int("min_gb", 20)
def max_gb() -> int:             return _int("max_gb", 500)
def gb_packages() -> list:       return _list("gb_packages", [20, 50, 100, 200])
def card_number() -> str:        return get("card_number", "—")
def card_holder() -> str:        return get("card_holder", "—")
def bank_name() -> str:          return get("bank_name", "—")
def support_username() -> str:   return get("support_username", "@support")
def bot_channel() -> str:        return get("bot_channel", "—")
def wallet_min_charge() -> int:  return _int("wallet_min_charge", 50000)
def referral_bonus_mb() -> int:  return _int("referral_bonus_mb", 0)
def referral_bonus_toman() -> int: return _int("referral_bonus_toman", 0)
def referral_min_purchases() -> int: return _int("referral_min_purchases", 1)
def free_trial_enabled() -> bool: return _bool("free_trial_enabled", False)
def free_trial_gb() -> int:      return _int("free_trial_gb", 1)
def captcha_enabled() -> bool:   return _bool("captcha_enabled", True)
def force_join_enabled() -> bool: return _bool("force_join_enabled", False)
def force_join_channels() -> list: return _list("force_join_channels", [])
def rate_limit_per_minute() -> int: return _int("rate_limit_per_minute", 20)
def points_per_10k() -> int:     return _int("points_per_10k", 1)
def points_to_toman() -> int:    return _int("points_to_toman", 100)
def server_selection() -> str:   return get("server_selection", "auto")
def payment_timeout_min() -> int: return _int("payment_timeout_min", 15)
def daily_report_enabled() -> bool: return _bool("daily_report_enabled", True)
def multi_card_enabled() -> bool: return _bool("multi_card_enabled", False)
def card_numbers() -> list:      return _list("card_numbers", [])

def get_payment_card() -> dict:
    """Returns active card info, rotating if multi-card enabled."""
    import random
    if multi_card_enabled():
        cards = card_numbers()
        if cards:
            card = random.choice(cards)
            return {"number": card.get("number", card_number()),
                    "holder": card.get("holder", card_holder()),
                    "bank":   card.get("bank", bank_name())}
    return {"number": card_number(), "holder": card_holder(), "bank": bank_name()}
