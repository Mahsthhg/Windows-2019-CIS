<?php
/**
 * exam/result.php - صفحه نتیجه آزمون (Fixed session keys)
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

// Fixed: use 'exam_result' key set by submit_exam.php
$r = $_SESSION['exam_result'] ?? null;

if (!$r) {
    die('<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>نتیجه</title></head>
    <body style="font-family:sans-serif;text-align:center;padding:60px;background:#0f172a;color:white;">
    <h2>⚠️ اطلاعات نتیجه یافت نشد</h2><p>لطفاً آزمون را کامل کنید</p></body></html>');
}

$score    = (float)$r['score'];
$maxScore = (float)$r['max_score'];
$percent  = $maxScore > 0 ? round(($score / $maxScore) * 100) : 0;
$correct  = (int)$r['correct'];
$wrong    = (int)$r['wrong'];
$empty    = (int)$r['empty'];
$cheat    = (int)$r['cheat'];
$title    = $r['form_title'] ?? 'آزمون';
$threshold= (int)($r['pass_threshold'] ?? 0);
$passed   = $threshold === 0 || $percent >= $threshold;
$showRes  = $r['show_results'] ?? 'always';

// پیام بر اساس درصد
if ($percent >= 90)     { $grade='A+'; $msg='فوق‌العاده عالی! 🏆';         $gradeBg='#059669'; }
elseif ($percent >= 80) { $grade='A';  $msg='عالی! نتیجه بسیار خوب 🎉';     $gradeBg='#10b981'; }
elseif ($percent >= 70) { $grade='B';  $msg='خوب! قابل قبول است 👍';         $gradeBg='#3b82f6'; }
elseif ($percent >= 60) { $grade='C';  $msg='قابل قبول - تلاش بیشتری کنید 📚'; $gradeBg='#f59e0b'; }
elseif ($percent >= 40) { $grade='D';  $msg='ضعیف - نیاز به مطالعه بیشتر 📖'; $gradeBg='#ef4444'; }
else                    { $grade='F';  $msg='قبول نشدید - بیشتر تلاش کنید ⚠️'; $gradeBg='#dc2626'; }

// پاک کردن نتیجه از session بعد از نمایش
// (پس از 30 ثانیه، از طریق fetch)
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>نتیجه آزمون | <?= h($title) ?></title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap');
*{margin:0;padding:0;box-sizing:border-box;}
body{
    font-family:'Vazirmatn','Segoe UI',sans-serif;
    background:radial-gradient(ellipse at 30% 30%,#1e1b4b 0%,#0f172a 60%);
    min-height:100vh;display:flex;align-items:center;justify-content:center;
    padding:20px;
}

/* ── Confetti (pure CSS) ── */
.confetti-wrap{position:fixed;inset:0;pointer-events:none;z-index:0;overflow:hidden;}
.confetto{position:absolute;top:-20px;width:10px;height:10px;border-radius:2px;animation:fall linear infinite;}
@keyframes fall{to{transform:translateY(110vh) rotate(720deg);}}

.card{
    max-width:520px;width:100%;
    background:white;border-radius:48px;
    overflow:hidden;
    box-shadow:0 32px 64px rgba(0,0,0,.4);
    animation:rise .6s cubic-bezier(.2,.9,.4,1.1);
    position:relative;z-index:1;
}
@keyframes rise{from{opacity:0;transform:translateY(40px) scale(.96);}to{opacity:1;transform:translateY(0) scale(1);}}

.result-header{
    background:linear-gradient(135deg,<?= $gradeBg ?>,<?= $gradeBg ?>cc);
    color:white;padding:36px 24px;text-align:center;position:relative;overflow:hidden;
}
.result-header::after{content:'';position:absolute;bottom:-24px;left:0;right:0;height:48px;background:white;border-radius:50% 50% 0 0;}
.grade-circle{
    width:80px;height:80px;border-radius:50%;
    background:rgba(255,255,255,.2);border:3px solid rgba(255,255,255,.5);
    display:inline-flex;align-items:center;justify-content:center;
    font-size:32px;font-weight:800;margin-bottom:12px;
}
.result-header h1{font-size:22px;font-weight:800;margin-bottom:6px;}
.result-header p{font-size:14px;opacity:.9;}

.score-section{padding:32px 24px 16px;text-align:center;}
.score-big{font-size:64px;font-weight:800;line-height:1;}
.score-big .slash{font-size:36px;opacity:.5;margin:0 4px;}
.score-big .max{font-size:36px;color:#64748b;}
.percent-ring{
    display:inline-block;background:#f1f5f9;
    padding:8px 20px;border-radius:40px;
    font-size:18px;font-weight:800;
    margin-top:12px;color:#0f172a;
}

.stats-row{
    display:grid;grid-template-columns:repeat(3,1fr);
    gap:12px;padding:0 24px 16px;
}
.stat-box{
    background:#f8fafc;border-radius:20px;padding:16px 8px;
    text-align:center;border:1px solid #e2e8f0;
}
.stat-box strong{font-size:28px;font-weight:800;display:block;margin-bottom:4px;}
.stat-box span{font-size:11px;color:#64748b;}
.stat-correct strong{color:#10b981;}
.stat-wrong   strong{color:#ef4444;}
.stat-empty   strong{color:#f59e0b;}

.cheat-row{
    margin:0 24px 16px;padding:12px 20px;
    border-radius:20px;display:flex;align-items:center;gap:10px;
    font-size:13px;font-weight:600;
}
.cheat-row.no-cheat{background:#dcfce7;color:#166534;}
.cheat-row.has-cheat{background:#fee2e2;color:#991b1b;}

.pass-badge{
    margin:0 24px 16px;padding:14px 20px;border-radius:20px;
    text-align:center;font-size:15px;font-weight:800;
}
.pass-badge.passed{background:#dcfce7;color:#166534;}
.pass-badge.failed{background:#fee2e2;color:#991b1b;}

.msg-box{
    margin:0 24px 24px;padding:16px;border-radius:20px;
    background:#f8fafc;text-align:center;font-size:15px;font-weight:700;
    color:#0f172a;
}

.actions{padding:0 24px 32px;display:flex;gap:12px;}
.btn{
    flex:1;padding:14px;border:none;border-radius:20px;
    font-size:15px;font-weight:800;cursor:pointer;
    font-family:inherit;transition:.2s;
}
.btn-close{background:#e2e8f0;color:#475569;}
.btn-close:hover{background:#cbd5e1;}
.btn-home{background:#6366f1;color:white;}
.btn-home:hover{background:#4f46e5;}

@media(max-width:480px){
    .stats-row{grid-template-columns:repeat(3,1fr);gap:8px;}
    .score-big{font-size:48px;}
    .actions{flex-direction:column;}
}
</style>
</head>
<body>

<!-- Confetti for passing grades -->
<?php if ($passed && $percent >= 70): ?>
<div class="confetti-wrap" id="confetti"></div>
<?php endif; ?>

<div class="card">
    <div class="result-header">
        <div class="grade-circle"><?= $grade ?></div>
        <h1>نتیجه آزمون</h1>
        <p><?= h($title) ?></p>
    </div>

    <?php if ($showRes === 'never'): ?>
    <div class="score-section">
        <p style="color:#64748b;padding:20px;text-align:center;">نتیجه این آزمون توسط استاد محرمانه اعلام می‌شود.</p>
    </div>
    <?php else: ?>

    <div class="score-section">
        <div class="score-big">
            <?= $score ?>
            <span class="slash">/</span>
            <span class="max"><?= $maxScore ?></span>
        </div>
        <div class="percent-ring"><?= $percent ?>%</div>
    </div>

    <div class="stats-row">
        <div class="stat-box stat-correct"><strong><?= $correct ?></strong><span>✅ صحیح</span></div>
        <div class="stat-box stat-wrong">  <strong><?= $wrong   ?></strong><span>❌ غلط</span></div>
        <div class="stat-box stat-empty">  <strong><?= $empty   ?></strong><span>📭 خالی</span></div>
    </div>

    <?php if ($threshold > 0): ?>
    <div class="pass-badge <?= $passed ? 'passed' : 'failed' ?>">
        <?= $passed ? '✅ قبول شدید' : '❌ قبول نشدید' ?>
        (حد قبولی: <?= $threshold ?>%)
    </div>
    <?php endif; ?>

    <div class="cheat-row <?= $cheat > 0 ? 'has-cheat' : 'no-cheat' ?>">
        <span><?= $cheat > 0 ? '⚠️' : '✅' ?></span>
        <?= $cheat > 0 ? "تقلب ثبت شده: $cheat مورد" : 'بدون تقلب' ?>
    </div>

    <div class="msg-box"><?= $msg ?></div>

    <?php endif; ?>

    <div class="actions">
        <button class="btn btn-close" onclick="window.close(); history.back();">🔒 بستن</button>
        <button class="btn btn-home" onclick="window.location='../index.php'">🏠 صفحه اصلی</button>
    </div>
</div>

<script>
// Clear session result after viewing
setTimeout(() => fetch('../api/clear_result.php'), 3000);

// Confetti animation
<?php if ($passed && $percent >= 70): ?>
(function() {
    const colors = ['#6366f1','#8b5cf6','#10b981','#f59e0b','#ef4444','#3b82f6'];
    const container = document.getElementById('confetti');
    if (!container) return;
    for (let i = 0; i < 60; i++) {
        const el = document.createElement('div');
        el.className = 'confetto';
        el.style.cssText = `
            left:${Math.random()*100}%;
            width:${6+Math.random()*8}px;
            height:${6+Math.random()*8}px;
            background:${colors[Math.floor(Math.random()*colors.length)]};
            opacity:${0.6+Math.random()*.4};
            animation-duration:${2+Math.random()*4}s;
            animation-delay:${Math.random()*3}s;
            border-radius:${Math.random()>0.5?'50%':'2px'};
        `;
        container.appendChild(el);
    }
    setTimeout(() => container.remove(), 8000);
})();
<?php endif; ?>
</script>
</body>
</html>

<?php
// پاک کردن نتیجه از session
unset($_SESSION['exam_result']);
?>
