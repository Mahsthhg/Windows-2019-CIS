<?php
/**
 * attendance.php - صفحه ثبت حضور دانش‌آموزان
 * Fixed: removed teacher_id from INSERT (not needed in attendance_records)
 */
require_once __DIR__ . '/config/database.php';
require_once __DIR__ . '/config/security.php';

$link = sanitizeString($_GET['link'] ?? '', 100);
if (empty($link)) die(errorPage('لینک نامعتبر است', 'آدرس وارد شده صحیح نیست'));

$stmt = $pdo->prepare("SELECT * FROM attendances WHERE unique_link=?");
$stmt->execute([$link]);
$att = $stmt->fetch();
if (!$att) die(errorPage('جلسه یافت نشد', 'این لینک معتبر نیست یا حذف شده'));

$now = time();
$start = $att['start_time'] ? strtotime($att['start_time']) : null;
$end   = $att['end_time']   ? strtotime($att['end_time'])   : null;
$active = $att['is_active'] && $start && $end && $now >= $start && $now <= $end;

if (!$active) {
    if (!$start || !$end) die(errorPage('جلسه هنوز فعال نشده', 'معلم به زودی جلسه را فعال خواهد کرد'));
    if ($now < $start)    die(errorPage('جلسه هنوز شروع نشده', 'شروع از ساعت ' . date('H:i', $start)));
    if ($now > $end)      die(errorPage('زمان ثبت حضور به پایان رسید', 'پایان در ' . date('H:i', $end)));
    die(errorPage('جلسه غیرفعال است', 'با معلم تماس بگیرید'));
}

$remaining = max(0, $end - $now);
$total_dur = $att['duration_minutes'] * 60;
$progress  = $total_dur > 0 ? min(100, (($total_dur - $remaining) / $total_dur) * 100) : 0;

$error   = '';
$success = false;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    requireCsrf();
    $name     = sanitizeString($_POST['student_name'] ?? '', 200);
    $national = sanitizeString($_POST['national_code'] ?? '', 10);
    $class    = sanitizeString($_POST['class_number'] ?? '', 50);
    $ip       = getClientIP();
    $gpsLat   = ($_POST['gps_lat'] ?? '') !== '' ? (float)$_POST['gps_lat'] : null;
    $gpsLng   = ($_POST['gps_lng'] ?? '') !== '' ? (float)$_POST['gps_lng'] : null;

    if (mb_strlen($name) < 3) {
        $error = 'نام و نام خانوادگی باید حداقل ۳ کاراکتر باشد';
    } elseif (empty($class)) {
        $error = 'شماره کلاس الزامی است';
    } elseif ($national !== '' && !validateNationalCode($national)) {
        $error = 'کد ملی وارد شده معتبر نیست';
    } elseif ($att['require_location'] && ($gpsLat === null || $gpsLng === null)) {
        $error = 'برای ثبت حضور باید دسترسی به موقعیت مکانی را تأیید کنید';
    } else {
        // تشخیص تکراری: بر اساس کد ملی (در صورت وجود) یا نام — نه IP،
        // چون چند دانش‌آموز ممکن است روی یک وای‌فای/NAT مشترک باشند
        if ($national !== '') {
            $s = $pdo->prepare("SELECT COUNT(*) FROM attendance_records WHERE attendance_id=? AND national_code=?");
            $s->execute([$att['id'], $national]);
        } else {
            $s = $pdo->prepare("SELECT COUNT(*) FROM attendance_records WHERE attendance_id=? AND student_name=?");
            $s->execute([$att['id'], $name]);
        }
        if ((int)$s->fetchColumn() > 0) {
            $error = 'شما قبلاً در این جلسه حضور خود را ثبت کرده‌اید';
        } else {
            $pdo->prepare("INSERT INTO attendance_records (attendance_id, student_name, national_code, class_number, ip_address, gps_lat, gps_lng) VALUES (?,?,?,?,?,?,?)")
                ->execute([$att['id'], $name, $national, $class, $ip, $gpsLat, $gpsLng]);
            $success = true;
        }
    }
}
$csrf = generateCsrfToken();

function errorPage(string $title, string $detail): string {
    return '<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' . htmlspecialchars($title) . '</title>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;800&display=swap">
    <style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:"Vazirmatn",sans-serif;background:linear-gradient(135deg,#0f172a,#1e293b);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
    .card{background:white;border-radius:40px;padding:48px;text-align:center;max-width:400px;width:100%;box-shadow:0 32px 64px rgba(0,0,0,.4);}
    .icon{font-size:72px;margin-bottom:20px;}h2{font-size:24px;font-weight:800;color:#0f172a;margin-bottom:12px;}p{color:#64748b;}</style>
    </head><body><div class="card"><div class="icon">⚠️</div><h2>' . htmlspecialchars($title) . '</h2><p>' . htmlspecialchars($detail) . '</p></div></body></html>';
}
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>ثبت حضور | <?= h($att['title']) ?></title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Vazirmatn',sans-serif;background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;position:relative;overflow:hidden;}
body::before{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(ellipse at 40% 40%,rgba(99,102,241,.15) 0%,transparent 60%);pointer-events:none;}

.card{max-width:480px;width:100%;background:rgba(255,255,255,.98);border-radius:48px;overflow:hidden;box-shadow:0 32px 64px rgba(0,0,0,.4);position:relative;z-index:1;animation:rise .5s cubic-bezier(.2,.9,.4,1.1);}
@keyframes rise{from{opacity:0;transform:translateY(30px);}to{opacity:1;transform:translateY(0);}}

.header{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;padding:36px 28px;text-align:center;position:relative;overflow:hidden;}
.header::before{content:'';position:absolute;inset:0;background:radial-gradient(circle at 30% 40%,rgba(255,255,255,.15) 0%,transparent 70%);}
.header-icon{font-size:52px;margin-bottom:12px;display:block;animation:bounce .6s ease;}
@keyframes bounce{0%,100%{transform:translateY(0);}50%{transform:translateY(-10px);}}
.header h1{font-size:22px;font-weight:800;margin-bottom:6px;position:relative;}
.header p{font-size:13px;opacity:.9;position:relative;}
.session-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.2);padding:6px 16px;border-radius:40px;font-size:12px;margin-top:12px;position:relative;}

.timer-section{background:#1e293b;padding:20px 24px;}
.timer-label{font-size:11px;color:#94a3b8;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;text-align:center;}
.timer-display{font-size:48px;font-weight:800;font-family:monospace;color:#fbbf24;text-align:center;text-shadow:0 0 20px rgba(251,191,36,.3);letter-spacing:4px;}
.prog-bar{background:rgba(255,255,255,.1);border-radius:20px;height:6px;margin-top:12px;}
.prog-fill{background:linear-gradient(90deg,#fbbf24,#f59e0b);height:100%;border-radius:20px;transition:width 1s ease;width:<?= $progress ?>%;}

.form-area{padding:32px 28px;}
.form-group{margin-bottom:22px;}
label{display:flex;align-items:center;gap:8px;font-weight:700;font-size:13px;color:#0f172a;margin-bottom:10px;}
.form-control{width:100%;padding:15px 18px;border:2px solid #e2e8f0;border-radius:24px;font-size:15px;font-family:inherit;transition:.3s;}
.form-control:focus{outline:none;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.1);}
.btn-submit{width:100%;padding:17px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;border:none;border-radius:40px;font-size:17px;font-weight:800;cursor:pointer;font-family:inherit;transition:.3s;position:relative;overflow:hidden;}
.btn-submit::before{content:'';position:absolute;top:0;left:-100%;width:100%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.2),transparent);transition:.5s;}
.btn-submit:hover::before{left:100%;}
.btn-submit:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(99,102,241,.4);}
.error{background:#fee2e2;color:#991b1b;border:1px solid #fecaca;padding:12px 16px;border-radius:20px;margin-bottom:20px;font-size:13px;animation:shake .3s ease;}
@keyframes shake{0%,100%{transform:translateX(0);}25%,75%{transform:translateX(-4px);}50%{transform:translateX(4px);}}
.success-box{background:linear-gradient(135deg,#dcfce7,#bbf7d0);border-radius:24px;padding:32px;text-align:center;}
.success-icon{font-size:64px;margin-bottom:12px;}
.success-box p{font-size:16px;font-weight:700;color:#166534;}
.success-box small{font-size:12px;color:#4ade80;display:block;margin-top:8px;}
.footer{background:#f8fafc;padding:16px;text-align:center;font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;}
</style>
</head>
<body>
<div class="card">
    <div class="header">
        <span class="header-icon">📋</span>
        <h1>ثبت حضور و غیاب</h1>
        <p><?= h($att['title']) ?><?= $att['class_name'] ? ' | ' . h($att['class_name']) : '' ?></p>
        <div class="session-badge">⏱️ <?= $att['duration_minutes'] ?> دقیقه | کد: <?= substr($att['unique_link'],-8) ?></div>
    </div>

    <?php if ($remaining > 0): ?>
    <div class="timer-section">
        <div class="timer-label">⏰ زمان باقی‌مانده</div>
        <div class="timer-display" id="timerDisplay"><?= sprintf('%02d:%02d', floor($remaining/60), $remaining%60) ?></div>
        <div class="prog-bar"><div class="prog-fill" id="progFill"></div></div>
    </div>
    <?php endif; ?>

    <div class="form-area">
        <?php if ($success): ?>
        <div class="success-box">
            <div class="success-icon">✅</div>
            <p>حضور شما ثبت شد!</p>
            <small>ساعت ثبت: <?= date('H:i:s') ?></small>
        </div>
        <?php else: ?>
            <?php if ($error): ?><div class="error">⚠️ <?= h($error) ?></div><?php endif; ?>
            <form method="POST" id="attForm">
                <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
                <input type="hidden" name="gps_lat" id="gpsLat" value="">
                <input type="hidden" name="gps_lng" id="gpsLng" value="">
                <?php if ($att['require_location']): ?>
                <div id="locStatus" style="background:#fffbeb;border:1px solid #fde68a;color:#92400e;border-radius:14px;padding:10px 14px;font-size:12px;margin-bottom:14px;">📍 در حال دریافت موقعیت مکانی شما...</div>
                <?php endif; ?>
                <div class="form-group">
                    <label><span>👤</span> نام و نام خانوادگی</label>
                    <input class="form-control" name="student_name" placeholder="مثال: علی محمدی" required autofocus minlength="3">
                </div>
                <div class="form-group">
                    <label><span>🆔</span> کد ملی (اختیاری)</label>
                    <input class="form-control" name="national_code" placeholder="۱۰ رقم" pattern="[0-9]{10}" maxlength="10">
                </div>
                <div class="form-group">
                    <label><span>🏫</span> شماره کلاس</label>
                    <input class="form-control" name="class_number" placeholder="مثال: ۲۰۱" required>
                </div>
                <button type="submit" class="btn-submit">✅ ثبت حضور</button>
            </form>
        <?php endif; ?>
    </div>
    <div class="footer">سامانه مدیریت حضور‌وغیاب پیشرفته | v2.0</div>
</div>

<?php if ($remaining > 0 && !$success): ?>
<script>
let rem = <?= $remaining ?>;
const tot = <?= $total_dur ?>;
const disp = document.getElementById('timerDisplay');
const prog = document.getElementById('progFill');
setInterval(() => {
    if (--rem <= 0) { disp.textContent='00:00'; if(prog)prog.style.width='100%'; setTimeout(()=>location.reload(),1000); return; }
    disp.textContent = String(Math.floor(rem/60)).padStart(2,'0')+':'+String(rem%60).padStart(2,'0');
    if (prog && tot>0) prog.style.width = Math.min(100,((tot-rem)/tot)*100)+'%';
}, 1000);
</script>
<?php endif; ?>
<?php if ($att['require_location'] && !$success): ?>
<script>
// دریافت موقعیت مکانی برای جلسات نیازمند GPS
(function(){
    const st = document.getElementById('locStatus');
    if (!navigator.geolocation) { if(st){st.textContent='⚠️ مرورگر شما از موقعیت‌یابی پشتیبانی نمی‌کند';} return; }
    navigator.geolocation.getCurrentPosition(
        p => {
            document.getElementById('gpsLat').value = p.coords.latitude;
            document.getElementById('gpsLng').value = p.coords.longitude;
            if (st) { st.style.background='#dcfce7'; st.style.borderColor='#86efac'; st.style.color='#166534'; st.textContent='✅ موقعیت مکانی تأیید شد'; }
        },
        () => { if(st){ st.style.background='#fee2e2'; st.style.borderColor='#fecaca'; st.style.color='#991b1b'; st.textContent='❌ دسترسی به موقعیت رد شد — برای ثبت حضور لازم است'; } },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
})();
</script>
<?php endif; ?>
</body>
</html>
