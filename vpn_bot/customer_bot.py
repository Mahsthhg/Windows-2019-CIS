"""
Customer-facing Telegram bot.
Handles: purchase flow, order history, guides, support, discount codes.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes,
)
from config import (
    PRICE_PER_GB, MIN_GB, MAX_GB,
    CARD_NUMBER, CARD_HOLDER, BANK_NAME,
    BOT_NAME, SUPPORT_USERNAME,
    FORCE_JOIN_ENABLED, FORCE_JOIN_CHANNELS,
)
from database import (
    upsert_user, get_user, get_user_orders, get_order,
    create_order, create_ticket, get_discount_code,
)
from keyboards import (
    main_menu_kb, cancel_reply_kb, cancel_inline_kb,
    gb_packages_kb, confirm_order_kb, guide_kb, order_detail_kb,
)
from guides import GUIDES

logger = logging.getLogger(__name__)

# ─── Conversation states ──────────────────────────────────────────────────────
(
    MAIN_MENU,
    SELECT_GB,
    CUSTOM_GB_INPUT,
    CONFIRM_ORDER,
    UPLOAD_RECEIPT,
    SUPPORT_MESSAGE,
    DISCOUNT_INPUT,
) = range(7)


# ─── Helpers ──────────────────────────────────────────────────────────────────

STATUS_EMOJI = {
    "pending":  "⏳",
    "approved": "✅",
    "rejected": "❌",
}
STATUS_LABEL = {
    "pending":  "در انتظار بررسی",
    "approved": "تایید شده",
    "rejected": "رد شده",
}

def fmt_price(p: int) -> str:
    return f"{p:,} تومان"


async def _send_to_main_menu(update: Update, text: str = "منوی اصلی:") -> None:
    await update.effective_message.reply_text(text, reply_markup=main_menu_kb())


# ─── Force Join ───────────────────────────────────────────────────────────────

async def _get_unjoined_channels(bot, user_id: int) -> list[str]:
    """کانال‌هایی که کاربر عضو آن‌ها نیست را برمی‌گرداند."""
    unjoined = []
    for channel in FORCE_JOIN_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ("left", "kicked", "banned"):
                unjoined.append(channel)
        except Exception:
            # اگر بات ادمین کانال نباشد یا خطایی رخ دهد، رد می‌کنیم
            unjoined.append(channel)
    return unjoined


def _join_required_keyboard(channels: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        label = ch if ch.startswith("@") else f"@{ch}"
        # لینک عمومی کانال
        url = f"https://t.me/{label.lstrip('@')}"
        buttons.append([InlineKeyboardButton(f"📢 عضویت در {label}", url=url)])
    buttons.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])
    return InlineKeyboardMarkup(buttons)


async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    True  → کاربر عضو همه کانال‌هاست، ادامه بده.
    False → عضو نیست، پیام نمایش داده شد، handler باید return کند.
    """
    if not FORCE_JOIN_ENABLED or not FORCE_JOIN_CHANNELS:
        return True

    user_id = update.effective_user.id
    unjoined = await _get_unjoined_channels(context.bot, user_id)

    if not unjoined:
        return True

    channels_text = "\n".join(f"• {ch}" for ch in unjoined)
    msg = (
        "⛔ *برای استفاده از ربات باید عضو کانال زیر باشید:*\n\n"
        f"{channels_text}\n\n"
        "بعد از عضویت روی دکمه *✅ عضو شدم* بزنید."
    )
    kb = _join_required_keyboard(unjoined)

    if update.callback_query:
        await update.callback_query.answer("ابتدا عضو کانال شوید!", show_alert=True)
        await update.callback_query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    return False


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    upsert_user(user.id, user.username, user.full_name)
    context.user_data.clear()

    if not await check_membership(update, context):
        return MAIN_MENU

    text = (
        f"👋 سلام {user.first_name} عزیز!\n\n"
        f"🌐 به *{BOT_NAME}* خوش آمدید!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ سریع‌ترین و پایدارترین کانفیگ‌های VLESS\n"
        f"💰 قیمت: {fmt_price(PRICE_PER_GB)} / گیگابایت\n"
        f"📦 حداقل: {MIN_GB} گیگ  |  حداکثر: {MAX_GB} گیگ\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "لطفاً از منوی زیر انتخاب کنید:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())
    return MAIN_MENU


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await _send_to_main_menu(update, "❌ عملیات لغو شد.")
    return MAIN_MENU


# ─── Main menu dispatcher ─────────────────────────────────────────────────────

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text

    if text == "❌ انصراف":
        context.user_data.clear()
        await _send_to_main_menu(update, "منوی اصلی:")
        return MAIN_MENU

    if not await check_membership(update, context):
        return MAIN_MENU

    if text == "🛒 خرید کانفیگ":
        msg = (
            "🛒 *خرید کانفیگ VPN*\n\n"
            f"💰 قیمت: {fmt_price(PRICE_PER_GB)} / گیگابایت\n"
            f"📦 حداقل خرید: {MIN_GB} گیگابایت\n\n"
            "لطفاً حجم مورد نظر را انتخاب کنید:"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=gb_packages_kb())
        return SELECT_GB

    if text == "📦 سفارشات من":
        await show_orders(update, context)
        return MAIN_MENU

    if text == "📚 راهنمای نصب":
        await update.message.reply_text(
            "📚 پلتفرم مورد نظر را انتخاب کنید:",
            reply_markup=guide_kb()
        )
        return MAIN_MENU

    if text == "💬 پشتیبانی":
        await update.message.reply_text(
            "💬 *پشتیبانی*\n\n"
            "پیام خود را تایپ کنید.\n"
            "تیم پشتیبانی در کمترین زمان پاسخ می‌دهد.\n\n"
            "برای لغو بزنید /cancel",
            parse_mode="Markdown",
            reply_markup=cancel_reply_kb()
        )
        return SUPPORT_MESSAGE

    if text == "🎁 کد تخفیف":
        await update.message.reply_text(
            "🎁 *کد تخفیف*\n\n"
            "کد تخفیف خود را وارد کنید:\n"
            "(برای لغو: /cancel)",
            parse_mode="Markdown",
            reply_markup=cancel_reply_kb()
        )
        return DISCOUNT_INPUT

    if text == "ℹ️ درباره ما":
        await show_about(update, context)
        return MAIN_MENU

    return MAIN_MENU


# ─── Callback: guides & misc ──────────────────────────────────────────────────

async def handle_inline_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── بررسی مجدد عضویت بعد از کلیک "عضو شدم" ──
    if data == "check_join":
        if not FORCE_JOIN_ENABLED or not FORCE_JOIN_CHANNELS:
            await query.message.reply_text("✅ دسترسی تایید شد!", reply_markup=main_menu_kb())
            return MAIN_MENU

        unjoined = await _get_unjoined_channels(context.bot, query.from_user.id)
        if unjoined:
            channels_text = "\n".join(f"• {ch}" for ch in unjoined)
            await query.answer("هنوز عضو نشدید!", show_alert=True)
            await query.edit_message_text(
                "❌ *هنوز عضو کانال زیر نشدید:*\n\n"
                f"{channels_text}\n\n"
                "بعد از عضویت دوباره بزنید.",
                parse_mode="Markdown",
                reply_markup=_join_required_keyboard(unjoined)
            )
        else:
            await query.edit_message_text("✅ عضویت تایید شد!")
            user = query.from_user
            text = (
                f"👋 سلام {user.first_name} عزیز!\n\n"
                f"🌐 به *{BOT_NAME}* خوش آمدید!\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 قیمت: {fmt_price(PRICE_PER_GB)} / گیگابایت\n"
                f"📦 حداقل: {MIN_GB} گیگ  |  حداکثر: {MAX_GB} گیگ\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "لطفاً از منوی زیر انتخاب کنید:"
            )
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())
        return MAIN_MENU

    if data in GUIDES:
        await query.message.reply_text(GUIDES[data], reply_markup=guide_kb())
        return MAIN_MENU

    if data == "back_main":
        await query.message.reply_text("منوی اصلی:", reply_markup=main_menu_kb())
        return MAIN_MENU

    if data.startswith("viewconfig_"):
        order_id = int(data.split("_")[1])
        order = get_order(order_id)
        if order and order["status"] == "approved":
            config_text = (
                f"📋 کانفیگ سفارش #{order_id}\n\n"
                f"```\n{order['config']}\n```"
            )
            await query.message.reply_text(config_text, parse_mode="Markdown")
            if order.get("sub_link"):
                await query.message.reply_text(
                    f"🔗 لینک Subscription:\n`{order['sub_link']}`",
                    parse_mode="Markdown"
                )
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
        await query.edit_message_text(
            "🛒 حجم مورد نظر را انتخاب کنید:", reply_markup=gb_packages_kb()
        )
        return SELECT_GB

    if data == "cancel":
        await query.message.reply_text("❌ خرید لغو شد.", reply_markup=main_menu_kb())
        return MAIN_MENU

    if data == "buy_custom":
        await query.edit_message_text(
            f"✏️ *حجم دلخواه*\n\n"
            f"عددی بین {MIN_GB} تا {MAX_GB} وارد کنید (گیگابایت):",
            parse_mode="Markdown",
            reply_markup=cancel_inline_kb()
        )
        return CUSTOM_GB_INPUT

    if data.startswith("buy_"):
        gb = int(data.split("_")[1])
        await _show_order_summary(query, context, gb)
        return CONFIRM_ORDER

    return SELECT_GB


async def _show_order_summary(query_or_msg, context: ContextTypes.DEFAULT_TYPE, gb: int) -> None:
    discount = context.user_data.get("discount_pct", 0)
    base_price = gb * PRICE_PER_GB
    discount_amount = int(base_price * discount / 100)
    total_price = base_price - discount_amount
    context.user_data["selected_gb"] = gb
    context.user_data["total_price"] = total_price

    discount_line = ""
    if discount:
        discount_line = f"🎁 تخفیف {discount}٪: -{fmt_price(discount_amount)}\n"

    text = (
        "📋 *خلاصه سفارش*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 حجم: {gb} گیگابایت\n"
        f"💰 قیمت پایه: {fmt_price(base_price)}\n"
        f"{discount_line}"
        f"💳 *مبلغ قابل پرداخت: {fmt_price(total_price)}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "آیا تایید می‌کنید؟"
    )
    kb = confirm_order_kb(gb)
    if hasattr(query_or_msg, "edit_message_text"):
        await query_or_msg.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await query_or_msg.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def handle_custom_gb_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        await _send_to_main_menu(update, "❌ خرید لغو شد.")
        return MAIN_MENU

    try:
        gb = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            f"❌ لطفاً یک عدد معتبر وارد کنید (بین {MIN_GB} تا {MAX_GB}):",
            reply_markup=cancel_reply_kb()
        )
        return CUSTOM_GB_INPUT

    if not (MIN_GB <= gb <= MAX_GB):
        await update.message.reply_text(
            f"❌ حجم باید بین {MIN_GB} و {MAX_GB} گیگابایت باشد.\nمجدداً وارد کنید:",
            reply_markup=cancel_reply_kb()
        )
        return CUSTOM_GB_INPUT

    await _show_order_summary(update.message, context, gb)
    return CONFIRM_ORDER


async def handle_confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.message.reply_text("❌ خرید لغو شد.", reply_markup=main_menu_kb())
        return MAIN_MENU

    if data == "back_buy":
        await query.edit_message_text(
            "🛒 حجم مورد نظر را انتخاب کنید:", reply_markup=gb_packages_kb()
        )
        return SELECT_GB

    if data.startswith("confirm_"):
        gb = int(data.split("_")[1])
        context.user_data["selected_gb"] = gb
        total_price = context.user_data.get("total_price", gb * PRICE_PER_GB)

        text = (
            "💳 *اطلاعات پرداخت*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 حجم: {gb} گیگابایت\n"
            f"💰 مبلغ: *{fmt_price(total_price)}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏦 بانک: {BANK_NAME}\n"
            f"💳 شماره کارت:\n`{CARD_NUMBER}`\n\n"
            f"👤 به نام: {CARD_HOLDER}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ دقیقاً *{fmt_price(total_price)}* واریز کنید.\n\n"
            "📸 بعد از واریز، *عکس رسید* را ارسال کنید:"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=cancel_inline_kb())
        return UPLOAD_RECEIPT

    return CONFIRM_ORDER


async def handle_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Handle inline cancel
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("❌ خرید لغو شد.", reply_markup=main_menu_kb())
        context.user_data.clear()
        return MAIN_MENU

    if not update.message.photo:
        await update.message.reply_text(
            "📸 لطفاً *عکس* رسید پرداخت را ارسال کنید.",
            parse_mode="Markdown",
            reply_markup=cancel_reply_kb()
        )
        return UPLOAD_RECEIPT

    user = update.effective_user
    gb = context.user_data.get("selected_gb")
    total_price = context.user_data.get("total_price", (gb or 0) * PRICE_PER_GB)

    if not gb:
        await _send_to_main_menu(update, "خطا رخ داد. لطفاً دوباره شروع کنید.")
        return MAIN_MENU

    receipt_file_id = update.message.photo[-1].file_id
    order_id = create_order(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        gb_amount=gb,
        total_price=total_price,
        receipt_file_id=receipt_file_id,
    )

    # Notify admin via shared reference
    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        await _notify_admin(context.bot, admin_bot, order_id, user, gb, total_price, receipt_file_id)

    await update.message.reply_text(
        "✅ *سفارش شما ثبت شد!*\n\n"
        f"🆔 شماره سفارش: *#{order_id}*\n"
        f"📦 حجم: {gb} گیگابایت\n"
        f"💰 مبلغ: {fmt_price(total_price)}\n\n"
        "⏳ سفارش در حال بررسی است.\n"
        "پس از تایید، کانفیگ ارسال می‌شود.\n\n"
        f"📞 پشتیبانی: {SUPPORT_USERNAME}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )
    context.user_data.clear()
    return MAIN_MENU


async def _notify_admin(customer_bot, admin_bot, order_id, user, gb, total_price, receipt_file_id):
    """
    file_id های Telegram به ربات دریافت‌کننده وابسته‌اند.
    رسید را از طریق ربات مشتری دانلود، سپس با ربات ادمین آپلود می‌کنیم.
    """
    from config import ADMIN_CHAT_ID
    from keyboards import admin_new_order_kb
    from io import BytesIO

    uname = f"@{user.username}" if user.username else "—"
    caption = (
        "🛍️ *سفارش جدید!*\n\n"
        f"🆔 سفارش: #{order_id}\n"
        f"👤 نام: {user.full_name}\n"
        f"🔗 یوزرنیم: {uname}\n"
        f"📟 آیدی: `{user.id}`\n"
        f"📦 حجم: {gb} گیگابایت\n"
        f"💰 مبلغ: {fmt_price(total_price)}"
    )
    try:
        # دانلود فایل از طریق ربات مشتری (که file_id برایش معتبر است)
        tg_file = await customer_bot.get_file(receipt_file_id)
        file_bytes = await tg_file.download_as_bytearray()
        photo_buf = BytesIO(bytes(file_bytes))
        photo_buf.name = "receipt.jpg"

        # آپلود از طریق ربات ادمین (تا دکمه‌های inline کار کنند)
        await admin_bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo_buf,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=admin_new_order_kb(order_id)
        )
    except Exception as e:
        logger.error("Failed to notify admin: %s", e)
        # Fallback: متن بدون عکس
        try:
            await admin_bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=caption + "\n\n⚠️ ارسال رسید ناموفق بود.",
                parse_mode="Markdown",
                reply_markup=admin_new_order_kb(order_id)
            )
        except Exception as e2:
            logger.error("Admin fallback also failed: %s", e2)


# ─── Support ──────────────────────────────────────────────────────────────────

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        await _send_to_main_menu(update, "❌ لغو شد.")
        return MAIN_MENU

    user = update.effective_user
    msg = update.message.text
    ticket_id = create_ticket(user.id, user.username, user.full_name, msg)

    admin_bot = context.bot_data.get("admin_bot_instance")
    if admin_bot:
        from config import ADMIN_CHAT_ID
        from keyboards import admin_cancel_kb
        uname = f"@{user.username}" if user.username else "—"
        notif = (
            f"💬 *تیکت پشتیبانی جدید* — #{ticket_id}\n\n"
            f"👤 {user.full_name}\n"
            f"🔗 {uname} | `{user.id}`\n\n"
            f"📝 پیام:\n{msg}\n\n"
            f"برای پاسخ: `/reply_{ticket_id} متن پاسخ`"
        )
        try:
            await admin_bot.send_message(ADMIN_CHAT_ID, notif, parse_mode="Markdown")
        except Exception as e:
            logger.error("Support notify failed: %s", e)

    await update.message.reply_text(
        f"✅ پیام شما با شماره تیکت *#{ticket_id}* ثبت شد.\n"
        "پشتیبانی به زودی پاسخ می‌دهد.",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )
    return MAIN_MENU


# ─── Discount codes ───────────────────────────────────────────────────────────

async def handle_discount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text in ("❌ انصراف", "/cancel"):
        await _send_to_main_menu(update, "❌ لغو شد.")
        return MAIN_MENU

    code = update.message.text.strip().upper()
    discount = get_discount_code(code)
    if not discount:
        await update.message.reply_text(
            "❌ کد تخفیف معتبر نیست یا قبلاً استفاده شده.\n"
            "مجدداً وارد کنید یا /cancel بزنید:",
            reply_markup=cancel_reply_kb()
        )
        return DISCOUNT_INPUT

    pct = discount["discount_pct"]
    context.user_data["discount_code"] = code
    context.user_data["discount_pct"] = pct
    await update.message.reply_text(
        f"✅ کد تخفیف *{pct}٪* اعمال شد!\n\n"
        "حالا برو خرید کانفیگ 🛒",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )
    return MAIN_MENU


# ─── Orders list ─────────────────────────────────────────────────────────────

async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    orders = get_user_orders(user.id)
    if not orders:
        await update.message.reply_text(
            "📦 شما هنوز سفارشی ثبت نکرده‌اید.\n\n"
            "برای خرید روی 🛒 خرید کانفیگ بزنید.",
            reply_markup=main_menu_kb()
        )
        return

    text = "📦 *سفارشات شما:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "❓")
        label = STATUS_LABEL.get(o["status"], o["status"])
        text += (
            f"{emoji} سفارش *#{o['id']}*\n"
            f"   📦 {o['gb_amount']} گیگ | 💰 {fmt_price(o['total_price'])}\n"
            f"   وضعیت: {label}\n"
            f"   تاریخ: {o['created_at'][:16]}\n\n"
        )
        if o["status"] == "approved":
            buttons.append([InlineKeyboardButton(
                f"📋 مشاهده کانفیگ #{o['id']}", callback_data=f"viewconfig_{o['id']}"
            )])

    kb = InlineKeyboardMarkup(buttons) if buttons else None
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb or main_menu_kb())


# ─── About ────────────────────────────────────────────────────────────────────

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"ℹ️ *{BOT_NAME}*\n\n"
        "🌐 ارائه‌دهنده بهترین کانفیگ‌های VLESS\n\n"
        "✅ پروتکل: VLESS + XTLS/Reality\n"
        "✅ سرعت بالا و پینگ پایین\n"
        "✅ پشتیبانی ۲۴/۷\n"
        "✅ ضمانت کیفیت\n\n"
        f"💬 پشتیبانی: {SUPPORT_USERNAME}\n\n"
        f"📦 قیمت: {fmt_price(PRICE_PER_GB)} / گیگابایت\n"
        f"📦 حداقل خرید: {MIN_GB} گیگ\n"
        f"📦 حداکثر خرید: {MAX_GB} گیگ"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())


# ─── Wire up ──────────────────────────────────────────────────────────────────

def setup_customer_bot(app: Application, admin_bot_instance=None) -> None:
    if admin_bot_instance:
        app.bot_data["admin_bot_instance"] = admin_bot_instance

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
        ],
        states={
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
                CallbackQueryHandler(handle_inline_main),
            ],
            SELECT_GB: [
                CallbackQueryHandler(handle_gb_selection),
            ],
            CUSTOM_GB_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_gb_input),
                CallbackQueryHandler(handle_gb_selection, pattern="^cancel$"),
            ],
            CONFIRM_ORDER: [
                CallbackQueryHandler(handle_confirm_order),
            ],
            UPLOAD_RECEIPT: [
                MessageHandler(filters.PHOTO, handle_receipt_upload),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_receipt_upload),
                CallbackQueryHandler(handle_receipt_upload, pattern="^cancel$"),
            ],
            SUPPORT_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_support_message),
            ],
            DISCOUNT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_discount_input),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("start",  cmd_start),
        ],
        allow_reentry=True,
        name="customer_conv",
        persistent=False,
    )

    app.add_handler(conv)
    logger.info("Customer bot handlers registered.")
