<?php
/**
 * login.php - ورود معلم با کلید یک‌بارمصرف یا رمز عبور
 * Fixed: table name, session keys, rate limiting, CSRF
 */

require_once __DIR__ . '/config/database.php';
require_once __DIR__ . '/config/security.php';

// اگر قبلاً لاگین کرده، برو به پنل
if (isTeacher()) redirect('teacher/panel.php');

$error  = '';
$notice = '';

if (isset($_GET['expired'])) $notice = '⏰ نشست شما منقضی شد. دوباره وارد شوید.';
if (isset($_GET['logout']))  $notice = '✅ با موفقیت خارج شدید.';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    requireCsrf();

    $input_key = sanitizeString($_POST['access_key'] ?? '', 120);
    $clientIP  = getClientIP();

    if (empty($input_key)) {
        $error = 'لطفاً کلید دسترسی یا رمز عبور را وارد کنید.';
    } elseif (!checkRateLimit('teacher_login', $clientIP, 8, 300)) {
        $error = '⛔ تعداد تلاش‌های بیش از حد. لطفاً 5 دقیقه صبر کنید.';
    } else {
        recordRateLimitAttempt('teacher_login', $clientIP);

        $loggedIn = false;

        // ── روش 1: کلید یک‌بارمصرف ──────────────────────────────
        $stmt = $pdo->prepare("
            SELECT ak.*, u.id AS teacher_id, u.fullname, u.subject, u.is_active, u.role
            FROM access_keys ak
            JOIN users u ON ak.teacher_id = u.id
            WHERE ak.access_key = ?
              AND ak.is_used = 0
              AND ak.expires_at > NOW()
              AND u.is_active = 1
              AND u.role = 'teacher'
            LIMIT 1
        ");
        $stmt->execute([$input_key]);
        $keyData = $stmt->fetch();

        if ($keyData) {
            // مارک کلید به عنوان استفاده‌شده
            $pdo->prepare("UPDATE access_keys SET is_used=1, used_at=NOW() WHERE id=?")
                ->execute([$keyData['id']]);

            // آپدیت last_login
            $pdo->prepare("UPDATE users SET last_login=NOW() WHERE id=?")
                ->execute([$keyData['teacher_id']]);

            regenerateSession();
            $_SESSION['teacher_id']      = $keyData['teacher_id'];
            $_SESSION['teacher_name']    = $keyData['fullname'];
            $_SESSION['teacher_subject'] = $keyData['subject'];
            $_SESSION['teacher_role']    = 'teacher';
            $_SESSION['last_activity']   = time();
            $loggedIn = true;
        }

        // ── روش 2: نام‌کاربری + رمز عبور ───────────────────────
        if (!$loggedIn && str_contains($input_key, ':')) {
            [$uname, $pwd] = explode(':', $input_key, 2);
            $stmt = $pdo->prepare("
                SELECT * FROM users
                WHERE username = ? AND is_active = 1 AND role = 'teacher'
                LIMIT 1
            ");
            $stmt->execute([sanitizeString($uname, 50)]);
            $user = $stmt->fetch();

            if ($user && password_verify($pwd, $user['password'])) {
                $pdo->prepare("UPDATE users SET last_login=NOW() WHERE id=?")
                    ->execute([$user['id']]);
                regenerateSession();
                $_SESSION['teacher_id']      = $user['id'];
                $_SESSION['teacher_name']    = $user['fullname'];
                $_SESSION['teacher_subject'] = $user['subject'];
                $_SESSION['teacher_role']    = 'teacher';
                $_SESSION['last_activity']   = time();
                $loggedIn = true;
            }
        }

        if ($loggedIn) {
            redirect('teacher/panel.php');
        } else {
            $error = 'کلید نامعتبر، منقضی شده، قبلاً استفاده شده، یا اطلاعات ورود اشتباه است.';
        }
    }
}
$csrf = generateCsrfToken();
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ورود معلم | سامانه آزمون</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{
    background:linear-gradient(135deg,#0f172a 0%,#1e293b 50%,#0a0f1e 100%);
    min-height:100vh;display:flex;align-items:center;justify-content:center;
    font-family:'Vazirmatn','Segoe UI',sans-serif;padding:20px;
    position:relative;overflow:hidden;
}
body::before{
    content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;
    background:radial-gradient(ellipse at 40% 40%,rgba(59,130,246,.12) 0%,transparent 60%);
    animation:float 8s ease-in-out infinite;
}
body::after{
    content:'';position:absolute;bottom:-30%;right:-30%;width:100%;height:100%;
    background:radial-gradient(ellipse at 60% 60%,rgba(139,92,246,.1) 0%,transparent 60%);
    animation:float 10s ease-in-out infinite reverse;
}
@keyframes float{0%,100%{transform:translate(0,0);}50%{transform:translate(2%,2%);}}
.card{
    background:rgba(255,255,255,.03);
    backdrop-filter:blur(24px);
    border:1px solid rgba(255,255,255,.1);
    border-radius:40px;padding:48px 40px;
    width:100%;max-width:460px;
    box-shadow:0 32px 64px rgba(0,0,0,.4);
    position:relative;z-index:1;
    animation:fadeUp .5s cubic-bezier(.2,.9,.4,1.1);
}
@keyframes fadeUp{from{opacity:0;transform:translateY(30px);}to{opacity:1;transform:translateY(0);}}
.logo{text-align:center;margin-bottom:32px;}
.logo-icon{font-size:56px;display:block;animation:bounce .6s ease;}
@keyframes bounce{0%,100%{transform:translateY(0);}50%{transform:translateY(-8px);}}
.logo h1{font-size:24px;font-weight:800;color:white;margin-top:12px;}
.logo p{font-size:13px;color:rgba(255,255,255,.5);margin-top:6px;}
.form-group{margin-bottom:24px;}
.form-group label{display:block;font-size:12px;font-weight:700;color:rgba(255,255,255,.6);margin-bottom:10px;letter-spacing:.5px;text-transform:uppercase;}
.input-wrap{position:relative;}
.input-wrap input{
    width:100%;padding:16px 20px;
    background:rgba(255,255,255,.06);
    border:1px solid rgba(255,255,255,.12);
    border-radius:24px;color:white;font-size:15px;
    font-family:inherit;letter-spacing:1px;
    transition:.3s;
}
.input-wrap input:focus{
    outline:none;
    border-color:rgba(99,102,241,.6);
    background:rgba(255,255,255,.1);
    box-shadow:0 0 0 3px rgba(99,102,241,.15);
}
.input-wrap input::placeholder{color:rgba(255,255,255,.3);letter-spacing:0;}
.btn-login{
    width:100%;padding:16px;
    background:linear-gradient(135deg,#6366f1,#8b5cf6);
    color:white;border:none;border-radius:28px;
    font-size:16px;font-weight:800;cursor:pointer;
    font-family:inherit;transition:.3s;
    position:relative;overflow:hidden;
}
.btn-login::before{
    content:'';position:absolute;top:0;left:-100%;
    width:100%;height:100%;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.15),transparent);
    transition:.5s;
}
.btn-login:hover::before{left:100%;}
.btn-login:hover{transform:translateY(-2px);box-shadow:0 12px 30px rgba(99,102,241,.4);}
.error-box{
    background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);
    color:#fca5a5;padding:14px 18px;border-radius:20px;
    font-size:13px;margin-bottom:24px;text-align:center;
    animation:shake .3s ease;
}
@keyframes shake{0%,100%{transform:translateX(0);}25%,75%{transform:translateX(-4px);}50%{transform:translateX(4px);}}
.notice-box{
    background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.3);
    color:#6ee7b7;padding:14px 18px;border-radius:20px;
    font-size:13px;margin-bottom:24px;text-align:center;
}
.hint{margin-top:24px;text-align:center;color:rgba(255,255,255,.4);font-size:12px;line-height:1.8;}
.hint a{color:rgba(99,102,241,.8);text-decoration:none;}
.hint a:hover{color:rgba(139,92,246,1);}
.divider{display:flex;align-items:center;gap:12px;margin:20px 0;color:rgba(255,255,255,.3);font-size:12px;}
.divider::before,.divider::after{content:'';flex:1;height:1px;background:rgba(255,255,255,.1);}
.admin-link{
    display:block;text-align:center;
    color:rgba(255,255,255,.5);font-size:12px;
    text-decoration:none;margin-top:16px;
    padding:10px;border-radius:20px;
    transition:.2s;
}
.admin-link:hover{background:rgba(255,255,255,.05);color:rgba(255,255,255,.8);}
</style>
</head>
<body>
<div class="card">
    <div class="logo">
        <span class="logo-icon">📘</span>
        <h1>سامانه آزمون آنلاین</h1>
        <p>ورود اختصاصی معلمان</p>
    </div>

    <?php if ($error): ?>
        <div class="error-box">⚠️ <?= h($error) ?></div>
    <?php endif; ?>
    <?php if ($notice): ?>
        <div class="notice-box"><?= h($notice) ?></div>
    <?php endif; ?>

    <form method="POST" autocomplete="off">
        <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">

        <div class="form-group">
            <label>کلید دسترسی</label>
            <div class="input-wrap">
                <input
                    type="text"
                    name="access_key"
                    placeholder="KEY-XXXXXXXXXXXXXXXX"
                    autofocus
                    autocomplete="off"
                    spellcheck="false"
                    required
                >
            </div>
        </div>

        <button type="submit" class="btn-login">
            ورود به سامانه →
        </button>
    </form>

    <div class="hint">
        برای دریافت کلید دسترسی با مدیر سیستم تماس بگیرید<br>
        یا به <a href="https://eitaa.com/MahanSoleymani01" target="_blank" rel="noopener">@MahanSoleymani01</a> پیام دهید
    </div>

    <div class="divider">یا</div>
    <a href="admin/index.php" class="admin-link">🔒 ورود به پنل مدیریت</a>
</div>
</body>
</html>
