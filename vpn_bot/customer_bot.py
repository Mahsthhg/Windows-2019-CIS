"""ربات مشتری v3 — فلش سیل، قرعه‌کشی، امتیاز، سرور، تمدید خودکار."""
import logging
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes,
)
from config import BOT_NAME, ADMIN_IDS, PANEL_ENABLED
import settings_manager as sm
from database import (
    upsert_user, get_user, get_user_orders, get_order,
    create_order, create_ticket, get_discount_code, use_discount_code,
    get_wallet, deduct_wallet, create_wallet_charge,
    get_wallet_history, get_user_by_ref_code, mark_trial_used,
    rate_order, get_bonus_mb, deduct_bonus_mb,
    get_active_flash_sale, get_active_lottery, get_lottery_entries,
    enter_lottery, get_servers, add_loyalty_points,
    redeem_points_to_wallet,
)
from keyboards import (
    main_menu_kb, cancel_reply_kb, cancel_inline_kb,
    gb_packages_kb, confirm_order_kb, guide_kb,
    wallet_kb, rating_kb, join_required_kb, order_config_kb,
    captcha_kb, points_kb, lottery_kb, servers_status_kb,
    server_select_kb,
)
from guides import GUIDES
from utils import (
    get_vip, next_vip, vip_progress_bar, fmt, fmt_gb, fmt_dt,
    is_rate_limited, STATUS_EMOJI, STATUS_LABEL, STAR_MAP, TX_EMOJI, h,
)
from captcha import generate_captcha

logger = logging.getLogger(__name__)

# ─── States ───────────────────────────────────────────────────────────────────
(
    MAIN_MENU,
    SELECT_GB, CUSTOM_GB_INPUT, CONFIRM_ORDER,
    DISCOUNT_INPUT, UPLOAD_RECEIPT,
    WALLET_AMOUNT, WALLET_RECEIPT,
    SUPPORT_MESSAGE,
    CAPTCHA,
) = range(10)


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _unjoined(bot, user_id: int) -> list:
    if not sm.force_join_enabled():
        return []
    channels = sm.force_join_channels()
    out = []
    for ch in channels:
        try:
            m = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in ("left", "kicked", "banned"):
                out.append(ch)
        except Exception:
            out.append(ch)
    return out


async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    missing = await _unjoined(context.bot, uid)
    if not missing:
        return True
    channels_text = "\n".join(f"• {h(c)}" for c in missing)
    txt = (
        f"⛔ <b>برای استفاده از ربات عضو کانال زیر شوید:</b>\n\n"
        f"{channels_text}\n\n"
        "بعد از عضویت روی ✅ عضو شدم بزنید."
    )
    kb = join_required_kb(missing)
    if update.callback_query:
        await update.callback_query.answer("ابتدا عضو کانال شوید!", show_alert=True)
        await update.callback_query.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
    else:
        await update.effective_message.reply_text(txt, parse_mode="HTML", reply_markup=kb)
    return False


def _menu_kb_for(user_id: int):
    db_user = get_user(user_id)
    show_trial = sm.free_trial_enabled() and db_user and not db_user.get("free_trial_used")
    lottery = get_active_lottery()
    show_lottery = lottery is not None
    return main_menu_kb(show_trial=show_trial, show_lottery=show_lottery)


# ─── CAPTCHA ──────────────────────────────────────────────────────────────────

async def _send_captcha(message, context: ContextTypes.DEFAULT_TYPE):
    img, answer, choices = generate_captcha()
    context.user_data["captcha_answer"] = answer
    context.user_data["captcha_attempts"] = 3
    kb = captcha_kb(choices)
    caption = "🛡 <b>تایید امنیتی</b>\n\nجواب درست را انتخاب کنید:"
    if img:
        await message.reply_photo(photo=img, caption=caption, parse_mode="HTML", reply_markup=kb)
    else:
        await message.reply_text(caption, parse_mode="HTML", reply_markup=kb)


async def handle_captcha_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    if not data.startswith("cap_"):
        await query.answer()
        return CAPTCHA

    try:
        chosen = int(data.split("_")[1])
    except (ValueError, IndexError):
        await query.answer()
        return CAPTCHA

    correct = context.user_data.get("captcha_answer")
    if chosen == correct:
        await query.answer("✅ عالی! کپچا تایید شد.")
        try:
            if query.message.photo:
                await query.edit_message_caption(
                    caption="✅ <b>تایید شد!</b> خوش آمدید.", parse_mode="HTML"
                )
            else:
                await query.edit_message_text("✅ <b>تایید شد!</b> خوش آمدید.", parse_mode="HTML")
        except Exception:
            pass
        context.user_data.pop("captcha_answer", None)
        context.user_data.pop("captcha_attempts", None)
        user = update.effective_user
        db_user = get_user(user.id)
        vip_label, _ = get_vip(db_user.get("total_spent", 0) if db_user else 0)
        await query.message.reply_text(
            f"👋 سلام <b>{h(user.first_name)}</b>!\n\n"
            f"🌐 <b>{h(BOT_NAME)}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ کانفیگ VLESS سریع و پایدار\n"
            f"💰 {fmt(sm.price_per_gb())} / گیگابایت\n"
            f"📦 {sm.min_gb()} تا {sm.max_gb()} گیگابایت\n"
            f"💎 سطح شما: {h(vip_label)}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "از منوی زیر انتخاب کنید:",
            parse_mode="HTML",
            reply_markup=_menu_kb_for(user.id)
        )
        return MAIN_MENU

    attempts = context.user_data.get("captcha_attempts", 3) - 1
    context.user_data["captcha_attempts"] = attempts
    if attempts <= 0:
        await query.answer("❌ تلاش‌های شما تمام شد! دوباره /start بزنید.", show_alert=True)
        return ConversationHandler.END
    await query.answer(f"❌ غلط! {attempts} تلاش دیگر دارید.", show_alert=True)
    img, answer, choices = generate_captcha()
    context.user_data["captcha_answer"] = answer
    kb = captcha_kb(choices)
    caption = f"🛡 <b>تایید امنیتی</b> — {attempts} تلاش باقی\n\nجواب درست را انتخاب کنید:"
    try:
        if query.message.photo and img:
            await query.edit_message_media(
                media=__import__("telegram").InputMediaPhoto(
                    media=img, caption=caption, parse_mode="HTML"
                ),
                reply_markup=kb
            )
        else:
            await query.edit_message_text(caption, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await query.message.reply_text(caption, parse_mode="HTML", reply_markup=kb)
    return CAPTCHA


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user

    referred_by = None
    if context.args:
        ref_user = get_user_by_ref_code(context.args[0])
        if ref_user and ref_user["user_id"] != user.id:
            referred_by = ref_user["user_id"]

    is_new = upsert_user(user.id, user.username, user.full_name, referred_by)
    context.user_data.clear()

    db_user = get_user(user.id)
    if db_user and db_user.get("is_blocked"):
        await update.message.reply_text("⛔ حساب شما مسدود شده است.")
        return ConversationHandler.END

    if not await check_join(update, context):
        return MAIN_MENU

    if is_new and sm.captcha_enabled():
        await _send_captcha(update.message, context)
        return CAPTCHA

    vip_label, _ = get_vip(db_user.get("total_spent", 0) if db_user else 0)
    welcome = "🎉 <b>خوش آمدید!</b>" if is_new else f"👋 سلام <b>{h(user.first_name)}</b>!"
    if referred_by:
        welcome += "\n🎁 از طریق دعوت دوست وارد شدید!"

    flash = get_active_flash_sale()
    flash_line = f"\n🔥 <b>فلش سیل فعال: {flash['discount_pct']}٪ تخفیف!</b>" if flash else ""

    await update.message.reply_text(
        f"{welcome}\n\n"
        f"🌐 <b>{h(BOT_NAME)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ کانفیگ VLESS سریع و پایدار\n"
        f"💰 {fmt(sm.price_per_gb())} / گیگابایت\n"
        f"📦 {sm.min_gb()} تا {sm.max_gb()} گیگابایت\n"
        f"💎 سطح شما: {h(vip_label)}"
        f"{flash_line}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "از منوی زیر انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=_menu_kb_for(user.id)
    )
    return MAIN_MENU


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ لغو شد.", reply_markup=_menu_kb_for(update.effective_user.id))
    return MAIN_MENU


# ─── Main Menu ────────────────────────────────────────────────────────────────

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user = update.effective_user

    if text == "❌ انصراف":
        context.user_data.clear()
        await update.message.reply_text("منوی اصلی:", reply_markup=_menu_kb_for(user.id))
        return MAIN_MENU

    db_user = get_user(user.id)
    if db_user and db_user.get("is_blocked"):
        await update.message.reply_text("⛔ حساب شما مسدود شده است.")
        return ConversationHandler.END

    if is_rate_limited(user.id):
        await update.message.reply_text("⚠️ خیلی سریع پیام می‌فرستید. کمی صبر کنید.")
        return MAIN_MENU

    if not await check_join(update, context):
        return MAIN_MENU

    if text == "🛒 خرید کانفیگ":
        return await _start_buy_flow(update, context, db_user)

    if text == "💰 کیف پول":
        return await show_wallet(update, context)

    if text == "📦 سفارشات من":
        await show_orders(update, context)
        return MAIN_MENU

    if text == "👤 پروفایل من":
        await show_profile(update, context)
        return MAIN_MENU

    if text == "🌐 وضعیت سرورها":
        await show_servers_status(update, context)
        return MAIN_MENU

    if text == "⭐ امتیازات من":
        await show_points(update, context, db_user)
        return MAIN_MENU

    if text == "📚 راهنمای نصب":
        await update.message.reply_text("📚 پلتفرم خود را انتخاب کنید:", reply_markup=guide_kb())
        return MAIN_MENU

    if text == "👥 دعوت دوستان":
        await show_referral(update, context)
        return MAIN_MENU

    if text == "🎯 آزمایش رایگان":
        return await request_trial(update, context)

    if text == "🎰 قرعه‌کشی":
        await show_lottery(update, context)
        return MAIN_MENU

    if text == "💬 پشتیبانی":
        await update.message.reply_text(
            "💬 <b>پشتیبانی</b>\n\nپیام خود را بنویسید:\n(/cancel برای لغو)",
            parse_mode="HTML", reply_markup=cancel_reply_kb()
        )
        return SUPPORT_MESSAGE

    if text == "ℹ️ درباره ما":
        await show_about(update, context)
        return MAIN_MENU

    # /config_X shortcut
    if text and text.startswith("/config_"):
        try:
            order_id = int(text.split("_")[1])
            order = get_order(order_id)
            if order and order["user_id"] == user.id and order["status"] == "approved":
                await update.message.reply_text(
                    f"📋 <b>کانفیگ سفارش #{order_id}</b>\n\n<code>{h(order['config'])}</code>",
                    parse_mode="HTML",
                    reply_markup=order_config_kb(order_id, order.get("auto_renew", 0))
                )
        except Exception:
            pass
        return MAIN_MENU

    return MAIN_MENU


async def _start_buy_flow(update, context, db_user):
    vip_label, vip_disc = get_vip((db_user or {}).get("total_spent", 0))
    flash = get_active_flash_sale()
    flash_pct = flash["discount_pct"] if flash else 0
    disc_line = f"💎 تخفیف VIP {h(vip_label)}: {vip_disc}٪\n" if vip_disc else ""
    flash_line = f"🔥 <b>فلش سیل: {flash_pct}٪ تخفیف اضافه!</b>\n" if flash else ""

    servers = [s for s in get_servers() if s.get("is_active")]
    context.user_data["servers"] = servers
    context.user_data["flash_pct"] = flash_pct
    if flash:
        context.user_data["flash_discount"] = flash_pct

    await update.message.reply_text(
        "🛒 <b>خرید کانفیگ VPN</b>\n\n"
        f"💰 قیمت پایه: {fmt(sm.price_per_gb())} / گیگ\n"
        f"{flash_line}"
        f"{disc_line}"
        f"📦 حداقل: {sm.min_gb()} گیگ\n\n"
        "حجم مورد نظر را انتخاب کنید:",
        parse_mode="HTML", reply_markup=gb_packages_kb(flash_pct)
    )
    return SELECT_GB


# ─── Inline callbacks (MAIN_MENU state) ──────────────────────────────────────

async def handle_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    user = query.from_user

    if data == "noop":
        await query.answer()
        return MAIN_MENU

    if data == "check_join":
        missing = await _unjoined(context.bot, user.id)
        if missing:
            await query.answer("هنوز عضو نشدید!", show_alert=True)
            await query.edit_message_reply_markup(reply_markup=join_required_kb(missing))
        else:
            await query.answer("✅ عضویت تایید شد!")
            try:
                await query.edit_message_text("✅ عضویت تایید شد!", parse_mode="HTML")
            except Exception:
                pass
            await query.message.reply_text(
                "از منوی زیر انتخاب کنید:", reply_markup=_menu_kb_for(user.id)
            )
        return MAIN_MENU

    await query.answer()

    if data in GUIDES:
        await query.message.reply_text(GUIDES[data], parse_mode="HTML", reply_markup=guide_kb())
        return MAIN_MENU

    if data == "back_main":
        await query.message.reply_text("منوی اصلی:", reply_markup=_menu_kb_for(user.id))
        return MAIN_MENU

    if data.startswith("viewconfig_"):
        order_id = int(data.split("_")[1])
        order = get_order(order_id)
        if order and order["status"] == "approved" and order["user_id"] == user.id:
            await query.message.reply_text(
                f"📋 <b>کانفیگ سفارش #{order_id}</b>\n\n<code>{h(order['config'])}</code>",
                parse_mode="HTML"
            )
        return MAIN_MENU

    if data.startswith("viewsub_"):
        order_id = int(data.split("_")[1])
        order = get_order(order_id)
        if order and order["status"] == "approved" and order["user_id"] == user.id:
            if order.get("sub_link"):
                await query.message.reply_text(
                    f"🔗 <b>لینک Sub سفارش #{order_id}</b>\n\n<code>{h(order['sub_link'])}</code>",
                    parse_mode="HTML"
                )
            else:
                await query.answer("لینک Sub ندارد.", show_alert=True)
        return MAIN_MENU

    if data.startswith("renew_"):
        order_id = int(data.split("_")[1])
        order = get_order(order_id)
        if order and order["user_id"] == user.id:
            context.user_data["renew_order_id"] = order_id
            return await _start_buy_flow_inline(query, context, order["gb_amount"])
        return MAIN_MENU

    if data.startswith("autorenew_"):
        order_id = int(data.split("_")[1])
        order = get_order(order_id)
        if order and order["user_id"] == user.id:
            from database import toggle_auto_renew
            new_state = toggle_auto_renew(order_id)
            label = "✅ فعال شد" if new_state else "❌ غیرفعال شد"
            await query.answer(f"تمدید خودکار {label}", show_alert=True)
            try:
                await query.edit_message_reply_markup(
                    reply_markup=order_config_kb(order_id, new_state)
                )
            except Exception:
                pass
        return MAIN_MENU

    if data.startswith("rate_"):
        parts = data.split("_")
        order_id, stars = int(parts[1]), int(parts[2])
        rate_order(order_id, stars)
        await query.edit_message_text(
            f"⭐ امتیاز {STAR_MAP.get(stars, '')} ثبت شد. ممنون از نظرتون!"
        )
        return MAIN_MENU

    if data.startswith("enter_lottery_"):
        lottery_id = int(data.split("_")[2])
        lottery = get_active_lottery()
        if not lottery or lottery["id"] != lottery_id:
            await query.answer("قرعه‌کشی دیگر فعال نیست!", show_alert=True)
            return MAIN_MENU
        existing = get_lottery_entries(lottery_id)
        already = any(e["user_id"] == user.id for e in existing)
        if already:
            await query.answer("شما قبلاً ثبت‌نام کرده‌اید!", show_alert=True)
            return MAIN_MENU
        enter_lottery(lottery_id, user.id)
        await query.answer("🎟 ثبت‌نام شما انجام شد! موفق باشید!", show_alert=True)
        try:
            await query.edit_message_reply_markup(
                reply_markup=lottery_kb(lottery_id, entered=True)
            )
        except Exception:
            pass
        return MAIN_MENU

    if data == "redeem_points":
        db_user = get_user(user.id)
        points = (db_user or {}).get("loyalty_points", 0)
        rate = sm.points_to_toman()
        if points < 1:
            await query.answer("امتیازی ندارید.", show_alert=True)
            return MAIN_MENU
        toman = points * rate
        ok = redeem_points_to_wallet(user.id, points, toman)
        if ok:
            await query.answer(f"✅ {points} امتیاز به {fmt(toman)} تومان تبدیل شد!", show_alert=True)
            try:
                await query.edit_message_text(
                    f"✅ <b>{points} امتیاز</b> به <b>{fmt(toman)} تومان</b> کیف پول تبدیل شد!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            await query.answer("خطا در تبدیل امتیاز.", show_alert=True)
        return MAIN_MENU

    if data == "wallet_charge":
        context.user_data["flow"] = "wallet_charge"
        await query.message.reply_text(
            f"💳 <b>شارژ کیف پول</b>\n\n"
            f"حداقل شارژ: {fmt(sm.wallet_min_charge())}\n\n"
            "مبلغ دلخواه (تومان) را وارد کنید:\n(/cancel برای لغو)",
            parse_mode="HTML", reply_markup=cancel_reply_kb()
        )
        return WALLET_AMOUNT

    if data == "wallet_history":
        await show_wallet_history(query.message, user.id)
        return MAIN_MENU

    return MAIN_MENU


async def _start_buy_flow_inline(query, context, gb=None):
    flash = get_active_flash_sale()
    flash_pct = flash["discount_pct"] if flash else 0
    context.user_data["flash_pct"] = flash_pct
    if flash:
        context.user_data["flash_discount"] = flash_pct
    if gb:
        context.user_data["selected_gb"] = gb
        await _show_order_confirm(query, context, gb)
        return CONFIRM_ORDER
    await query.message.reply_text(
        "حجم مورد نظر را انتخاب کنید:",
        reply_markup=gb_packages_kb(flash_pct)
    )
    return SELECT_GB


# ─── Buy Flow ─────────────────────────────────────────────────────────────────

async def handle_gb_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_main":
        await query.message.reply_text("منوی اصلی:", reply_markup=_menu_kb_for(query.from_user.id))
        return MAIN_MENU
    if data == "back_buy":
        flash_pct = context.user_data.get("flash_pct", 0)
        await query.edit_message_text("حجم مورد نظر را انتخاب کنید:", reply_markup=gb_packages_kb(flash_pct))
        return SELECT_GB
    if data == "cancel":
        await query.message.reply_text("❌ خرید لغو شد.", reply_markup=_menu_kb_for(query.from_user.id))
        return MAIN_MENU
    if data == "buy_custom":
        await query.edit_message_text(
            f"✏️ <b>حجم دلخواه</b>\n\nعددی بین {sm.min_gb()} تا {sm.max_gb()} وارد کنید:",
            parse_mode="HTML", reply_markup=cancel_inline_kb()
        )
        return CUSTOM_GB_INPUT
    if data.startswith("buy_"):
        gb = int(data.split("_")[1])
        await _show_order_confirm(query, context, gb)
        return CONFIRM_ORDER
    return SELECT_GB


async def handle_custom_gb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        await update.message.reply_text("❌ لغو شد.", reply_markup=_menu_kb_for(update.effective_user.id))
        return MAIN_MENU
    try:
        gb = int(update.message.text.strip())
        if not (sm.min_gb() <= gb <= sm.max_gb()):
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            f"❌ عدد بین {sm.min_gb()} تا {sm.max_gb()} وارد کنید:",
            reply_markup=cancel_reply_kb()
        )
        return CUSTOM_GB_INPUT
    await _show_order_confirm(update.message, context, gb)
    return CONFIRM_ORDER


async def _show_order_confirm(msg_or_query, context: ContextTypes.DEFAULT_TYPE, gb: int):
    if hasattr(msg_or_query, "from_user"):
        user_id = msg_or_query.from_user.id
    elif hasattr(msg_or_query, "chat"):
        user_id = msg_or_query.chat.id
    else:
        user_id = 0

    db_user = get_user(user_id) or {}
    vip_label, vip_disc = get_vip(db_user.get("total_spent", 0))
    extra_disc = context.user_data.get("discount_pct", 0)
    flash_disc = context.user_data.get("flash_discount", 0)
    total_disc = min(vip_disc + extra_disc + flash_disc, 70)
    base_price = gb * sm.price_per_gb()
    discount_amt = int(base_price * total_disc / 100)
    total_price = base_price - discount_amt
    wallet_bal = get_wallet(user_id)
    wallet_ok = wallet_bal >= total_price
    bonus_mb = get_bonus_mb(user_id)
    points = db_user.get("loyalty_points", 0)
    rate = sm.points_to_toman()
    points_val = points * rate
    points_ok = points_val >= total_price

    context.user_data.update({
        "selected_gb": gb,
        "total_price": total_price,
        "discount_pct": extra_disc,
        "bonus_mb": bonus_mb,
    })

    disc_lines = ""
    if vip_disc:
        disc_lines += f"💎 تخفیف VIP ({h(vip_label)}): {vip_disc}٪\n"
    if flash_disc:
        disc_lines += f"🔥 فلش سیل: {flash_disc}٪\n"
    if extra_disc:
        disc_lines += f"🎁 کد تخفیف: {extra_disc}٪\n"
    if discount_amt:
        disc_lines += f"💸 مبلغ تخفیف: -{fmt(discount_amt)}\n"
    bonus_line = f"🎁 بونوس معرفی: <b>+{bonus_mb} مگابایت</b> اضافه می‌شود\n" if bonus_mb else ""
    points_line = f"⭐ امتیاز قابل استفاده: {points} = {fmt(points_val)}\n" if points > 0 else ""

    text = (
        "📋 <b>خلاصه سفارش</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 حجم: {fmt_gb(gb)}\n"
        f"💰 قیمت پایه: {fmt(base_price)}\n"
        f"{disc_lines}"
        f"💳 <b>مبلغ نهایی: {fmt(total_price)}</b>\n"
        f"{bonus_line}"
        f"{points_line}"
        f"💼 موجودی کیف پول: {fmt(wallet_bal)}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = confirm_order_kb(gb, wallet_ok=wallet_ok, points_ok=points_ok)
    if hasattr(msg_or_query, "edit_message_text"):
        await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def handle_confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.message.reply_text("❌ لغو شد.", reply_markup=_menu_kb_for(query.from_user.id))
        return MAIN_MENU
    if data == "back_buy":
        flash_pct = context.user_data.get("flash_pct", 0)
        await query.edit_message_text("حجم مورد نظر را انتخاب کنید:", reply_markup=gb_packages_kb(flash_pct))
        return SELECT_GB
    if data == "apply_discount":
        await query.message.reply_text(
            "🎁 کد تخفیف خود را وارد کنید:", reply_markup=cancel_reply_kb()
        )
        return DISCOUNT_INPUT
    if data.startswith("pay_wallet_"):
        gb = int(data.split("_")[2])
        return await _process_wallet_payment(query, context, gb)
    if data.startswith("pay_points_"):
        gb = int(data.split("_")[2])
        return await _process_points_payment(query, context, gb)
    if data.startswith("pay_card_"):
        gb = int(data.split("_")[2])
        total_price = context.user_data.get("total_price", gb * sm.price_per_gb())
        card = sm.get_payment_card()
        await query.edit_message_text(
            "💳 <b>اطلاعات پرداخت</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 {fmt_gb(gb)}\n"
            f"💰 <b>مبلغ: {fmt(total_price)}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏦 {h(card['bank'])}\n"
            f"💳 شماره کارت:\n<code>{h(card['number'])}</code>\n\n"
            f"👤 به نام: {h(card['holder'])}\n\n"
            f"⚠️ دقیقاً <b>{fmt(total_price)}</b> واریز کنید.\n\n"
            "📸 عکس رسید را ارسال کنید:",
            parse_mode="HTML", reply_markup=cancel_inline_kb()
        )
        return UPLOAD_RECEIPT
    return CONFIRM_ORDER


async def _process_wallet_payment(query, context, gb: int) -> int:
    user = query.from_user
    total_price = context.user_data.get("total_price", gb * sm.price_per_gb())
    order_id = create_order(
        user_id=user.id, username=user.username, full_name=user.full_name,
        gb_amount=gb, total_price=total_price, paid_by_wallet=1
    )
    success = deduct_wallet(user.id, total_price, order_id)
    if not success:
        await query.answer("موجودی کافی نیست!", show_alert=True)
        return CONFIRM_ORDER

    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        uname = f"@{user.username}" if user.username else "—"
        from keyboards import admin_order_kb
        for aid in ADMIN_IDS:
            try:
                await admin_bot.send_message(
                    chat_id=aid,
                    text=(
                        "🛍️ <b>سفارش جدید (کیف پول)</b>\n\n"
                        f"🆔 #{order_id}\n"
                        f"👤 {h(user.full_name)} | {h(uname)}\n"
                        f"📟 <code>{user.id}</code>\n"
                        f"📦 {fmt_gb(gb)}\n"
                        f"💰 {fmt(total_price)}\n"
                        "💼 <b>پرداخت از کیف پول</b>"
                    ),
                    parse_mode="HTML",
                    reply_markup=admin_order_kb(order_id)
                )
            except Exception as e:
                logger.error("Wallet order notify failed: %s", e)

    await query.edit_message_text(
        f"✅ <b>سفارش #{order_id} ثبت شد!</b>\n\n"
        f"📦 {fmt_gb(gb)} | 💰 {fmt(total_price)}\n"
        "💼 پرداخت از کیف پول انجام شد.\n"
        "⏳ منتظر ارسال کانفیگ باشید.",
        parse_mode="HTML"
    )
    context.user_data.clear()
    return MAIN_MENU


async def _process_points_payment(query, context, gb: int) -> int:
    user = query.from_user
    total_price = context.user_data.get("total_price", gb * sm.price_per_gb())
    db_user = get_user(user.id) or {}
    points = db_user.get("loyalty_points", 0)
    rate = sm.points_to_toman()
    needed_pts = -(-total_price // rate)  # ceiling division
    if points < needed_pts:
        await query.answer("امتیاز کافی ندارید!", show_alert=True)
        return CONFIRM_ORDER

    ok = redeem_points_to_wallet(user.id, needed_pts, total_price)
    if not ok:
        await query.answer("خطا در تبدیل امتیاز.", show_alert=True)
        return CONFIRM_ORDER

    order_id = create_order(
        user_id=user.id, username=user.username, full_name=user.full_name,
        gb_amount=gb, total_price=total_price, paid_by_wallet=1
    )
    deduct_wallet(user.id, total_price, order_id)

    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        uname = f"@{user.username}" if user.username else "—"
        from keyboards import admin_order_kb
        for aid in ADMIN_IDS:
            try:
                await admin_bot.send_message(
                    chat_id=aid,
                    text=(
                        "🛍️ <b>سفارش جدید (امتیاز)</b>\n\n"
                        f"🆔 #{order_id}\n"
                        f"👤 {h(user.full_name)} | {h(uname)}\n"
                        f"📦 {fmt_gb(gb)} | 💰 {fmt(total_price)}\n"
                        f"⭐ پرداخت با {needed_pts} امتیاز"
                    ),
                    parse_mode="HTML",
                    reply_markup=admin_order_kb(order_id)
                )
            except Exception as e:
                logger.error("Points order notify: %s", e)

    await query.edit_message_text(
        f"✅ <b>سفارش #{order_id} ثبت شد!</b>\n\n"
        f"📦 {fmt_gb(gb)} | ⭐ {needed_pts} امتیاز استفاده شد\n"
        "⏳ منتظر ارسال کانفیگ باشید.",
        parse_mode="HTML"
    )
    context.user_data.clear()
    return MAIN_MENU


async def handle_discount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        await update.message.reply_text("❌ لغو شد.", reply_markup=_menu_kb_for(update.effective_user.id))
        return MAIN_MENU
    code = update.message.text.strip().upper()
    disc = get_discount_code(code)
    if not disc:
        await update.message.reply_text(
            "❌ کد نامعتبر یا منقضی شده.\nدوباره وارد کنید:",
            reply_markup=cancel_reply_kb()
        )
        return DISCOUNT_INPUT
    pct = disc["discount_pct"]
    context.user_data["discount_code"] = code
    context.user_data["discount_pct"] = pct
    gb = context.user_data.get("selected_gb", 0)
    await update.message.reply_text(
        f"✅ کد تخفیف <b>{pct}٪</b> اعمال شد!", parse_mode="HTML"
    )
    if gb:
        await _show_order_confirm(update.message, context, gb)
        return CONFIRM_ORDER
    flash_pct = context.user_data.get("flash_pct", 0)
    await update.message.reply_text("حالا حجم خود را انتخاب کنید:", reply_markup=gb_packages_kb(flash_pct))
    return SELECT_GB


async def handle_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "❌ لغو شد.", reply_markup=_menu_kb_for(update.effective_user.id)
        )
        context.user_data.clear()
        return MAIN_MENU
    if not update.message.photo:
        await update.message.reply_text(
            "📸 لطفاً عکس رسید ارسال کنید.", reply_markup=cancel_reply_kb()
        )
        return UPLOAD_RECEIPT

    user = update.effective_user
    gb = context.user_data.get("selected_gb")
    total_price = context.user_data.get("total_price", (gb or 0) * sm.price_per_gb())
    if not gb:
        await update.message.reply_text("خطا. دوباره /start بزنید.", reply_markup=_menu_kb_for(user.id))
        return MAIN_MENU

    receipt_file_id = update.message.photo[-1].file_id
    order_id = create_order(
        user_id=user.id, username=user.username, full_name=user.full_name,
        gb_amount=gb, total_price=total_price, receipt_file_id=receipt_file_id
    )

    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        await _notify_admin_order(
            context.bot, admin_bot, order_id, user, gb, total_price, receipt_file_id
        )

    code = context.user_data.get("discount_code")
    if code:
        use_discount_code(code, user.id, order_id)

    await update.message.reply_text(
        f"✅ <b>سفارش #{order_id} ثبت شد!</b>\n\n"
        f"📦 {fmt_gb(gb)} | 💰 {fmt(total_price)}\n"
        "⏳ پس از بررسی رسید، کانفیگ ارسال می‌شود.\n\n"
        f"📞 پشتیبانی: {h(sm.support_username())}",
        parse_mode="HTML", reply_markup=_menu_kb_for(user.id)
    )
    context.user_data.clear()
    return MAIN_MENU


async def _notify_admin_order(customer_bot, admin_bot, order_id, user, gb, total_price, receipt_file_id):
    from keyboards import admin_order_kb
    uname = f"@{user.username}" if user.username else "—"
    caption = (
        "🛍️ <b>سفارش جدید!</b>\n\n"
        f"🆔 #{order_id} | 📦 {fmt_gb(gb)} | 💰 {fmt(total_price)}\n"
        f"👤 {h(user.full_name)} | {h(uname)}\n"
        f"📟 <code>{user.id}</code>"
    )
    try:
        f = await customer_bot.get_file(receipt_file_id)
        buf = BytesIO(bytes(await f.download_as_bytearray()))
        buf.name = "receipt.jpg"
        for aid in ADMIN_IDS:
            try:
                await admin_bot.send_photo(
                    chat_id=aid, photo=buf, caption=caption,
                    parse_mode="HTML", reply_markup=admin_order_kb(order_id)
                )
                buf.seek(0)
            except Exception as e:
                logger.error("Notify admin %s: %s", aid, e)
    except Exception as e:
        logger.error("Download receipt: %s", e)
        for aid in ADMIN_IDS:
            try:
                await admin_bot.send_message(
                    chat_id=aid, text=caption + "\n\n⚠️ ارسال رسید ناموفق",
                    parse_mode="HTML", reply_markup=admin_order_kb(order_id)
                )
            except Exception as e2:
                logger.error("Fallback notify: %s", e2)


# ─── Wallet ───────────────────────────────────────────────────────────────────

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    bal = get_wallet(user.id)
    await update.message.reply_text(
        "💰 <b>کیف پول</b>\n\n"
        f"💼 موجودی: <b>{fmt(bal)}</b>\n\n"
        "با کیف پول می‌توانید بدون ارسال رسید خرید کنید.",
        parse_mode="HTML", reply_markup=wallet_kb()
    )
    return MAIN_MENU


async def show_wallet_history(message, user_id: int):
    txs = get_wallet_history(user_id)
    if not txs:
        await message.reply_text("📋 تاریخچه‌ای وجود ندارد.")
        return
    text = "📋 <b>تاریخچه کیف پول</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for tx in txs[:20]:
        sign = "+" if tx["amount"] > 0 else ""
        label = h(TX_EMOJI.get(tx["type"], tx["type"]))
        status = "✅" if tx["status"] == "approved" else ("⏳" if tx["status"] == "pending" else "❌")
        text += f"{status} {label}\n   {sign}{fmt(abs(tx['amount']))} | {fmt_dt(tx['created_at'])}\n\n"
    await message.reply_text(text, parse_mode="HTML")


async def handle_wallet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        return await cmd_cancel(update, context)
    try:
        amount = int(update.message.text.strip().replace(",", "").replace("،", ""))
        if amount < sm.wallet_min_charge():
            await update.message.reply_text(
                f"❌ حداقل شارژ {fmt(sm.wallet_min_charge())} است.",
                reply_markup=cancel_reply_kb()
            )
            return WALLET_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ عدد معتبر وارد کنید:", reply_markup=cancel_reply_kb())
        return WALLET_AMOUNT

    context.user_data["wallet_amount"] = amount
    card = sm.get_payment_card()
    await update.message.reply_text(
        f"💳 <b>شارژ کیف پول</b>\n\n"
        f"💰 مبلغ: <b>{fmt(amount)}</b>\n\n"
        f"🏦 {h(card['bank'])}\n"
        f"💳 <code>{h(card['number'])}</code>\n"
        f"👤 {h(card['holder'])}\n\n"
        "📸 عکس رسید را ارسال کنید:",
        parse_mode="HTML", reply_markup=cancel_reply_kb()
    )
    return WALLET_RECEIPT


async def handle_wallet_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        return await cmd_cancel(update, context)
    if not update.message.photo:
        await update.message.reply_text(
            "📸 لطفاً عکس رسید ارسال کنید.", reply_markup=cancel_reply_kb()
        )
        return WALLET_RECEIPT

    user = update.effective_user
    amount = context.user_data.get("wallet_amount", 0)
    receipt_file_id = update.message.photo[-1].file_id
    tx_id = create_wallet_charge(user.id, amount, receipt_file_id)

    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        uname = f"@{user.username}" if user.username else "—"
        caption = (
            "💳 <b>درخواست شارژ کیف پول</b>\n\n"
            f"🆔 تراکنش #{tx_id}\n"
            f"👤 {h(user.full_name)} | {h(uname)}\n"
            f"📟 <code>{user.id}</code>\n"
            f"💰 مبلغ: <b>{fmt(amount)}</b>"
        )
        try:
            f = await context.bot.get_file(receipt_file_id)
            buf = BytesIO(bytes(await f.download_as_bytearray()))
            buf.name = "receipt.jpg"
            from keyboards import admin_wallet_kb
            for aid in ADMIN_IDS:
                try:
                    await admin_bot.send_photo(
                        chat_id=aid, photo=buf, caption=caption,
                        parse_mode="HTML", reply_markup=admin_wallet_kb(tx_id)
                    )
                    buf.seek(0)
                except Exception as e:
                    logger.error("Wallet notify %s: %s", aid, e)
        except Exception as e:
            logger.error("Wallet receipt download: %s", e)

    await update.message.reply_text(
        f"✅ درخواست شارژ <b>{fmt(amount)}</b> ثبت شد.\n"
        f"🆔 شماره تراکنش: #{tx_id}\n\n"
        "پس از تایید ادمین به کیف پول اضافه می‌شود.",
        parse_mode="HTML", reply_markup=_menu_kb_for(user.id)
    )
    context.user_data.clear()
    return MAIN_MENU


# ─── Servers Status ───────────────────────────────────────────────────────────

async def show_servers_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    servers = get_servers()
    if not servers:
        await update.message.reply_text("🌐 هیچ سروری تعریف نشده.")
        return
    text = "🌐 <b>وضعیت سرورها</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for s in servers:
        load = s.get("load_pct", 0)
        status = "🟢 آنلاین" if s.get("is_active") else "🔴 آفلاین"
        flag = s.get("flag", "🌐")
        bar = "█" * round(load / 10) + "░" * (10 - round(load / 10))
        text += f"{flag} <b>{h(s['name'])}</b> — {status}\n   {bar} {load}٪\n\n"
    await update.message.reply_text(
        text, parse_mode="HTML",
        reply_markup=servers_status_kb(servers)
    )


# ─── Points ───────────────────────────────────────────────────────────────────

async def show_points(update: Update, context: ContextTypes.DEFAULT_TYPE, db_user):
    points = (db_user or {}).get("loyalty_points", 0)
    rate = sm.points_to_toman()
    per10k = sm.points_per_10k()
    await update.message.reply_text(
        "⭐ <b>سیستم امتیاز</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⭐ امتیاز شما: <b>{points}</b>\n"
        f"💸 ارزش: <b>{fmt(points * rate)} تومان</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 به ازای هر ۱۰,۰۰۰ تومان خرید: <b>{per10k} امتیاز</b>\n"
        f"📌 هر امتیاز = <b>{fmt(rate)} تومان</b>\n\n"
        "امتیازات را به کیف پول تبدیل کنید:",
        parse_mode="HTML",
        reply_markup=points_kb(points, rate) if points > 0 else cancel_inline_kb()
    )


# ─── Lottery ──────────────────────────────────────────────────────────────────

async def show_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lottery = get_active_lottery()
    if not lottery:
        await update.message.reply_text("🎰 در حال حاضر قرعه‌کشی فعالی وجود ندارد.")
        return
    user = update.effective_user
    entries = get_lottery_entries(lottery["id"])
    entered = any(e["user_id"] == user.id for e in entries)

    prize_text = ""
    if lottery.get("prize_gb"):
        prize_text += f"📦 <b>{lottery['prize_gb']} گیگابایت</b> رایگان\n"
    if lottery.get("prize_toman"):
        prize_text += f"💰 <b>{fmt(lottery['prize_toman'])}</b> شارژ کیف پول\n"

    draw_dt = lottery.get("draw_at", "—")[:16] if lottery.get("draw_at") else "—"

    await update.message.reply_text(
        "🎰 <b>قرعه‌کشی فعال</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 <b>{h(lottery['name'])}</b>\n\n"
        f"🎁 جایزه:\n{prize_text}\n"
        f"📅 زمان قرعه‌کشی: <b>{draw_dt}</b>\n"
        f"👥 شرکت‌کنندگان: <b>{len(entries)}</b>\n\n"
        + ("✅ <b>شما ثبت‌نام کرده‌اید!</b>" if entered else "برای شرکت دکمه زیر را بزنید:"),
        parse_mode="HTML",
        reply_markup=lottery_kb(lottery["id"], entered)
    )


# ─── Referral ─────────────────────────────────────────────────────────────────

async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id)
    if not db_user:
        return
    code = db_user.get("referral_code", "—")
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={code}"

    bonus_mb = sm.referral_bonus_mb()
    bonus_toman = sm.referral_bonus_toman()
    if bonus_toman > 0:
        bonus_text = f"🎁 جایزه هر دو طرف: <b>{fmt(bonus_toman)}</b>\n"
    elif bonus_mb > 0:
        bonus_text = f"🎁 جایزه: <b>{bonus_mb} مگابایت</b> هدیه\n"
    else:
        bonus_text = ""

    from database import get_user_referrals
    refs = get_user_referrals(user.id)
    refs_text = f"👥 تعداد زیرمجموعه: <b>{len(refs)}</b>\n" if refs else ""

    await update.message.reply_text(
        "👥 <b>دعوت دوستان</b>\n\n"
        f"{bonus_text}"
        f"{refs_text}"
        "وقتی دوستتان اولین خرید را انجام دهد، هر دو جایزه می‌گیرید!\n\n"
        f"🔗 لینک اختصاصی شما:\n<code>{ref_link}</code>\n\n"
        "لینک بالا را کپی کنید و برای دوستانتان بفرستید.",
        parse_mode="HTML"
    )


# ─── Profile ──────────────────────────────────────────────────────────────────

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id)
    if not db_user:
        return
    spent = db_user.get("total_spent", 0)
    vip_label, vip_disc = get_vip(spent)
    bar = vip_progress_bar(spent)
    nxt = next_vip(spent)
    nxt_line = f"⬆️ تا {h(nxt[0])}: {fmt(nxt[1])}" if nxt else "💎 بالاترین سطح!"

    bonus_mb = db_user.get("bonus_mb", 0)
    bonus_line = f"🎁 بونوس معرفی: <b>{bonus_mb} مگابایت</b>\n" if bonus_mb else ""
    points = db_user.get("loyalty_points", 0)
    points_line = f"⭐ امتیاز وفاداری: <b>{points}</b>\n" if points else ""

    await update.message.reply_text(
        "👤 <b>پروفایل من</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام: {h(user.full_name)}\n"
        f"🔗 یوزرنیم: @{h(user.username or '—')}\n"
        f"📅 عضویت: {fmt_dt(db_user.get('join_date',''))}\n\n"
        f"💎 سطح: <b>{h(vip_label)}</b>\n"
        + (f"🔖 تخفیف: {vip_disc}٪\n" if vip_disc else "")
        + f"📊 {h(bar)}\n"
        f"{nxt_line}\n\n"
        f"🛍️ تعداد سفارش: {db_user.get('total_orders', 0)}\n"
        f"💰 کل خرید: {fmt(spent)}\n"
        f"💼 کیف پول: {fmt(db_user.get('wallet_balance', 0))}\n"
        f"{points_line}"
        f"{bonus_line}",
        parse_mode="HTML"
    )


async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    orders = get_user_orders(user.id, limit=8)
    if not orders:
        await update.message.reply_text("📦 هنوز سفارشی ندارید.")
        return
    text = "📦 <b>سفارشات من</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for o in orders:
        st = STATUS_EMOJI.get(o["status"], "?")
        exp = f" | 📅 {o['expiry_date'][:10]}" if o.get("expiry_date") else ""
        text += (
            f"{st} <b>#{o['id']}</b> — {fmt_gb(o['gb_amount'])}\n"
            f"   💰 {fmt(o['total_price'])} | {fmt_dt(o['created_at'])}{exp}\n"
        )
        if o["status"] == "approved" and o.get("config"):
            text += f"   📋 /config_{o['id']}\n"
        text += "\n"
    await update.message.reply_text(text, parse_mode="HTML")


# ─── Trial ────────────────────────────────────────────────────────────────────

async def request_trial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db_user = get_user(user.id)
    if not sm.free_trial_enabled():
        await update.message.reply_text("آزمایش رایگان فعال نیست.")
        return MAIN_MENU
    if db_user and db_user.get("free_trial_used"):
        await update.message.reply_text("❌ قبلاً از آزمایش رایگان استفاده کرده‌اید.")
        return MAIN_MENU

    trial_gb = sm.free_trial_gb()
    order_id = create_order(
        user_id=user.id, username=user.username, full_name=user.full_name,
        gb_amount=trial_gb, total_price=0, is_trial=1
    )
    mark_trial_used(user.id)

    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        uname = f"@{user.username}" if user.username else "—"
        from keyboards import admin_order_kb
        for aid in ADMIN_IDS:
            try:
                await admin_bot.send_message(
                    chat_id=aid,
                    text=(
                        "🎯 <b>درخواست آزمایش رایگان</b>\n\n"
                        f"🆔 #{order_id}\n"
                        f"👤 {h(user.full_name)} | {h(uname)}\n"
                        f"📟 <code>{user.id}</code>\n"
                        f"📦 {trial_gb} گیگابایت رایگان"
                    ),
                    parse_mode="HTML",
                    reply_markup=admin_order_kb(order_id)
                )
            except Exception as e:
                logger.error("Trial notify %s: %s", aid, e)

    await update.message.reply_text(
        f"🎯 <b>درخواست آزمایش رایگان ثبت شد!</b>\n\n"
        f"📦 {trial_gb} گیگابایت\n"
        "پس از تایید ادمین، کانفیگ ارسال می‌شود.",
        parse_mode="HTML", reply_markup=_menu_kb_for(user.id)
    )
    return MAIN_MENU


# ─── Support ──────────────────────────────────────────────────────────────────

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        return await cmd_cancel(update, context)
    user = update.effective_user
    tid = create_ticket(user.id, user.username, user.full_name, update.message.text)

    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        uname = f"@{user.username}" if user.username else "—"
        for aid in ADMIN_IDS:
            try:
                await admin_bot.send_message(
                    chat_id=aid,
                    text=(
                        f"💬 <b>تیکت #{tid}</b>\n\n"
                        f"👤 {h(user.full_name)} | {h(uname)} | <code>{user.id}</code>\n\n"
                        f"📝 {h(update.message.text)}\n\n"
                        f"پاسخ: <code>/reply_{tid} متن</code>"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error("Support notify %s: %s", aid, e)

    await update.message.reply_text(
        f"✅ تیکت <b>#{tid}</b> ثبت شد. به زودی پاسخ می‌گیرید.",
        parse_mode="HTML", reply_markup=_menu_kb_for(user.id)
    )
    return MAIN_MENU


# ─── About ────────────────────────────────────────────────────────────────────

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"ℹ️ <b>{h(BOT_NAME)}</b>\n\n"
        "🔒 پروتکل: VLESS + XTLS/Reality\n"
        "⚡ سرعت بالا | پینگ کم\n"
        "🌍 سرورهای اختصاصی\n"
        "✅ ضمانت کیفیت\n"
        "🔄 پشتیبانی آنلاین\n\n"
        f"💰 {fmt(sm.price_per_gb())} / گیگابایت\n"
        f"📦 {sm.min_gb()} تا {sm.max_gb()} گیگابایت\n\n"
        f"📢 کانال: {h(sm.bot_channel())}\n"
        f"💬 پشتیبانی: {h(sm.support_username())}",
        parse_mode="HTML"
    )


# ─── Config delivery ──────────────────────────────────────────────────────────

async def deliver_config(customer_bot, order: dict, config: str, sub_link: str):
    uid = order["user_id"]
    is_trial = order.get("is_trial", 0)
    title = "آزمایش رایگان" if is_trial else "سفارش"
    trial_header = "🎯 <b>آزمایش رایگان</b>\n" if is_trial else ""
    expiry_line = f"📅 انقضا: <code>{order.get('expiry_date','—')}</code>\n" if order.get("expiry_date") else ""

    try:
        await customer_bot.send_message(
            uid,
            f"🎉 <b>{title} شما تایید شد!</b>\n"
            f"{trial_header}\n"
            f"🆔 سفارش #{order['id']}\n"
            f"📦 {fmt_gb(order['gb_amount'])}\n"
            f"{expiry_line}"
            "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 <b>کانفیگ VLESS:</b>\n"
            f"<code>{h(config)}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Config delivery failed: %s", e)
        return

    if sub_link:
        try:
            await customer_bot.send_message(
                uid,
                f"🔗 <b>لینک Subscription:</b>\n<code>{h(sub_link)}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Sub link delivery: %s", e)

    try:
        await customer_bot.send_message(
            uid,
            "📚 <b>راهنمای نصب سریع:</b>\n\n"
            "🍎 آیفون: <b>NPV Tunnel</b> یا <b>V2Box</b> (App Store)\n"
            "🤖 اندروید: <b>V2RayNG</b> یا <b>Hiddify</b> (Play Store)\n"
            "🪟 ویندوز: <b>V2RayN</b> (GitHub)\n\n"
            "در ربات روی 📚 <b>راهنمای نصب</b> بزنید برای راهنمای کامل.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Guide delivery: %s", e)

    try:
        await customer_bot.send_message(
            uid,
            "⭐ <b>نظر شما مهمه!</b>\n\nبه سرویس ما امتیاز بدید:",
            parse_mode="HTML",
            reply_markup=rating_kb(order["id"])
        )
    except Exception as e:
        logger.error("Rating request: %s", e)


# ─── Setup ────────────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception in customer bot: %s", context.error, exc_info=context.error)


def setup_customer_bot(app: Application, admin_bot_instance=None) -> None:
    if admin_bot_instance:
        app.bot_data["admin_bot_instance"] = admin_bot_instance

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            CAPTCHA: [
                CallbackQueryHandler(handle_captcha_cb, pattern="^cap_"),
            ],
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
                CallbackQueryHandler(handle_inline),
            ],
            SELECT_GB: [
                CallbackQueryHandler(handle_gb_selection),
            ],
            CUSTOM_GB_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_gb),
                CallbackQueryHandler(handle_gb_selection, pattern="^cancel$"),
            ],
            CONFIRM_ORDER: [
                CallbackQueryHandler(handle_confirm_order),
            ],
            DISCOUNT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_discount_input),
            ],
            UPLOAD_RECEIPT: [
                MessageHandler(filters.PHOTO, handle_receipt_upload),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_receipt_upload),
                CallbackQueryHandler(handle_receipt_upload, pattern="^cancel$"),
            ],
            WALLET_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_amount),
            ],
            WALLET_RECEIPT: [
                MessageHandler(filters.PHOTO, handle_wallet_receipt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_receipt),
            ],
            SUPPORT_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_support),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("start",  cmd_start),
        ],
        allow_reentry=True,
        name="customer_conv",
    )
    app.add_handler(conv)
    app.add_error_handler(error_handler)
    logger.info("Customer bot v3 ready.")
