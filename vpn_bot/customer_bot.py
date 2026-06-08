"""ربات مشتری — خرید، کیف پول، معرفی، VIP، راهنما، پشتیبانی."""
import logging
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes,
)
from config import (
    PRICE_PER_GB, MIN_GB, MAX_GB, CARD_NUMBER, CARD_HOLDER, BANK_NAME,
    BOT_NAME, SUPPORT_USERNAME, WALLET_MIN_CHARGE,
    FORCE_JOIN_ENABLED, FORCE_JOIN_CHANNELS,
    FREE_TRIAL_ENABLED, FREE_TRIAL_GB,
    PANEL_ENABLED, ADMIN_IDS,
)
from database import (
    upsert_user, get_user, get_user_orders, get_order,
    create_order, create_ticket, get_discount_code, use_discount_code,
    get_wallet, deduct_wallet, create_wallet_charge,
    get_wallet_history, get_user_by_ref_code, mark_trial_used,
    rate_order,
)
from keyboards import (
    main_menu_kb, cancel_reply_kb, cancel_inline_kb,
    gb_packages_kb, confirm_order_kb, guide_kb,
    wallet_kb, rating_kb, join_required_kb, order_config_kb,
)
from guides import GUIDES
from utils import get_vip, next_vip, vip_progress_bar, fmt, fmt_gb, fmt_dt, is_rate_limited, STATUS_EMOJI, STATUS_LABEL, STAR_MAP, TX_EMOJI

logger = logging.getLogger(__name__)

# ─── States ───────────────────────────────────────────────────────────────────
(
    MAIN_MENU,
    SELECT_GB, CUSTOM_GB_INPUT, CONFIRM_ORDER,
    DISCOUNT_INPUT, UPLOAD_RECEIPT,
    WALLET_AMOUNT, WALLET_RECEIPT,
    SUPPORT_MESSAGE,
) = range(9)


# ─── Force Join ───────────────────────────────────────────────────────────────

async def _unjoined(bot, user_id: int) -> list[str]:
    if not FORCE_JOIN_ENABLED or not FORCE_JOIN_CHANNELS:
        return []
    out = []
    for ch in FORCE_JOIN_CHANNELS:
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
    txt = (
        "⛔ *برای استفاده از ربات عضو کانال زیر شوید:*\n\n"
        + "\n".join(f"• {c}" for c in missing)
        + "\n\nبعد از عضویت روی *✅ عضو شدم* بزنید."
    )
    kb = join_required_kb(missing)
    if update.callback_query:
        await update.callback_query.answer("ابتدا عضو کانال شوید!", show_alert=True)
        await update.callback_query.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.effective_message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)
    return False


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    # deep link referral: /start REF_XXXXXX
    referred_by = None
    if context.args:
        ref_code = context.args[0]
        ref_user = get_user_by_ref_code(ref_code)
        if ref_user and ref_user["user_id"] != user.id:
            referred_by = ref_user["user_id"]

    is_new = upsert_user(user.id, user.username, user.full_name, referred_by)
    context.user_data.clear()

    if not await check_join(update, context):
        return MAIN_MENU

    db_user = get_user(user.id)
    show_trial = FREE_TRIAL_ENABLED and not db_user.get("free_trial_used")
    vip_label, _ = get_vip(db_user.get("total_spent", 0))

    welcome = "🎉 خوش آمدید!" if is_new else f"👋 سلام {user.first_name}!"
    if referred_by:
        welcome += "\n🎁 از طریق دعوت دوست وارد شدید!"

    text = (
        f"{welcome}\n\n"
        f"🌐 *{BOT_NAME}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ کانفیگ VLESS سریع و پایدار\n"
        f"💰 {fmt(PRICE_PER_GB)} / گیگابایت\n"
        f"📦 {MIN_GB} تا {MAX_GB} گیگابایت\n"
        f"💎 سطح شما: {vip_label}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "از منوی زیر انتخاب کنید:"
    )
    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=main_menu_kb(show_trial))
    return MAIN_MENU


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    db_user = get_user(update.effective_user.id)
    show_trial = FREE_TRIAL_ENABLED and db_user and not db_user.get("free_trial_used")
    await update.message.reply_text("❌ لغو شد.", reply_markup=main_menu_kb(show_trial))
    return MAIN_MENU


# ─── Main menu ────────────────────────────────────────────────────────────────

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user = update.effective_user

    if text == "❌ انصراف":
        context.user_data.clear()
        db_user = get_user(user.id)
        show_trial = FREE_TRIAL_ENABLED and db_user and not db_user.get("free_trial_used")
        await update.message.reply_text("منوی اصلی:", reply_markup=main_menu_kb(show_trial))
        return MAIN_MENU

    # anti-spam
    if is_rate_limited(user.id):
        await update.message.reply_text("⚠️ خیلی سریع پیام می‌فرستید. کمی صبر کنید.")
        return MAIN_MENU

    if not await check_join(update, context):
        return MAIN_MENU

    if text == "🛒 خرید کانفیگ":
        db_user = get_user(user.id)
        vip_label, vip_disc = get_vip(db_user.get("total_spent", 0))
        discount_line = f"💎 تخفیف VIP {vip_label}: {vip_disc}٪\n" if vip_disc else ""
        await update.message.reply_text(
            "🛒 *خرید کانفیگ VPN*\n\n"
            f"💰 قیمت پایه: {fmt(PRICE_PER_GB)} / گیگ\n"
            f"{discount_line}"
            f"📦 حداقل: {MIN_GB} گیگ\n\n"
            "حجم مورد نظر را انتخاب کنید:",
            parse_mode="Markdown", reply_markup=gb_packages_kb()
        )
        return SELECT_GB

    if text == "💰 کیف پول":
        return await show_wallet(update, context)

    if text == "📦 سفارشات من":
        await show_orders(update, context)
        return MAIN_MENU

    if text == "👤 پروفایل من":
        await show_profile(update, context)
        return MAIN_MENU

    if text == "📚 راهنمای نصب":
        await update.message.reply_text("📚 پلتفرم خود را انتخاب کنید:", reply_markup=guide_kb())
        return MAIN_MENU

    if text == "👥 دعوت دوستان":
        await show_referral(update, context)
        return MAIN_MENU

    if text == "🎯 آزمایش رایگان":
        return await request_trial(update, context)

    if text == "💬 پشتیبانی":
        await update.message.reply_text(
            "💬 *پشتیبانی*\n\nپیام خود را بنویسید:\n(/cancel برای لغو)",
            parse_mode="Markdown", reply_markup=cancel_reply_kb()
        )
        return SUPPORT_MESSAGE

    if text == "ℹ️ درباره ما":
        await show_about(update, context)
        return MAIN_MENU

    return MAIN_MENU


# ─── Inline callbacks (MAIN_MENU state) ──────────────────────────────────────

async def handle_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    # Force join check
    if data == "check_join":
        missing = await _unjoined(context.bot, user.id)
        if missing:
            await query.answer("هنوز عضو نشدید!", show_alert=True)
            await query.edit_message_reply_markup(reply_markup=join_required_kb(missing))
        else:
            await query.edit_message_text("✅ عضویت تایید شد!")
            db_user = get_user(user.id)
            show_trial = FREE_TRIAL_ENABLED and db_user and not db_user.get("free_trial_used")
            await query.message.reply_text("از منوی زیر انتخاب کنید:",
                                           reply_markup=main_menu_kb(show_trial))
        return MAIN_MENU

    # Guides
    if data in GUIDES:
        await query.message.reply_text(GUIDES[data], reply_markup=guide_kb())
        return MAIN_MENU

    if data == "back_main":
        db_user = get_user(user.id)
        show_trial = FREE_TRIAL_ENABLED and db_user and not db_user.get("free_trial_used")
        await query.message.reply_text("منوی اصلی:", reply_markup=main_menu_kb(show_trial))
        return MAIN_MENU

    # View config
    if data.startswith("viewconfig_"):
        order_id = int(data.split("_")[1])
        order = get_order(order_id)
        if order and order["status"] == "approved" and order["user_id"] == user.id:
            await query.message.reply_text(
                f"📋 *کانفیگ سفارش #{order_id}*\n\n`{order['config']}`",
                parse_mode="Markdown"
            )
        return MAIN_MENU

    if data.startswith("viewsub_"):
        order_id = int(data.split("_")[1])
        order = get_order(order_id)
        if order and order["status"] == "approved" and order["user_id"] == user.id:
            if order.get("sub_link"):
                await query.message.reply_text(
                    f"🔗 *لینک Sub سفارش #{order_id}*\n\n`{order['sub_link']}`",
                    parse_mode="Markdown"
                )
            else:
                await query.answer("لینک Sub ندارد.", show_alert=True)
        return MAIN_MENU

    if data.startswith("usage_"):
        order_id = int(data.split("_")[1])
        order = get_order(order_id)
        if order and PANEL_ENABLED and order.get("panel_username"):
            from panel_api import marzban
            usage = await marzban.get_user_usage(order["panel_username"])
            if usage:
                await query.message.reply_text(
                    f"📊 *مصرف سفارش #{order_id}*\n\n"
                    f"✅ استفاده شده: {usage['used_gb']} GB\n"
                    f"📦 کل: {usage['total_gb']} GB\n"
                    f"🔋 باقی‌مانده: {usage['remaining_gb']} GB\n"
                    f"🔄 وضعیت: {usage['status']}",
                    parse_mode="Markdown"
                )
            else:
                await query.answer("اطلاعات در دسترس نیست.", show_alert=True)
        return MAIN_MENU

    # Rating
    if data.startswith("rate_"):
        parts = data.split("_")
        order_id, stars = int(parts[1]), int(parts[2])
        rate_order(order_id, stars)
        await query.edit_message_text(
            f"⭐ امتیاز {STAR_MAP[stars]} ثبت شد. ممنون از نظرتون!"
        )
        return MAIN_MENU

    # Wallet
    if data == "wallet_charge":
        context.user_data["flow"] = "wallet_charge"
        await query.message.reply_text(
            f"💳 *شارژ کیف پول*\n\n"
            f"حداقل شارژ: {fmt(WALLET_MIN_CHARGE)}\n\n"
            "مبلغ دلخواه (تومان) را وارد کنید:\n(/cancel برای لغو)",
            parse_mode="Markdown", reply_markup=cancel_reply_kb()
        )
        return WALLET_AMOUNT

    if data == "wallet_history":
        await show_wallet_history(query.message, user.id)
        return MAIN_MENU

    return MAIN_MENU


# ─── Buy flow ─────────────────────────────────────────────────────────────────

async def handle_gb_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_main":
        await query.message.reply_text("منوی اصلی:", reply_markup=main_menu_kb())
        return MAIN_MENU
    if data == "back_buy":
        await query.edit_message_text("حجم مورد نظر را انتخاب کنید:", reply_markup=gb_packages_kb())
        return SELECT_GB
    if data == "cancel":
        await query.message.reply_text("❌ خرید لغو شد.", reply_markup=main_menu_kb())
        return MAIN_MENU
    if data == "buy_custom":
        await query.edit_message_text(
            f"✏️ حجم دلخواه\n\nعددی بین {MIN_GB} تا {MAX_GB} وارد کنید:",
            reply_markup=cancel_inline_kb()
        )
        return CUSTOM_GB_INPUT
    if data.startswith("buy_"):
        gb = int(data.split("_")[1])
        await _show_order_confirm(query, context, gb)
        return CONFIRM_ORDER
    return SELECT_GB


async def handle_custom_gb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        await update.message.reply_text("❌ لغو شد.", reply_markup=main_menu_kb())
        return MAIN_MENU
    try:
        gb = int(update.message.text.strip())
        if not (MIN_GB <= gb <= MAX_GB):
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            f"❌ عدد بین {MIN_GB} تا {MAX_GB} وارد کنید:", reply_markup=cancel_reply_kb()
        )
        return CUSTOM_GB_INPUT
    await _show_order_confirm(update.message, context, gb)
    return CONFIRM_ORDER


async def _show_order_confirm(msg_or_query, context: ContextTypes.DEFAULT_TYPE, gb: int):
    user_id = context._user_id if hasattr(context, '_user_id') else \
              (msg_or_query.from_user.id if hasattr(msg_or_query, "from_user") else
               msg_or_query.message.chat_id if hasattr(msg_or_query, "message") else 0)
    # get user_id properly
    if hasattr(msg_or_query, "from_user"):
        user_id = msg_or_query.from_user.id
    elif hasattr(msg_or_query, "chat"):
        user_id = msg_or_query.chat.id

    db_user = get_user(user_id) or {}
    vip_label, vip_disc = get_vip(db_user.get("total_spent", 0))
    extra_disc = context.user_data.get("discount_pct", 0)
    total_disc = min(vip_disc + extra_disc, 50)
    base_price = gb * PRICE_PER_GB
    discount_amt = int(base_price * total_disc / 100)
    total_price = base_price - discount_amt
    wallet_bal = get_wallet(user_id)
    wallet_ok = wallet_bal >= total_price

    context.user_data.update({
        "selected_gb": gb,
        "total_price": total_price,
        "discount_pct": total_disc,
    })

    disc_lines = ""
    if vip_disc:
        disc_lines += f"💎 تخفیف VIP ({vip_label}): {vip_disc}٪\n"
    if extra_disc:
        disc_lines += f"🎁 کد تخفیف: {extra_disc}٪\n"
    if discount_amt:
        disc_lines += f"💸 مبلغ تخفیف: -{fmt(discount_amt)}\n"

    text = (
        "📋 *خلاصه سفارش*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 حجم: {fmt_gb(gb)}\n"
        f"💰 قیمت پایه: {fmt(base_price)}\n"
        f"{disc_lines}"
        f"💳 *مبلغ نهایی: {fmt(total_price)}*\n"
        f"💼 موجودی کیف پول: {fmt(wallet_bal)}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = confirm_order_kb(gb, wallet_ok=wallet_ok)
    if hasattr(msg_or_query, "edit_message_text"):
        await msg_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await msg_or_query.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def handle_confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.message.reply_text("❌ لغو شد.", reply_markup=main_menu_kb())
        return MAIN_MENU
    if data == "back_buy":
        await query.edit_message_text("حجم مورد نظر را انتخاب کنید:", reply_markup=gb_packages_kb())
        return SELECT_GB
    if data == "apply_discount":
        await query.message.reply_text(
            "🎁 کد تخفیف خود را وارد کنید:", reply_markup=cancel_reply_kb()
        )
        return DISCOUNT_INPUT

    # پرداخت از کیف پول
    if data.startswith("pay_wallet_"):
        gb = int(data.split("_")[2])
        return await _process_wallet_payment(query, context, gb)

    # پرداخت با کارت
    if data.startswith("pay_card_"):
        gb = int(data.split("_")[2])
        total_price = context.user_data.get("total_price", gb * PRICE_PER_GB)
        await query.edit_message_text(
            "💳 *اطلاعات پرداخت*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 {fmt_gb(gb)}\n"
            f"💰 *مبلغ: {fmt(total_price)}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏦 {BANK_NAME}\n"
            f"💳 شماره کارت:\n`{CARD_NUMBER}`\n\n"
            f"👤 به نام: {CARD_HOLDER}\n\n"
            f"⚠️ دقیقاً *{fmt(total_price)}* واریز کنید.\n\n"
            "📸 عکس رسید را ارسال کنید:",
            parse_mode="Markdown", reply_markup=cancel_inline_kb()
        )
        return UPLOAD_RECEIPT

    return CONFIRM_ORDER


async def _process_wallet_payment(query, context, gb: int) -> int:
    user = query.from_user
    total_price = context.user_data.get("total_price", gb * PRICE_PER_GB)
    order_id = create_order(
        user_id=user.id, username=user.username, full_name=user.full_name,
        gb_amount=gb, total_price=total_price, paid_by_wallet=1
    )
    success = deduct_wallet(user.id, total_price, order_id)
    if not success:
        await query.answer("موجودی کافی نیست!", show_alert=True)
        return CONFIRM_ORDER

    # notify admin
    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        uname = f"@{user.username}" if user.username else "—"
        for aid in ADMIN_IDS:
            try:
                from keyboards import admin_order_kb
                await admin_bot.send_message(
                    chat_id=aid,
                    text=(
                        "🛍️ *سفارش جدید (کیف پول)*\n\n"
                        f"🆔 #{order_id}\n"
                        f"👤 {user.full_name} | {uname}\n"
                        f"📟 `{user.id}`\n"
                        f"📦 {fmt_gb(gb)}\n"
                        f"💰 {fmt(total_price)}\n"
                        "💼 *پرداخت از کیف پول — نیاز به تایید مبلغ ندارد*"
                    ),
                    parse_mode="Markdown",
                    reply_markup=admin_order_kb(order_id)
                )
            except Exception as e:
                logger.error("Wallet order notify failed: %s", e)

    await query.edit_message_text(
        f"✅ *سفارش #{order_id} ثبت شد!*\n\n"
        f"📦 {fmt_gb(gb)} | 💰 {fmt(total_price)}\n"
        "💼 پرداخت از کیف پول انجام شد.\n"
        "⏳ منتظر ارسال کانفیگ باشید.",
        parse_mode="Markdown"
    )
    context.user_data.clear()
    return MAIN_MENU


async def handle_discount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        await update.message.reply_text("❌ لغو شد.", reply_markup=main_menu_kb())
        return MAIN_MENU
    code = update.message.text.strip().upper()
    disc = get_discount_code(code)
    if not disc:
        await update.message.reply_text("❌ کد نامعتبر یا منقضی شده.\nدوباره وارد کنید:",
                                        reply_markup=cancel_reply_kb())
        return DISCOUNT_INPUT
    pct = disc["discount_pct"]
    context.user_data["discount_code"] = code
    context.user_data["discount_pct"] = pct
    gb = context.user_data.get("selected_gb", 0)
    await update.message.reply_text(
        f"✅ کد تخفیف *{pct}٪* اعمال شد!", parse_mode="Markdown"
    )
    if gb:
        await _show_order_confirm(update.message, context, gb)
        return CONFIRM_ORDER
    await update.message.reply_text("حالا حجم خود را انتخاب کنید:", reply_markup=gb_packages_kb())
    return SELECT_GB


async def handle_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("❌ لغو شد.", reply_markup=main_menu_kb())
        context.user_data.clear()
        return MAIN_MENU
    if not update.message.photo:
        await update.message.reply_text("📸 لطفاً عکس رسید ارسال کنید.",
                                        reply_markup=cancel_reply_kb())
        return UPLOAD_RECEIPT

    user = update.effective_user
    gb = context.user_data.get("selected_gb")
    total_price = context.user_data.get("total_price", (gb or 0) * PRICE_PER_GB)
    if not gb:
        await update.message.reply_text("خطا. دوباره /start بزنید.", reply_markup=main_menu_kb())
        return MAIN_MENU

    receipt_file_id = update.message.photo[-1].file_id
    order_id = create_order(
        user_id=user.id, username=user.username, full_name=user.full_name,
        gb_amount=gb, total_price=total_price, receipt_file_id=receipt_file_id
    )

    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        await _notify_admin_order(context.bot, admin_bot, order_id, user, gb, total_price, receipt_file_id)

    code = context.user_data.get("discount_code")
    if code:
        use_discount_code(code, user.id, order_id)

    await update.message.reply_text(
        f"✅ *سفارش #{order_id} ثبت شد!*\n\n"
        f"📦 {fmt_gb(gb)} | 💰 {fmt(total_price)}\n"
        "⏳ پس از بررسی رسید، کانفیگ ارسال می‌شود.\n\n"
        f"📞 پشتیبانی: {SUPPORT_USERNAME}",
        parse_mode="Markdown", reply_markup=main_menu_kb()
    )
    context.user_data.clear()
    return MAIN_MENU


async def _notify_admin_order(customer_bot, admin_bot, order_id, user, gb, total_price, receipt_file_id):
    from keyboards import admin_order_kb
    uname = f"@{user.username}" if user.username else "—"
    caption = (
        "🛍️ *سفارش جدید!*\n\n"
        f"🆔 #{order_id} | 📦 {fmt_gb(gb)} | 💰 {fmt(total_price)}\n"
        f"👤 {user.full_name} | {uname}\n"
        f"📟 `{user.id}`"
    )
    try:
        f = await customer_bot.get_file(receipt_file_id)
        buf = BytesIO(bytes(await f.download_as_bytearray()))
        buf.name = "receipt.jpg"
        for aid in ADMIN_IDS:
            try:
                await admin_bot.send_photo(
                    chat_id=aid, photo=buf, caption=caption,
                    parse_mode="Markdown", reply_markup=admin_order_kb(order_id)
                )
                buf.seek(0)
            except Exception as e:
                logger.error("Notify admin %s failed: %s", aid, e)
    except Exception as e:
        logger.error("Download receipt failed: %s", e)
        for aid in ADMIN_IDS:
            try:
                await admin_bot.send_message(
                    chat_id=aid,
                    text=caption + "\n\n⚠️ ارسال رسید ناموفق",
                    parse_mode="Markdown",
                    reply_markup=admin_order_kb(order_id)
                )
            except Exception as e2:
                logger.error("Fallback notify failed: %s", e2)


# ─── Wallet ───────────────────────────────────────────────────────────────────

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    bal = get_wallet(user.id)
    await update.message.reply_text(
        "💰 *کیف پول*\n\n"
        f"💼 موجودی: *{fmt(bal)}*\n\n"
        "با کیف پول می‌توانید بدون ارسال رسید خرید کنید.",
        parse_mode="Markdown", reply_markup=wallet_kb()
    )
    return MAIN_MENU


async def show_wallet_history(message, user_id: int):
    txs = get_wallet_history(user_id)
    if not txs:
        await message.reply_text("📋 تاریخچه‌ای وجود ندارد.")
        return
    text = "📋 *تاریخچه کیف پول*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for tx in txs:
        sign = "+" if tx["amount"] > 0 else ""
        label = TX_EMOJI.get(tx["type"], tx["type"])
        status = "✅" if tx["status"] == "approved" else ("⏳" if tx["status"] == "pending" else "❌")
        text += f"{status} {label}\n   {sign}{fmt(abs(tx['amount']))} | {fmt_dt(tx['created_at'])}\n\n"
    await message.reply_text(text, parse_mode="Markdown")


async def handle_wallet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        return await cmd_cancel(update, context)
    try:
        amount = int(update.message.text.strip().replace(",", ""))
        if amount < WALLET_MIN_CHARGE:
            await update.message.reply_text(
                f"❌ حداقل شارژ {fmt(WALLET_MIN_CHARGE)} است.", reply_markup=cancel_reply_kb()
            )
            return WALLET_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ عدد معتبر وارد کنید:", reply_markup=cancel_reply_kb())
        return WALLET_AMOUNT

    context.user_data["wallet_amount"] = amount
    await update.message.reply_text(
        f"💳 *شارژ کیف پول*\n\n"
        f"💰 مبلغ: *{fmt(amount)}*\n\n"
        f"🏦 {BANK_NAME}\n"
        f"💳 `{CARD_NUMBER}`\n"
        f"👤 {CARD_HOLDER}\n\n"
        "📸 عکس رسید را ارسال کنید:",
        parse_mode="Markdown", reply_markup=cancel_reply_kb()
    )
    return WALLET_RECEIPT


async def handle_wallet_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        return await cmd_cancel(update, context)
    if not update.message.photo:
        await update.message.reply_text("📸 لطفاً عکس رسید ارسال کنید.", reply_markup=cancel_reply_kb())
        return WALLET_RECEIPT

    user = update.effective_user
    amount = context.user_data.get("wallet_amount", 0)
    receipt_file_id = update.message.photo[-1].file_id
    tx_id = create_wallet_charge(user.id, amount, receipt_file_id)

    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        uname = f"@{user.username}" if user.username else "—"
        caption = (
            "💳 *درخواست شارژ کیف پول*\n\n"
            f"🆔 تراکنش #{tx_id}\n"
            f"👤 {user.full_name} | {uname}\n"
            f"📟 `{user.id}`\n"
            f"💰 مبلغ: *{fmt(amount)}*"
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
                        parse_mode="Markdown", reply_markup=admin_wallet_kb(tx_id)
                    )
                    buf.seek(0)
                except Exception as e:
                    logger.error("Wallet notify admin %s: %s", aid, e)
        except Exception as e:
            logger.error("Wallet receipt download: %s", e)

    await update.message.reply_text(
        f"✅ درخواست شارژ *{fmt(amount)}* ثبت شد.\n"
        f"🆔 شماره تراکنش: #{tx_id}\n\n"
        "پس از تایید ادمین به کیف پول اضافه می‌شود.",
        parse_mode="Markdown", reply_markup=main_menu_kb()
    )
    context.user_data.clear()
    return MAIN_MENU


# ─── Referral ─────────────────────────────────────────────────────────────────

async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id)
    if not db_user:
        return
    code = db_user.get("referral_code", "—")
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={code}"

    from config import REFERRAL_BONUS_GB, REFERRAL_BONUS_TOMAN
    bonus_text = ""
    if REFERRAL_BONUS_TOMAN:
        bonus_text = f"🎁 جایزه هر دو طرف: {fmt(REFERRAL_BONUS_TOMAN)}\n"
    elif REFERRAL_BONUS_GB:
        bonus_text = f"🎁 جایزه: {REFERRAL_BONUS_GB} گیگابایت هدیه\n"

    await update.message.reply_text(
        "👥 *دعوت دوستان*\n\n"
        f"{bonus_text}"
        "وقتی دوستتان اولین خرید را انجام دهد، هر دو جایزه می‌گیرید!\n\n"
        f"🔗 لینک اختصاصی شما:\n`{ref_link}`\n\n"
        "لینک بالا را کپی کنید و برای دوستانتان بفرستید.",
        parse_mode="Markdown"
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
    nxt_line = f"⬆️ تا {nxt[0]}: {fmt(nxt[1])}" if nxt else "💎 بالاترین سطح!"

    await update.message.reply_text(
        "👤 *پروفایل من*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 نام: {user.full_name}\n"
        f"🔗 یوزرنیم: @{user.username or '—'}\n"
        f"📅 عضویت: {fmt_dt(db_user.get('join_date',''))}\n\n"
        f"💎 سطح: *{vip_label}*\n"
        f"{'🔖 تخفیف: ' + str(vip_disc) + '٪' if vip_disc else ''}\n"
        f"📊 {bar}\n"
        f"{nxt_line}\n\n"
        f"🛍️ تعداد سفارش: {db_user.get('total_orders', 0)}\n"
        f"💰 کل خرید: {fmt(spent)}\n"
        f"💼 کیف پول: {fmt(db_user.get('wallet_balance', 0))}",
        parse_mode="Markdown"
    )


# ─── Trial ────────────────────────────────────────────────────────────────────

async def request_trial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db_user = get_user(user.id)
    if not FREE_TRIAL_ENABLED:
        await update.message.reply_text("آزمایش رایگان فعال نیست.")
        return MAIN_MENU
    if db_user and db_user.get("free_trial_used"):
        await update.message.reply_text("❌ قبلاً از آزمایش رایگان استفاده کرده‌اید.")
        return MAIN_MENU

    order_id = create_order(
        user_id=user.id, username=user.username, full_name=user.full_name,
        gb_amount=FREE_TRIAL_GB, total_price=0, is_trial=1
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
                        "🎯 *درخواست آزمایش رایگان*\n\n"
                        f"🆔 #{order_id}\n"
                        f"👤 {user.full_name} | {uname}\n"
                        f"📦 {FREE_TRIAL_GB} گیگابایت رایگان"
                    ),
                    parse_mode="Markdown",
                    reply_markup=admin_order_kb(order_id)
                )
            except Exception as e:
                logger.error("Trial notify %s: %s", aid, e)

    await update.message.reply_text(
        f"🎯 *درخواست آزمایش رایگان ثبت شد!*\n\n"
        f"📦 {FREE_TRIAL_GB} گیگابایت\n"
        "پس از تایید ادمین، کانفیگ ارسال می‌شود.",
        parse_mode="Markdown", reply_markup=main_menu_kb()
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
                        f"💬 *تیکت #{tid}*\n\n"
                        f"👤 {user.full_name} | {uname} | `{user.id}`\n\n"
                        f"📝 {update.message.text}\n\n"
                        f"پاسخ: `/reply_{tid} متن`"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error("Support notify %s: %s", aid, e)

    await update.message.reply_text(
        f"✅ تیکت *#{tid}* ثبت شد. به زودی پاسخ می‌گیرید.",
        parse_mode="Markdown", reply_markup=main_menu_kb()
    )
    return MAIN_MENU


# ─── About ────────────────────────────────────────────────────────────────────

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import BOT_CHANNEL
    await update.message.reply_text(
        f"ℹ️ *{BOT_NAME}*\n\n"
        "🔒 پروتکل: VLESS + XTLS/Reality\n"
        "⚡ سرعت بالا | پینگ کم\n"
        "🌍 سرورهای اختصاصی\n"
        "✅ ضمانت کیفیت\n"
        "🔄 پشتیبانی آنلاین\n\n"
        f"💰 {fmt(PRICE_PER_GB)} / گیگابایت\n"
        f"📦 {MIN_GB} تا {MAX_GB} گیگابایت\n\n"
        f"📢 کانال: {BOT_CHANNEL}\n"
        f"💬 پشتیبانی: {SUPPORT_USERNAME}",
        parse_mode="Markdown"
    )


# ─── Deliver config to customer (called from admin_bot) ───────────────────────

async def deliver_config(customer_bot, order: dict, config: str, sub_link: str):
    uid = order["user_id"]
    is_trial = order.get("is_trial", 0)
    trial_line = "🎯 *آزمایش رایگان*\n" if is_trial else ""

    try:
        await customer_bot.send_message(
            uid,
            f"🎉 *{'آزمایش رایگان' if is_trial else 'سفارش'} شما تایید شد!*\n"
            f"{trial_line}\n"
            f"🆔 سفارش #{order['id']}\n"
            f"📦 {fmt_gb(order['gb_amount'])}\n"
            + (f"📅 انقضا: `{order.get('expiry_date','—')}`\n" if order.get('expiry_date') else "")
            + "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 *کانفیگ VLESS:*\n"
            f"`{config}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("Config delivery failed: %s", e)
        return

    if sub_link:
        try:
            await customer_bot.send_message(
                uid, f"🔗 *لینک Subscription:*\n`{sub_link}`", parse_mode="Markdown"
            )
        except Exception as e:
            logger.error("Sub link delivery: %s", e)

    # راهنما
    try:
        await customer_bot.send_message(
            uid,
            "📚 *راهنمای نصب سریع:*\n\n"
            "🍎 آیفون: *NPV Tunnel* یا *V2Box* (App Store)\n"
            "🤖 اندروید: *V2RayNG* یا *Hiddify* (Play Store)\n"
            "🪟 ویندوز: *V2RayN* (GitHub)\n\n"
            "در ربات روی 📚 *راهنمای نصب* بزنید برای راهنمای کامل.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("Guide delivery: %s", e)

    # درخواست امتیاز
    try:
        await customer_bot.send_message(
            uid,
            "⭐ *نظر شما مهمه!*\n\nبه سرویس ما امتیاز بدید:",
            parse_mode="Markdown",
            reply_markup=rating_kb(order["id"])
        )
    except Exception as e:
        logger.error("Rating request: %s", e)


# ─── Setup ────────────────────────────────────────────────────────────────────

def setup_customer_bot(app: Application, admin_bot_instance=None) -> None:
    if admin_bot_instance:
        app.bot_data["admin_bot_instance"] = admin_bot_instance

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
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
    logger.info("Customer bot ready.")
