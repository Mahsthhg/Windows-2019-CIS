<?php
/**
 * admin/index.php - داشبورد مدیریت
 * Fixed: uses proper DB auth, not plaintext password
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
requireAdminAuth();

if (isset($_GET['logout'])) { session_unset(); session_destroy(); redirect('login.php'); }

// Stats
$stats = [];
$qs = [
    'teachers'    => "SELECT COUNT(*) FROM users WHERE role='teacher' AND is_active=1",
    'exams'       => "SELECT COUNT(*) FROM forms",
    'results'     => "SELECT COUNT(*) FROM answers WHERE status='completed'",
    'attendances' => "SELECT COUNT(*) FROM attendances",
];
foreach ($qs as $k => $q) { $s = $pdo->query($q); $stats[$k] = (int)$s->fetchColumn(); }

// Recent teachers
$s = $pdo->query("SELECT u.*, COUNT(f.id) as exam_count, COUNT(k.id) as key_count FROM users u LEFT JOIN forms f ON f.teacher_id=u.id LEFT JOIN access_keys k ON k.teacher_id=u.id WHERE u.role='teacher' GROUP BY u.id ORDER BY u.id DESC LIMIT 10");
$teachers = $s->fetchAll();

// Actions
if (isset($_POST['create_key'])) {
    requireCsrf();
    $teach_id = validateInt($_POST['teacher_id'] ?? 0, 1);
    $days     = validateInt($_POST['days'] ?? 30, 1, 365) ?? 30;
    if ($teach_id) {
        $key = 'KEY-' . strtoupper(bin2hex(random_bytes(8)));
        $pdo->prepare("INSERT INTO access_keys (teacher_id, access_key, expiry_days, expires_at, created_by) VALUES (?,?,?,DATE_ADD(NOW(), INTERVAL ? DAY),?)")
            ->execute([$teach_id, $key, $days, $days, $_SESSION['admin_id']]);
        $newKey = $key;
    }
}

if (isset($_POST['create_teacher'])) {
    requireCsrf();
    $name    = sanitizeString($_POST['fullname'] ?? '', 100);
    $uname   = sanitizeString($_POST['username'] ?? '', 50);
    $sub     = sanitizeString($_POST['subject'] ?? '', 100);
    $pass    = $_POST['password'] ?? '';
    if ($name && $uname && strlen($pass) >= 6) {
        $hash = password_hash($pass, PASSWORD_BCRYPT, ['cost'=>12]);
        try {
            $pdo->prepare("INSERT INTO users (fullname,username,password,role,subject,is_active) VALUES (?,?,?,'teacher',?,1)")
                ->execute([$name, $uname, $hash, $sub]);
            $newTeacher = ['name'=>$name, 'username'=>$uname];
            // Auto-create 30-day key
            $key = 'KEY-' . strtoupper(bin2hex(random_bytes(8)));
            $teachId = (int)$pdo->lastInsertId();
            $pdo->prepare("INSERT INTO access_keys (teacher_id, access_key, expiry_days, expires_at, created_by) VALUES (?,?,30,DATE_ADD(NOW(),INTERVAL 30 DAY),?)")
                ->execute([$teachId, $key, $_SESSION['admin_id']]);
            $newTeacherKey = $key;
        } catch (PDOException $e) { $error = 'خطا: نام کاربری تکراری است'; }
    } else { $error = 'لطفاً همه فیلدها را پر کنید (رمز حداقل ۶ کاراکتر)'; }
}

if (isset($_GET['toggle_teacher'])) {
    $tid2 = validateInt($_GET['toggle_teacher'], 1);
    if ($tid2) $pdo->prepare("UPDATE users SET is_active=1-is_active WHERE id=? AND role='teacher'")->execute([$tid2]);
    redirect('index.php');
}
if (isset($_GET['delete_teacher'])) {
    $tid2 = validateInt($_GET['delete_teacher'], 1);
    if ($tid2) $pdo->prepare("DELETE FROM users WHERE id=? AND role='teacher'")->execute([$tid2]);
    redirect('index.php');
}

$csrf = generateCsrfToken();
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>پنل مدیریت | ادمین</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<style>
<?php include __DIR__ . '/../assets/css/panel.css'; ?>
.admin-header{background:linear-gradient(135deg,#1e1b4b,#0f172a);color:white;padding:20px 32px;margin-bottom:32px;display:flex;align-items:center;justify-content:space-between;border-radius:20px;}
.admin-logo{display:flex;align-items:center;gap:14px;}
.admin-logo h1{font-size:22px;font-weight:800;}
.key-box{background:#f0fdf4;border:1.5px solid #86efac;border-radius:16px;padding:16px;margin:12px 0;}
.key-val{font-family:monospace;font-size:18px;font-weight:800;color:#166534;letter-spacing:2px;}
</style>
</head>
<body style="background:#f1f5f9;font-family:'Vazirmatn',sans-serif;padding:24px;direction:rtl;">

<div style="max-width:1200px;margin:0 auto;">

<div class="admin-header">
    <div class="admin-logo">
        <span style="font-size:36px">🔐</span>
        <div><h1>پنل مدیریت سامانه</h1><small style="opacity:.6">مدیر: <?= h($_SESSION['admin_name']) ?></small></div>
    </div>
    <a href="?logout=1" style="background:rgba(239,68,68,.3);color:white;padding:10px 20px;border-radius:20px;text-decoration:none;font-weight:700;">🚪 خروج</a>
</div>

<!-- Quick Navigation -->
<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px;">
    <a href="monitor.php" style="display:flex;align-items:center;gap:8px;padding:12px 20px;background:white;border-radius:16px;text-decoration:none;color:#0f172a;font-weight:700;font-size:14px;border:2px solid #e2e8f0;transition:.2s;" onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='#e2e8f0'">
        🎥 مانیتورینگ زنده
    </a>
    <a href="snapshots.php" style="display:flex;align-items:center;gap:8px;padding:12px 20px;background:white;border-radius:16px;text-decoration:none;color:#0f172a;font-weight:700;font-size:14px;border:2px solid #e2e8f0;transition:.2s;" onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='#e2e8f0'">
        📷 اسنپشات‌های وب‌کم
    </a>
    <a href="gps_monitor.php" style="display:flex;align-items:center;gap:8px;padding:12px 20px;background:white;border-radius:16px;text-decoration:none;color:#0f172a;font-weight:700;font-size:14px;border:2px solid #e2e8f0;transition:.2s;" onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='#e2e8f0'">
        🗺️ نقشه GPS
    </a>
    <a href="ip_blacklist.php" style="display:flex;align-items:center;gap:8px;padding:12px 20px;background:white;border-radius:16px;text-decoration:none;color:#0f172a;font-weight:700;font-size:14px;border:2px solid #e2e8f0;transition:.2s;" onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='#e2e8f0'">
        🚫 لیست سیاه IP
    </a>
    <a href="audit_log.php" style="display:flex;align-items:center;gap:8px;padding:12px 20px;background:white;border-radius:16px;text-decoration:none;color:#0f172a;font-weight:700;font-size:14px;border:2px solid #e2e8f0;transition:.2s;" onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='#e2e8f0'">
        📋 لاگ عملکرد
    </a>
</div>

<!-- Stats -->
<div class="stats-grid" style="margin-bottom:32px;">
    <div class="stat-card stat-blue"><div class="stat-icon">👨‍🏫</div><div class="stat-value"><?= $stats['teachers'] ?></div><div class="stat-label">معلم فعال</div></div>
    <div class="stat-card stat-purple"><div class="stat-icon">📝</div><div class="stat-value"><?= $stats['exams'] ?></div><div class="stat-label">کل آزمون‌ها</div></div>
    <div class="stat-card stat-green"><div class="stat-icon">👥</div><div class="stat-value"><?= $stats['results'] ?></div><div class="stat-label">پاسخنامه ثبت شده</div></div>
    <div class="stat-card stat-orange"><div class="stat-icon">📋</div><div class="stat-value"><?= $stats['attendances'] ?></div><div class="stat-label">جلسه حضور‌وغیاب</div></div>
</div>

<?php if (isset($newKey)): ?>
<div class="card" style="margin-bottom:24px;border:2px solid #86efac;">
    <div class="card-body">
        <strong style="color:#166534;">✅ کلید دسترسی جدید ساخته شد:</strong>
        <div class="key-box"><div class="key-val"><?= h($newKey) ?></div></div>
        <small style="color:#64748b;">این کلید یک‌بارمصرف است. آن را برای معلم ارسال کنید.</small>
    </div>
</div>
<?php endif; ?>

<?php if (isset($newTeacherKey)): ?>
<div class="card" style="margin-bottom:24px;border:2px solid #86efac;">
    <div class="card-body">
        <strong style="color:#166534;">✅ معلم جدید ساخته شد.</strong>
        <div class="key-box">
            <div>کلید اول (30 روزه): <div class="key-val"><?= h($newTeacherKey) ?></div></div>
        </div>
    </div>
</div>
<?php endif; ?>

<?php if (isset($error)): ?>
<div class="alert alert-danger" style="margin-bottom:24px;"><?= h($error) ?></div>
<?php endif; ?>

<div class="grid-2col">
    <!-- ساخت معلم جدید -->
    <div class="card">
        <div class="card-header"><h3>➕ معلم جدید</h3></div>
        <div class="card-body">
            <form method="POST">
                <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
                <div class="form-group"><label>نام کامل</label><input class="form-control" name="fullname" required></div>
                <div class="form-group"><label>نام کاربری</label><input class="form-control" name="username" required pattern="[a-zA-Z0-9_]{3,50}"></div>
                <div class="form-group"><label>رشته تدریس</label><input class="form-control" name="subject" placeholder="مثال: ریاضی"></div>
                <div class="form-group"><label>رمز عبور (حداقل ۶ کاراکتر)</label><input class="form-control" type="password" name="password" required minlength="6"></div>
                <button type="submit" name="create_teacher" class="btn btn-primary">ساخت معلم + کلید اولیه</button>
            </form>
        </div>
    </div>

    <!-- ساخت کلید دسترسی -->
    <div class="card">
        <div class="card-header"><h3>🔑 ساخت کلید دسترسی</h3></div>
        <div class="card-body">
            <form method="POST">
                <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
                <div class="form-group">
                    <label>انتخاب معلم</label>
                    <select class="form-control" name="teacher_id" required>
                        <option value="">انتخاب کنید...</option>
                        <?php foreach ($teachers as $t): ?>
                        <option value="<?= $t['id'] ?>"><?= h($t['fullname']) ?> (<?= h($t['username']) ?>)</option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <div class="form-group">
                    <label>اعتبار (روز)</label>
                    <input class="form-control" type="number" name="days" value="30" min="1" max="365">
                </div>
                <button type="submit" name="create_key" class="btn btn-success">ساخت کلید</button>
            </form>
        </div>
    </div>
</div>

<!-- لیست معلمان -->
<div class="card">
    <div class="card-header"><h3>👨‍🏫 لیست معلمان (<?= count($teachers) ?>)</h3></div>
    <div class="table-wrap" style="overflow-x:auto;">
        <table class="data-table">
            <thead><tr><th>#</th><th>نام</th><th>نام کاربری</th><th>رشته</th><th>آزمون‌ها</th><th>آخرین ورود</th><th>وضعیت</th><th>عملیات</th></tr></thead>
            <tbody>
                <?php foreach ($teachers as $i => $t): ?>
                <tr>
                    <td><?= $i+1 ?></td>
                    <td><strong><?= h($t['fullname']) ?></strong></td>
                    <td style="font-family:monospace;"><?= h($t['username']) ?></td>
                    <td><?= h($t['subject'] ?? '—') ?></td>
                    <td><span class="badge badge-blue"><?= $t['exam_count'] ?></span></td>
                    <td style="font-size:12px;color:#64748b;"><?= $t['last_login'] ? substr($t['last_login'],0,16) : '—' ?></td>
                    <td><span class="badge <?= $t['is_active'] ? 'badge-green' : 'badge-red' ?>"><?= $t['is_active'] ? 'فعال' : 'غیرفعال' ?></span></td>
                    <td>
                        <a href="?toggle_teacher=<?= $t['id'] ?>" class="btn btn-secondary btn-sm"><?= $t['is_active'] ? '⛔' : '✅' ?></a>
                        <a href="?delete_teacher=<?= $t['id'] ?>" class="btn btn-danger btn-sm" onclick="return confirm('حذف شود؟')">🗑️</a>
                    </td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</div>

</div>
</body>
</html>
