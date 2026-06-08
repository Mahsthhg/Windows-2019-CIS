from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import GB_PACKAGES, PRICE_PER_GB


# ─── Customer Reply Keyboards ─────────────────────────────────────────────────

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        ["🛒 خرید کانفیگ",   "📦 سفارشات من"],
        ["📚 راهنمای نصب",   "🎁 کد تخفیف"],
        ["💬 پشتیبانی",      "ℹ️ درباره ما"],
    ], resize_keyboard=True)


def cancel_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True)


# ─── Customer Inline Keyboards ────────────────────────────────────────────────

def gb_packages_kb() -> InlineKeyboardMarkup:
    rows = []
    for gb in GB_PACKAGES:
        price = gb * PRICE_PER_GB
        rows.append([InlineKeyboardButton(
            f"📦 {gb} گیگ   ←   {price:,} تومان",
            callback_data=f"buy_{gb}"
        )])
    rows.append([InlineKeyboardButton("✏️ حجم دلخواه", callback_data="buy_custom")])
    rows.append([InlineKeyboardButton("🔙 بازگشت",    callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def confirm_order_kb(gb: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و رفتن به پرداخت", callback_data=f"confirm_{gb}")],
        [InlineKeyboardButton("🔙 تغییر حجم",             callback_data="back_buy")],
        [InlineKeyboardButton("❌ انصراف",                 callback_data="cancel")],
    ])


def cancel_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="cancel")]])


def guide_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍎 آیفون — NPV Tunnel",   callback_data="guide_ios_npv")],
        [InlineKeyboardButton("🍎 آیفون — V2Box",        callback_data="guide_ios_v2box")],
        [InlineKeyboardButton("🤖 اندروید — V2RayNG",    callback_data="guide_android_v2rayng")],
        [InlineKeyboardButton("🤖 اندروید — Hiddify",    callback_data="guide_android_hiddify")],
        [InlineKeyboardButton("🪟 ویندوز — V2RayN",     callback_data="guide_windows")],
        [InlineKeyboardButton("🍏 مک — V2Box",           callback_data="guide_mac")],
        [InlineKeyboardButton("🔙 بازگشت",              callback_data="back_main")],
    ])


def order_detail_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 مشاهده کانفیگ", callback_data=f"viewconfig_{order_id}")],
    ])


# ─── Admin Inline Keyboards ───────────────────────────────────────────────────

def admin_new_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تایید سفارش",    callback_data=f"adm_approve_{order_id}"),
            InlineKeyboardButton("❌ رد سفارش",       callback_data=f"adm_reject_{order_id}"),
        ],
        [InlineKeyboardButton("👤 پروفایل مشتری",    callback_data=f"adm_profile_{order_id}")],
    ])


def admin_confirm_send_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 ارسال کانفیگ برای مشتری", callback_data=f"adm_sendcfg_{order_id}")],
        [InlineKeyboardButton("🔙 بازگشت",                  callback_data=f"adm_back_{order_id}")],
    ])


def admin_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        ["📊 آمار کلی",         "📋 سفارشات در انتظار"],
        ["📢 پیام همگانی",      "👥 مدیریت کاربران"],
        ["🎫 ایجاد کد تخفیف",  "💰 گزارش درآمد"],
        ["🎫 تیکت‌های باز",    "⚙️ راهنما"],
    ], resize_keyboard=True)


def admin_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="adm_cancel")]])
