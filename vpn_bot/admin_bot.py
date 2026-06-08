"""ربات ادمین v2 — پنل فوق پیشرفته، تنظیمات پویا، جوین اجباری، HTML parse mode."""
import logging
import re
import signal
import os
from io import BytesIO
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from config import ADMIN_IDS, BOT_NAME, PANEL_ENABLED, PANEL_DEFAULT_DAYS
import settings_manager as sm
from database import (
    get_order, get_pending_orders, get_all_users, get_user,
    approve_order, reject_order, get_stats, close_ticket, get_open_tickets,
    block_user, unblock_user, create_discount_code, add_order_note,
    get_templates, get_template, save_template, delete_template, use_template,
    approve_wallet_charge, reject_wallet_charge, get_pending_wallet_charges,
    admin_adjust_wallet, search_orders, export_orders_csv,
    get_referral_stats, get_user_referrals,
)
from keyboards import (
    admin_main_kb, admin_cancel_kb, admin_order_kb,
    admin_wallet_kb, admin_templates_kb,
    admin_settings_kb, admin_settings_pricing_kb, admin_settings_payment_kb,
    admin_settings_referral_kb, admin_settings_trial_kb,
    admin_settings_wallet_kb, admin_settings_security_kb,
    admin_fj_kb, admin_referral_panel_kb,
)
from utils import fmt, fmt_gb, fmt_dt, get_vip, STATUS_EMOJI, STATUS_LABEL, STAR_MAP, h

logger = logging.getLogger(__name__)

# ─── State keys ───────────────────────────────────────────────────────────────
ST          = "adm_st"
PENDING_OID = "adm_oid"
PENDING_CFG = "adm_cfg"

S_IDLE           = "idle"
S_WAIT_CFG       = "wait_cfg"
S_WAIT_SUB       = "wait_sub"
S_WAIT_EXPIRY    = "wait_expiry"
S_WAIT_REJECT    = "wait_reject"
S_WAIT_BROADCAST = "wait_broadcast"
S_WAIT_DISCOUNT  = "wait_discount"
S_WAIT_TPL_NAME  = "wait_tpl_name"
S_WAIT_TPL_CFG   = "wait_tpl_cfg"
S_WAIT_TPL_SUB   = "wait_tpl_sub"
S_WAIT_SEARCH    = "wait_search"
S_WAIT_NOTE      = "wait_note"
S_WAIT_WALLET_ADJ= "wait_wallet_adj"
S_WAIT_SETTING   = "wait_setting_val"   # تنظیمات پویا
S_WAIT_FJ_CHANNEL= "wait_fj_channel"    # افزودن کانال جوین اجباری
S_WAIT_PKG       = "wait_packages"      # ویرایش بسته‌های GB

# ─── Settings Registry ────────────────────────────────────────────────────────
# key → (label, type, min_val, max_val)
SETTINGS_REGISTRY = {
    "price_per_gb":            ("💰 قیمت هر گیگابایت (تومان)",   "int",   1000,   500_000),
    "min_gb":                  ("📉 حداقل گیگابایت",              "int",   1,      500),
    "max_gb":                  ("📈 حداکثر گیگابایت",             "int",   10,     2000),
    "card_number":             ("💳 شماره کارت",                  "str",   None,   None),
    "card_holder":             ("👤 نام صاحب کارت",               "str",   None,   None),
    "bank_name":               ("🏦 نام بانک",                    "str",   None,   None),
    "support_username":        ("💬 یوزرنیم پشتیبانی",            "str",   None,   None),
    "bot_channel":             ("📢 آیدی کانال",                  "str",   None,   None),
    "wallet_min_charge":       ("💵 حداقل شارژ کیف پول (تومان)", "int",   10_000, 1_000_000),
    "referral_bonus_mb":       ("📡 جایزه معرفی (مگابایت)",       "int",   0,      50_000),
    "referral_bonus_toman":    ("💵 جایزه معرفی (تومان)",         "int",   0,      1_000_000),
    "referral_min_purchases":  ("🛒 حداقل خرید برای جایزه",       "int",   1,      10),
    "free_trial_gb":           ("🎯 گیگ آزمایش رایگان",           "int",   1,      100),
    "rate_limit_per_minute":   ("⚡ حداکثر پیام در دقیقه",        "int",   5,      60),
}

TOGGLE_SETTINGS = {
    "free_trial_enabled": "🎯 آزمایش رایگان",
    "captcha_enabled":    "🛡 کپچا",
    "force_join_enabled": "📢 جوین اجباری",
}


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
        f"👑 <b>پنل ادمین — {h(BOT_NAME)}</b>\n\n"
        f"⏳ سفارش در انتظار: <b>{s['pending_orders']}</b>\n"
        f"💬 تیکت باز: <b>{s['open_tickets']}</b>\n"
        f"👥 کاربران: <b>{s['total_users']:,}</b>\n\n"
        "سفارشات جدید به‌صورت خودکار اطلاع‌رسانی می‌شوند.",
        parse_mode="HTML",
        reply_markup=admin_main_kb()
    )


@admin_only
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_IDLE
    context.user_data.pop(PENDING_OID, None)
    context.user_data.pop(PENDING_CFG, None)
    context.user_data.pop("setting_key", None)
    await update.message.reply_text("❌ لغو شد.", reply_markup=admin_main_kb())


# ─── Callback handler ─────────────────────────────────────────────────────────

@admin_only
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── لغو ──
    if data == "adm_cancel":
        context.user_data[ST] = S_IDLE
        await query.message.reply_text("❌ لغو شد.", reply_markup=admin_main_kb())
        return

    # ── Settings panel ──
    if data == "cfg_back":
        await query.edit_message_text(
            "⚙️ <b>تنظیمات ربات</b>\n\nیک دسته را انتخاب کنید:",
            parse_mode="HTML", reply_markup=admin_settings_kb()
        )
        return

    if data == "cfg_close" or data == "fj_close" or data == "ref_close":
        try:
            await query.delete_message()
        except Exception:
            await query.edit_message_text("بسته شد.")
        return

    if data == "cfg_menu_pricing":
        await query.edit_message_text(
            "💰 <b>قیمت‌گذاری</b>",
            parse_mode="HTML",
            reply_markup=admin_settings_pricing_kb(sm.price_per_gb(), sm.min_gb(), sm.max_gb())
        )
        return

    if data == "cfg_menu_payment":
        await query.edit_message_text(
            "💳 <b>اطلاعات پرداخت</b>",
            parse_mode="HTML",
            reply_markup=admin_settings_payment_kb(sm.card_number(), sm.card_holder(), sm.bank_name())
        )
        return

    if data == "cfg_menu_referral":
        await query.edit_message_text(
            "🎁 <b>سیستم معرفی</b>",
            parse_mode="HTML",
            reply_markup=admin_settings_referral_kb(
                sm.referral_bonus_mb(), sm.referral_bonus_toman(), sm.referral_min_purchases()
            )
        )
        return

    if data == "cfg_menu_trial":
        await query.edit_message_text(
            "🎯 <b>آزمایش رایگان</b>",
            parse_mode="HTML",
            reply_markup=admin_settings_trial_kb(sm.free_trial_enabled(), sm.free_trial_gb())
        )
        return

    if data == "cfg_menu_wallet":
        await query.edit_message_text(
            "💼 <b>کیف پول</b>",
            parse_mode="HTML",
            reply_markup=admin_settings_wallet_kb(sm.wallet_min_charge())
        )
        return

    if data == "cfg_menu_security":
        await query.edit_message_text(
            "🛡 <b>کپچا و امنیت</b>",
            parse_mode="HTML",
            reply_markup=admin_settings_security_kb(sm.captcha_enabled(), sm.rate_limit_per_minute())
        )
        return

    if data == "cfg_menu_packages":
        pkgs = sm.gb_packages()
        await query.edit_message_text(
            f"📋 <b>بسته‌های GB فعلی:</b>\n\n{', '.join(str(g) for g in pkgs)} گیگ\n\n"
            "بسته‌های جدید را با کاما وارد کنید:\nمثال: <code>20,50,100,200</code>",
            parse_mode="HTML",
            reply_markup=admin_cancel_kb()
        )
        context.user_data[ST] = S_WAIT_PKG
        return

    # toggle settings
    if data.startswith("cfg_toggle_"):
        key = data[len("cfg_toggle_"):]
        current = sm.get(key, False)
        sm.set_val(key, not current)
        label = TOGGLE_SETTINGS.get(key, key)
        status = "✅ فعال" if not current else "❌ غیرفعال"
        await query.answer(f"{label}: {status}", show_alert=True)
        # refresh the relevant menu
        if key in ("free_trial_enabled",):
            await query.edit_message_text(
                "🎯 <b>آزمایش رایگان</b>",
                parse_mode="HTML",
                reply_markup=admin_settings_trial_kb(sm.free_trial_enabled(), sm.free_trial_gb())
            )
        elif key in ("captcha_enabled", "rate_limit_per_minute"):
            await query.edit_message_text(
                "🛡 <b>کپچا و امنیت</b>",
                parse_mode="HTML",
                reply_markup=admin_settings_security_kb(sm.captcha_enabled(), sm.rate_limit_per_minute())
            )
        elif key == "force_join_enabled":
            await query.edit_message_text(
                "📢 <b>جوین اجباری</b>",
                parse_mode="HTML",
                reply_markup=admin_fj_kb(sm.force_join_enabled(), sm.force_join_channels())
            )
        return

    # numeric/string setting input
    if data.startswith("cfg_set_"):
        key = data[len("cfg_set_"):]
        if key not in SETTINGS_REGISTRY:
            return
        label, stype, mn, mx = SETTINGS_REGISTRY[key]
        hint = f"(عدد بین {mn:,} تا {mx:,})" if stype == "int" and mn is not None else ""
        await query.message.reply_text(
            f"✏️ مقدار جدید برای <b>{h(label)}</b>:\n{hint}\n\n/cancel برای لغو",
            parse_mode="HTML",
            reply_markup=admin_cancel_kb()
        )
        context.user_data["setting_key"] = key
        context.user_data[ST] = S_WAIT_SETTING
        return

    # ── Force Join ──
    if data == "fj_toggle":
        sm.set_val("force_join_enabled", not sm.force_join_enabled())
        await query.edit_message_text(
            "📢 <b>جوین اجباری</b>",
            parse_mode="HTML",
            reply_markup=admin_fj_kb(sm.force_join_enabled(), sm.force_join_channels())
        )
        return

    if data == "fj_add":
        await query.message.reply_text(
            "➕ آیدی کانال را وارد کنید (مثال: <code>@my_channel</code>):\n/cancel برای لغو",
            parse_mode="HTML", reply_markup=admin_cancel_kb()
        )
        context.user_data[ST] = S_WAIT_FJ_CHANNEL
        return

    if data.startswith("fj_del_"):
        idx = int(data.split("_")[2])
        channels = sm.force_join_channels()
        if 0 <= idx < len(channels):
            removed = channels.pop(idx)
            sm.set_val("force_join_channels", channels)
            await query.answer(f"حذف شد: {removed}", show_alert=True)
        await query.edit_message_text(
            "📢 <b>جوین اجباری</b>",
            parse_mode="HTML",
            reply_markup=admin_fj_kb(sm.force_join_enabled(), sm.force_join_channels())
        )
        return

    # ── Referral Panel ──
    if data == "ref_leaderboard":
        rows = get_referral_stats()
        if not rows:
            await query.message.reply_text("هنوز زیرمجموعه‌ای ثبت نشده.")
            return
        text = "🏆 <b>لیدربورد زیرمجموعه</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, r in enumerate(rows, 1):
            uname = f"@{r['username']}" if r.get("username") else "—"
            text += (
                f"{i}. {h(r['full_name'])} ({h(uname)})\n"
                f"   👥 {r['total_refs']} نفر | ✅ جایزه دریافت: {r['paid_refs']}\n\n"
            )
        await query.message.reply_text(text, parse_mode="HTML")
        return

    if data == "ref_stats":
        rows = get_referral_stats()
        total_refs = sum(r["total_refs"] for r in rows)
        paid_refs  = sum(r["paid_refs"] for r in rows)
        await query.message.reply_text(
            f"📊 <b>آمار کلی معرفی‌ها</b>\n\n"
            f"👥 کل زیرمجموعه: <b>{total_refs}</b>\n"
            f"✅ جایزه پرداخت شده: <b>{paid_refs}</b>\n"
            f"👑 تعداد معرف فعال: <b>{len(rows)}</b>",
            parse_mode="HTML"
        )
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
                f"✅ سفارش <b>#{order_id}</b> در حال تایید\n\n"
                f"تعداد روز انقضا (پیش‌فرض: {PANEL_DEFAULT_DAYS}):\n"
                "(یا <code>-</code> برای پیش‌فرض)\n/cancel",
                parse_mode="HTML", reply_markup=admin_cancel_kb()
            )
        else:
            templates = get_templates()
            if templates:
                await query.message.reply_text(
                    f"✅ سفارش <b>#{order_id}</b> — قالب کانفیگ را انتخاب کنید:",
                    parse_mode="HTML",
                    reply_markup=admin_templates_kb(templates)
                )
            else:
                context.user_data[ST] = S_WAIT_CFG
                await query.message.reply_text(
                    f"✅ سفارش <b>#{order_id}</b>\n\n📤 کانفیگ VLESS را ارسال کنید:\n/cancel",
                    parse_mode="HTML", reply_markup=admin_cancel_kb()
                )
        return

    # ── Template selection ──
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
        approve_order(order_id, tpl["config"], tpl.get("sub_link", ""))
        customer_bot = context.bot_data.get("customer_bot_instance")
        if customer_bot and order:
            from customer_bot import deliver_config
            order["config"]   = tpl["config"]
            order["sub_link"] = tpl.get("sub_link", "")
            await deliver_config(customer_bot, order, tpl["config"], tpl.get("sub_link", ""))
        await query.edit_message_text(
            f"✅ سفارش <b>#{order_id}</b> تایید شد (قالب: {h(tpl['name'])}).",
            parse_mode="HTML"
        )
        context.user_data[ST] = S_IDLE
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
            f"❌ دلیل رد سفارش <b>#{order_id}</b> را بنویسید:\n"
            "(یا <code>-</code> بدون دلیل)\n/cancel",
            parse_mode="HTML", reply_markup=admin_cancel_kb()
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
        if order:
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
                        f"✅ شارژ <b>{fmt(tx['amount'])}</b> به کیف پول شما اضافه شد!",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error("Wallet approve notify: %s", e)
            try:
                await query.edit_message_caption(
                    caption=(query.message.caption or "") + f"\n\n✅ تایید شد — {fmt(tx['amount'])}"
                )
            except Exception:
                pass
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
                        f"❌ درخواست شارژ {fmt(tx['amount'])} رد شد."
                    )
                except Exception as e:
                    logger.error("Wallet reject notify: %s", e)
            try:
                await query.edit_message_caption(
                    caption=(query.message.caption or "") + "\n\n❌ رد شد"
                )
            except Exception:
                pass
        return


# ─── Text handler ─────────────────────────────────────────────────────────────

@admin_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get(ST, S_IDLE)

    # ── Dynamic setting value input ──
    if state == S_WAIT_SETTING:
        key = context.user_data.get("setting_key")
        if not key or key not in SETTINGS_REGISTRY:
            context.user_data[ST] = S_IDLE
            return
        label, stype, mn, mx = SETTINGS_REGISTRY[key]
        val = text.strip()
        if stype == "int":
            try:
                val = int(val.replace(",", "").replace("،", ""))
                if mn is not None and not (mn <= val <= mx):
                    await update.message.reply_text(
                        f"❌ عدد بین {mn:,} و {mx:,} وارد کنید.", reply_markup=admin_cancel_kb()
                    )
                    return
            except ValueError:
                await update.message.reply_text("❌ عدد معتبر وارد کنید.", reply_markup=admin_cancel_kb())
                return
        sm.set_val(key, val)
        await update.message.reply_text(
            f"✅ <b>{h(label)}</b> بروزرسانی شد:\n<code>{h(str(val))}</code>",
            parse_mode="HTML", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE
        context.user_data.pop("setting_key", None)
        return

    # ── Force join channel add ──
    if state == S_WAIT_FJ_CHANNEL:
        ch = text.strip()
        if not ch.startswith("@"):
            ch = "@" + ch
        channels = sm.force_join_channels()
        if ch not in channels:
            channels.append(ch)
            sm.set_val("force_join_channels", channels)
        await update.message.reply_text(
            f"✅ کانال <b>{h(ch)}</b> اضافه شد.\n\n"
            "📢 <b>جوین اجباری</b>",
            parse_mode="HTML",
            reply_markup=admin_fj_kb(sm.force_join_enabled(), sm.force_join_channels())
        )
        context.user_data[ST] = S_IDLE
        return

    # ── GB packages edit ──
    if state == S_WAIT_PKG:
        try:
            pkgs = sorted(set(int(x.strip()) for x in text.replace("،", ",").split(",")))
            if not pkgs or any(p <= 0 for p in pkgs):
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ فرمت نادرست. مثال: <code>20,50,100,200</code>",
                parse_mode="HTML", reply_markup=admin_cancel_kb()
            )
            return
        sm.set_val("gb_packages", pkgs)
        await update.message.reply_text(
            f"✅ بسته‌های GB بروزرسانی شد:\n<code>{', '.join(str(p) for p in pkgs)}</code>",
            parse_mode="HTML", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE
        return

    # ── Expiry ──
    if state == S_WAIT_EXPIRY:
        days = PANEL_DEFAULT_DAYS
        if text.strip() != "-":
            try:
                days = int(text.strip())
            except ValueError:
                await update.message.reply_text("عدد وارد کنید یا <code>-</code> برای پیش‌فرض:",
                                                parse_mode="HTML")
                return
        order_id = context.user_data.get(PENDING_OID)
        if PANEL_ENABLED:
            order = get_order(order_id)
            if order:
                try:
                    from panel_api import marzban
                    safe_name = "user" + str(order_id) + re.sub(r'\W', '', (order.get("username") or "x"))[:8]
                    result = await marzban.create_user(safe_name, order["gb_amount"], days)
                    config, sub_link = result["config"], result["sub_link"]
                    expiry, panel_un = result["expiry_date"], result["panel_user"]
                    approve_order(order_id, config, sub_link, expiry, panel_un)
                    customer_bot = context.bot_data.get("customer_bot_instance")
                    if customer_bot:
                        order.update({"config": config, "sub_link": sub_link,
                                      "expiry_date": expiry, "panel_username": panel_un})
                        from customer_bot import deliver_config
                        await deliver_config(customer_bot, order, config, sub_link)
                    await update.message.reply_text(
                        f"✅ سفارش <b>#{order_id}</b> تایید شد (Marzban).\n"
                        f"👤 پنل: <code>{h(panel_un)}</code>\n📅 انقضا: {h(expiry)}",
                        parse_mode="HTML", reply_markup=admin_main_kb()
                    )
                except Exception as e:
                    logger.error("Panel create_user: %s", e)
                    await update.message.reply_text(
                        f"❌ خطای پنل: {h(str(e))}\n\nکانفیگ را دستی ارسال کنید:",
                        parse_mode="HTML", reply_markup=admin_cancel_kb()
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

    # ── Config ──
    if state == S_WAIT_CFG:
        context.user_data[PENDING_CFG] = text.strip()
        context.user_data[ST] = S_WAIT_SUB
        await update.message.reply_text(
            "🔗 لینک Subscription را ارسال کنید:\n(<code>-</code> اگر ندارید)",
            parse_mode="HTML", reply_markup=admin_cancel_kb()
        )
        return

    # ── Sub link ──
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
            context.user_data[ST] = S_IDLE
            return

        approve_order(order_id, config, sub_link, expiry)
        customer_bot = context.bot_data.get("customer_bot_instance")
        if customer_bot:
            order.update({"config": config, "sub_link": sub_link, "expiry_date": expiry})
            from customer_bot import deliver_config
            await deliver_config(customer_bot, order, config, sub_link)

        await update.message.reply_text(
            f"✅ سفارش <b>#{order_id}</b> تایید شد و کانفیگ ارسال گردید.",
            parse_mode="HTML", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE
        context.user_data.pop(PENDING_OID, None)
        context.user_data.pop(PENDING_CFG, None)
        return

    # ── Reject ──
    if state == S_WAIT_REJECT:
        order_id = context.user_data.get(PENDING_OID)
        note = "" if text.strip() == "-" else text.strip()
        order = get_order(order_id)
        if not order:
            await update.message.reply_text("❌ سفارش پیدا نشد.")
            context.user_data[ST] = S_IDLE
            return
        reject_order(order_id, note)
        customer_bot = context.bot_data.get("customer_bot_instance")
        if customer_bot:
            reason = f"\n\n❗ دلیل: {h(note)}" if note else ""
            try:
                await customer_bot.send_message(
                    order["user_id"],
                    f"❌ سفارش <b>#{order_id}</b> رد شد.{reason}",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error("Reject notify: %s", e)
        await update.message.reply_text(
            f"❌ سفارش <b>#{order_id}</b> رد شد.",
            parse_mode="HTML", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE
        return

    # ── Note ──
    if state == S_WAIT_NOTE:
        order_id = context.user_data.get(PENDING_OID)
        add_order_note(order_id, text)
        await update.message.reply_text("📝 یادداشت ثبت شد.", reply_markup=admin_main_kb())
        context.user_data[ST] = S_IDLE
        return

    # ── Broadcast ──
    if state == S_WAIT_BROADCAST:
        users = get_all_users()
        customer_bot = context.bot_data.get("customer_bot_instance")
        sent = failed = 0
        if customer_bot:
            for u in users:
                try:
                    await customer_bot.send_message(u["user_id"], text, parse_mode="HTML")
                    sent += 1
                except Exception:
                    failed += 1
        await update.message.reply_text(
            f"📢 پیام ارسال شد.\n✅ موفق: {sent}\n❌ ناموفق: {failed}",
            reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE
        return

    # ── Discount ──
    if state == S_WAIT_DISCOUNT:
        parts = text.strip().split()
        if len(parts) < 2:
            await update.message.reply_text(
                "فرمت: <code>CODE PERCENT [MAX_USES]</code>", parse_mode="HTML"
            )
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
            f"✅ کد <code>{code}</code> | {pct}٪ | {uses} بار — ساخته شد.",
            parse_mode="HTML", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE
        return

    # ── Template name/config/sub ──
    if state == S_WAIT_TPL_NAME:
        context.user_data["tpl_name"] = text.strip()
        context.user_data[ST] = S_WAIT_TPL_CFG
        await update.message.reply_text("📤 کانفیگ VLESS را وارد کنید:", reply_markup=admin_cancel_kb())
        return

    if state == S_WAIT_TPL_CFG:
        context.user_data["tpl_config"] = text.strip()
        context.user_data[ST] = S_WAIT_TPL_SUB
        await update.message.reply_text(
            "🔗 لینک Sub را وارد کنید (یا <code>-</code>):",
            parse_mode="HTML", reply_markup=admin_cancel_kb()
        )
        return

    if state == S_WAIT_TPL_SUB:
        name   = context.user_data.get("tpl_name")
        config = context.user_data.get("tpl_config")
        sub    = "" if text.strip() == "-" else text.strip()
        save_template(name, config, sub)
        await update.message.reply_text(
            f"✅ قالب <b>{h(name)}</b> ذخیره شد.",
            parse_mode="HTML", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE
        return

    # ── Search ──
    if state == S_WAIT_SEARCH:
        results = search_orders(text.strip())
        if not results:
            await update.message.reply_text("❌ نتیجه‌ای پیدا نشد.", reply_markup=admin_main_kb())
        else:
            out = f"🔍 <b>نتایج جستجو</b> ({len(results)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for o in results:
                st_e = STATUS_EMOJI.get(o["status"], "?")
                out += (
                    f"{st_e} #{o['id']} | {h(o['full_name'])} | "
                    f"{fmt_gb(o['gb_amount'])} | {fmt(o['total_price'])}\n"
                )
            await update.message.reply_text(out, parse_mode="HTML", reply_markup=admin_main_kb())
        context.user_data[ST] = S_IDLE
        return

    # ── Wallet adjust ──
    if state == S_WAIT_WALLET_ADJ:
        parts = text.strip().split(maxsplit=1)
        try:
            uid    = int(parts[0])
            amount = int(parts[1]) if len(parts) > 1 else 0
            if amount == 0:
                raise ValueError
        except (ValueError, IndexError):
            await update.message.reply_text(
                "فرمت: <code>USER_ID AMOUNT</code>\nمثال: <code>123456 50000</code>",
                parse_mode="HTML"
            )
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
            f"✅ کیف پول کاربر <code>{uid}</code> → {fmt(amount)}",
            parse_mode="HTML", reply_markup=admin_main_kb()
        )
        context.user_data[ST] = S_IDLE
        return

    # ── Menu buttons ──
    menu = {
        "📊 آمار کلی":          show_stats,
        "📋 سفارشات در انتظار": show_pending,
        "💰 شارژ کیف‌پول‌ها":  show_pending_wallets,
        "💬 تیکت‌های باز":      show_tickets,
        "📋 قالب‌های کانفیگ":  show_templates,
        "🔍 جستجو":             start_search,
        "📢 پیام همگانی":       start_broadcast,
        "👥 کاربران":           show_users,
        "🎫 کد تخفیف":         start_discount,
        "📤 خروجی CSV":         export_csv,
        "📈 گزارش درآمد":      show_revenue,
        "⚙️ تنظیمات":          show_settings,
        "📢 جوین اجباری":      show_force_join,
        "👥 زیرمجموعه":        show_referral_panel,
        "🔄 ریستارت":          do_restart,
        "⚙️ راهنما":           show_help,
    }
    handler = menu.get(text)
    if handler:
        await handler(update, context)


# ─── /reply ───────────────────────────────────────────────────────────────────

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
                f"💬 <b>پاسخ پشتیبانی — تیکت #{tid}</b>\n\n{h(body)}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Reply delivery: %s", e)
    await update.message.reply_text(f"✅ پاسخ تیکت #{tid} ارسال شد.", reply_markup=admin_main_kb())


@admin_only
async def cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت: /block USER_ID")
        return
    uid = int(context.args[0])
    block_user(uid)
    await update.message.reply_text(f"🚫 {uid} مسدود شد.")


@admin_only
async def cmd_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت: /unblock USER_ID")
        return
    uid = int(context.args[0])
    unblock_user(uid)
    await update.message.reply_text(f"✅ {uid} رفع مسدودیت شد.")


@admin_only
async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_WALLET_ADJ
    await update.message.reply_text(
        "💼 تنظیم کیف پول\n\nفرمت: <code>USER_ID AMOUNT</code>\n"
        "برای کاهش عدد منفی:\n<code>123456 -50000</code>",
        parse_mode="HTML", reply_markup=admin_cancel_kb()
    )


@admin_only
async def cmd_deltpl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت: /deltpl TEMPLATE_ID")
        return
    delete_template(int(context.args[0]))
    await update.message.reply_text("✅ قالب حذف شد.")


@admin_only
async def cmd_addtemplate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_TPL_NAME
    await update.message.reply_text(
        "📋 نام قالب را وارد کنید:\n(مثال: سرور ایران ۱)", reply_markup=admin_cancel_kb()
    )


# ─── Menu Handlers ────────────────────────────────────────────────────────────

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    avg_r = round(float(s.get("avg_rating") or 0), 1)
    await update.message.reply_text(
        "📊 <b>آمار کلی</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 امروز: {s['today_orders']} سفارش | {fmt(s['today_revenue'])}\n\n"
        f"👥 کل کاربران: {s['total_users']:,}\n"
        f"🚫 مسدود: {s['blocked_users']}\n\n"
        f"⏳ انتظار: {s['pending_orders']}\n"
        f"✅ تایید: {s['approved_orders']:,}\n"
        f"❌ رد: {s['rejected_orders']}\n\n"
        f"💰 درآمد کل: {fmt(s['total_revenue'])}\n"
        f"💼 از کیف پول: {fmt(s['wallet_revenue'])}\n"
        f"📦 گیگ فروش: {s['total_gb_sold']:,} GB\n"
        f"💼 موجودی کیف‌پول‌ها: {fmt(s['total_wallet'])}\n"
        f"💬 تیکت باز: {s['open_tickets']}\n"
        f"⭐ میانگین امتیاز: {avg_r}/5",
        parse_mode="HTML", reply_markup=admin_main_kb()
    )


async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = get_pending_orders()
    if not orders:
        await update.message.reply_text("✅ سفارش در انتظاری نیست.", reply_markup=admin_main_kb())
        return
    text = f"📋 <b>سفارشات در انتظار</b> ({len(orders)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for o in orders:
        w = "💼" if o.get("paid_by_wallet") else "💳"
        t = "🎯" if o.get("is_trial") else ""
        text += (
            f"{w}{t} <b>#{o['id']}</b> — {h(o['full_name'])}\n"
            f"   📦 {fmt_gb(o['gb_amount'])} | 💰 {fmt(o['total_price'])}\n"
            f"   ⏰ {fmt_dt(o['created_at'])}\n\n"
        )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_main_kb())


async def show_pending_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txs = get_pending_wallet_charges()
    if not txs:
        await update.message.reply_text("✅ شارژی در انتظار نیست.", reply_markup=admin_main_kb())
        return
    for tx in txs:
        uname = f"@{tx['username']}" if tx.get("username") else "—"
        text = (
            f"💳 <b>شارژ #{tx['id']}</b>\n\n"
            f"👤 {h(tx['full_name'])} | {h(uname)}\n"
            f"💰 {fmt(tx['amount'])}\n"
            f"⏰ {fmt_dt(tx['created_at'])}"
        )
        if tx.get("receipt_file_id"):
            try:
                f = await context.bot.get_file(tx["receipt_file_id"])
                buf = BytesIO(bytes(await f.download_as_bytearray()))
                buf.name = "r.jpg"
                await update.message.reply_photo(
                    photo=buf, caption=text, parse_mode="HTML",
                    reply_markup=admin_wallet_kb(tx["id"])
                )
                continue
            except Exception:
                pass
        await update.message.reply_text(
            text, parse_mode="HTML", reply_markup=admin_wallet_kb(tx["id"])
        )


async def show_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tickets = get_open_tickets()
    if not tickets:
        await update.message.reply_text("✅ تیکت بازی نیست.", reply_markup=admin_main_kb())
        return
    text = f"💬 <b>تیکت‌های باز</b> ({len(tickets)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for t in tickets:
        uname = f"@{t['username']}" if t.get("username") else "—"
        snippet = h((t["message"] or "")[:70].replace("\n", " "))
        text += (
            f"🎫 <b>#{t['id']}</b> — {h(t['full_name'])} ({h(uname)})\n"
            f"   📝 {snippet}\n"
            f"   <code>/reply_{t['id']} [پاسخ]</code>\n\n"
        )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_main_kb())


async def show_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    templates = get_templates()
    if not templates:
        await update.message.reply_text(
            "📋 هنوز قالبی ندارید.\nبرای افزودن: /addtemplate",
            reply_markup=admin_main_kb()
        )
        return
    text = f"📋 <b>قالب‌های کانفیگ</b> ({len(templates)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for t in templates:
        sub_badge = "🔗" if t.get("sub_link") else ""
        text += f"• <b>{h(t['name'])}</b> {sub_badge} — استفاده: {t['use_count']} | آیدی: {t['id']}\n"
    text += "\nحذف: <code>/deltpl ID</code>"
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_main_kb())


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_SEARCH
    await update.message.reply_text(
        "🔍 عبارت جستجو را وارد کنید:\n(نام، یوزرنیم یا شماره سفارش)",
        reply_markup=admin_cancel_kb()
    )


async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_BROADCAST
    await update.message.reply_text(
        "📢 متن پیام همگانی را ارسال کنید:\n(HTML پشتیبانی می‌شود)",
        reply_markup=admin_cancel_kb()
    )


async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    text = f"👥 <b>کاربران</b> ({len(users)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for u in users[:15]:
        uname = f"@{u['username']}" if u.get("username") else "—"
        vip, _ = get_vip(u.get("total_spent", 0))
        text += (
            f"• {h(u['full_name'])} ({h(uname)})\n"
            f"  <code>{u['user_id']}</code> | {h(vip)} | {fmt(u['total_spent'])}\n\n"
        )
    if len(users) > 15:
        text += f"... و {len(users)-15} نفر دیگر"
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_main_kb())


async def start_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[ST] = S_WAIT_DISCOUNT
    await update.message.reply_text(
        "🎫 <b>کد تخفیف جدید</b>\n\nفرمت: <code>CODE PERCENT [MAX_USES]</code>\n"
        "مثال: <code>VIP20 20 10</code>",
        parse_mode="HTML", reply_markup=admin_cancel_kb()
    )


async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    csv = export_orders_csv()
    buf = BytesIO(csv.encode("utf-8"))
    buf.name = "orders.csv"
    await update.message.reply_document(document=buf, filename="orders.csv", caption="📤 خروجی سفارشات")


async def show_revenue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    avg = s["total_revenue"] // max(s["approved_orders"], 1)
    await update.message.reply_text(
        "📈 <b>گزارش درآمد</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 کل: {fmt(s['total_revenue'])}\n"
        f"💼 از کیف پول: {fmt(s['wallet_revenue'])}\n"
        f"🛍️ سفارشات: {s['approved_orders']:,}\n"
        f"📦 گیگ: {s['total_gb_sold']:,} GB\n"
        f"📊 میانگین: {fmt(avg)}\n"
        f"📅 امروز: {fmt(s['today_revenue'])}",
        parse_mode="HTML", reply_markup=admin_main_kb()
    )


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ <b>تنظیمات ربات</b>\n\n"
        f"💰 قیمت/گیگ: {fmt(sm.price_per_gb())}\n"
        f"💳 کارت: {h(sm.card_number())}\n"
        f"🛡 کپچا: {'✅' if sm.captcha_enabled() else '❌'}\n"
        f"🎯 آزمایش رایگان: {'✅' if sm.free_trial_enabled() else '❌'}\n"
        f"📢 جوین اجباری: {'✅' if sm.force_join_enabled() else '❌'}\n\n"
        "یک دسته را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=admin_settings_kb()
    )


async def show_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = sm.force_join_channels()
    enabled = sm.force_join_enabled()
    ch_text = "\n".join(f"• {h(c)}" for c in channels) if channels else "هیچ کانالی ثبت نشده"
    await update.message.reply_text(
        f"📢 <b>جوین اجباری</b>\n\n"
        f"وضعیت: {'✅ فعال' if enabled else '❌ غیرفعال'}\n\n"
        f"<b>کانال‌ها:</b>\n{ch_text}",
        parse_mode="HTML",
        reply_markup=admin_fj_kb(enabled, channels)
    )


async def show_referral_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_referral_stats()
    total = sum(r["total_refs"] for r in rows)
    await update.message.reply_text(
        f"👥 <b>پنل زیرمجموعه</b>\n\n"
        f"📊 کل زیرمجموعه‌ها: <b>{total}</b>\n"
        f"🎁 جایزه MB: {sm.referral_bonus_mb()} مگ\n"
        f"💵 جایزه تومان: {fmt(sm.referral_bonus_toman())}\n"
        f"🛒 حداقل خرید برای جایزه: {sm.referral_min_purchases()}",
        parse_mode="HTML",
        reply_markup=admin_referral_panel_kb()
    )


async def do_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 ربات در حال ریستارت...")
    logger.info("Admin triggered restart.")
    os.kill(os.getpid(), signal.SIGTERM)


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ <b>راهنمای ادمین</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>سفارشات:</b>\n"
        "  تایید: دکمه ✅ روی سفارش\n"
        "  رد: دکمه ❌ روی سفارش\n\n"
        "💬 <b>پشتیبانی:</b>\n"
        "  <code>/reply_ID متن پاسخ</code>\n\n"
        "💼 <b>کیف پول:</b>\n"
        "  <code>/wallet</code> → تنظیم دستی\n\n"
        "🚫 <b>مسدودسازی:</b>\n"
        "  <code>/block ID</code> | <code>/unblock ID</code>\n\n"
        "📋 <b>قالب کانفیگ:</b>\n"
        "  <code>/addtemplate</code> | <code>/deltpl ID</code>\n\n"
        "⚙️ <b>تنظیمات پویا:</b>\n"
        "  دکمه ⚙️ تنظیمات در منو\n\n"
        "📢 <b>جوین اجباری:</b>\n"
        "  دکمه 📢 جوین اجباری در منو\n\n"
        "🔄 <b>ریستارت:</b>\n"
        "  دکمه 🔄 ریستارت در منو",
        parse_mode="HTML", reply_markup=admin_main_kb()
    )


async def _show_user_profile(message, user_id: int):
    u = get_user(user_id)
    if not u:
        await message.reply_text("❌ کاربر پیدا نشد.")
        return
    uname = f"@{u['username']}" if u.get("username") else "—"
    vip, disc = get_vip(u.get("total_spent", 0))
    refs = get_user_referrals(user_id)
    await message.reply_text(
        f"👤 <b>پروفایل کاربر</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <code>{u['user_id']}</code>\n"
        f"👤 {h(u['full_name'])}\n"
        f"🔗 {h(uname)}\n"
        f"📅 {fmt_dt(u.get('join_date',''))}\n"
        f"💎 {h(vip)}\n"
        f"🛍️ سفارشات: {u['total_orders']}\n"
        f"💰 کل خرید: {fmt(u['total_spent'])}\n"
        f"💼 کیف پول: {fmt(u['wallet_balance'])}\n"
        f"👥 زیرمجموعه: {len(refs)}\n"
        f"🎁 بونوس MB: {u.get('bonus_mb', 0)}\n"
        f"🎯 آزمایش: {'استفاده شده' if u['free_trial_used'] else 'نشده'}\n"
        f"🚫 مسدود: {'بله' if u['is_blocked'] else 'خیر'}",
        parse_mode="HTML"
    )


# ─── Error Handler ────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception in admin bot: %s", context.error, exc_info=context.error)


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
    app.add_error_handler(error_handler)
    logger.info("Admin bot v2 ready.")
