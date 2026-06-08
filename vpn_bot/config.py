import os
from dotenv import load_dotenv

load_dotenv()

# ─── Bot Tokens ───────────────────────────────────────────────────────────────
CUSTOMER_BOT_TOKEN = os.getenv("CUSTOMER_BOT_TOKEN", "YOUR_CUSTOMER_BOT_TOKEN")
ADMIN_BOT_TOKEN    = os.getenv("ADMIN_BOT_TOKEN",    "YOUR_ADMIN_BOT_TOKEN")

# ─── Admin Settings ───────────────────────────────────────────────────────────
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
# چند ادمین با کاما: 123,456,789
ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", os.getenv("ADMIN_CHAT_ID", "0")).split(",")
    if x.strip()
]
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@your_support")

# ─── Pricing ──────────────────────────────────────────────────────────────────
PRICE_PER_GB = 5_000
MIN_GB       = 20
MAX_GB       = 500

# ─── Payment ──────────────────────────────────────────────────────────────────
CARD_NUMBER = os.getenv("CARD_NUMBER", "5022291544985573")
CARD_HOLDER = os.getenv("CARD_HOLDER", "خلیلی")
BANK_NAME   = os.getenv("BANK_NAME",   "بانک ملت")

# ─── Predefined packages ──────────────────────────────────────────────────────
GB_PACKAGES = [20, 50, 100, 200, 300, 500]

# ─── VIP Levels: label → (min_spent_toman, discount_pct) ─────────────────────
VIP_LEVELS = [
    ("💎 دیاموند", 5_000_000, 20),
    ("🥇 طلایی",   1_000_000, 15),
    ("🥈 نقره‌ای",   500_000, 10),
    ("🥉 برنزی",    100_000,  5),
    ("👤 عادی",           0,  0),
]

# ─── Referral ─────────────────────────────────────────────────────────────────
# جایزه معرفی — فقط یکی از دو حالت فعال باشد:
REFERRAL_BONUS_MB    = int(float(os.getenv("REFERRAL_BONUS_MB",   "100")))  # مگابایت
REFERRAL_BONUS_TOMAN = int(float(os.getenv("REFERRAL_BONUS_TOMAN", "0")))   # تومان کیف‌پول

# ─── Free Trial ───────────────────────────────────────────────────────────────
FREE_TRIAL_ENABLED = os.getenv("FREE_TRIAL_ENABLED", "false").lower() == "true"
FREE_TRIAL_GB      = int(os.getenv("FREE_TRIAL_GB", "5"))

# ─── Wallet ───────────────────────────────────────────────────────────────────
WALLET_MIN_CHARGE = int(os.getenv("WALLET_MIN_CHARGE", "50_000"))

# ─── Marzban Panel ────────────────────────────────────────────────────────────
PANEL_ENABLED     = os.getenv("PANEL_ENABLED", "false").lower() == "true"
PANEL_URL         = os.getenv("PANEL_URL", "").rstrip("/")
PANEL_USERNAME    = os.getenv("PANEL_USERNAME", "admin")
PANEL_PASSWORD    = os.getenv("PANEL_PASSWORD", "")
PANEL_INBOUND_TAG = os.getenv("PANEL_INBOUND_TAG", "vless-tcp-reality")
PANEL_DEFAULT_DAYS = int(os.getenv("PANEL_DEFAULT_DAYS", "30"))

# ─── Scheduler ────────────────────────────────────────────────────────────────
DAILY_REPORT_HOUR   = int(os.getenv("DAILY_REPORT_HOUR",   "8"))
EXPIRY_WARNING_DAYS = int(os.getenv("EXPIRY_WARNING_DAYS", "3"))

# ─── Force Join ───────────────────────────────────────────────────────────────
FORCE_JOIN_ENABLED  = os.getenv("FORCE_JOIN_ENABLED", "false").lower() == "true"
FORCE_JOIN_CHANNELS = [
    ch.strip()
    for ch in os.getenv("FORCE_JOIN_CHANNELS", "").split(",")
    if ch.strip()
]

# ─── Anti-spam ────────────────────────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "15"))

# ─── Database / Bot Info ──────────────────────────────────────────────────────
DB_PATH     = os.getenv("DB_PATH",     "vpn_sales.db")
BOT_NAME    = os.getenv("BOT_NAME",    "VPN Pro Shop")
BOT_CHANNEL = os.getenv("BOT_CHANNEL", "@your_channel")
