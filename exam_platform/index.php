<?php
/**
 * index.php - صفحهٔ اصلی عمومی سامانه
 * کاربر واردشده به پنل مربوطه می‌رود؛ بقیه صفحهٔ معرفی عمومی را می‌بینند.
 */
require_once __DIR__ . '/config/database.php';
require_once __DIR__ . '/config/security.php';
if (isTeacher()) redirect('teacher/panel.php');
if (isAdmin())   redirect('admin/index.php');

$siteName = APP_NAME;
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= h($siteName) ?></title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800;900&display=swap">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{--primary:#6366f1;--primary-d:#4f46e5;--accent:#8b5cf6;}
body{font-family:'Vazirmatn','Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;overflow-x:hidden;}
.bg{position:fixed;inset:0;z-index:0;background:
    radial-gradient(ellipse at 20% 10%,rgba(99,102,241,.18),transparent 55%),
    radial-gradient(ellipse at 85% 90%,rgba(139,92,246,.15),transparent 55%),
    linear-gradient(160deg,#0f172a,#1e1b4b 60%,#0f172a);}
.wrap{position:relative;z-index:1;max-width:1100px;margin:0 auto;padding:24px 20px 60px;}
.nav{display:flex;align-items:center;justify-content:space-between;padding:14px 0;flex-wrap:wrap;gap:12px;}
.brand{display:flex;align-items:center;gap:12px;font-weight:900;font-size:20px;}
.brand .ico{font-size:30px;}
.nav-actions{display:flex;gap:10px;flex-wrap:wrap;}
.btn{display:inline-flex;align-items:center;gap:8px;padding:11px 22px;border-radius:40px;font-size:14px;font-weight:800;text-decoration:none;cursor:pointer;border:none;font-family:inherit;transition:.25s;}
.btn-primary{background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 12px 30px rgba(99,102,241,.4);}
.btn-ghost{background:rgba(255,255,255,.06);color:#fff;border:1px solid rgba(255,255,255,.12);}
.btn-ghost:hover{background:rgba(255,255,255,.12);}
.hero{text-align:center;padding:70px 0 50px;}
.hero h1{font-size:clamp(30px,6vw,52px);font-weight:900;line-height:1.25;color:#fff;}
.hero h1 .grad{background:linear-gradient(135deg,#818cf8,#c4b5fd);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;}
.hero p{margin-top:18px;font-size:clamp(14px,2.5vw,18px);color:#94a3b8;max-width:640px;margin-inline:auto;line-height:1.9;}
.hero .cta{margin-top:34px;display:flex;gap:14px;justify-content:center;flex-wrap:wrap;}
.features{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin-top:30px;}
.feat{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:24px;padding:26px;transition:.25s;}
.feat:hover{transform:translateY(-4px);border-color:rgba(99,102,241,.5);background:rgba(99,102,241,.07);}
.feat .fico{font-size:34px;margin-bottom:14px;}
.feat h3{font-size:17px;font-weight:800;color:#fff;margin-bottom:8px;}
.feat p{font-size:13px;color:#94a3b8;line-height:1.8;}
.footer{text-align:center;margin-top:54px;color:#64748b;font-size:12px;line-height:2;}
.footer a{color:#a5b4fc;text-decoration:none;}
.exam-note{margin-top:40px;background:rgba(255,255,255,.04);border:1px dashed rgba(255,255,255,.15);border-radius:20px;padding:20px 24px;text-align:center;font-size:14px;color:#cbd5e1;}
</style>
</head>
<body>
<div class="bg"></div>
<div class="wrap">

    <div class="nav">
        <div class="brand"><span class="ico">📘</span> <?= h($siteName) ?></div>
        <div class="nav-actions">
            <a href="login.php" class="btn btn-ghost">👨‍🏫 ورود معلم</a>
            <a href="admin/index.php" class="btn btn-primary">🔐 پنل مدیریت</a>
        </div>
    </div>

    <div class="hero">
        <h1>سامانهٔ جامع <span class="grad">آزمون و حضوروغیاب آنلاین</span></h1>
        <p>برگزاری آزمون امن با ضدتقلب پیشرفته، نظارت تصویری با هوش مصنوعی، کنترل موقعیت مکانی (GPS)
           و گزارش‌گیری حرفه‌ای — مناسب مدارس و مراکز آموزشی.</p>
        <div class="cta">
            <a href="login.php" class="btn btn-primary">شروع کنید →</a>
        </div>
    </div>

    <div class="features">
        <div class="feat"><div class="fico">🛡️</div><h3>ضدتقلب چندلایه</h3><p>تشخیص تعویض تب، تمام‌صفحهٔ اجباری، مسدودسازی کپی/راست‌کلیک و ثبت کامل رویدادها.</p></div>
        <div class="feat"><div class="fico">🤖</div><h3>نظارت هوشمند با وب‌کم</h3><p>تشخیص چهره با هوش مصنوعی؛ خروج سر از کادر یا حضور چند نفر به‌عنوان تقلب ثبت می‌شود.</p></div>
        <div class="feat"><div class="fico">🗺️</div><h3>کنترل موقعیت GPS</h3><p>محدودهٔ مجاز آزمون و شناسایی تقلب گروهی بر اساس نزدیکی مکانی شرکت‌کنندگان.</p></div>
        <div class="feat"><div class="fico">📝</div><h3>فرم‌ساز پیشرفته</h3><p>بیش از ۱۲ نوع سوال، بانک سوال، نمره‌منفی، حد قبولی و چیدمان تصادفی.</p></div>
        <div class="feat"><div class="fico">📊</div><h3>گزارش و آنالیتیکس</h3><p>نمودار توزیع نمرات، خروجی Excel/CSV و مانیتورینگ زندهٔ شرکت‌کنندگان.</p></div>
        <div class="feat"><div class="fico">📱</div><h3>سازگار با موبایل</h3><p>پنل مدیریت، پنل معلم و صفحهٔ آزمون به‌طور کامل روی گوشی کار می‌کنند.</p></div>
    </div>

    <div class="exam-note">
        🎓 دانش‌آموز گرامی: برای شرکت در آزمون یا ثبت حضور، از <strong>لینک اختصاصی</strong> که معلم برایتان ارسال کرده استفاده کنید.
    </div>

    <div class="footer">
        © <?= date('Y') ?> <?= h($siteName) ?> — نسخهٔ <?= h(APP_VERSION) ?><br>
        ارتباط با پشتیبانی: <a href="https://eitaa.com/MahanSoleymani01" target="_blank" rel="noopener">@MahanSoleymani01</a>
    </div>

</div>
</body>
</html>
