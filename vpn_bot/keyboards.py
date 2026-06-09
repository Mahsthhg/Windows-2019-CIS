from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


# ─── Customer Reply Keyboards ─────────────────────────────────────────────────

def main_menu_kb(show_trial=False, show_lottery=False) -> ReplyKeyboardMarkup:
    import settings_manager as sm
    rows = [
        ["🛒 خرید کانفیگ",    "💰 کیف پول"],
        ["📦 سفارشات من",     "👤 پروفایل من"],
        ["🌐 وضعیت سرورها",  "⭐ امتیازات من"],
        ["📚 راهنمای نصب",    "👥 دعوت دوستان"],
        ["💬 پشتیبانی",       "ℹ️ درباره ما"],
    ]
    if show_lottery:
        rows.insert(0, ["🎰 قرعه‌کشی"])
    if show_trial and sm.free_trial_enabled():
        rows.insert(0, ["🎯 آزمایش رایگان"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def cancel_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True)


# ─── Customer Inline Keyboards ────────────────────────────────────────────────

def gb_packages_kb(flash_pct: int = 0) -> InlineKeyboardMarkup:
    import settings_manager as sm
    ppg = sm.price_per_gb()
    rows = []
    for gb in sm.gb_packages():
        base = gb * ppg
        if flash_pct:
            discounted = int(base * (100 - flash_pct) / 100)
            rows.append([InlineKeyboardButton(
                f"📦 {gb} گیگ  〈 ~~{base:,}~~ ← {discounted:,} تومان 🔥{flash_pct}٪〉",
                callback_data=f"buy_{gb}"
            )])
        else:
            rows.append([InlineKeyboardButton(
                f"📦 {gb} گیگ   ←   {base:,} تومان",
                callback_data=f"buy_{gb}"
            )])
    rows.append([InlineKeyboardButton("✏️ حجم دلخواه", callback_data="buy_custom")])
    rows.append([InlineKeyboardButton("🔙 بازگشت",    callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def confirm_order_kb(gb: int, wallet_ok=False, points_ok=False,
                     zarinpal_ok=False, usdt_ok=False) -> InlineKeyboardMarkup:
    import settings_manager as sm
    rows = []
    if wallet_ok:
        rows.append([InlineKeyboardButton("💰 پرداخت از کیف پول (آنی)", callback_data=f"pay_wallet_{gb}")])
    if points_ok:
        rows.append([InlineKeyboardButton("⭐ پرداخت با امتیاز", callback_data=f"pay_points_{gb}")])
    if zarinpal_ok:
        rows.append([InlineKeyboardButton("💳 پرداخت آنلاین — زرین‌پال", callback_data=f"pay_zp_{gb}")])
    if usdt_ok:
        rows.append([InlineKeyboardButton("🔷 پرداخت با USDT (TRC20)", callback_data=f"pay_usdt_{gb}")])
    rows.append([InlineKeyboardButton("💵 پرداخت با کارت (دستی)", callback_data=f"pay_card_{gb}")])
    rows += [
        [InlineKeyboardButton("🎁 کد تخفیف دارم",  callback_data="apply_discount")],
        [InlineKeyboardButton("🔙 تغییر حجم",       callback_data="back_buy")],
        [InlineKeyboardButton("❌ انصراف",           callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(rows)


def zarinpal_verify_kb(gb: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ پرداخت کردم، تایید کن", callback_data=f"zp_verify_{gb}")],
        [InlineKeyboardButton("❌ انصراف از پرداخت",      callback_data="zp_cancel")],
    ])


def usdt_payment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ارسال کردم، بررسی کن", callback_data="usdt_check")],
        [InlineKeyboardButton("❌ انصراف از پرداخت",     callback_data="usdt_cancel")],
    ])


def server_select_kb(servers: list) -> InlineKeyboardMarkup:
    rows = []
    for s in servers:
        load_bar = _load_bar(s.get('load_pct', 0))
        flag = s.get('flag', '🌐')
        rows.append([InlineKeyboardButton(
            f"{flag} {s['name']}  {load_bar}",
            callback_data=f"srv_{s['id']}"
        )])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_buy")])
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


def points_kb(points: int, rate: int) -> InlineKeyboardMarkup:
    toman = points * rate
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"💸 تبدیل {points} امتیاز به {toman:,} تومان",
            callback_data="redeem_points"
        )],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
    ])


def order_config_kb(order_id: int, auto_renew: bool = False) -> InlineKeyboardMarkup:
    renew_label = "🔄 تمدید خودکار: ✅" if auto_renew else "🔄 تمدید خودکار: ❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 مشاهده کانفیگ",    callback_data=f"viewconfig_{order_id}")],
        [InlineKeyboardButton("🔗 لینک Sub",          callback_data=f"viewsub_{order_id}")],
        [InlineKeyboardButton("🛒 تمدید سرویس",       callback_data=f"renew_{order_id}")],
        [InlineKeyboardButton(renew_label,             callback_data=f"autorenew_{order_id}")],
    ])


def captcha_kb(choices: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(str(c), callback_data=f"cap_{c}")
        for c in choices
    ]])


def lottery_kb(lottery_id: int, entered: bool) -> InlineKeyboardMarkup:
    if entered:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ شما ثبت‌نام کرده‌اید", callback_data="noop")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎟 شرکت در قرعه‌کشی", callback_data=f"enter_lottery_{lottery_id}")],
        [InlineKeyboardButton("🔙 بازگشت",            callback_data="back_main")],
    ])


def servers_status_kb(servers: list) -> InlineKeyboardMarkup:
    rows = []
    for s in servers:
        load = s.get('load_pct', 0)
        bar  = _load_bar(load)
        flag = s.get('flag', '🌐')
        status = "🟢" if s.get('is_active') else "🔴"
        rows.append([InlineKeyboardButton(
            f"{status} {flag} {s['name']}  {bar}  ({load}٪)",
            callback_data="noop"
        )])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


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
        ["🌐 سرورها",            "👨‍💼 ریسلرها"],
        ["🔥 فلش سیل",           "🎰 قرعه‌کشی"],
        ["📜 لاگ ادمین",          "📢 جوین اجباری"],
        ["👥 زیرمجموعه",         "🔄 ریستارت"],
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
        [InlineKeyboardButton("⭐ سیستم امتیاز",     callback_data="cfg_menu_points")],
        [InlineKeyboardButton("💳 زرین‌پال",            callback_data="cfg_menu_zarinpal")],
        [InlineKeyboardButton("🔷 USDT (کریپتو)",       callback_data="cfg_menu_usdt")],
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
        [InlineKeyboardButton(f"💳 شماره کارت: ...{cn[-4:]}", callback_data="cfg_set_card_number")],
        [InlineKeyboardButton(f"👤 نام: {ch}",                  callback_data="cfg_set_card_holder")],
        [InlineKeyboardButton(f"🏦 بانک: {bn}",                 callback_data="cfg_set_bank_name")],
        [InlineKeyboardButton("💬 پشتیبانی username",           callback_data="cfg_set_support_username")],
        [InlineKeyboardButton("💳 چند کارت",                    callback_data="cfg_menu_multicards")],
        [InlineKeyboardButton("🔙 بازگشت",                      callback_data="cfg_back")],
    ])


def admin_settings_referral_kb(bonus_mb: int, bonus_toman: int, min_p: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📡 جایزه MB: {bonus_mb} مگ",    callback_data="cfg_set_referral_bonus_mb")],
        [InlineKeyboardButton(f"💵 جایزه تومان: {bonus_toman:,}", callback_data="cfg_set_referral_bonus_toman")],
        [InlineKeyboardButton(f"🛒 حداقل خرید: {min_p}",        callback_data="cfg_set_referral_min_purchases")],
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


def admin_settings_points_kb(per10k: int, to_toman: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐ امتیاز به ازای هر ۱۰ هزار: {per10k}", callback_data="cfg_set_points_per_10k")],
        [InlineKeyboardButton(f"💸 ارزش هر امتیاز: {to_toman} تومان",    callback_data="cfg_set_points_to_toman")],
        [InlineKeyboardButton("🔙 بازگشت",                                callback_data="cfg_back")],
    ])


def admin_settings_zarinpal_kb(enabled: bool, merchant_id: str, sandbox: bool) -> InlineKeyboardMarkup:
    status = "✅ فعال" if enabled else "❌ غیرفعال"
    sb = "sandbox ✅" if sandbox else "live 🔴"
    mid = f"...{merchant_id[-8:]}" if len(merchant_id) > 8 else (merchant_id or "تنظیم نشده")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"وضعیت: {status}", callback_data="cfg_toggle_zarinpal_enabled")],
        [InlineKeyboardButton(f"🔑 Merchant ID: {mid}", callback_data="cfg_set_zarinpal_merchant_id")],
        [InlineKeyboardButton(f"حالت: {sb}", callback_data="cfg_toggle_zarinpal_sandbox")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="cfg_back")],
    ])


def admin_settings_usdt_kb(enabled: bool, address: str, rate: int) -> InlineKeyboardMarkup:
    status = "✅ فعال" if enabled else "❌ غیرفعال"
    addr = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else (address or "تنظیم نشده")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"وضعیت: {status}", callback_data="cfg_toggle_usdt_enabled")],
        [InlineKeyboardButton(f"📬 آدرس: {addr}", callback_data="cfg_set_usdt_address")],
        [InlineKeyboardButton(f"💱 نرخ: 1 USDT = {rate:,} تومان", callback_data="cfg_set_usdt_rate")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="cfg_back")],
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


# ─── Admin Servers Panel ──────────────────────────────────────────────────────

def admin_servers_kb(servers: list) -> InlineKeyboardMarkup:
    rows = []
    for s in servers:
        status = "🟢" if s.get('is_active') else "🔴"
        default_mark = " ★" if s.get('is_default') else ""
        rows.append([InlineKeyboardButton(
            f"{status} {s.get('flag','🌐')} {s['name']}{default_mark}",
            callback_data=f"adm_srv_{s['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ افزودن سرور",  callback_data="adm_srv_add")])
    rows.append([InlineKeyboardButton("❌ بستن",          callback_data="adm_srv_close")])
    return InlineKeyboardMarkup(rows)


def admin_server_detail_kb(server_id: int, is_active: bool, is_default: bool) -> InlineKeyboardMarkup:
    toggle_label = "🔴 غیرفعال کن" if is_active else "🟢 فعال کن"
    default_label = "★ پیش‌فرض (فعال)" if is_default else "☆ تنظیم به عنوان پیش‌فرض"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label,  callback_data=f"adm_srv_toggle_{server_id}")],
        [InlineKeyboardButton(default_label, callback_data=f"adm_srv_default_{server_id}")],
        [InlineKeyboardButton("✏️ ویرایش نام",  callback_data=f"adm_srv_rename_{server_id}")],
        [InlineKeyboardButton("📊 آپدیت لود",   callback_data=f"adm_srv_load_{server_id}")],
        [InlineKeyboardButton("🗑 حذف سرور",    callback_data=f"adm_srv_del_{server_id}")],
        [InlineKeyboardButton("🔙 بازگشت",      callback_data="adm_srv_back")],
    ])


# ─── Admin Resellers Panel ────────────────────────────────────────────────────

def admin_resellers_kb(resellers: list) -> InlineKeyboardMarkup:
    rows = []
    for r in resellers:
        status = "🟢" if r.get('is_active') else "🔴"
        rows.append([InlineKeyboardButton(
            f"{status} {r.get('full_name') or r.get('username') or r['user_id']}  |  {r.get('balance', 0):,} تومان",
            callback_data=f"adm_res_{r['user_id']}"
        )])
    rows.append([InlineKeyboardButton("➕ ریسلر جدید",  callback_data="adm_res_add")])
    rows.append([InlineKeyboardButton("❌ بستن",          callback_data="adm_res_close")])
    return InlineKeyboardMarkup(rows)


def admin_reseller_detail_kb(user_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_label = "🔴 غیرفعال کن" if is_active else "🟢 فعال کن"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 افزایش اعتبار",    callback_data=f"adm_res_credit_{user_id}")],
        [InlineKeyboardButton("📊 گزارش فروش",       callback_data=f"adm_res_report_{user_id}")],
        [InlineKeyboardButton(toggle_label,           callback_data=f"adm_res_toggle_{user_id}")],
        [InlineKeyboardButton("🗑 حذف ریسلر",        callback_data=f"adm_res_del_{user_id}")],
        [InlineKeyboardButton("🔙 بازگشت",           callback_data="adm_res_back")],
    ])


# ─── Admin Flash Sale Panel ───────────────────────────────────────────────────

def admin_flash_kb(sales: list) -> InlineKeyboardMarkup:
    rows = []
    for s in sales:
        status = "🟢" if s.get('is_active') else ("⏳" if not s.get('notified') else "✅")
        rows.append([InlineKeyboardButton(
            f"{status} {s['name']} — {s['discount_pct']}٪",
            callback_data=f"adm_flash_{s['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ فلش سیل جدید", callback_data="adm_flash_add")])
    rows.append([InlineKeyboardButton("❌ بستن",           callback_data="adm_flash_close")])
    return InlineKeyboardMarkup(rows)


def admin_flash_detail_kb(sale_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle = "🔴 پایان دادن" if is_active else "🟢 فعال کردن دستی"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle,                    callback_data=f"adm_flash_toggle_{sale_id}")],
        [InlineKeyboardButton("📢 برودکست دستی",         callback_data=f"adm_flash_broadcast_{sale_id}")],
        [InlineKeyboardButton("🗑 حذف",                  callback_data=f"adm_flash_del_{sale_id}")],
        [InlineKeyboardButton("🔙 بازگشت",               callback_data="adm_flash_back")],
    ])


# ─── Admin Lottery Panel ──────────────────────────────────────────────────────

def admin_lottery_kb(lotteries: list) -> InlineKeyboardMarkup:
    rows = []
    for lt in lotteries:
        status = "🟢" if lt.get('status') == 'active' else "✅"
        rows.append([InlineKeyboardButton(
            f"{status} {lt['name']}",
            callback_data=f"adm_lot_{lt['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ قرعه‌کشی جدید", callback_data="adm_lot_add")])
    rows.append([InlineKeyboardButton("❌ بستن",            callback_data="adm_lot_close")])
    return InlineKeyboardMarkup(rows)


def admin_lottery_detail_kb(lot_id: int, is_active: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 لیست شرکت‌کنندگان", callback_data=f"adm_lot_entries_{lot_id}")],
        [InlineKeyboardButton("🎰 قرعه‌کشی دستی",    callback_data=f"adm_lot_draw_{lot_id}")],
        [InlineKeyboardButton("🗑 لغو و بستن",         callback_data=f"adm_lot_cancel_{lot_id}")],
        [InlineKeyboardButton("🔙 بازگشت",             callback_data="adm_lot_back")],
    ])


# ─── Admin Logs Panel ─────────────────────────────────────────────────────────

def admin_logs_kb(page: int, has_next: bool) -> InlineKeyboardMarkup:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"adm_log_page_{page-1}"))
    if has_next:
        row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"adm_log_page_{page+1}"))
    rows = [row] if row else []
    rows.append([InlineKeyboardButton("❌ بستن", callback_data="adm_log_close")])
    return InlineKeyboardMarkup(rows)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_bar(pct: int) -> str:
    filled = round(pct / 10)
    return "█" * filled + "░" * (10 - filled)
