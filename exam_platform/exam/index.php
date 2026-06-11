<?php
/**
 * exam/index.php - صفحه آزمون پیشرفته با ضد تقلب کامل
 * Fixed: session keys, question types, anti-cheat, auto-save
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

$slug = sanitizeString($_GET['slug'] ?? $_GET['link'] ?? '', 100);
if (empty($slug)) die(renderError('لینک نامعتبر است'));

// یافتن فرم
$stmt = $pdo->prepare("SELECT * FROM forms WHERE exam_link=? AND is_active=1");
$stmt->execute([$slug]);
$form = $stmt->fetch();
if (!$form) die(renderError('آزمون یافت نشد یا فعال نیست'));

$settings = $form;
$fid      = (int)$form['id'];
$tid      = (int)$form['teacher_id'];
$clientIP = getClientIP();

// بررسی IP در لیست سیاه
$stmt = $pdo->prepare("SELECT id FROM ip_blacklist WHERE ip_address=? AND is_active=1 AND (expires_at IS NULL OR expires_at > NOW())");
$stmt->execute([$clientIP]);
if ($stmt->fetch()) die(renderError('دسترسی شما مسدود شده است. با مدیر تماس بگیرید.'));

// بررسی زمان
$now = time();
if ($form['start_time'] && strtotime($form['start_time']) > $now) {
    die(renderError('آزمون هنوز شروع نشده است. زمان شروع: ' . $form['start_time']));
}
if ($form['end_time'] && strtotime($form['end_time']) < $now) {
    die(renderError('زمان آزمون به پایان رسیده است.'));
}

// بررسی رمز عبور آزمون
if ($form['password']) {
    if (!isset($_SESSION['exam_auth_' . $fid])) {
        if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['exam_password'])) {
            if ($_POST['exam_password'] === $form['password']) {
                $_SESSION['exam_auth_' . $fid] = true;
            } else {
                $pwError = 'رمز عبور اشتباه است';
            }
        }
        if (!isset($_SESSION['exam_auth_' . $fid])) {
            die(renderPasswordForm($form['title'], $pwError ?? ''));
        }
    }
}

// بررسی تعداد تلاش
$stmt = $pdo->prepare("SELECT COUNT(*) FROM answers WHERE form_id=? AND user_ip=? AND status='completed'");
$stmt->execute([$fid, $clientIP]);
$attempts = (int)$stmt->fetchColumn();
if ($attempts >= $form['max_attempts']) {
    die(renderError('شما قبلاً در این آزمون شرکت کرده‌اید. تعداد مجاز: ' . $form['max_attempts']));
}

// دریافت سوالات
$stmt = $pdo->prepare("SELECT * FROM questions WHERE form_id=? ORDER BY order_index");
$stmt->execute([$fid]);
$questions = $stmt->fetchAll();

if (empty($questions)) die(renderError('این آزمون سوالی ندارد'));

// ترتیب تصادفی سوالات
if ($form['shuffle_questions']) {
    if (!isset($_SESSION['exam_order_' . $fid])) {
        $order = range(0, count($questions) - 1);
        shuffle($order);
        $_SESSION['exam_order_' . $fid] = $order;
    }
    $order = $_SESSION['exam_order_' . $fid];
    $shuffled = [];
    foreach ($order as $i) $shuffled[] = $questions[$i];
    $questions = $shuffled;
}

// ترتیب تصادفی گزینه‌ها
if ($form['shuffle_options']) {
    foreach ($questions as &$q) {
        if (in_array($q['type'], ['multiple_choice', 'multi_select', 'dropdown'])) {
            $opts = json_decode($q['options'], true);
            if (is_array($opts) && count($opts) > 1) {
                $correctIdx = (int)$q['correct_answer'] - 1;
                $correctVal = $opts[$correctIdx] ?? null;
                if (!isset($_SESSION['opt_order_' . $q['id']])) {
                    $oOrder = range(0, count($opts)-1);
                    shuffle($oOrder);
                    $_SESSION['opt_order_' . $q['id']] = $oOrder;
                }
                $oOrder = $_SESSION['opt_order_' . $q['id']];
                $newOpts = [];
                foreach ($oOrder as $oi) $newOpts[] = $opts[$oi];
                $q['options'] = json_encode($newOpts, JSON_UNESCAPED_UNICODE);
                // پیدا کردن ایندکس جدید گزینه صحیح
                if ($correctVal !== null) {
                    $newCorrect = array_search($correctVal, $newOpts);
                    $q['correct_answer'] = $newCorrect !== false ? (string)($newCorrect + 1) : $q['correct_answer'];
                }
            }
        }
    }
    unset($q);
}

// محاسبه حداکثر امتیاز
$maxScore = 0;
foreach ($questions as $q) $maxScore += (float)$q['points'];

// دریافت نام دانش‌آموز (از session اگر موجود)
$studentName = $_SESSION['exam_student_name_' . $fid] ?? '';

// شروع آزمون (ثبت رکورد)
if (!isset($_SESSION['exam_start_' . $fid])) {
    $_SESSION['exam_start_' . $fid] = time();
}
$startTime = $_SESSION['exam_start_' . $fid];

// ── ساخت/بازیابی رکورد «started» تا مانیتورینگ زنده، عکس‌ها و GPS به شرکت‌کننده وصل شوند ──
$answerId  = $_SESSION['exam_answer_id_' . $fid] ?? null;
$validRow  = false;
if ($answerId) {
    $chk = $pdo->prepare("SELECT id FROM answers WHERE id=? AND form_id=? AND status='started'");
    $chk->execute([$answerId, $fid]);
    if ($chk->fetch()) $validRow = true;
}
if (!$validRow) {
    $ua = substr($_SERVER['HTTP_USER_AGENT'] ?? '', 0, 500);
    $fp = substr(hash('sha256', $clientIP . $ua), 0, 16);
    $ins = $pdo->prepare("INSERT INTO answers (form_id, teacher_id, user_ip, user_agent, browser_fp, status, started_at) VALUES (?,?,?,?,?, 'started', NOW())");
    $ins->execute([$fid, $tid, $clientIP, $ua, $fp]);
    $answerId = (int)$pdo->lastInsertId();
    $_SESSION['exam_answer_id_' . $fid] = $answerId;
}

$elapsed = time() - $startTime;
$remaining = max(0, $form['duration'] * 60 - $elapsed);

// Helper: render error page
function renderError(string $msg): string {
    return '<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>خطا</title>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;800&display=swap">
    <style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:"Vazirmatn",sans-serif;background:#0f172a;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
    .card{background:white;border-radius:32px;padding:48px;text-align:center;max-width:400px;width:100%;}
    .icon{font-size:64px;margin-bottom:20px;}h2{font-size:22px;font-weight:800;color:#0f172a;margin-bottom:12px;}p{color:#64748b;}</style>
    </head><body><div class="card"><div class="icon">⚠️</div><h2>خطا</h2><p>' . htmlspecialchars($msg, ENT_QUOTES, 'UTF-8') . '</p></div></body></html>';
}

function renderPasswordForm(string $title, string $error = ''): string {
    return '<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>رمز آزمون</title>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;800&display=swap">
    <style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:"Vazirmatn",sans-serif;background:#0f172a;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
    .card{background:white;border-radius:32px;padding:48px;text-align:center;max-width:400px;width:100%;}.h1{font-size:22px;font-weight:800;margin-bottom:24px;}
    input{width:100%;padding:14px;border:2px solid #e2e8f0;border-radius:20px;font-size:16px;margin-bottom:16px;font-family:inherit;text-align:center;}
    input:focus{outline:none;border-color:#6366f1;}
    .btn{width:100%;padding:14px;background:#6366f1;color:white;border:none;border-radius:20px;font-size:16px;font-weight:800;cursor:pointer;font-family:inherit;}
    .err{color:#dc2626;font-size:13px;margin-bottom:16px;}</style>
    </head><body><div class="card"><div style="font-size:48px;margin-bottom:16px;">🔒</div>
    <div class="h1">' . htmlspecialchars($title, ENT_QUOTES) . '</div>
    <p style="color:#64748b;margin-bottom:20px;">این آزمون رمزدار است</p>
    ' . ($error ? '<div class="err">❌ ' . htmlspecialchars($error) . '</div>' : '') . '
    <form method="POST"><input type="password" name="exam_password" placeholder="رمز عبور آزمون" autofocus required>
    <button type="submit" class="btn">ورود ←</button></form></div></body></html>';
}
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title><?= h($form['title']) ?> | آزمون آنلاین</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{--primary:#6366f1;--success:#10b981;--danger:#ef4444;--warning:#f59e0b;}
body{font-family:'Vazirmatn','Segoe UI',sans-serif;background:#f1f5f9;min-height:100vh;padding-bottom:100px;}
body.fullscreen-mode{background:#0f172a;}

/* ── Anti-Cheat Overlay ── */
#cheatOverlay{
    display:none;position:fixed;inset:0;
    background:rgba(220,38,38,.95);
    z-index:9999;
    align-items:center;justify-content:center;
    flex-direction:column;gap:16px;
    color:white;text-align:center;
    padding:40px;
}
#cheatOverlay.show{display:flex;}
#cheatOverlay h2{font-size:28px;font-weight:800;}
#cheatOverlay p{font-size:16px;opacity:.9;}
#cheatOverlay .cheat-counter{font-size:56px;font-weight:800;}

/* ── Warning Banner ── */
#warnBanner{
    position:fixed;top:0;left:0;right:0;
    background:var(--warning);color:#1a1a1a;
    padding:12px;text-align:center;
    font-weight:700;font-size:14px;
    z-index:1000;display:none;
    animation:slideDown .3s ease;
}
@keyframes slideDown{from{transform:translateY(-100%)}to{transform:translateY(0)}}
#warnBanner.show{display:block;}

/* ── Fixed Header ── */
.exam-topbar{
    position:fixed;top:0;left:0;right:0;
    background:linear-gradient(135deg,#1e293b,#0f172a);
    color:white;padding:12px 24px;
    display:flex;align-items:center;justify-content:space-between;
    z-index:500;box-shadow:0 4px 20px rgba(0,0,0,.3);
}
.exam-topbar .title{font-size:16px;font-weight:700;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.timer-display{
    background:rgba(255,255,255,.1);
    border:1px solid rgba(255,255,255,.2);
    padding:8px 20px;border-radius:40px;
    font-family:monospace;font-size:20px;font-weight:800;
    min-width:110px;text-align:center;
    transition:color .3s;
}
.timer-display.warn{color:var(--warning);}
.timer-display.danger{color:var(--danger);animation:pulse 1s ease infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
.cheat-count{
    background:rgba(239,68,68,.2);border:1px solid rgba(239,68,68,.4);
    padding:6px 14px;border-radius:40px;font-size:13px;
    display:flex;align-items:center;gap:6px;
}

/* ── Progress ── */
.exam-progress{
    position:fixed;top:60px;left:0;right:0;
    height:4px;background:rgba(255,255,255,.1);z-index:499;
}
.exam-progress-fill{
    height:100%;background:linear-gradient(90deg,var(--primary),#8b5cf6);
    transition:width .4s ease;
}

/* ── Main Content ── */
.exam-wrapper{
    max-width:780px;margin:0 auto;
    padding:90px 20px 120px;
}

/* ── Question Card ── */
.q-card{
    background:white;border-radius:24px;
    padding:32px;margin-bottom:20px;
    border:2px solid transparent;
    transition:border-color .3s;
    animation:fadeIn .3s ease;
}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.q-card.one-at-a-time{display:none;}
.q-card.active{display:block;border-color:var(--primary);}
.q-card.answered{border-color:var(--success);}

.q-number{
    display:inline-flex;align-items:center;justify-content:center;
    width:36px;height:36px;border-radius:50%;
    background:var(--primary);color:white;
    font-size:14px;font-weight:800;
    margin-bottom:16px;
}
.q-points{float:left;background:#ede9fe;color:#5b21b6;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;}
.q-title{font-size:17px;font-weight:700;line-height:1.6;margin-bottom:8px;color:#0f172a;}
.q-desc{font-size:13px;color:#64748b;margin-bottom:20px;}
.q-hint{background:#fefce8;border:1px solid #fde68a;border-radius:12px;padding:10px 14px;font-size:12px;color:#92400e;margin-bottom:16px;}

/* ── Options ── */
.options{display:flex;flex-direction:column;gap:10px;}
.option-label{
    display:flex;align-items:center;gap:14px;
    padding:14px 18px;background:#f8fafc;
    border:2px solid #e2e8f0;border-radius:16px;
    cursor:pointer;transition:.2s;font-size:15px;
}
.option-label:hover{border-color:var(--primary);background:#f0f0ff;}
.option-label.selected{border-color:var(--primary);background:#ede9fe;font-weight:600;}
.option-label input{accent-color:var(--primary);width:18px;height:18px;cursor:pointer;flex-shrink:0;}
.option-letter{
    width:28px;height:28px;border-radius:50%;
    background:#e2e8f0;display:flex;align-items:center;justify-content:center;
    font-size:12px;font-weight:700;flex-shrink:0;
    transition:.2s;
}
.option-label.selected .option-letter{background:var(--primary);color:white;}

/* ── Text Inputs ── */
.q-input{
    width:100%;padding:14px 18px;
    border:2px solid #e2e8f0;border-radius:16px;
    font-size:15px;font-family:inherit;
    transition:.2s;background:white;
}
.q-input:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(99,102,241,.1);}
textarea.q-input{min-height:120px;resize:vertical;}

/* ── True/False ── */
.tf-options{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.tf-btn{
    padding:20px;border:2px solid #e2e8f0;border-radius:20px;
    cursor:pointer;text-align:center;font-size:16px;font-weight:700;
    transition:.2s;background:white;
}
.tf-btn:hover,.tf-btn.selected{border-color:var(--primary);background:#ede9fe;}
.tf-btn.selected.true-btn{border-color:var(--success);background:#dcfce7;color:#166534;}
.tf-btn.selected.false-btn{border-color:var(--danger);background:#fee2e2;color:#991b1b;}

/* ── Rating ── */
.rating-stars{display:flex;gap:8px;font-size:32px;cursor:pointer;justify-content:center;padding:16px 0;}
.rating-stars span{transition:.2s;opacity:.4;}
.rating-stars span.active{opacity:1;}
.rating-stars span:hover,.rating-stars span:hover~span{opacity:.7;}

/* ── Fill Blank ── */
.fill-blank-text{font-size:16px;line-height:2.5;margin-bottom:12px;background:#f8fafc;padding:16px;border-radius:16px;}
.blank-input{
    display:inline-block;min-width:80px;max-width:200px;
    border:none;border-bottom:3px solid var(--primary);
    background:transparent;font-size:16px;font-family:inherit;
    padding:0 6px;color:var(--primary);font-weight:700;
    text-align:center;
}
.blank-input:focus{outline:none;}

/* ── Section Title ── */
.section-divider{
    padding:20px 0;text-align:center;
    border-top:2px dashed #e2e8f0;
    border-bottom:2px dashed #e2e8f0;
    margin:8px 0 24px;
}
.section-divider h3{font-size:18px;font-weight:800;color:#0f172a;}

/* ── Navigator ── */
#questionNav{
    position:fixed;bottom:0;left:0;right:0;
    background:white;padding:16px 24px;
    border-top:1px solid #e2e8f0;
    display:flex;align-items:center;justify-content:space-between;
    gap:12px;box-shadow:0 -4px 20px rgba(0,0,0,.08);
    z-index:500;
}
.nav-btn{
    padding:12px 28px;border:none;border-radius:40px;
    font-size:15px;font-weight:800;cursor:pointer;
    font-family:inherit;transition:.2s;
    display:flex;align-items:center;gap:8px;
}
.nav-prev{background:#e2e8f0;color:#475569;}
.nav-prev:hover{background:#cbd5e1;}
.nav-next{background:var(--primary);color:white;}
.nav-next:hover{background:#4f46e5;transform:translateY(-1px);}
.nav-submit{background:var(--success);color:white;}
.nav-submit:hover{background:#059669;}
.q-counter{color:#64748b;font-size:14px;font-weight:600;}

/* ── Mini Navigator ── */
.mini-nav{
    display:flex;gap:4px;flex-wrap:wrap;
    padding:4px;max-width:300px;
}
.mini-dot{
    width:28px;height:28px;border-radius:50%;
    background:#f1f5f9;border:2px solid #e2e8f0;
    font-size:11px;font-weight:700;cursor:pointer;
    display:flex;align-items:center;justify-content:center;
    transition:.2s;color:#64748b;
}
.mini-dot.current{border-color:var(--primary);color:var(--primary);}
.mini-dot.answered{background:#dcfce7;border-color:var(--success);color:#166534;}

/* ── Confirm Submit ── */
#submitConfirm{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9000;align-items:center;justify-content:center;}
#submitConfirm.show{display:flex;}
.confirm-box{background:white;border-radius:32px;padding:40px;max-width:440px;width:100%;text-align:center;}
.confirm-box h3{font-size:22px;font-weight:800;margin-bottom:12px;}
.confirm-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0;}
.confirm-stat{background:#f8fafc;border-radius:16px;padding:12px;}
.confirm-stat strong{font-size:24px;font-weight:800;display:block;}
.confirm-stat span{font-size:11px;color:#64748b;}

/* ── Webcam ── */
#cameraPanel{
    position:fixed;bottom:80px;left:20px;
    background:rgba(15,23,42,.95);
    border-radius:16px;padding:12px;
    z-index:600;display:none;
    border:2px solid rgba(99,102,241,.5);
}
#cameraPanel.show{display:block;}
#camPreview{width:180px;height:135px;border-radius:12px;object-fit:cover;background:#1e293b;display:block;}
#camStatus{font-size:10px;color:#94a3b8;margin-top:6px;text-align:center;}
#camRequestAlert{
    position:fixed;top:80px;left:50%;transform:translateX(-50%);
    background:linear-gradient(135deg,#6366f1,#8b5cf6);
    color:white;border-radius:20px;padding:16px 24px;
    z-index:700;display:none;text-align:center;
    box-shadow:0 8px 24px rgba(99,102,241,.4);
    animation:slideDown .4s ease;
}
#camRequestAlert.show{display:block;}
#camRequestAlert strong{display:block;font-size:16px;font-weight:800;margin-bottom:6px;}
#camRequestAlert p{font-size:13px;opacity:.9;}

/* ── GPS Status ── */
#gpsIndicator{
    position:fixed;bottom:80px;right:20px;
    background:rgba(15,23,42,.9);
    border-radius:12px;padding:8px 14px;
    z-index:600;font-size:12px;color:white;
    display:flex;align-items:center;gap:8px;
}
#gpsDot{width:8px;height:8px;border-radius:50%;background:#94a3b8;}
#gpsDot.ok{background:#10b981;}
#gpsDot.warn{background:#f59e0b;}
#gpsDot.err{background:#ef4444;}

/* ── Watermark ── */
.watermark{
    position:fixed;top:50%;left:50%;
    transform:translate(-50%,-50%) rotate(-30deg);
    font-size:clamp(14px,3vw,24px);
    font-weight:800;color:rgba(99,102,241,.06);
    pointer-events:none;z-index:1;
    white-space:nowrap;user-select:none;
    letter-spacing:4px;
}
/* Hidden canvas for snapshots */
#snapCanvas{display:none;}

@media(max-width:640px){
    .exam-topbar{padding:10px 16px;}
    .exam-topbar .title{max-width:150px;font-size:13px;}
    .timer-display{font-size:16px;padding:6px 12px;}
    .q-card{padding:20px;}
    .nav-btn{padding:10px 20px;font-size:14px;}
}
</style>
</head>
<body>

<!-- ── Watermark ── -->
<div class="watermark" id="watermarkEl"><?= h($studentName ?: APP_NAME) ?></div>

<!-- ── Webcam Panel ── -->
<?php if ($form['require_camera']): ?>
<!-- موتور تشخیص چهره (هوش مصنوعی، سمت مرورگر) -->
<script defer src="https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.13/dist/face-api.min.js"></script>
<div id="cameraPanel">
    <video id="camPreview" autoplay muted playsinline></video>
    <div id="camStatus">📷 وب‌کم فعال</div>
</div>
<div id="camRequestAlert">
    <strong>📷 درخواست تصویر</strong>
    <p>ادمین یک تصویر از شما درخواست کرده است</p>
</div>
<?php endif; ?>

<!-- ── GPS Indicator ── -->
<?php if ($form['gps_required']): ?>
<div id="gpsIndicator">
    <div id="gpsDot"></div>
    <span id="gpsText">GPS: در حال اتصال...</span>
</div>
<?php endif; ?>

<canvas id="snapCanvas"></canvas>

<!-- ── Anti-Cheat Overlay ── -->
<div id="cheatOverlay">
    <div style="font-size:72px">🚨</div>
    <h2>تقلب ثبت شد!</h2>
    <div class="cheat-counter" id="cheatNum">0</div>
    <p id="cheatMsg">خروج از صفحه آزمون ممنوع است</p>
    <button onclick="closeCheatOverlay()" style="margin-top:20px;padding:14px 32px;background:white;color:#dc2626;border:none;border-radius:40px;font-size:16px;font-weight:800;cursor:pointer;font-family:inherit;">بازگشت به آزمون</button>
</div>

<!-- ── Warning Banner ── -->
<div id="warnBanner"></div>

<!-- ── Top Bar ── -->
<div class="exam-topbar">
    <div class="title">📋 <?= h($form['title']) ?></div>
    <div class="timer-display" id="timerDisplay">
        <?= sprintf('%02d:%02d', floor($remaining/60), $remaining%60) ?>
    </div>
    <div class="cheat-count">
        <span>⚠️</span>
        <span id="cheatCountDisplay">0</span>
        تقلب
    </div>
</div>
<div class="exam-progress"><div class="exam-progress-fill" id="progressFill" style="width:0%"></div></div>

<!-- ── Exam Form ── -->
<div class="exam-wrapper">
    <form id="examForm" method="POST" action="../api/submit_exam.php">
        <input type="hidden" name="csrf_token" value="<?= h(generateCsrfToken()) ?>">
        <input type="hidden" name="form_id" value="<?= $fid ?>">
        <input type="hidden" name="start_time" value="<?= $startTime ?>">
        <input type="hidden" name="time_per_question" id="timePerQuestion" value="{}">

        <?php
        $qNum = 0;
        $modeOneAtATime = !$form['allow_back']; // One at a time if no back allowed
        foreach ($questions as $idx => $q):
            $opts = $q['options'] ? json_decode($q['options'], true) : [];
            $isFirst = $idx === 0;
            $isInfo = in_array($q['type'], ['name_family','national_code','phone','section_title']);
            if ($q['type'] !== 'section_title') $qNum++;
            $cardClass = $modeOneAtATime ? 'q-card one-at-a-time' . ($isFirst ? ' active' : '') : 'q-card';
        ?>

        <?php if ($q['type'] === 'section_title'): ?>
        <div class="section-divider">
            <h3><?= h($q['title']) ?></h3>
            <?php if ($q['description']): ?><p style="color:#64748b;margin-top:6px;font-size:14px;"><?= h($q['description']) ?></p><?php endif; ?>
        </div>

        <?php else: ?>
        <div class="<?= $cardClass ?>" id="qcard_<?= $idx ?>" data-idx="<?= $idx ?>">
            <?php if ($q['type'] !== 'name_family' && $q['type'] !== 'national_code' && $q['type'] !== 'phone'): ?>
            <span class="q-points"><?= (float)$q['points'] ?> pt</span>
            <?php endif; ?>

            <div class="q-number"><?= $qNum ?></div>
            <div class="q-title"><?= h($q['title']) ?>
                <?php if (!$q['required']): ?> <span style="font-size:12px;color:var(--text-muted);font-weight:400">(اختیاری)</span><?php endif; ?>
            </div>
            <?php if ($q['description']): ?><div class="q-desc"><?= h($q['description']) ?></div><?php endif; ?>
            <?php if ($q['hint']): ?><div class="q-hint">💡 <?= h($q['hint']) ?></div><?php endif; ?>

            <?php /* ── Multiple Choice ── */ ?>
            <?php if (in_array($q['type'], ['multiple_choice', 'dropdown'])): ?>
            <div class="options">
                <?php foreach ($opts as $oi => $opt):
                    $letters = ['الف','ب','ج','د','ه','و'];
                ?>
                <label class="option-label" onclick="selectOption(this)">
                    <input type="radio" name="q_<?= $q['id'] ?>" value="<?= $oi+1 ?>" <?= !$q['required']?'':'required' ?>>
                    <span class="option-letter"><?= $letters[$oi] ?? ($oi+1) ?></span>
                    <?= h($opt) ?>
                </label>
                <?php endforeach; ?>
            </div>

            <?php /* ── Multi Select ── */ ?>
            <?php elseif ($q['type'] === 'multi_select'): ?>
            <div class="options" id="ms_<?= $q['id'] ?>">
                <?php foreach ($opts as $oi => $opt): ?>
                <label class="option-label" onclick="toggleMultiSelect(this)">
                    <input type="checkbox" name="q_<?= $q['id'] ?>[]" value="<?= $oi+1 ?>">
                    <span class="option-letter"><?= $oi+1 ?></span>
                    <?= h($opt) ?>
                </label>
                <?php endforeach; ?>
            </div>

            <?php /* ── True / False ── */ ?>
            <?php elseif ($q['type'] === 'true_false'): ?>
            <input type="hidden" name="q_<?= $q['id'] ?>" id="tf_<?= $q['id'] ?>" value="">
            <div class="tf-options">
                <div class="tf-btn true-btn" onclick="selectTF(<?= $q['id'] ?>,'true',this)">✅ درست</div>
                <div class="tf-btn false-btn" onclick="selectTF(<?= $q['id'] ?>,'false',this)">❌ غلط</div>
            </div>

            <?php /* ── Fill Blank ── */ ?>
            <?php elseif ($q['type'] === 'fill_blank'):
                $parts = explode('___', $q['title']);
            ?>
            <div class="fill-blank-text">
                <?php if (count($parts) <= 1): // بدون ___ یعنی یک جای خالی ساده ?>
                    <input class="blank-input" name="q_<?= $q['id'] ?>[]" type="text" placeholder="پاسخ" oninput="markAnswered(<?= $idx ?>)">
                <?php else:
                    foreach ($parts as $pi => $part):
                        echo h($part);
                        if ($pi < count($parts)-1): ?>
                        <input class="blank-input" name="q_<?= $q['id'] ?>[]" type="text" placeholder="..." oninput="markAnswered(<?= $idx ?>)">
                        <?php endif;
                    endforeach;
                endif; ?>
            </div>

            <?php /* ── Rating ── */ ?>
            <?php elseif ($q['type'] === 'rating'): ?>
            <?php $maxRating = (int)($opts[0] ?? 5); ?>
            <input type="hidden" name="q_<?= $q['id'] ?>" id="rating_<?= $q['id'] ?>" value="">
            <div class="rating-stars" id="stars_<?= $q['id'] ?>">
                <?php for ($r=1; $r<=$maxRating; $r++): ?>
                <span data-val="<?= $r ?>" onclick="setRating(<?= $q['id'] ?>,<?= $r ?>)">⭐</span>
                <?php endfor; ?>
            </div>
            <p style="text-align:center;font-size:13px;color:var(--text-muted);margin-top:-8px;">انتخاب نشده</p>

            <?php /* ── Numeric ── */ ?>
            <?php elseif ($q['type'] === 'numeric'): ?>
            <input class="q-input" type="number" step="any" name="q_<?= $q['id'] ?>" placeholder="عدد را وارد کنید" <?= $q['required']?'required':'' ?> oninput="markAnswered(<?= $idx ?>)">

            <?php /* ── Short Text ── */ ?>
            <?php elseif ($q['type'] === 'short_text'): ?>
            <input class="q-input" type="text" name="q_<?= $q['id'] ?>" placeholder="پاسخ خود را بنویسید..." maxlength="500" <?= $q['required']?'required':'' ?> oninput="markAnswered(<?= $idx ?>)">

            <?php /* ── Long Text / Descriptive ── */ ?>
            <?php elseif ($q['type'] === 'long_text'): ?>
            <textarea class="q-input" name="q_<?= $q['id'] ?>" placeholder="پاسخ تشریحی خود را بنویسید..." maxlength="5000" <?= $q['required']?'required':'' ?> oninput="markAnswered(<?= $idx ?>)"></textarea>

            <?php /* ── Name / National Code / Phone ── */ ?>
            <?php elseif ($q['type'] === 'name_family'): ?>
            <input class="q-input" type="text" name="q_<?= $q['id'] ?>" id="field_name" placeholder="نام و نام خانوادگی" required oninput="markAnswered(<?= $idx ?>)">

            <?php elseif ($q['type'] === 'national_code'): ?>
            <input class="q-input" type="text" name="q_<?= $q['id'] ?>" id="field_national" placeholder="کد ملی ۱۰ رقمی" pattern="[0-9]{10}" maxlength="10" required oninput="validateNationalCode(this);markAnswered(<?= $idx ?>)">
            <p id="ncError" style="color:var(--danger);font-size:12px;margin-top:6px;display:none;">⚠️ کد ملی نامعتبر است</p>

            <?php elseif ($q['type'] === 'phone'): ?>
            <input class="q-input" type="tel" name="q_<?= $q['id'] ?>" placeholder="شماره موبایل" pattern="[0-9]{11}" maxlength="11" oninput="markAnswered(<?= $idx ?>)">

            <?php endif; ?>
        </div><!-- /q-card -->
        <?php endif; ?>
        <?php endforeach; ?>

    </form><!-- /examForm -->
</div>

<!-- ── Fixed Bottom Nav ── -->
<div id="questionNav">
    <?php if ($modeOneAtATime): ?>
    <button class="nav-btn nav-prev" id="prevBtn" onclick="prevQ()" style="<?= !$form['allow_back']?'display:none':'' ?>">← قبلی</button>
    <div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
        <span class="q-counter" id="qCounter">سوال 1 از <?= $qNum ?></span>
        <div class="mini-nav" id="miniNav">
            <?php for ($i=0;$i<count($questions);$i++): if($questions[$i]['type']==='section_title') continue; ?>
            <div class="mini-dot <?= $i===0?'current':'' ?>" id="dot_<?= $i ?>" onclick="goToQ(<?= $i ?>)"><?= $i+1 ?></div>
            <?php endfor; ?>
        </div>
    </div>
    <button class="nav-btn nav-next" id="nextBtn" onclick="nextQ()">بعدی ←</button>
    <?php else: ?>
    <div style="flex:1;text-align:center;color:var(--text-muted);font-size:14px;">همه سوالات نمایش داده شده</div>
    <button class="nav-btn nav-submit" onclick="showSubmitConfirm()">✅ ثبت نهایی</button>
    <?php endif; ?>
</div>

<!-- ── Submit Confirm Modal ── -->
<div id="submitConfirm">
    <div class="confirm-box">
        <div style="font-size:48px;margin-bottom:12px;">📋</div>
        <h3>ثبت نهایی آزمون</h3>
        <p style="color:#64748b;margin-bottom:16px;">آیا مطمئن هستید؟ بعد از ثبت امکان ویرایش وجود ندارد.</p>
        <div class="confirm-stats">
            <div class="confirm-stat"><strong id="confAnswered">0</strong><span>پاسخ داده</span></div>
            <div class="confirm-stat"><strong id="confUnanswered">0</strong><span>بی‌پاسخ</span></div>
            <div class="confirm-stat"><strong id="confCheat">0</strong><span>تقلب</span></div>
        </div>
        <div style="display:flex;gap:12px;">
            <button onclick="submitExam()" style="flex:1;padding:14px;background:var(--success);color:white;border:none;border-radius:20px;font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;">✅ بله، ثبت شود</button>
            <button onclick="closeConfirm()" style="flex:1;padding:14px;background:#e2e8f0;color:#475569;border:none;border-radius:20px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;">انصراف</button>
        </div>
    </div>
</div>

<script>
// ══ State ════════════════════════════════════════════════════════
const FORM_ID       = <?= $fid ?>;
const TOTAL_Q       = <?= $qNum ?>;
const ALLOW_BACK    = <?= $form['allow_back'] ? 'true' : 'false' ?>;
const ONE_AT_A_TIME = <?= $modeOneAtATime ? 'true' : 'false' ?>;
const REQ_FULLSCREEN= <?= $form['require_fullscreen'] ? 'true' : 'false' ?>;
const REQ_CAMERA    = <?= $form['require_camera'] ? 'true' : 'false' ?>;
const REQ_GPS       = <?= $form['gps_required'] ? 'true' : 'false' ?>;
const ANSWER_ID     = <?= $answerId ? $answerId : 'null' ?>;
const STUDENT_NAME  = '<?= h(addslashes($studentName)) ?>';

let currentIdx   = 0;
let cheatCount   = 0;
let timeLeft     = <?= $remaining ?>;
let answered     = {};
let timePerQ     = {};
let qStartTime   = Date.now();
let formCards    = [];

// ══ Init ═════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    formCards = Array.from(document.querySelectorAll('[id^="qcard_"]'));
    if (ONE_AT_A_TIME && formCards.length) showQ(parseInt(formCards[0].dataset.idx));
    updateProgress();
    startTimer();
    if (REQ_FULLSCREEN) requestFullscreen();
    initAntiCheat();
    if (REQ_CAMERA)  initCamera();
    if (REQ_GPS)     initGPS();
    updateWatermark();
});

// ══ Navigation ═══════════════════════════════════════════════════
function showQ(idx) {
    // Save time spent on current
    const spent = Math.round((Date.now() - qStartTime) / 1000);
    if (currentIdx !== idx) timePerQ[currentIdx] = (timePerQ[currentIdx] || 0) + spent;
    qStartTime = Date.now();
    currentIdx = idx;

    formCards.forEach((card, i) => {
        card.classList.remove('active');
    });
    const target = document.getElementById('qcard_' + idx);
    if (target) target.classList.add('active');

    // Update dots — کلید answered برابر data-idx است، نه جایگاه نقطه
    document.querySelectorAll('.mini-dot').forEach(dot => {
        dot.classList.remove('current');
        const di = parseInt(dot.id.replace('dot_', ''));
        if (answered[di]) dot.classList.add('answered');
    });
    const curDot = document.getElementById('dot_' + idx);
    if (curDot) curDot.classList.add('current');

    // Update counter
    const counter = document.getElementById('qCounter');
    if (counter) counter.textContent = `سوال ${countUpTo(idx)} از ${TOTAL_Q}`;

    // Prev/Next — بر اساس جایگاه واقعی کارت‌ها (نه ایندکس خام) تا با وجود بخش‌بندی هم درست کار کند
    const pos = posOf(idx);
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    if (prevBtn) prevBtn.style.display = (ALLOW_BACK && pos > 0) ? 'flex' : 'none';
    if (nextBtn) {
        const isLast = (pos >= formCards.length - 1);
        nextBtn.textContent = isLast ? '✅ ثبت نهایی' : 'بعدی ←';
        nextBtn.className   = 'nav-btn ' + (isLast ? 'nav-submit' : 'nav-next');
        nextBtn.onclick      = isLast ? showSubmitConfirm : nextQ;
    }

    updateProgress();
}

// جایگاه کارت با data-idx مشخص در آرایهٔ formCards
function posOf(idx) {
    return formCards.findIndex(c => parseInt(c.dataset.idx) === idx);
}

function countUpTo(idx) {
    const pos = posOf(idx);
    return pos >= 0 ? pos + 1 : 1;
}

function nextQ() {
    const pos = posOf(currentIdx);
    if (pos >= 0 && pos < formCards.length - 1) showQ(parseInt(formCards[pos + 1].dataset.idx));
    else showSubmitConfirm();
}

function prevQ() {
    const pos = posOf(currentIdx);
    if (pos > 0) showQ(parseInt(formCards[pos - 1].dataset.idx));
}

function goToQ(idx) { showQ(idx); }

function updateProgress() {
    const total = Object.keys(answered).length;
    const pct   = TOTAL_Q > 0 ? (total / TOTAL_Q) * 100 : 0;
    const fill  = document.getElementById('progressFill');
    if (fill) fill.style.width = pct + '%';
}

// ══ Answer Marking ═══════════════════════════════════════════════
function markAnswered(idx) {
    answered[idx] = true;
    const dot = document.getElementById('dot_' + idx);
    if (dot) dot.classList.add('answered');
    const card = document.getElementById('qcard_' + idx);
    if (card) card.classList.add('answered');
    updateProgress();
}

function selectOption(label) {
    const container = label.closest('.options');
    container?.querySelectorAll('.option-label').forEach(l => l.classList.remove('selected'));
    label.classList.add('selected');
    const inp = label.querySelector('input');
    const card = label.closest('[id^="qcard_"]');
    if (card) markAnswered(parseInt(card.dataset.idx));
}

function toggleMultiSelect(label) {
    label.classList.toggle('selected');
    const card = label.closest('[id^="qcard_"]');
    const container = label.closest('.options');
    const any = container?.querySelector('input:checked');
    if (any && card) markAnswered(parseInt(card.dataset.idx));
}

function selectTF(qid, val, btn) {
    document.querySelectorAll(`[onclick*="selectTF(${qid}"]`).forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    document.getElementById('tf_' + qid).value = val;
    const card = btn.closest('[id^="qcard_"]');
    if (card) markAnswered(parseInt(card.dataset.idx));
}

function setRating(qid, val) {
    document.getElementById('rating_' + qid).value = val;
    const stars = document.querySelectorAll(`#stars_${qid} span`);
    stars.forEach((s, i) => s.classList.toggle('active', i < val));
    const card = document.querySelector(`[id^="qcard_"]`);
    document.querySelectorAll('[id^="qcard_"]').forEach(c => {
        if (c.querySelector(`#rating_${qid}`)) markAnswered(parseInt(c.dataset.idx));
    });
    const hint = document.querySelector(`#stars_${qid} + p`);
    if (hint) hint.textContent = `${val} ستاره`;
}

// ══ National Code Validation ══════════════════════════════════
function validateNationalCode(input) {
    const code = input.value;
    const errEl = document.getElementById('ncError');
    if (code.length !== 10) { if(errEl) errEl.style.display=''; return; }
    if (/^(\d)\1{9}$/.test(code)) { if(errEl) errEl.style.display=''; return; }
    let sum = 0;
    for (let i=0;i<9;i++) sum += parseInt(code[i]) * (10-i);
    const rem = sum % 11;
    const check = parseInt(code[9]);
    const valid = rem < 2 ? check === rem : check === (11-rem);
    if (errEl) errEl.style.display = valid ? 'none' : '';
}

// ══ Timer ════════════════════════════════════════════════════════
function startTimer() {
    const display = document.getElementById('timerDisplay');
    const interval = setInterval(() => {
        timeLeft--;
        if (timeLeft <= 0) {
            clearInterval(interval);
            timeLeft = 0;
            submitExam(true);
            return;
        }
        const m = Math.floor(timeLeft/60).toString().padStart(2,'0');
        const s = (timeLeft%60).toString().padStart(2,'0');
        display.textContent = `${m}:${s}`;
        if (timeLeft <= 60) display.className = 'timer-display danger';
        else if (timeLeft <= 300) display.className = 'timer-display warn';
        // Auto-save every 60s
        if (timeLeft % 60 === 0) autoSave();
    }, 1000);
}

// ══ Anti-Cheat ═══════════════════════════════════════════════════
function initAntiCheat() {
    // Tab / window visibility
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) recordCheat('tab_switch', 'تغییر تب');
    });

    // Window blur
    window.addEventListener('blur', () => recordCheat('window_blur', 'خروج از پنجره'));

    // Fullscreen exit
    document.addEventListener('fullscreenchange', () => {
        if (!document.fullscreenElement && REQ_FULLSCREEN) {
            recordCheat('fullscreen_exit', 'خروج از تمام‌صفحه');
            setTimeout(() => requestFullscreen(), 500);
        }
    });

    // Copy / paste prevention
    document.addEventListener('copy',  e => { e.preventDefault(); recordCheat('copy_paste', 'کپی'); showWarn('کپی ممنوع است!'); });
    document.addEventListener('paste', e => { e.preventDefault(); recordCheat('copy_paste', 'پیست'); showWarn('پیست ممنوع است!'); });
    document.addEventListener('cut',   e => { e.preventDefault(); recordCheat('copy_paste', 'برش'); });

    // Right-click prevention
    document.addEventListener('contextmenu', e => { e.preventDefault(); recordCheat('right_click', 'راست‌کلیک'); showWarn('راست‌کلیک ممنوع است!'); });

    // Print screen & keyboard shortcuts
    document.addEventListener('keydown', e => {
        if (e.key === 'PrintScreen') { e.preventDefault(); recordCheat('screenshot_key', 'PrintScreen'); }
        if ((e.ctrlKey || e.metaKey) && ['c','v','x','a','p','s'].includes(e.key.toLowerCase())) {
            e.preventDefault();
            if (e.key.toLowerCase() !== 'a') recordCheat('keyboard_shortcut', 'Ctrl+' + e.key.toUpperCase());
        }
        // Disable F12, F11 etc.
        if (['F12','F11'].includes(e.key)) { e.preventDefault(); recordCheat('devtools', e.key); }
        if (e.ctrlKey && e.shiftKey && ['I','J','C'].includes(e.key.toUpperCase())) {
            e.preventDefault(); recordCheat('devtools', 'DevTools');
        }
    });

    // خروج ماوس — فقط وقتی واقعاً از بالای صفحه (نوار آدرس/تب‌ها) خارج شود، نه هر لبه‌ای
    document.addEventListener('mouseout', e => {
        if (!e.relatedTarget && e.clientY <= 0) recordCheat('mouse_out', 'خروج ماوس از بالای صفحه');
    });
}

let lastCheatAt = 0;
const cheatCooldown = {};
function recordCheat(type, detail) {
    const now = Date.now();
    // جلوگیری از شمارش مضاعف رویدادهای هم‌زمان (مثل blur + visibilitychange در یک تعویض تب)
    if (now - lastCheatAt < 800) return;
    // محدودیت هر نوع: حداکثر یک‌بار هر ۲ ثانیه (جلوگیری از اسپم خروج ماوس و ...)
    if (cheatCooldown[type] && now - cheatCooldown[type] < 2000) return;
    lastCheatAt = now;
    cheatCooldown[type] = now;

    cheatCount++;
    document.getElementById('cheatCountDisplay').textContent = cheatCount;

    fetch('../api/anti_cheat.php', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({form_id: FORM_ID, type: type, details: detail})
    }).catch(()=>{});

    const overlay = document.getElementById('cheatOverlay');
    const numEl   = document.getElementById('cheatNum');
    const msgEl   = document.getElementById('cheatMsg');
    numEl.textContent = cheatCount;
    msgEl.textContent = detail + ' ثبت شد';
    overlay.classList.add('show');
    setTimeout(() => overlay.classList.remove('show'), 3000);
}

function closeCheatOverlay() {
    document.getElementById('cheatOverlay').classList.remove('show');
    if (REQ_FULLSCREEN && !document.fullscreenElement) requestFullscreen();
}

function showWarn(msg) {
    const b = document.getElementById('warnBanner');
    b.textContent = '⚠️ ' + msg;
    b.classList.add('show');
    setTimeout(() => b.classList.remove('show'), 2500);
}

function requestFullscreen() {
    if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(()=>{});
    }
}

// ══ Submit ═══════════════════════════════════════════════════════
function showSubmitConfirm() {
    const ans = Object.keys(answered).length;
    const un  = TOTAL_Q - ans;
    document.getElementById('confAnswered').textContent    = ans;
    document.getElementById('confUnanswered').textContent  = un;
    document.getElementById('confCheat').textContent       = cheatCount;
    document.getElementById('submitConfirm').classList.add('show');
}

function closeConfirm() {
    document.getElementById('submitConfirm').classList.remove('show');
}

function submitExam(autoSubmit = false) {
    // Update hidden fields
    document.getElementById('timePerQuestion').value = JSON.stringify(timePerQ);
    // Add cheat count
    let hid = document.createElement('input');
    hid.type='hidden'; hid.name='cheat_count'; hid.value=cheatCount;
    document.getElementById('examForm').appendChild(hid);
    document.getElementById('examForm').submit();
}

// ══ Auto Save ════════════════════════════════════════════════════
function autoSave() {
    const formData = new FormData(document.getElementById('examForm'));
    formData.append('auto_save', '1');
    fetch('../api/save_answer.php', { method: 'POST', body: formData }).catch(()=>{});
}

// ══ CSS Selection Disable (Anti-screenshot trick) ═════════════
document.addEventListener('selectstart', e => {
    if (!['INPUT','TEXTAREA'].includes(e.target.tagName)) e.preventDefault();
});

// ══ Watermark ════════════════════════════════════════════════════
function updateWatermark() {
    const wm = document.getElementById('watermarkEl');
    if (!wm) return;
    const name = STUDENT_NAME || document.getElementById('field_name')?.value || '';
    if (name) wm.textContent = name;
    setInterval(() => {
        const n = document.getElementById('field_name')?.value || STUDENT_NAME;
        if (n) wm.textContent = n;
    }, 5000);
}

// ══ Webcam Anti-Cheat ════════════════════════════════════════════
let camStream = null;
let snapInterval = null;
let camRequestInterval = null;

// ── تشخیص چهره با هوش مصنوعی (face-api.js) ──
const FACE_MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.13/model';
let faceApiReady   = false;
let faceMonitor    = null;
let lastFaceCount  = -1;     // آخرین تعداد چهرهٔ تشخیص‌داده‌شده (-1 یعنی نامشخص)
let noFaceStreak   = 0, multiFaceStreak = 0;
let noFaceFlagged  = false, multiFaceFlagged = false;

async function loadFaceModels() {
    if (typeof faceapi === 'undefined') return false;
    try {
        await faceapi.nets.tinyFaceDetector.loadFromUri(FACE_MODEL_URL);
        faceApiReady = true;
        return true;
    } catch (e) {
        faceApiReady = false;
        return false;
    }
}

async function detectFaceCount() {
    const video = document.getElementById('camPreview');
    if (!faceApiReady || !video || video.readyState < 2) return null;
    try {
        const res = await faceapi.detectAllFaces(
            video,
            new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 })
        );
        return res.length;
    } catch (e) { return null; }
}

function setCamState(text, color) {
    const status = document.getElementById('camStatus');
    if (status) { status.textContent = text; status.style.color = color || '#94a3b8'; }
    const dot = document.getElementById('camPanelDot');
    if (dot) dot.style.background = color || '#94a3b8';
}

function startFaceMonitor() {
    if (faceMonitor) return;
    faceMonitor = setInterval(async () => {
        const n = await detectFaceCount();
        if (n === null) return;
        lastFaceCount = n;
        if (n === 0) {
            noFaceStreak++; multiFaceStreak = 0; multiFaceFlagged = false;
            setCamState('⚠️ سر شما در کادر دیده نمی‌شود', '#f59e0b');
            if (noFaceStreak >= 2 && !noFaceFlagged) {
                recordCheat('no_face', 'سر از کادر دوربین خارج شد');
                noFaceFlagged = true;
                takeSnapshot('cheat_detect');
            }
        } else if (n > 1) {
            multiFaceStreak++; noFaceStreak = 0; noFaceFlagged = false;
            setCamState('🚨 ' + n + ' نفر در کادر دوربین', '#ef4444');
            if (multiFaceStreak >= 2 && !multiFaceFlagged) {
                recordCheat('multiple_faces', n + ' چهره در کادر دوربین دیده شد');
                multiFaceFlagged = true;
                takeSnapshot('cheat_detect');
            }
        } else {
            noFaceStreak = 0; multiFaceStreak = 0; noFaceFlagged = false; multiFaceFlagged = false;
            setCamState('✅ چهره تأیید شد', '#10b981');
        }
    }, 2500);
}

function initCamera() {
    const panel = document.getElementById('cameraPanel');
    const video = document.getElementById('camPreview');
    const status= document.getElementById('camStatus');

    navigator.mediaDevices.getUserMedia({ video: { width:640, height:480, facingMode:'user' }, audio: false })
    .then(async stream => {
        camStream = stream;
        if (video) { video.srcObject = stream; }
        if (panel) panel.classList.add('show');
        if (status) status.textContent = '📷 وب‌کم فعال — در حال ضبط';

        // بارگذاری مدل هوش مصنوعی و شروع نظارت بر چهره
        const ok = await loadFaceModels();
        if (ok) startFaceMonitor();
        else if (status) status.textContent = '📷 وب‌کم فعال (نظارت تصویری)';

        // Take exam-start snapshot
        setTimeout(() => takeSnapshot('exam_start'), 2000);

        // Random snapshots every 90-210 seconds
        function scheduleNextSnap() {
            const delay = (90 + Math.floor(Math.random() * 120)) * 1000;
            snapInterval = setTimeout(() => {
                takeSnapshot('auto');
                scheduleNextSnap();
            }, delay);
        }
        scheduleNextSnap();

        // Poll for admin camera requests every 30s
        camRequestInterval = setInterval(checkCameraRequest, 30000);
    })
    .catch(err => {
        if (panel) panel.style.display = 'none';
        recordCheat('camera_denied', 'دوربین مسدود: ' + err.name);
        if (status) status.textContent = '❌ دوربین مسدود';
    });
}

function takeSnapshot(trigger = 'auto') {
    const video  = document.getElementById('camPreview');
    const canvas = document.getElementById('snapCanvas');
    if (!video || !canvas || !camStream) return;

    canvas.width  = 320;
    canvas.height = 240;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, 320, 240);
    const imageData = canvas.toDataURL('image/jpeg', 0.7);

    fetch('../api/upload_snapshot.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            form_id     : FORM_ID,
            image       : imageData,
            trigger     : trigger,
            student_name: STUDENT_NAME || document.getElementById('field_name')?.value || '',
            answer_id   : ANSWER_ID,
            face_count  : lastFaceCount   // نتیجهٔ هوش مصنوعی (-1 یعنی نامشخص)
        })
    })
    .then(r => r.json())
    .catch(() => {});
}

function checkCameraRequest() {
    fetch('../api/camera_request.php?form_id=' + FORM_ID)
    .then(r => r.json())
    .then(d => {
        if (d.requested) {
            const alert = document.getElementById('camRequestAlert');
            if (alert) {
                alert.classList.add('show');
                setTimeout(() => alert.classList.remove('show'), 5000);
            }
            takeSnapshot('admin_request');
        }
    })
    .catch(() => {});
}

// ══ GPS Anti-Cheat ═══════════════════════════════════════════════
let gpsWatchId = null;
let lastGpsTime = 0;

function initGPS() {
    const dot  = document.getElementById('gpsDot');
    const text = document.getElementById('gpsText');

    if (!navigator.geolocation) {
        if (dot) dot.className = 'err';
        if (text) text.textContent = 'GPS: پشتیبانی نمی‌شود';
        return;
    }

    if (dot) dot.className = 'warn';
    if (text) text.textContent = 'GPS: در حال تعیین موقعیت...';

    navigator.geolocation.getCurrentPosition(
        pos => sendLocation(pos),
        err => {
            if (dot) dot.className = 'err';
            if (text) text.textContent = 'GPS: ' + getGpsError(err);
            recordCheat('gps_denied', 'GPS رد شد: ' + err.message);
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );

    // Re-check every 5 minutes
    setInterval(() => {
        const now = Date.now();
        if (now - lastGpsTime > 4 * 60 * 1000) {
            navigator.geolocation.getCurrentPosition(sendLocation, () => {}, { enableHighAccuracy: true });
        }
    }, 5 * 60 * 1000);
}

function sendLocation(pos) {
    lastGpsTime = Date.now();
    const dot  = document.getElementById('gpsDot');
    const text = document.getElementById('gpsText');

    fetch('../api/save_location.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            form_id     : FORM_ID,
            lat         : pos.coords.latitude,
            lng         : pos.coords.longitude,
            accuracy    : pos.coords.accuracy,
            student_name: STUDENT_NAME || document.getElementById('field_name')?.value || '',
            answer_id   : ANSWER_ID
        })
    })
    .then(r => r.json())
    .then(d => {
        if (d.out_of_bounds) {
            if (dot) dot.className = 'warn';
            if (text) text.textContent = 'GPS: خارج از محدوده مجاز';
            showWarn('⚠️ شما خارج از محدوده مجاز آزمون هستید!');
        } else if (d.collusion) {
            if (dot) dot.className = 'err';
            if (text) text.textContent = `GPS: تقلب گروهی شناسایی شد!`;
            recordCheat('gps_collusion', 'نزدیکی مکانی با ' + d.suspects + ' نفر دیگر');
            showWarn('🚨 موقعیت شما با دانش‌آموز دیگری یکسان است — تقلب ثبت شد!');
        } else {
            if (dot) dot.className = 'ok';
            if (text) text.textContent = 'GPS: موقعیت تأیید شد';
        }
    })
    .catch(() => {
        if (dot) dot.className = 'err';
    });
}

function getGpsError(err) {
    if (err.code === 1) return 'دسترسی رد شد';
    if (err.code === 2) return 'موقعیت یافت نشد';
    if (err.code === 3) return 'وقت تمام شد';
    return 'خطا';
}
</script>
</body>
</html>
