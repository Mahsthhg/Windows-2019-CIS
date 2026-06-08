"""ربات ادمین — مدیریت سفارشات، کیف پول، قالب‌ها، آمار، پیام همگانی."""
import logging
import re
from io import BytesIO, StringIO
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from config import ADMIN_IDS, PRICE_PER_GB, BOT_NAME, PANEL_ENABLED, PANEL_DEFAULT_DAYS
from database import (
    get_order, get_pending_orders, get_all_users, get_user,
    approve_order, reject_order, get_stats, close_ticket, get_open_tickets,
    block_user, unblock_user, create_discount_code, add_order_note,
    get_templates, get_template, save_template, delete_template, use_template,
    approve_wallet_charge, reject_wallet_charge, get_pending_wallet_charges,
    admin_adjust_wallet, search_orders, export_orders_csv,
)
from keyboards import (
    admin_main_kb, admin_cancel_kb, admin_order_kb,
    admin_wallet_kb, admin_templates_kb,
)
from utils import fmt, fmt_gb, fmt_dt, get_vip, STATUS_EMOJI, STATUS_LABEL, STAR_MAP

logger = logging.getLogger(__name__)

# ─── State keys ───────────────────────────────────────────────────────────────
ST          = "adm_st"
PENDING_OID = "adm_oid"
PENDING_CFG = "adm_cfg"

S_IDLE          = "idle"
S_WAIT_CFG      = "wait_cfg"
S_WAIT_SUB      = "wait_sub"
S_WAIT_EXPIRY   = "wait_expiry"
S_WAIT_REJECT   = "wait_reject"
S_WAIT_BROADCAST= "wait_broadcast"
S_WAIT_DISCOUNT = "wait_discount"
S_WAIT_TPL_NAME = "wait_tpl_name"
S_WAIT_TPL_CFG  = "wait_tpl_cfg"
S_WAIT_TPL_SUB  = "wait_tpl_sub"
S_WAIT_SEARCH   = "wait_search"
S_WAIT_NOTE     = "wait_note"
S_WAIT_WALLET_ADJ = "wait_wallet_adj"


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def admin_only(fn):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.effective_message.reply_text("⛔ دسترسی مجاز نیست.")
            return
        return await fn(update, context)
    return wrapper


# ─── /start ───────────────────────────────────────────────────────────────────

@admin_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_IDLE
    s = get_stats()
    await update.message.reply_text(
        f"👑 *پنل ادمین — {BOT_NAME}*\n\n"
        f"⏳ سفارش در انتظار: {s['pending_orders']}\n"
        f"💬 تیکت باز: {s['open_tickets']}\n"
        f"👥 کاربران: {s['total_users']:,}\n\n"
        "سفارشات جدید به‌صورت خودکار اطلاع‌رسانی می‌شوند.",
        parse_mode="Markdown",
        reply_markup=admin_main_kb()
    )


@admin_only
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_IDLE
    context.user_data.pop(PENDING_OID, None)
    context.user_data.pop(PENDING_CFG, None)
    await update.message.reply_text("❌ لغو شد.", reply_markup=admin_main_kb())


# ─── Callback handler ─────────────────────────────────────────────────────────

@admin_only
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "adm_cancel":
        context.user_data[ST] = S_IDLE
        await query.message.reply_text("❌ لغو شد.", reply_markup=admin_main_kb())
        return

    # ── Order approve ──
    if data.startswith("adm_approve_"):
        order_id = int(data.split("_")[2])
        order = get_order(order_id)
        if not order:
            await query.message.reply_text("❌ سفارش پیدا نشد.")
            return
        if order["status"] != "pending":
            await query.answer(f"وضعیت: {STATUS_LABEL.get(order['status'])}", show_alert=True)
            return
        context.user_data[ST] = S_WAIT_EXPIRY
        context.user_data[PENDING_OID] = order_id
        await query.edit_message_reply_markup(reply_markup=None)

        if PANEL_ENABLED:
            await query.message.reply_text(
                f"✅ سفارش *#{order_id}* در حال تایید\n\n"
                "🤖 تعداد روز انقضا را وارد کنید (پیش‌فرض: "
                f"{PANEL_DEFAULT_DAYS}):\n"
                "(یا `-` برای پیش‌فرض)\n(/cancel برای لغو)",
                parse_mode="Markdown", reply_markup=admin_cancel_kb()
            )
        else:
            templates = get_templates()
            if templates:
                await query.message.reply_text(
                    f"✅ سفارش *#{order_id}* — قالب کانفیگ را انتخاب کنید:",
                    parse_mode="Markdown",
                    reply_markup=admin_templates_kb(templates)
                )
            else:
                context.user_data[ST] = S_WAIT_CFG
                await query.message.reply_text(
                    f"✅ سفارش *#{order_id}*\n\n📤 کانفیگ VLESS را ارسال کنید:\n(/cancel)",
                    parse_mode="Markdown", reply_markup=admin_cancel_kb()
                )
        return

    # ── Template selection for order ──
    if data.startswith("adm_tpl_"):
        order_id = context.user_data.get(PENDING_OID)
        if not order_id:
            await query.answer("خطا: سفارشی انتخاب نشده.", show_alert=True)
            return
        if data == "adm_tpl_manual":
            context.user_data[ST] = S_WAIT_CFG
            await query.edit_message_text(
                "📤 کانفیگ VLESS را ارسال کنید:", reply_markup=admin_cancel_kb()
            )
            return
        tpl_id = int(data.split("_")[2])
        tpl = get_template(tpl_id)
        if not tpl:
            await query.answer("قالب پیدا نشد.", show_alert=True)
            return
        use_template(tpl_id)
        order = get_order(order_id)
        result = approve_order(order_id, tpl["config"], tpl.get("sub_link",""))
        customer_bot = context.bot_data.get("customer_bot_instance")
        if customer_bot and order:
            from customer_bot import deliver_config
            order["config"]    = tpl["config"]
            order["sub_link"]  = tpl.get("sub_link","")
            await deliver_config(customer_bot, order, tpl["config"], tpl.get("sub_link",""))
        await query.edit_message_text(
            f"✅ سفارش *#{order_id}* تایید شد (قالب: {tpl['name']}).",
            parse_mode="Markdown"
        )
        return

    # ── Order reject ──
    if data.startswith("adm_reject_"):
        order_id = int(data.split("_")[2])
        order = get_order(order_id)
        if not order or order["status"] != "pending":
            await query.answer("قابل رد نیست.", show_alert=True)
            return
        context.user_data[ST] = S_WAIT_REJECT
        context.user_data[PENDING_OID] = order_id
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"❌ دلیل رد سفارش *#{order_id}* را بنویسید:\n(یا `-` بدون دلیل)\n(/cancel)",
            parse_mode="Markdown", reply_markup=admin_cancel_kb()
        )
        return

    # ── Order note ──
    if data.startswith("adm_note_"):
        order_id = int(data.split("_")[2])
        context.user_data[ST] = S_WAIT_NOTE
        context.user_data[PENDING_OID] = order_id
        await query.message.reply_text(
            f"📝 یادداشت برای سفارش #{order_id}:", reply_markup=admin_cancel_kb()
        )
        return

    # ── User profile ──
    if data.startswith("adm_profile_"):
        order_id = int(data.split("_")[2])
        order = get_order(order_id)
        if not order:
            return
        await _show_user_profile(query.message, order["user_id"])
        return

    # ── Wallet approve/reject ──
    if data.startswith("adm_wapprove_"):
        tx_id = int(data.split("_")[2])
        tx = approve_wallet_charge(tx_id)
        if tx:
            customer_bot = context.bot_data.get("customer_bot_instance")
            if customer_bot:
                try:
                    await customer_bot.send_message(
                        tx["user_id"],
                        f"✅ شارژ *{fmt(tx['amount'])}* به کیف پول شما اضافه شد!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error("Wallet approve notify: %s", e)
            await query.edit_message_caption(
                caption=(query.message.caption or "") + f"\n\n✅ تایید شد — {fmt(tx['amount'])}"
            )
        return

    if data.startswith("adm_wreject_"):
        tx_id = int(data.split("_")[2])
        tx = reject_wallet_charge(tx_id)
        if tx:
            customer_bot = context.bot_data.get("customer_bot_instance")
            if customer_bot:
                try:
                    await customer_bot.send_message(
                        tx["user_id"],
                        f"❌ درخواست شارژ {fmt(tx['amount'])} رد شد.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error("Wallet reject notify: %s", e)
            await query.edit_message_caption(
                caption=(query.message.caption or "") + "\n\n❌ رد شد"
            )
        return


# ─── Text message handler ─────────────────────────────────────────────────────

@admin_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get(ST, S_IDLE)

    # ── State machine ──

    if state == S_WAIT_EXPIRY:
        days = PANEL_DEFAULT_DAYS
        if text.strip() != "-":
            try:
                days = int(text.strip())
            except ValueError:
                await update.message.reply_text("عدد وارد کنید یا `-` برای پیش‌فرض:")
                return
        order_id = context.user_data.get(PENDING_OID)
        if PANEL_ENABLED:
            order = get_order(order_id)
            if order:
                try:
                    from panel_api import marzban
                    import re as _re
                    safe_name = "user" + str(order_id) + _re.sub(r'\W', '', (order.get("username") or "x"))[:8]
                    result = await marzban.create_user(safe_name, order["gb_amount"], days)
                    config   = result["config"]
                    sub_link = result["sub_link"]
                    expiry   = result["expiry_date"]
                    panel_un = result["panel_user"]
                    approve_order(order_id, config, sub_link, expiry, panel_un)
                    customer_bot = context.bot_data.get("customer_bot_instance")
                    if customer_bot:
                        order.update({"config": config, "sub_link": sub_link,
                                      "expiry_date": expiry, "panel_username": panel_un})
                        from customer_bot import deliver_config
                        await deliver_config(customer_bot, order, config, sub_link)
                    await update.message.reply_text(
                        f"✅ سفارش *#{order_id}* تایید شد (Marzban).\n"
                        f"👤 پنل: `{panel_un}`\n📅 انقضا: {expiry}",
                        parse_mode="Markdown", reply_markup=admin_main_kb()
                    )
                except Exception as e:
                    logger.error("Panel create_user: %s", e)
                    await update.message.reply_text(
                        f"❌ خطای پنل: {e}\n\nکانفیگ را دستی ارسال کنید:",
                        reply_markup=admin_cancel_kb()
                    )
                    context.user_data[ST] = S_WAIT_CFG
                    return
        else:
            context.user_data["expiry_days"] = days
            context.user_data[ST] = S_WAIT_CFG
            await update.message.reply_text(
                "📤 کانفیگ VLESS را ارسال کنید:", reply_markup=admin_cancel_kb()
            )
            return
        context.user_data[ST] = S_IDLE
        return

    if state == S_WAIT_CFG:
        context.user_data[PENDING_CFG] = text.strip()
        context.user_data[ST] = S_WAIT_SUB
        await update.message.reply_text(
            "🔗 لینک Subscription را ارسال کنید:\n(یا `-` اگر ندارید)",
            reply_markup=admin_cancel_kb()
        )
        return

    if state == S_WAIT_SUB:
        order_id = context.user_data.get(PENDING_OID)
        config   = context.user_data.get(PENDING_CFG, "")
        sub_link = "" if text.strip() == "-" else text.strip()

        from datetime import datetime, timedelta
        days = context.user_data.get("expiry_days", 0)
        expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d") if days else None

        order = get_order(order_id)
        if not order:
            await update.message.reply_text("❌ سفارش پیدا نشد.")
            context.user_data[ST] = S_IDLE; return

        approve_order(order_id, config, sub_link, expiry)

        customer_bot = context.bot_data.get("customer_bot_instance")
        if customer_bot:
            order.update({"config": config, "sub_link": sub_link, "expiry_date": expiry})
            from customer_bot import deliver_config
            await deliver_config(customer_bot, order, config, sub_link)

        await update.message.reply_text(
            f"✅ سفارش *#{order_id}* تایید شد و کانفیگ ارسال گردید.",
            parse_mode="Markdown", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE
        context.user_data.pop(PENDING_OID, None)
        context.user_data.pop(PENDING_CFG, None)
        return

    if state == S_WAIT_REJECT:
        order_id = context.user_data.get(PENDING_OID)
        note = "" if text.strip() == "-" else text.strip()
        order = get_order(order_id)
        if not order:
            await update.message.reply_text("❌ سفارش پیدا نشد.")
            context.user_data[ST] = S_IDLE; return
        reject_order(order_id, note)
        customer_bot = context.bot_data.get("customer_bot_instance")
        if customer_bot:
            reason = f"\n\n❗ دلیل: {note}" if note else ""
            try:
                await customer_bot.send_message(
                    order["user_id"],
                    f"❌ سفارش *#{order_id}* رد شد.{reason}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error("Reject notify: %s", e)
        await update.message.reply_text(
            f"❌ سفارش *#{order_id}* رد شد.", parse_mode="Markdown", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE; return

    if state == S_WAIT_NOTE:
        order_id = context.user_data.get(PENDING_OID)
        add_order_note(order_id, text)
        await update.message.reply_text(f"📝 یادداشت ثبت شد.", reply_markup=admin_main_kb())
        context.user_data[ST] = S_IDLE; return

    if state == S_WAIT_BROADCAST:
        users = get_all_users()
        customer_bot = context.bot_data.get("customer_bot_instance")
        sent = failed = 0
        if customer_bot:
            for u in users:
                try:
                    await customer_bot.send_message(u["user_id"], text, parse_mode="Markdown")
                    sent += 1
                except Exception:
                    failed += 1
        await update.message.reply_text(
            f"📢 پیام ارسال شد.\n✅ موفق: {sent}\n❌ ناموفق: {failed}",
            reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE; return

    if state == S_WAIT_DISCOUNT:
        parts = text.strip().split()
        if len(parts) < 2:
            await update.message.reply_text("فرمت: `CODE PERCENT [MAX_USES]`", parse_mode="Markdown")
            return
        code = parts[0].upper()
        try:
            pct  = int(parts[1])
            uses = int(parts[2]) if len(parts) > 2 else 1
        except ValueError:
            await update.message.reply_text("❌ عدد نامعتبر.")
            return
        create_discount_code(code, pct, uses)
        await update.message.reply_text(
            f"✅ کد `{code}` | {pct}٪ | {uses} بار\nساخته شد.",
            parse_mode="Markdown", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE; return

    if state == S_WAIT_TPL_NAME:
        context.user_data["tpl_name"] = text.strip()
        context.user_data[ST] = S_WAIT_TPL_CFG
        await update.message.reply_text("📤 کانفیگ VLESS را وارد کنید:", reply_markup=admin_cancel_kb())
        return

    if state == S_WAIT_TPL_CFG:
        context.user_data["tpl_config"] = text.strip()
        context.user_data[ST] = S_WAIT_TPL_SUB
        await update.message.reply_text("🔗 لینک Sub را وارد کنید (یا `-`):", reply_markup=admin_cancel_kb())
        return

    if state == S_WAIT_TPL_SUB:
        name   = context.user_data.get("tpl_name")
        config = context.user_data.get("tpl_config")
        sub    = "" if text.strip() == "-" else text.strip()
        save_template(name, config, sub)
        await update.message.reply_text(
            f"✅ قالب *{name}* ذخیره شد.", parse_mode="Markdown", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE; return

    if state == S_WAIT_SEARCH:
        results = search_orders(text.strip())
        if not results:
            await update.message.reply_text("❌ نتیجه‌ای پیدا نشد.", reply_markup=admin_main_kb())
        else:
            out = f"🔍 *نتایج جستجو* ({len(results)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for o in results:
                st_e = STATUS_EMOJI.get(o["status"], "?")
                out += f"{st_e} #{o['id']} | {o['full_name']} | {fmt_gb(o['gb_amount'])} | {fmt(o['total_price'])}\n"
            await update.message.reply_text(out, parse_mode="Markdown", reply_markup=admin_main_kb())
        context.user_data[ST] = S_IDLE; return

    if state == S_WAIT_WALLET_ADJ:
        parts = text.strip().split(maxsplit=1)
        try:
            uid    = int(parts[0])
            amount = int(parts[1]) if len(parts) > 1 else 0
            if amount == 0:
                raise ValueError
        except (ValueError, IndexError):
            await update.message.reply_text("فرمت: `USER_ID AMOUNT`\nمثال: `123456 50000`",
                                            parse_mode="Markdown")
            return
        admin_adjust_wallet(uid, amount)
        customer_bot = context.bot_data.get("customer_bot_instance")
        if customer_bot:
            try:
                sign = "+" if amount > 0 else ""
                await customer_bot.send_message(
                    uid, f"💼 کیف پول شما {sign}{fmt(amount)} تنظیم شد توسط ادمین."
                )
            except Exception:
                pass
        await update.message.reply_text(
            f"✅ کیف پول کاربر `{uid}` → {fmt(amount)}", parse_mode="Markdown",
            reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE; return

    # ── Menu buttons ──
    menu_handlers = {
        "📊 آمار کلی":           show_stats,
        "📋 سفارشات در انتظار":  show_pending,
        "💰 شارژ کیف‌پول‌ها":   show_pending_wallets,
        "💬 تیکت‌های باز":       show_tickets,
        "📋 قالب‌های کانفیگ":   show_templates,
        "🔍 جستجو":              start_search,
        "📢 پیام همگانی":        start_broadcast,
        "👥 کاربران":            show_users,
        "🎫 کد تخفیف":          start_discount,
        "📤 خروجی CSV":          export_csv,
        "📈 گزارش درآمد":       show_revenue,
        "⚙️ راهنما":            show_help,
    }
    handler = menu_handlers.get(text)
    if handler:
        await handler(update, context)


# ─── /reply_<id> ─────────────────────────────────────────────────────────────

@admin_only
async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match = re.match(r"^/reply_(\d+)(?:\s+(.+))?$", update.message.text, re.DOTALL)
    if not match:
        await update.message.reply_text("فرمت: /reply_ID متن پاسخ")
        return
    tid  = int(match.group(1))
    body = (match.group(2) or "").strip()
    if not body:
        await update.message.reply_text("لطفاً متن پاسخ را بنویسید.")
        return
    uid = close_ticket(tid, body)
    if not uid:
        await update.message.reply_text("❌ تیکت پیدا نشد.")
        return
    customer_bot = context.bot_data.get("customer_bot_instance")
    if customer_bot:
        try:
            await customer_bot.send_message(
                uid,
                f"💬 *پاسخ پشتیبانی — تیکت #{tid}*\n\n{body}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error("Reply delivery: %s", e)
    await update.message.reply_text(f"✅ پاسخ تیکت #{tid} ارسال شد.", reply_markup=admin_main_kb())


@admin_only
async def cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت: /block USER_ID"); return
    uid = int(context.args[0])
    block_user(uid)
    await update.message.reply_text(f"🚫 {uid} مسدود شد.")


@admin_only
async def cmd_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت: /unblock USER_ID"); return
    uid = int(context.args[0])
    unblock_user(uid)
    await update.message.reply_text(f"✅ {uid} رفع مسدودیت شد.")


@admin_only
async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_WALLET_ADJ
    await update.message.reply_text(
        "💼 تنظیم کیف پول\n\nفرمت: `USER_ID AMOUNT`\n"
        "برای کاهش عدد منفی:\n`123456 -50000`",
        parse_mode="Markdown", reply_markup=admin_cancel_kb()
    )


@admin_only
async def cmd_deltpl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت: /deltpl TEMPLATE_ID"); return
    delete_template(int(context.args[0]))
    await update.message.reply_text("✅ قالب حذف شد.")


# ─── Menu handlers ────────────────────────────────────────────────────────────

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    avg_r = round(float(s.get("avg_rating") or 0), 1)
    await update.message.reply_text(
        "📊 *آمار کلی*\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 امروز: {s['today_orders']} سفارش | {fmt(s['today_revenue'])}\n\n"
        f"👥 کل کاربران: {s['total_users']:,}\n"
        f"🚫 مسدود: {s['blocked_users']}\n\n"
        f"⏳ انتظار: {s['pending_orders']}\n"
        f"✅ تایید: {s['approved_orders']:,}\n"
        f"❌ رد: {s['rejected_orders']}\n\n"
        f"💰 درآمد کل: {fmt(s['total_revenue'])}\n"
        f"💼 درآمد کیف پول: {fmt(s['wallet_revenue'])}\n"
        f"📦 گیگ فروش: {s['total_gb_sold']:,} GB\n"
        f"💼 موجودی کیف پول‌ها: {fmt(s['total_wallet'])}\n"
        f"💬 تیکت باز: {s['open_tickets']}\n"
        f"⭐ میانگین امتیاز: {avg_r}/5",
        parse_mode="Markdown", reply_markup=admin_main_kb()
    )


async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = get_pending_orders()
    if not orders:
        await update.message.reply_text("✅ سفارش در انتظاری نیست.", reply_markup=admin_main_kb())
        return
    text = f"📋 *سفارشات در انتظار* ({len(orders)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for o in orders:
        wallet_badge = "💼" if o.get("paid_by_wallet") else "💳"
        trial_badge  = "🎯" if o.get("is_trial") else ""
        text += (
            f"{wallet_badge}{trial_badge} *#{o['id']}* — {o['full_name']}\n"
            f"   📦 {fmt_gb(o['gb_amount'])} | 💰 {fmt(o['total_price'])}\n"
            f"   ⏰ {fmt_dt(o['created_at'])}\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


async def show_pending_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txs = get_pending_wallet_charges()
    if not txs:
        await update.message.reply_text("✅ شارژی در انتظار نیست.", reply_markup=admin_main_kb())
        return
    for tx in txs:
        uname = f"@{tx['username']}" if tx.get("username") else "—"
        text = (
            f"💳 *شارژ #{tx['id']}*\n\n"
            f"👤 {tx['full_name']} | {uname}\n"
            f"💰 {fmt(tx['amount'])}\n"
            f"⏰ {fmt_dt(tx['created_at'])}"
        )
        if tx.get("receipt_file_id"):
            try:
                f = await context.bot.get_file(tx["receipt_file_id"])
                buf = BytesIO(bytes(await f.download_as_bytearray()))
                buf.name = "r.jpg"
                await update.message.reply_photo(
                    photo=buf, caption=text, parse_mode="Markdown",
                    reply_markup=admin_wallet_kb(tx["id"])
                )
                continue
            except Exception:
                pass
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=admin_wallet_kb(tx["id"]))


async def show_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tickets = get_open_tickets()
    if not tickets:
        await update.message.reply_text("✅ تیکت بازی نیست.", reply_markup=admin_main_kb())
        return
    text = f"💬 *تیکت‌های باز* ({len(tickets)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for t in tickets:
        uname = f"@{t['username']}" if t.get("username") else "—"
        snippet = (t["message"] or "")[:70].replace("\n", " ")
        text += (
            f"🎫 *#{t['id']}* — {t['full_name']} ({uname})\n"
            f"   📝 {snippet}\n"
            f"   `/reply_{t['id']} [پاسخ]`\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


async def show_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    templates = get_templates()
    if not templates:
        await update.message.reply_text(
            "📋 هنوز قالبی ندارید.\n"
            "برای افزودن قالب: /addtemplate",
            reply_markup=admin_main_kb()
        )
        return
    text = f"📋 *قالب‌های کانفیگ* ({len(templates)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for t in templates:
        sub_badge = "🔗" if t.get("sub_link") else ""
        text += f"• *{t['name']}* {sub_badge} — استفاده: {t['use_count']} | آیدی: {t['id']}\n"
    text += "\nحذف قالب: `/deltpl ID`"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_SEARCH
    await update.message.reply_text(
        "🔍 عبارت جستجو را وارد کنید:\n(نام، یوزرنیم یا شماره سفارش)",
        reply_markup=admin_cancel_kb()
    )


async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_BROADCAST
    await update.message.reply_text(
        "📢 متن پیام همگانی را ارسال کنید:\n(Markdown پشتیبانی می‌شود)",
        reply_markup=admin_cancel_kb()
    )


async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    text = f"👥 *کاربران* ({len(users)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for u in users[:15]:
        uname = f"@{u['username']}" if u.get("username") else "—"
        vip, _ = get_vip(u.get("total_spent", 0))
        text += (
            f"• {u['full_name']} ({uname})\n"
            f"  `{u['user_id']}` | {vip} | {fmt(u['total_spent'])}\n\n"
        )
    if len(users) > 15:
        text += f"... و {len(users)-15} نفر دیگر"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


async def start_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_DISCOUNT
    await update.message.reply_text(
        "🎫 *کد تخفیف جدید*\n\nفرمت: `CODE PERCENT [MAX_USES]`\n"
        "مثال: `VIP20 20 10`",
        parse_mode="Markdown", reply_markup=admin_cancel_kb()
    )


async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    csv = export_orders_csv()
    buf = BytesIO(csv.encode("utf-8"))
    buf.name = "orders.csv"
    await update.message.reply_document(document=buf, filename="orders.csv",
                                        caption="📤 خروجی سفارشات")


async def show_revenue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    avg = s["total_revenue"] // max(s["approved_orders"], 1)
    await update.message.reply_text(
        "📈 *گزارش درآمد*\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 کل: {fmt(s['total_revenue'])}\n"
        f"💼 از کیف پول: {fmt(s['wallet_revenue'])}\n"
        f"🛍️ سفارشات: {s['approved_orders']:,}\n"
        f"📦 گیگ: {s['total_gb_sold']:,} GB\n"
        f"📊 میانگین: {fmt(avg)}\n"
        f"📅 امروز: {fmt(s['today_revenue'])}",
        parse_mode="Markdown", reply_markup=admin_main_kb()
    )


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ *راهنمای ادمین*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 *سفارشات:*\n"
        "  تایید: دکمه ✅ روی سفارش\n"
        "  رد: دکمه ❌ روی سفارش\n\n"
        "💬 *پشتیبانی:*\n"
        "  `/reply_ID متن پاسخ`\n\n"
        "💼 *کیف پول:*\n"
        "  `/wallet` → تنظیم دستی\n\n"
        "🚫 *مسدودسازی:*\n"
        "  `/block USER_ID` | `/unblock USER_ID`\n\n"
        "📋 *قالب کانفیگ:*\n"
        "  `/addtemplate` | `/deltpl ID`\n\n"
        "🤖 *پنل Marzban:*\n"
        "  `PANEL_ENABLED=true` در .env\n\n"
        "📢 *پیام همگانی:* از منو",
        parse_mode="Markdown", reply_markup=admin_main_kb()
    )


async def _show_user_profile(message, user_id: int):
    u = get_user(user_id)
    if not u:
        await message.reply_text("❌ کاربر پیدا نشد.")
        return
    uname = f"@{u['username']}" if u.get("username") else "—"
    vip, disc = get_vip(u.get("total_spent", 0))
    await message.reply_text(
        f"👤 *پروفایل کاربر*\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 `{u['user_id']}`\n"
        f"👤 {u['full_name']}\n"
        f"🔗 {uname}\n"
        f"📅 {fmt_dt(u.get('join_date',''))}\n"
        f"💎 {vip}\n"
        f"🛍️ سفارشات: {u['total_orders']}\n"
        f"💰 کل خرید: {fmt(u['total_spent'])}\n"
        f"💼 کیف پول: {fmt(u['wallet_balance'])}\n"
        f"🎯 آزمایش: {'استفاده شده' if u['free_trial_used'] else 'نشده'}\n"
        f"🚫 مسدود: {'بله' if u['is_blocked'] else 'خیر'}",
        parse_mode="Markdown"
    )


# ─── /addtemplate ─────────────────────────────────────────────────────────────

@admin_only
async def cmd_addtemplate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_TPL_NAME
    await update.message.reply_text(
        "📋 نام قالب را وارد کنید:\n(مثال: سرور ایران ۱)", reply_markup=admin_cancel_kb()
    )


# ─── Setup ────────────────────────────────────────────────────────────────────

def setup_admin_bot(app: Application, customer_bot_instance: Bot = None) -> None:
    if customer_bot_instance:
        app.bot_data["customer_bot_instance"] = customer_bot_instance

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("cancel",      cmd_cancel))
    app.add_handler(CommandHandler("block",       cmd_block))
    app.add_handler(CommandHandler("unblock",     cmd_unblock))
    app.add_handler(CommandHandler("wallet",      cmd_wallet))
    app.add_handler(CommandHandler("addtemplate", cmd_addtemplate))
    app.add_handler(CommandHandler("deltpl",      cmd_deltpl))
    app.add_handler(MessageHandler(filters.Regex(r"^/reply_\d+"), cmd_reply))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Chat(chat_id=ADMIN_IDS),
        handle_text
    ))
    logger.info("Admin bot ready.")
