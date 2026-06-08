import os
from dotenv import load_dotenv

load_dotenv()

# ─── Bot Tokens ───────────────────────────────────────────────────────────────
CUSTOMER_BOT_TOKEN = os.getenv("CUSTOMER_BOT_TOKEN", "YOUR_CUSTOMER_BOT_TOKEN")
ADMIN_BOT_TOKEN    = os.getenv("ADMIN_BOT_TOKEN",    "YOUR_ADMIN_BOT_TOKEN")

# ─── Admin Settings ───────────────────────────────────────────────────────────
ADMIN_CHAT_ID      = int(os.getenv("ADMIN_CHAT_ID", "0"))
SUPPORT_USERNAME   = os.getenv("SUPPORT_USERNAME", "@your_support")

# ─── Pricing ──────────────────────────────────────────────────────────────────
PRICE_PER_GB = 5_000      # Toman per GB
MIN_GB       = 20
MAX_GB       = 500

# ─── Payment ──────────────────────────────────────────────────────────────────
CARD_NUMBER = os.getenv("CARD_NUMBER", "5022291544985573")
CARD_HOLDER = os.getenv("CARD_HOLDER", "خلیلی")
BANK_NAME   = os.getenv("BANK_NAME",   "بانک ملت")

# ─── Predefined packages ──────────────────────────────────────────────────────
GB_PACKAGES = [20, 50, 100, 200, 300, 500]

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "vpn_sales.db")

# ─── Bot Info ─────────────────────────────────────────────────────────────────
BOT_NAME    = os.getenv("BOT_NAME",    "VPN Pro Shop")
BOT_CHANNEL = os.getenv("BOT_CHANNEL", "@your_channel")

# ─── Force Join ───────────────────────────────────────────────────────────────
# برای غیرفعال کردن: FORCE_JOIN_ENABLED=false
FORCE_JOIN_ENABLED  = os.getenv("FORCE_JOIN_ENABLED", "false").lower() == "true"
# چند کانال با کاما جدا کن: @chan1,@chan2
FORCE_JOIN_CHANNELS = [
    ch.strip()
    for ch in os.getenv("FORCE_JOIN_CHANNELS", "").split(",")
    if ch.strip()
]
