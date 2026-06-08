from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


# ─── Customer Reply Keyboards ─────────────────────────────────────────────────

def main_menu_kb(show_trial=False) -> ReplyKeyboardMarkup:
    import settings_manager as sm
    rows = [
        ["🛒 خرید کانفیگ",    "💰 کیف پول"],
        ["📦 سفارشات من",     "👤 پروفایل من"],
        ["📚 راهنمای نصب",    "👥 دعوت دوستان"],
        ["💬 پشتیبانی",       "ℹ️ درباره ما"],
    ]
    if show_trial and sm.free_trial_enabled():
        rows.insert(0, ["🎯 آزمایش رایگان"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def cancel_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True)


# ─── Customer Inline Keyboards ────────────────────────────────────────────────

def gb_packages_kb() -> InlineKeyboardMarkup:
    import settings_manager as sm
    ppg = sm.price_per_gb()
    rows = []
    for gb in sm.gb_packages():
        price = gb * ppg
        rows.append([InlineKeyboardButton(
            f"📦 {gb} گیگ   ←   {price:,} تومان",
            callback_data=f"buy_{gb}"
        )])
    rows.append([InlineKeyboardButton("✏️ حجم دلخواه", callback_data="buy_custom")])
    rows.append([InlineKeyboardButton("🔙 بازگشت",    callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def confirm_order_kb(gb: int, wallet_ok=False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("✅ پرداخت با کارت", callback_data=f"pay_card_{gb}")],
    ]
    if wallet_ok:
        rows.insert(0, [InlineKeyboardButton(
            "💰 پرداخت از کیف پول (آنی)", callback_data=f"pay_wallet_{gb}"
        )])
    rows += [
        [InlineKeyboardButton("🎁 کد تخفیف دارم",  callback_data="apply_discount")],
        [InlineKeyboardButton("🔙 تغییر حجم",       callback_data="back_buy")],
        [InlineKeyboardButton("❌ انصراف",           callback_data="cancel")],
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
    ])


def captcha_kb(choices: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(str(c), callback_data=f"cap_{c}")
        for c in choices
    ]])


# ─── Force Join ───────────────────────────────────────────────────────────────

def join_required_kb(channels: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        label = ch if ch.startswith("@") else f"@{ch}"
        rows.append([InlineKeyboardButton(
            f"📢 عضویت در {label}",
            url=f"https://t.me/{label.lstrip('@')}"
        )])
    rows.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])
    return InlineKeyboardMarkup(rows)


# ─── Admin Reply Keyboard ─────────────────────────────────────────────────────

def admin_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        ["📊 آمار کلی",          "📋 سفارشات در انتظار"],
        ["💰 شارژ کیف‌پول‌ها",   "💬 تیکت‌های باز"],
        ["📋 قالب‌های کانفیگ",   "🔍 جستجو"],
        ["📢 پیام همگانی",        "👥 کاربران"],
        ["🎫 کد تخفیف",          "📤 خروجی CSV"],
        ["📈 گزارش درآمد",       "⚙️ تنظیمات"],
        ["📢 جوین اجباری",       "👥 زیرمجموعه"],
        ["🔄 ریستارت",           "⚙️ راهنما"],
    ], resize_keyboard=True)


def admin_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="adm_cancel")]])


# ─── Admin Order / Wallet Inline ──────────────────────────────────────────────

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
        InlineKeyboardButton("✅ تایید شارژ", callback_data=f"adm_wapprove_{tx_id}"),
        InlineKeyboardButton("❌ رد",          callback_data=f"adm_wreject_{tx_id}"),
    ]])


def admin_templates_kb(templates: list) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        f"📋 {t['name']}", callback_data=f"adm_tpl_{t['id']}"
    )] for t in templates]
    rows.append([InlineKeyboardButton("✏️ ارسال دستی", callback_data="adm_tpl_manual")])
    return InlineKeyboardMarkup(rows)


# ─── Admin Settings Panel ─────────────────────────────────────────────────────

def admin_settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 قیمت‌گذاری",       callback_data="cfg_menu_pricing")],
        [InlineKeyboardButton("💳 اطلاعات پرداخت",   callback_data="cfg_menu_payment")],
        [InlineKeyboardButton("🎁 سیستم معرفی",      callback_data="cfg_menu_referral")],
        [InlineKeyboardButton("🎯 آزمایش رایگان",    callback_data="cfg_menu_trial")],
        [InlineKeyboardButton("💼 کیف پول",          callback_data="cfg_menu_wallet")],
        [InlineKeyboardButton("🛡 کپچا و امنیت",     callback_data="cfg_menu_security")],
        [InlineKeyboardButton("📋 بسته‌های GB",      callback_data="cfg_menu_packages")],
        [InlineKeyboardButton("❌ بستن",              callback_data="cfg_close")],
    ])


def admin_settings_pricing_kb(ppg: int, mn: int, mx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💰 قیمت/گیگ: {ppg:,} تومان", callback_data="cfg_set_price_per_gb")],
        [InlineKeyboardButton(f"📉 حداقل گیگ: {mn}",          callback_data="cfg_set_min_gb")],
        [InlineKeyboardButton(f"📈 حداکثر گیگ: {mx}",         callback_data="cfg_set_max_gb")],
        [InlineKeyboardButton("🔙 بازگشت",                     callback_data="cfg_back")],
    ])


def admin_settings_payment_kb(cn: str, ch: str, bn: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 شماره کارت: {cn[-4:]}****", callback_data="cfg_set_card_number")],
        [InlineKeyboardButton(f"👤 نام: {ch}",                  callback_data="cfg_set_card_holder")],
        [InlineKeyboardButton(f"🏦 بانک: {bn}",                 callback_data="cfg_set_bank_name")],
        [InlineKeyboardButton("💬 پشتیبانی username",           callback_data="cfg_set_support_username")],
        [InlineKeyboardButton("🔙 بازگشت",                      callback_data="cfg_back")],
    ])


def admin_settings_referral_kb(bonus_mb: int, bonus_toman: int, min_p: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📡 جایزه MB: {bonus_mb} مگ",    callback_data="cfg_set_referral_bonus_mb")],
        [InlineKeyboardButton(f"💵 جایزه تومان: {bonus_toman:,}", callback_data="cfg_set_referral_bonus_toman")],
        [InlineKeyboardButton(f"🛒 حداقل خرید برای جایزه: {min_p}", callback_data="cfg_set_referral_min_purchases")],
        [InlineKeyboardButton("🔙 بازگشت",                       callback_data="cfg_back")],
    ])


def admin_settings_trial_kb(enabled: bool, gb: int) -> InlineKeyboardMarkup:
    status = "✅ فعال" if enabled else "❌ غیرفعال"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"وضعیت: {status}", callback_data="cfg_toggle_free_trial_enabled")],
        [InlineKeyboardButton(f"حجم آزمایشی: {gb} گیگ",         callback_data="cfg_set_free_trial_gb")],
        [InlineKeyboardButton("🔙 بازگشت",                       callback_data="cfg_back")],
    ])


def admin_settings_wallet_kb(min_c: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💵 حداقل شارژ: {min_c:,} تومان", callback_data="cfg_set_wallet_min_charge")],
        [InlineKeyboardButton("🔙 بازگشت",                        callback_data="cfg_back")],
    ])


def admin_settings_security_kb(captcha: bool, rate: int) -> InlineKeyboardMarkup:
    cs = "✅ فعال" if captcha else "❌ غیرفعال"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🛡 کپچا: {cs}", callback_data="cfg_toggle_captcha_enabled")],
        [InlineKeyboardButton(f"⚡ rate limit: {rate}/min",       callback_data="cfg_set_rate_limit_per_minute")],
        [InlineKeyboardButton("🔙 بازگشت",                        callback_data="cfg_back")],
    ])


# ─── Admin Force Join Panel ───────────────────────────────────────────────────

def admin_fj_kb(enabled: bool, channels: list) -> InlineKeyboardMarkup:
    status = "✅ فعال" if enabled else "❌ غیرفعال"
    rows = [
        [InlineKeyboardButton(f"وضعیت جوین اجباری: {status}", callback_data="fj_toggle")],
        [InlineKeyboardButton("➕ افزودن کانال", callback_data="fj_add")],
    ]
    for i, ch in enumerate(channels):
        rows.append([InlineKeyboardButton(
            f"🗑 حذف {ch}", callback_data=f"fj_del_{i}"
        )])
    rows.append([InlineKeyboardButton("❌ بستن", callback_data="fj_close")])
    return InlineKeyboardMarkup(rows)


# ─── Admin Referral Panel ─────────────────────────────────────────────────────

def admin_referral_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 لیدربورد زیرمجموعه",  callback_data="ref_leaderboard")],
        [InlineKeyboardButton("📊 آمار کلی معرفی‌ها",   callback_data="ref_stats")],
        [InlineKeyboardButton("❌ بستن",                  callback_data="ref_close")],
    ])
