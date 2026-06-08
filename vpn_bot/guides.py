GUIDES: dict[str, str] = {

"guide_ios_npv": """
🍎 راهنمای نصب روی آیفون — NPV Tunnel
━━━━━━━━━━━━━━━━━━━━━━━━

📥 مرحله ۱ — دانلود اپ
• App Store را باز کنید
• NPV Tunnel را جستجو کنید
• اپ را نصب کنید

⚙️ مرحله ۲ — اضافه کردن کانفیگ
• اپ را باز کنید
• روی دکمه ➕ بالا سمت راست بزنید
• گزینه «Import from Clipboard» را انتخاب کنید
• کانفیگ VLESS خود را paste کنید و ذخیره کنید

🔗 مرحله ۳ — اضافه کردن Sub (اختیاری)
• وارد تب Subscriptions شوید
• دکمه ➕ را بزنید
• لینک Subscription را وارد کنید
• Update را بزنید تا سرورها بروزرسانی شوند

▶️ مرحله ۴ — اتصال
• روی کانفیگ اضافه‌شده کلیک کنید
• دکمه Connect را بزنید
• اجازه دسترسی VPN را بدهید

✅ متصل شدید! از اینترنت آزاد لذت ببرید.

💡 نکته: اگر سرعت کم بود، روی سرور دیگری از Sub بزنید.
""",

"guide_ios_v2box": """
🍎 راهنمای نصب روی آیفون — V2Box
━━━━━━━━━━━━━━━━━━━━━━━━

📥 مرحله ۱ — دانلود اپ
• App Store را باز کنید
• «V2Box - V2ray VPN Client» جستجو کنید
• نصب کنید (رایگان است)

⚙️ مرحله ۲ — وارد کردن کانفیگ
• اپ را باز کنید → تب «Configs»
• دکمه ➕ بالا راست را بزنید
• «Import from Clipboard» را انتخاب کنید
• کانفیگ VLESS خود را paste کنید
• ذخیره کنید

🔗 مرحله ۳ — اضافه کردن Subscription
• تب «Subscriptions» را باز کنید
• دکمه ➕ را بزنید
• لینک Sub خود را وارد کنید
• دکمه «Update» را بزنید

▶️ مرحله ۴ — اتصال
• به تب «Configs» برگردید
• کانفیگ مورد نظر را انتخاب کنید
• دکمه «Connect» در پایین صفحه را بزنید

✅ اتصال برقرار شد!

💡 برای تست: whoer.net را در مرورگر باز کنید.
""",

"guide_android_v2rayng": """
🤖 راهنمای نصب روی اندروید — V2RayNG
━━━━━━━━━━━━━━━━━━━━━━━━

📥 مرحله ۱ — دانلود اپ
• Google Play: «v2rayNG» جستجو کنید
• یا از GitHub دانلود کنید:
  github.com/2dust/v2rayNG/releases

⚙️ مرحله ۲ — وارد کردن کانفیگ
• اپ را باز کنید
• دکمه ➕ گوشه بالا راست را بزنید
• «Import Config from Clipboard» را انتخاب کنید
• کانفیگ VLESS را paste کنید

🔗 مرحله ۳ — اضافه کردن Subscription
• از منوی ☰ گزینه «Subscription Group Settings» را بزنید
• ➕ را بزنید و لینک Sub را وارد کنید
• بالا راست آیکون refresh را بزنید
• سرورها لود می‌شوند

▶️ مرحله ۴ — اتصال
• کانفیگ مورد نظر را انتخاب کنید (دایره سبز شود)
• دکمه ▶️ گوشه پایین راست را بزنید
• به VPN اجازه دسترسی بدهید

✅ متصل شدید!

💡 برای بهترین سرعت: سرورهای مختلف را تست کنید (Real Delay).
""",

"guide_android_hiddify": """
🤖 راهنمای نصب روی اندروید — Hiddify
━━━━━━━━━━━━━━━━━━━━━━━━

📥 مرحله ۱ — دانلود اپ
• Google Play: «Hiddify» جستجو کنید
• یا از GitHub: github.com/hiddify/hiddify-next/releases

⚙️ مرحله ۲ — اضافه کردن Subscription
• اپ را باز کنید
• دکمه «افزودن پروفایل» یا ➕ را بزنید
• «اضافه کردن از URL» را انتخاب کنید
• لینک Sub را وارد کنید
• «ذخیره» را بزنید — سرورها لود می‌شوند

⚙️ یا: وارد کردن کانفیگ مستقیم
• ➕ → «اضافه کردن از متن»
• کانفیگ VLESS را paste کنید

▶️ مرحله ۳ — اتصال
• از لیست سرورها یکی را انتخاب کنید
• دکمه اتصال را بزنید

✅ متصل شدید!

💡 Hiddify برای مبتدی‌ها بسیار کاربرپسند است.
""",

"guide_windows": """
🪟 راهنمای نصب روی ویندوز — V2RayN
━━━━━━━━━━━━━━━━━━━━━━━━

📥 مرحله ۱ — دانلود
• GitHub: github.com/2dust/v2rayN/releases
• فایل «v2rayN-With-Core.zip» را دانلود کنید

⚙️ مرحله ۲ — نصب
• فایل ZIP را Extract کنید
• v2rayN.exe را اجرا کنید
• آیکون در System Tray ظاهر می‌شود

📋 مرحله ۳ — وارد کردن کانفیگ
• روی آیکون system tray دابل‌کلیک کنید
• از منو: Servers → Add [VMess/VLESS] Server
• یا: Ctrl+V برای paste از clipboard
• Save را بزنید

🔗 مرحله ۴ — Subscription
• Subscriptions → Subscription Group Setting
• ➕ بزنید و لینک Sub را وارد کنید
• OK → Subscriptions → Update Subscription

▶️ مرحله ۵ — اتصال
• کانفیگ را انتخاب کنید → Enter
• System Proxy را فعال کنید:
  از System Tray → System proxy → Set system proxy

✅ ویندوز از پروکسی استفاده می‌کند.

💡 برای Firefox: تنظیمات proxy دستی یا FoxyProxy.
""",

"guide_mac": """
🍏 راهنمای نصب روی مک — V2Box / Hiddify
━━━━━━━━━━━━━━━━━━━━━━━━

روش ۱: V2Box (Mac App Store)
• Mac App Store → «V2Box» جستجو و نصب کنید
• باز کنید → Configs → ➕ → Import from Clipboard
• کانفیگ VLESS را paste کنید
• Subscriptions → ➕ → لینک Sub را وارد کنید
• Connect را بزنید

روش ۲: Hiddify (پیشنهادی)
• github.com/hiddify/hiddify-next/releases
• فایل .dmg را دانلود و نصب کنید
• افزودن پروفایل → از URL → لینک Sub را وارد کنید
• اتصال بزنید

✅ متصل شدید!

💡 نکته مک: در System Preferences → Network
   از پروکسی SOCKS5 می‌توانید استفاده کنید.
""",
}
