<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
$teacher = requireTeacherAuth();
$tid = $teacher['id'];

// Stats
$stats = [];
foreach ([
    'exams'        => "SELECT COUNT(*) FROM forms WHERE teacher_id=?",
    'questions'    => "SELECT COUNT(*) FROM questions WHERE form_id IN (SELECT id FROM forms WHERE teacher_id=?)",
    'participants' => "SELECT COUNT(*) FROM answers WHERE teacher_id=? AND status='completed'",
    'attendances'  => "SELECT COUNT(*) FROM attendances WHERE teacher_id=?",
] as $k => $q) {
    $s = $pdo->prepare($q); $s->execute([$tid]);
    $stats[$k] = (int)$s->fetchColumn();
}

// Last 5 exams
$s = $pdo->prepare("SELECT id,title,is_active,created_at FROM forms WHERE teacher_id=? ORDER BY id DESC LIMIT 5");
$s->execute([$tid]); $recentExams = $s->fetchAll();

// Last 5 results
$s = $pdo->prepare("SELECT a.user_name, a.score, a.max_score, f.title, a.submitted_at FROM answers a JOIN forms f ON a.form_id=f.id WHERE a.teacher_id=? AND a.status='completed' ORDER BY a.submitted_at DESC LIMIT 5");
$s->execute([$tid]); $recentResults = $s->fetchAll();

// آزمون‌های مشکوک (تقلب بالا) — هشدار برای معلم
$s = $pdo->prepare("SELECT a.user_name, a.user_ip, a.cheat_count, f.title, f.id as form_id, a.submitted_at
                    FROM answers a JOIN forms f ON a.form_id=f.id
                    WHERE a.teacher_id=? AND a.cheat_count >= 3 AND a.status='completed'
                    ORDER BY a.cheat_count DESC, a.submitted_at DESC LIMIT 6");
$s->execute([$tid]); $suspicious = $s->fetchAll();
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>پنل معلم | <?= h($teacher['name']) ?></title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<style>
<?php include __DIR__ . '/../assets/css/panel.css'; ?>
</style>
</head>
<body>
<?php include __DIR__ . '/includes/sidebar.php'; ?>
<div class="main-content">
    <div class="page-header">
        <div>
            <h1>داشبورد</h1>
            <p>خوش آمدید، <?= h($teacher['name']) ?> | رشته: <?= h($teacher['subject']) ?></p>
        </div>
        <div class="header-actions">
            <a href="create_exam.php" class="btn btn-primary">➕ آزمون جدید</a>
        </div>
    </div>

    <!-- Stats Grid -->
    <div class="stats-grid">
        <div class="stat-card stat-blue">
            <div class="stat-icon">📝</div>
            <div class="stat-value"><?= $stats['exams'] ?></div>
            <div class="stat-label">آزمون ساخته شده</div>
        </div>
        <div class="stat-card stat-purple">
            <div class="stat-icon">❓</div>
            <div class="stat-value"><?= $stats['questions'] ?></div>
            <div class="stat-label">سوال طراحی شده</div>
        </div>
        <div class="stat-card stat-green">
            <div class="stat-icon">👥</div>
            <div class="stat-value"><?= $stats['participants'] ?></div>
            <div class="stat-label">شرکت‌کننده</div>
        </div>
        <div class="stat-card stat-orange">
            <div class="stat-icon">📋</div>
            <div class="stat-value"><?= $stats['attendances'] ?></div>
            <div class="stat-label">جلسه حضور‌وغیاب</div>
        </div>
    </div>

    <!-- Suspicious activity alert -->
    <?php if (!empty($suspicious)): ?>
    <div class="card" style="margin-bottom:24px;border:1.5px solid #fecaca;">
        <div class="card-header" style="background:#fef2f2;">
            <h3 style="color:#991b1b;">🚨 آزمون‌های مشکوک (تقلب بالا)</h3>
            <span style="font-size:12px;color:#dc2626;"><?= count($suspicious) ?> مورد</span>
        </div>
        <div class="list-items">
            <?php foreach ($suspicious as $sp): ?>
            <div class="list-item">
                <div class="item-info">
                    <strong><?= h($sp['user_name'] ?: 'ناشناس') ?></strong>
                    <small><?= h($sp['title']) ?> | <?= h(substr($sp['submitted_at'],0,16)) ?> | <span style="font-family:monospace;"><?= h($sp['user_ip']) ?></span></small>
                </div>
                <div class="item-actions">
                    <span class="badge badge-red">⚠️ <?= (int)$sp['cheat_count'] ?> تقلب</span>
                    <a href="results.php?form=<?= (int)$sp['form_id'] ?>" class="btn btn-secondary btn-sm">بررسی</a>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
    </div>
    <?php endif; ?>

    <div class="grid-2col">
        <!-- Recent Exams -->
        <div class="card">
            <div class="card-header">
                <h3>📝 آخرین آزمون‌ها</h3>
                <a href="create_exam.php">مشاهده همه →</a>
            </div>
            <div class="list-items">
                <?php if ($recentExams): foreach ($recentExams as $e): ?>
                <div class="list-item">
                    <div class="item-info">
                        <strong><?= h($e['title']) ?></strong>
                        <small><?= substr($e['created_at'],0,10) ?></small>
                    </div>
                    <div class="item-actions">
                        <span class="badge <?= $e['is_active'] ? 'badge-green' : 'badge-gray' ?>">
                            <?= $e['is_active'] ? 'فعال' : 'پیش‌نویس' ?>
                        </span>
                        <a href="create_exam.php?edit=<?= $e['id'] ?>" class="btn-sm">✏️</a>
                    </div>
                </div>
                <?php endforeach; else: ?>
                <div class="empty-state">هنوز آزمونی ساخته نشده</div>
                <?php endif; ?>
            </div>
        </div>

        <!-- Recent Results -->
        <div class="card">
            <div class="card-header">
                <h3>📊 آخرین نتایج</h3>
                <a href="results.php">مشاهده همه →</a>
            </div>
            <div class="list-items">
                <?php if ($recentResults): foreach ($recentResults as $r): ?>
                <div class="list-item">
                    <div class="item-info">
                        <strong><?= h($r['user_name'] ?: 'ناشناس') ?></strong>
                        <small><?= h($r['title']) ?></small>
                    </div>
                    <div class="item-actions">
                        <span class="score-badge">
                            <?= round($r['score'],1) ?>/<?= round($r['max_score'],1) ?>
                        </span>
                    </div>
                </div>
                <?php endforeach; else: ?>
                <div class="empty-state">هنوز نتیجه‌ای ثبت نشده</div>
                <?php endif; ?>
            </div>
        </div>
    </div>

    <!-- Quick Guide -->
    <div class="card guide-card">
        <div class="card-header"><h3>📖 راهنمای سریع</h3></div>
        <div class="guide-grid">
            <div class="guide-item">
                <span class="guide-icon">1️⃣</span>
                <strong>ساخت آزمون</strong>
                <p>از منوی "آزمون‌ها" → "آزمون جدید" استفاده کنید</p>
            </div>
            <div class="guide-item">
                <span class="guide-icon">2️⃣</span>
                <strong>افزودن سوال</strong>
                <p>10+ نوع سوال در فرم‌ساز پیشرفته</p>
            </div>
            <div class="guide-item">
                <span class="guide-icon">3️⃣</span>
                <strong>فعال‌سازی</strong>
                <p>لینک آزمون را برای دانش‌آموزان ارسال کنید</p>
            </div>
            <div class="guide-item">
                <span class="guide-icon">4️⃣</span>
                <strong>نتایج</strong>
                <p>آمار کامل + خروجی Excel از بخش نتایج</p>
            </div>
        </div>
    </div>
</div>
</body>
</html>
