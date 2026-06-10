<?php
/**
 * admin/ip_blacklist.php - مدیریت لیست سیاه IP
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
requireAdminAuth();

$msg = '';
$msgType = 'success';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    requireCsrf();
    $action = sanitizeString($_POST['action'] ?? '', 20);

    if ($action === 'add') {
        $ip     = filter_var(trim($_POST['ip'] ?? ''), FILTER_VALIDATE_IP);
        $reason = sanitizeString($_POST['reason'] ?? '', 500);
        $days   = validateInt($_POST['days'] ?? 0, 0) ?? 0;

        if (!$ip) {
            $msg = 'آدرس IP نامعتبر است'; $msgType = 'error';
        } else {
            $expires = $days > 0 ? date('Y-m-d H:i:s', strtotime("+$days days")) : null;
            try {
                $pdo->prepare("INSERT INTO ip_blacklist (ip_address, reason, blocked_by, expires_at) VALUES (?,?,?,?) ON DUPLICATE KEY UPDATE reason=VALUES(reason), is_active=1, expires_at=VALUES(expires_at)")
                    ->execute([$ip, $reason, $_SESSION['admin_id'], $expires]);
                $pdo->prepare("INSERT INTO admin_audit_log (admin_id, action, details, ip_address) VALUES (?,?,?,?)")
                    ->execute([$_SESSION['admin_id'], 'ban_ip', 'مسدود کردن IP: '.$ip.' دلیل: '.$reason, getClientIP()]);
                $msg = "IP $ip با موفقیت مسدود شد";
            } catch (PDOException $e) {
                $msg = 'خطا: ' . $e->getMessage(); $msgType = 'error';
            }
        }
    }

    if ($action === 'remove') {
        $id = validateInt($_POST['bl_id'] ?? 0, 1);
        if ($id) {
            $stmt = $pdo->prepare("SELECT ip_address FROM ip_blacklist WHERE id=?");
            $stmt->execute([$id]);
            $row = $stmt->fetch();
            $pdo->prepare("UPDATE ip_blacklist SET is_active=0 WHERE id=?")->execute([$id]);
            if ($row) {
                $pdo->prepare("INSERT INTO admin_audit_log (admin_id, action, details, ip_address) VALUES (?,?,?,?)")
                    ->execute([$_SESSION['admin_id'], 'unban_ip', 'رفع مسدودیت IP: '.$row['ip_address'], getClientIP()]);
            }
            $msg = 'مسدودیت رفع شد';
        }
    }
}

$blacklist = $pdo->query("
    SELECT b.*, u.fullname as admin_name
    FROM ip_blacklist b
    LEFT JOIN users u ON u.id=b.blocked_by
    ORDER BY b.is_active DESC, b.created_at DESC
    LIMIT 200
")->fetchAll();

$csrf = generateCsrfToken();
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>لیست سیاه IP | ادمین</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{--primary:#6366f1;--danger:#ef4444;--success:#10b981;--bg:#f1f5f9;--border:#e2e8f0;--muted:#64748b;}
body{font-family:'Vazirmatn',sans-serif;background:var(--bg);}
.topbar{background:linear-gradient(135deg,#1e293b,#0f172a);color:white;padding:16px 24px;display:flex;align-items:center;gap:16px;}
.topbar h1{font-size:20px;font-weight:800;}
.topbar a{color:rgba(255,255,255,.7);text-decoration:none;}
.main{padding:24px;max-width:1100px;margin:0 auto;}
.add-card{background:white;border-radius:16px;padding:24px;margin-bottom:24px;}
.add-card h2{font-size:16px;font-weight:800;margin-bottom:16px;}
.form-row{display:grid;grid-template-columns:1fr 2fr 1fr auto;gap:12px;align-items:end;}
.field{display:flex;flex-direction:column;gap:6px;}
.field label{font-size:12px;font-weight:700;color:var(--muted);}
.field input,.field select{padding:10px 14px;border:2px solid var(--border);border-radius:12px;font-family:inherit;font-size:14px;}
.field input:focus,.field select:focus{outline:none;border-color:var(--primary);}
.btn-add{padding:10px 20px;background:var(--danger);color:white;border:none;border-radius:12px;font-weight:700;font-family:inherit;cursor:pointer;}
.msg{padding:12px 16px;border-radius:12px;margin-bottom:16px;font-size:14px;font-weight:700;}
.msg.success{background:#dcfce7;color:#166534;}
.msg.error{background:#fee2e2;color:#991b1b;}
.bl-table{width:100%;border-collapse:collapse;background:white;border-radius:16px;overflow:hidden;}
.bl-table th{text-align:right;padding:14px 16px;background:#f8fafc;font-size:13px;font-weight:700;color:var(--muted);}
.bl-table td{padding:12px 16px;border-top:1px solid var(--border);font-size:13px;}
.status-badge{padding:3px 10px;border-radius:10px;font-size:11px;font-weight:700;}
.active-badge{background:#fee2e2;color:#991b1b;}
.inactive-badge{background:#f1f5f9;color:var(--muted);}
.btn-remove{padding:5px 12px;background:#fee2e2;color:#991b1b;border:none;border-radius:8px;font-size:11px;font-weight:700;cursor:pointer;font-family:inherit;}
</style>
</head>
<body>
<div class="topbar">
    <a href="index.php">← ادمین</a>
    <h1>🚫 لیست سیاه IP</h1>
    <div style="flex:1"></div>
    <span style="font-size:13px;opacity:.7;"><?= count(array_filter($blacklist, fn($b) => $b['is_active'])) ?> فعال</span>
</div>
<div class="main">
    <?php if ($msg): ?>
    <div class="msg <?= $msgType ?>"><?= h($msg) ?></div>
    <?php endif; ?>

    <div class="add-card">
        <h2>🔒 مسدود کردن IP جدید</h2>
        <form method="POST">
            <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
            <input type="hidden" name="action" value="add">
            <div class="form-row">
                <div class="field">
                    <label>آدرس IP</label>
                    <input type="text" name="ip" placeholder="192.168.1.1" required>
                </div>
                <div class="field">
                    <label>دلیل</label>
                    <input type="text" name="reason" placeholder="دلیل مسدودسازی..." required>
                </div>
                <div class="field">
                    <label>مدت (روز — 0=دائمی)</label>
                    <input type="number" name="days" value="0" min="0" max="3650">
                </div>
                <button type="submit" class="btn-add">🚫 مسدود کردن</button>
            </div>
        </form>
    </div>

    <table class="bl-table">
        <thead>
            <tr>
                <th>آدرس IP</th>
                <th>وضعیت</th>
                <th>دلیل</th>
                <th>توسط</th>
                <th>انقضا</th>
                <th>تاریخ</th>
                <th>عملیات</th>
            </tr>
        </thead>
        <tbody>
            <?php if (empty($blacklist)): ?>
            <tr><td colspan="7" style="text-align:center;padding:40px;color:var(--muted);">لیست سیاه خالی است</td></tr>
            <?php else: ?>
            <?php foreach ($blacklist as $b): ?>
            <tr>
                <td style="font-family:monospace;font-weight:700;"><?= h($b['ip_address']) ?></td>
                <td>
                    <?php if ($b['is_active']): ?>
                    <span class="status-badge active-badge">● فعال</span>
                    <?php else: ?>
                    <span class="status-badge inactive-badge">رفع شد</span>
                    <?php endif; ?>
                </td>
                <td style="font-size:12px;color:#475569;max-width:300px;"><?= h($b['reason'] ?? '-') ?></td>
                <td style="font-size:12px;"><?= h($b['admin_name'] ?? 'نامشخص') ?></td>
                <td style="font-size:12px;color:var(--muted);"><?= $b['expires_at'] ? h(substr($b['expires_at'],0,10)) : 'دائمی' ?></td>
                <td style="font-size:12px;color:var(--muted);"><?= h(substr($b['created_at'],0,10)) ?></td>
                <td>
                    <?php if ($b['is_active']): ?>
                    <form method="POST" style="display:inline;" onsubmit="return confirm('رفع مسدودیت؟')">
                        <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
                        <input type="hidden" name="action" value="remove">
                        <input type="hidden" name="bl_id" value="<?= $b['id'] ?>">
                        <button class="btn-remove">رفع مسدودیت</button>
                    </form>
                    <?php endif; ?>
                </td>
            </tr>
            <?php endforeach; ?>
            <?php endif; ?>
        </tbody>
    </table>
</div>
</body>
</html>
