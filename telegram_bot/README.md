# 🚀 ربات تلگرام دانلودر همه‌کاره | All-in-One Telegram Media Downloader Bot

یک ربات تلگرام حرفه‌ای، سریع و پایدار برای دانلود موزیک و ویدیو از تقریباً همه‌ی
پلتفرم‌ها — با دکمه‌های شیشه‌ای جذاب، جستجوی آهنگ، و پشتیبانی کامل از گروه.

A professional, fast and robust Telegram bot to download audio & video from
almost any platform — with glassy inline buttons, music search and full group
support.

---

## ✨ امکانات | Features

- ▶️ **YouTube** — ویدیو با انتخاب کیفیت (144p تا 1080p) یا فقط صدا (MP3)
- 📸 **Instagram** — پست، ریلز، استوری
- 🎵 **TikTok** — بدون واترمارک
- 🎧 **Spotify** — دانلود آهنگ (از طریق `spotdl`)
- ☁️ **SoundCloud** · 🐦 **X/Twitter** · 📘 **Facebook** · 🎮 **Twitch** · 🎬 **Vimeo** · 👽 **Reddit**
- 🔞 سایت‌های بزرگسال و **+۱۰۰۰ سایت دیگر** (هر چیزی که `yt-dlp` پشتیبانی کند)
- 🔎 **جستجوی آهنگ** با `/find` و `/music`
- 🪟 **دکمه‌های شیشه‌ای** (Inline) برای انتخاب فرمت و کیفیت
- 👥 **پشتیبانی از گروه** — کافیست لینک بفرستید
- 🛡️ کنترل دسترسی (ادمین / لیست مجاز)، مدیریت خطای کامل، بدون کرش

---

## ⚡️ نصب سریع | Quick Start

### پیش‌نیازها
- Python **3.10+**
- **ffmpeg** نصب‌شده روی سیستم (برای استخراج صدا و ادغام ویدیو)

```bash
# 1) کلون و ورود به پوشه
cd telegram_bot

# 2) ساخت محیط مجازی و نصب وابستگی‌ها
python -m venv .venv
source .venv/bin/activate        # ویندوز: .venv\Scripts\activate
pip install -r requirements.txt

# 3) تنظیم توکن
cp .env.example .env
#  فایل .env را باز کن و BOT_TOKEN را از @BotFather بگذار

# 4) اجرا
python run.py
```

نصب ffmpeg:

```bash
# Debian/Ubuntu
sudo apt install ffmpeg
# macOS
brew install ffmpeg
# Windows (choco)
choco install ffmpeg
```

---

## 🐳 اجرا با Docker

```bash
cp .env.example .env       # توکن را وارد کن
docker compose up -d --build
docker compose logs -f
```
ffmpeg داخل ایمیج نصب می‌شود — نیازی به نصب جداگانه نیست.

---

## 🎮 نحوه استفاده | Usage

| دستور | کار |
|------|-----|
| `/start` | معرفی ربات |
| `/help` | راهنمای کامل |
| `/find <عبارت>` | جستجوی یوتیوب و نمایش نتایج |
| `/music <عبارت>` | جستجو و دانلود مستقیم MP3 |
| `/dl <لینک>` | دانلود از یک لینک مشخص |

**ساده‌ترین روش:** فقط لینک را برای ربات بفرست — خودش تشخیص می‌دهد و دکمه‌های
دانلود را نشان می‌دهد. در گروه‌ها هم همین‌طور کار می‌کند.

---

## ⚙️ پیکربندی | Configuration (`.env`)

| متغیر | توضیح |
|------|------|
| `BOT_TOKEN` | **(الزامی)** توکن از @BotFather |
| `ADMINS` | شناسه‌های عددی ادمین‌ها (با کاما) |
| `ALLOWED_USERS` | فقط این کاربران اجازه دارند (خالی = عمومی) |
| `MAX_FILESIZE_MB` | حداکثر حجم ارسال (پیش‌فرض 49) |
| `SEARCH_RESULTS` | تعداد نتایج جستجو |
| `DOWNLOAD_DIR` | پوشه‌ی موقت دانلود |
| `COOKIES_FILE` | فایل کوکی برای محتوای نیازمند لاگین/سن |
| `PROXY` | پروکسی برای مناطق محدود (`socks5://...`) |
| `BASE_URL` / `BASE_FILE_URL` | برای Local Bot API Server (حجم تا 2GB) |

### حجم بالای ۵۰ مگابایت
تلگرام برای ربات‌ها سقف ۵۰MB دارد. برای ارسال فایل‌های بزرگ‌تر (تا 2GB) یک
[Local Bot API Server](https://github.com/tdlib/telegram-bot-api) راه بیندازید
و `BASE_URL` و `BASE_FILE_URL` را در `.env` تنظیم کنید.

---

## 🗂️ ساختار پروژه

```
telegram_bot/
├─ run.py                  # نقطه ورود
├─ requirements.txt
├─ Dockerfile / docker-compose.yml
├─ .env.example
└─ mediabot/
   ├─ bot.py               # ساخت اپلیکیشن و ثبت هندلرها
   ├─ config.py            # خواندن تنظیمات از .env
   ├─ downloader.py        # موتور yt-dlp + spotdl (async)
   ├─ handlers.py          # دستورها، تشخیص لینک، کال‌بک‌ها
   ├─ keyboards.py         # دکمه‌های شیشه‌ای
   ├─ store.py             # نگه‌داری موقت توکن‌ها (TTL)
   ├─ texts.py             # متن‌های رابط کاربری
   └─ utils.py             # توابع کمکی
```

---

## ⚠️ مسئولیت قانونی | Disclaimer

این ابزار صرفاً برای استفاده‌ی شخصی و محتوایی است که حق دانلودش را دارید. مسئولیت
رعایت قوانین کپی‌رایت و شرایط استفاده‌ی هر پلتفرم بر عهده‌ی کاربر است. توسعه‌دهنده
هیچ مسئولیتی در قبال سوءاستفاده ندارد.

This tool is for personal use and content you have the right to download.
Respect copyright and each platform's Terms of Service.
