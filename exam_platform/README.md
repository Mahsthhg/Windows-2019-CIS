# سامانه آزمون آنلاین v2.0

پلتفرم پیشرفته آزمون آنلاین فارسی — بازنویسی کامل با امنیت، امکانات و UI فوق پیشرفته.

## امکانات کلیدی

### فرم‌ساز پیشرفته (12+ نوع سوال)
- چندگزینه‌ای (یک انتخاب / چند انتخاب)
- صحیح/غلط
- جای‌خالی (fill-in-the-blank)
- عددی (با مقایسه دقیق)
- متن کوتاه / متن بلند (تشریحی)
- ستاره‌بندی (Rating)
- لیست کشویی (Dropdown)
- فیلدهای اطلاعات (نام، کد ملی، شماره تماس)
- بخش‌بندی / عناوین جداکننده
- **Drag & Drop** برای مرتب‌سازی سوالات

### ضدتقلب فوق پیشرفته
- اجبار به حالت تمام‌صفحه (Fullscreen)
- تشخیص تغییر تب / خروج از پنجره
- جلوگیری از Copy-Paste
- جلوگیری از راست‌کلیک
- مسدودسازی PrintScreen و DevTools
- مسدودسازی Ctrl+C/V/X/P/S
- ثبت خروج ماوس از صفحه
- لاگ کامل تقلب در دیتابیس
- شمارنده تقلب در زمان واقعی

### امنیت فوق پیشرفته
- CSRF Token روی تمام فرم‌ها
- Rate Limiting ورود (8 تلاش / 5 دقیقه)
- Session Security (regeneration، timeout، httponly cookies)
- رمزهای bcrypt با cost=12
- Prepared Statements (صفر SQL injection)
- Input sanitization و validation کامل
- Secure HTTP Headers
- .htaccess محافظت از فایل‌های حساس
- بررسی مالکیت در تمام عملیات‌های معلم

### امتیازدهی پیشرفته
- امتیاز متفاوت برای هر سوال
- نمره منفی قابل تنظیم
- حد قبولی (pass threshold) قابل تنظیم
- محاسبه Multi-select صحیح
- محاسبه Fill-blank (case-insensitive)
- محاسبه Numeric (با tolerance)

### آنالیتیکس و گزارش
- نمودار توزیع نمرات
- میانگین، بیشینه، کمینه نمره
- تعداد قبول/مردود
- کل تقلب‌های ثبت شده
- جزئیات پاسخنامه هر شرکت‌کننده
- **خروجی CSV/Excel** با BOM فارسی

### بانک سوال
- ذخیره سوالات برای استفاده مجدد
- دسته‌بندی، سختی، تگ
- import مستقیم به آزمون
- شمارنده استفاده

## نصب

1. فایل‌ها را در root سرور قرار دهید
2. به `install.php` بروید
3. اطلاعات دیتابیس و رمز ادمین را وارد کنید
4. بعد از نصب، `install.php` را **حذف یا rename** کنید

## ساختار فایل‌ها
```
exam_platform/
├── config/database.php     ← اتصال DB + توابع امنیتی پایه
├── config/security.php     ← CSRF + Rate Limiting + Auth
├── admin/
│   ├── login.php           ← ورود ادمین (bcrypt)
│   └── index.php           ← داشبورد + مدیریت معلمان + کلیدها
├── teacher/
│   ├── panel.php           ← داشبورد معلم
│   ├── create_exam.php     ← فرم‌ساز پیشرفته
│   ├── results.php         ← نتایج + آنالیتیکس + CSV
│   ├── attendance.php      ← مدیریت حضور‌وغیاب
│   └── question_bank.php   ← بانک سوال
├── exam/
│   ├── index.php           ← صفحه آزمون (ضدتقلب کامل)
│   └── result.php          ← نتیجه (با confetti برای قبولی)
├── api/
│   ├── submit_exam.php     ← ثبت نهایی پاسخ‌ها
│   ├── anti_cheat.php      ← لاگ تقلب
│   └── save_answer.php     ← ذخیره خودکار
├── assets/css/panel.css    ← CSS یکپارچه با Vazirmatn
├── attendance.php          ← ثبت حضور دانش‌آموزان
├── login.php               ← ورود معلم (کلید یا username:pass)
└── install.php             ← نصب‌کننده گرافیکی
```

## باگ‌های اصلاح‌شده نسخه قبلی
- جدول اشتباه `teacher_keys` → `access_keys`
- Session key های اشتباه (`final_score` vs `last_score`)
- ستون‌های غیرموجود `final_slug` و `is_finalized` در `exam.php`
- مسیر اشتباه `../includes/db.php` در `teacher_dashboard.php`
- مقایسه plaintext رمز ادمین → bcrypt
- فقدان CSRF protection
- فقدان rate limiting
- `teacher_id NOT NULL` بدون مقدار در `attendance_records`
