from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from config import GB_PACKAGES, PRICE_PER_GB, FREE_TRIAL_ENABLED


# ─── Customer Reply Keyboards ─────────────────────────────────────────────────

def main_menu_kb(show_trial=False) -> ReplyKeyboardMarkup:
    rows = [
        ["🛒 خرید کانفیگ",    "💰 کیف پول"],
        ["📦 سفارشات من",     "👤 پروفایل من"],
        ["📚 راهنمای نصب",    "👥 دعوت دوستان"],
        ["💬 پشتیبانی",       "ℹ️ درباره ما"],
    ]
    if show_trial and FREE_TRIAL_ENABLED:
        rows.insert(0, ["🎯 آزمایش رایگان"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


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


def confirm_order_kb(gb: int, wallet_ok=False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("✅ پرداخت با کارت",     callback_data=f"pay_card_{gb}")],
    ]
    if wallet_ok:
        rows.insert(0, [InlineKeyboardButton("💰 پرداخت از کیف پول (آنی)", callback_data=f"pay_wallet_{gb}")])
    rows += [
        [InlineKeyboardButton("🎁 کد تخفیف دارم",     callback_data="apply_discount")],
        [InlineKeyboardButton("🔙 تغییر حجم",          callback_data="back_buy")],
        [InlineKeyboardButton("❌ انصراف",              callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(rows)


def cancel_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="cancel")]])


def guide_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍎 آیفون — NPV Tunnel",  callback_data="guide_ios_npv")],
        [InlineKeyboardButton("🍎 آیفون — V2Box",       callback_data="guide_ios_v2box")],
        [InlineKeyboardButton("🤖 اندروید — V2RayNG",   callback_data="guide_android_v2rayng")],
        [InlineKeyboardButton("🤖 اندروید — Hiddify",   callback_data="guide_android_hiddify")],
        [InlineKeyboardButton("🪟 ویندوز — V2RayN",    callback_data="guide_windows")],
        [InlineKeyboardButton("🍏 مک — V2Box",          callback_data="guide_mac")],
        [InlineKeyboardButton("🔙 بازگشت",             callback_data="back_main")],
    ])


def rating_kb(order_id: int) -> InlineKeyboardMarkup:
    stars = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(s, callback_data=f"rate_{order_id}_{i+1}")
        for i, s in enumerate(stars)
    ]])


def wallet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 شارژ کیف پول",      callback_data="wallet_charge")],
        [InlineKeyboardButton("📋 تاریخچه تراکنش‌ها", callback_data="wallet_history")],
        [InlineKeyboardButton("🔙 بازگشت",            callback_data="back_main")],
    ])


def order_config_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 مشاهده کانفیگ",  callback_data=f"viewconfig_{order_id}")],
        [InlineKeyboardButton("🔗 لینک Sub",        callback_data=f"viewsub_{order_id}")],
        [InlineKeyboardButton("📊 مصرف (پنل)",     callback_data=f"usage_{order_id}")],
    ])


# ─── Force Join ───────────────────────────────────────────────────────────────

def join_required_kb(channels: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        label = ch if ch.startswith("@") else f"@{ch}"
        rows.append([InlineKeyboardButton(f"📢 عضویت در {label}",
                                          url=f"https://t.me/{label.lstrip('@')}")])
    rows.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])
    return InlineKeyboardMarkup(rows)


# ─── Admin Inline Keyboards ───────────────────────────────────────────────────

def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تایید",      callback_data=f"adm_approve_{order_id}"),
            InlineKeyboardButton("❌ رد",          callback_data=f"adm_reject_{order_id}"),
        ],
        [InlineKeyboardButton("👤 پروفایل مشتری", callback_data=f"adm_profile_{order_id}")],
        [InlineKeyboardButton("📝 یادداشت",       callback_data=f"adm_note_{order_id}")],
    ])


def admin_wallet_kb(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ تایید شارژ",  callback_data=f"adm_wapprove_{tx_id}"),
        InlineKeyboardButton("❌ رد",           callback_data=f"adm_wreject_{tx_id}"),
    ]])


def admin_templates_kb(templates: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"📋 {t['name']}",
                                  callback_data=f"adm_tpl_{t['id']}")] for t in templates]
    rows.append([InlineKeyboardButton("✏️ ارسال دستی", callback_data="adm_tpl_manual")])
    return InlineKeyboardMarkup(rows)


def admin_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        ["📊 آمار کلی",          "📋 سفارشات در انتظار"],
        ["💰 شارژ کیف‌پول‌ها",   "💬 تیکت‌های باز"],
        ["📋 قالب‌های کانفیگ",   "🔍 جستجو"],
        ["📢 پیام همگانی",        "👥 کاربران"],
        ["🎫 کد تخفیف",          "📤 خروجی CSV"],
        ["📈 گزارش درآمد",       "⚙️ راهنما"],
    ], resize_keyboard=True)


def admin_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="adm_cancel")]])
