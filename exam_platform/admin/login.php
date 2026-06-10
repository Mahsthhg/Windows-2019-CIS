<?php
/**
 * admin/login.php - ورود امن ادمین (bcrypt + rate limiting)
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

if (isAdmin()) redirect('index.php');

$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    requireCsrf();
    $user = sanitizeString($_POST['username'] ?? '', 50);
    $pass = $_POST['password'] ?? '';
    $ip   = getClientIP();

    if (!checkRateLimit('admin_login', $ip, 5, 300)) {
        $error = '⛔ تعداد تلاش‌های بیش از حد. 5 دقیقه صبر کنید.';
    } else {
        recordRateLimitAttempt('admin_login', $ip);
        $stmt = $pdo->prepare("SELECT * FROM users WHERE username=? AND role='admin' AND is_active=1 LIMIT 1");
        $stmt->execute([$user]);
        $admin = $stmt->fetch();
        if ($admin && password_verify($pass, $admin['password'])) {
            $pdo->prepare("UPDATE users SET last_login=NOW() WHERE id=?")->execute([$admin['id']]);
            regenerateSession();
            $_SESSION['admin_id']   = $admin['id'];
            $_SESSION['admin_name'] = $admin['fullname'];
            $_SESSION['last_activity'] = time();
            redirect('index.php');
        } else {
            $error = '❌ نام کاربری یا رمز عبور اشتباه است.';
        }
    }
}
$csrf = generateCsrfToken();
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ورود ادمین</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;800&display=swap">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Vazirmatn',sans-serif;background:linear-gradient(135deg,#0f172a,#1e293b);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
.card{background:white;border-radius:32px;padding:48px 40px;max-width:420px;width:100%;box-shadow:0 32px 64px rgba(0,0,0,.4);}
h1{font-size:22px;font-weight:800;text-align:center;margin-bottom:8px;}
.sub{text-align:center;color:#64748b;font-size:13px;margin-bottom:32px;}
label{display:block;font-size:12px;font-weight:700;color:#374151;margin-bottom:8px;}
input{width:100%;padding:13px 16px;border:2px solid #e2e8f0;border-radius:16px;font-size:15px;font-family:inherit;margin-bottom:20px;transition:.2s;}
input:focus{outline:none;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.1);}
.btn{width:100%;padding:14px;background:#6366f1;color:white;border:none;border-radius:20px;font-size:16px;font-weight:800;cursor:pointer;font-family:inherit;transition:.2s;}
.btn:hover{background:#4f46e5;transform:translateY(-1px);}
.err{background:#fee2e2;color:#dc2626;padding:12px;border-radius:16px;font-size:13px;margin-bottom:20px;text-align:center;}
.back{text-align:center;margin-top:16px;font-size:12px;color:#64748b;}
.back a{color:#6366f1;text-decoration:none;}
</style>
</head>
<body>
<div class="card">
    <div style="text-align:center;font-size:48px;margin-bottom:12px;">🔐</div>
    <h1>پنل مدیریت</h1>
    <p class="sub">ورود اختصاصی ادمین سیستم</p>
    <?php if($error): ?><div class="err"><?= h($error) ?></div><?php endif; ?>
    <form method="POST">
        <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
        <label>نام کاربری</label>
        <input name="username" value="admin" required autofocus>
        <label>رمز عبور</label>
        <input type="password" name="password" required>
        <button type="submit" class="btn">ورود به پنل ←</button>
    </form>
    <div class="back"><a href="../login.php">← ورود معلم</a></div>
</div>
</body>
</html>
