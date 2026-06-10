<?php
/**
 * admin/audit_log.php - لاگ عملکرد ادمین
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
requireAdminAuth();

$page    = max(1, validateInt($_GET['page'] ?? 1, 1) ?? 1);
$search  = sanitizeString($_GET['q'] ?? '', 100);
$perPage = 50;
$offset  = ($page - 1) * $perPage;

$where = "WHERE 1=1";
$params = [];
if ($search) {
    $where .= " AND (l.action LIKE ? OR l.details LIKE ? OR l.ip_address LIKE ?)";
    $params = ["%$search%", "%$search%", "%$search%"];
}

$total = (int)$pdo->prepare("SELECT COUNT(*) FROM admin_audit_log l $where")->execute($params) ? 0 : 0;
$stmt = $pdo->prepare("SELECT COUNT(*) FROM admin_audit_log l $where");
$stmt->execute($params);
$total = (int)$stmt->fetchColumn();
$pages = max(1, ceil($total / $perPage));

$stmt = $pdo->prepare("
    SELECT l.*, u.fullname as admin_name
    FROM admin_audit_log l
    LEFT JOIN users u ON u.id = l.admin_id
    $where
    ORDER BY l.created_at DESC
    LIMIT $perPage OFFSET $offset
");
$stmt->execute($params);
$logs = $stmt->fetchAll();

$actionColors = [
    'login'           => '#dcfce7',
    'logout'          => '#f1f5f9',
    'create_teacher'  => '#ede9fe',
    'delete_teacher'  => '#fee2e2',
    'create_key'      => '#fef3c7',
    'camera_request'  => '#dbeafe',
    'ban_ip'          => '#fee2e2',
    'unban_ip'        => '#dcfce7',
    'delete_snapshot' => '#fef3c7',
    'toggle_flag_snapshot' => '#fef3c7',
];
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>لاگ عملکرد | ادمین</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{--primary:#6366f1;--bg:#f1f5f9;--border:#e2e8f0;--muted:#64748b;}
body{font-family:'Vazirmatn',sans-serif;background:var(--bg);}
.topbar{background:linear-gradient(135deg,#1e293b,#0f172a);color:white;padding:16px 24px;display:flex;align-items:center;gap:16px;}
.topbar h1{font-size:20px;font-weight:800;}
.topbar a{color:rgba(255,255,255,.7);text-decoration:none;}
.main{padding:24px;max-width:1200px;margin:0 auto;}
.search-bar{background:white;border-radius:16px;padding:16px;margin-bottom:20px;display:flex;gap:12px;}
.search-bar input{flex:1;padding:10px 16px;border:2px solid var(--border);border-radius:12px;font-family:inherit;font-size:14px;}
.search-bar input:focus{outline:none;border-color:var(--primary);}
.search-bar button{padding:10px 20px;background:var(--primary);color:white;border:none;border-radius:12px;font-weight:700;font-family:inherit;cursor:pointer;}
.log-table{width:100%;border-collapse:collapse;background:white;border-radius:16px;overflow:hidden;}
.log-table th{text-align:right;padding:14px 16px;background:#f8fafc;font-size:13px;font-weight:700;color:var(--muted);}
.log-table td{padding:12px 16px;border-top:1px solid var(--border);font-size:13px;vertical-align:middle;}
.action-badge{padding:3px 10px;border-radius:10px;font-size:11px;font-weight:700;display:inline-block;}
.pagination{display:flex;gap:8px;justify-content:center;margin-top:20px;}
.page-btn{padding:8px 16px;border-radius:12px;text-decoration:none;font-size:13px;font-weight:700;background:white;color:var(--muted);border:2px solid var(--border);}
.page-btn.active{background:var(--primary);color:white;border-color:var(--primary);}
</style>
</head>
<body>
<div class="topbar">
    <a href="index.php">← ادمین</a>
    <h1>📋 لاگ عملکرد ادمین</h1>
    <div style="flex:1"></div>
    <span style="font-size:13px;opacity:.7;"><?= $total ?> رکورد</span>
</div>
<div class="main">
    <form class="search-bar">
        <input type="text" name="q" value="<?= h($search) ?>" placeholder="جستجو در عملیات‌ها، جزئیات، IP...">
        <button type="submit">🔍 جستجو</button>
    </form>

    <table class="log-table">
        <thead>
            <tr>
                <th>#</th>
                <th>ادمین</th>
                <th>عملیات</th>
                <th>جزئیات</th>
                <th>IP</th>
                <th>زمان</th>
            </tr>
        </thead>
        <tbody>
            <?php if (empty($logs)): ?>
            <tr><td colspan="6" style="text-align:center;padding:40px;color:var(--muted);">لاگی یافت نشد</td></tr>
            <?php else: ?>
            <?php foreach ($logs as $log): ?>
            <tr>
                <td style="color:var(--muted);font-size:12px;"><?= $log['id'] ?></td>
                <td><?= h($log['admin_name'] ?? 'نامشخص') ?></td>
                <td>
                    <span class="action-badge" style="background:<?= $actionColors[$log['action']] ?? '#f1f5f9' ?>">
                        <?= h($log['action']) ?>
                    </span>
                </td>
                <td style="max-width:400px;font-size:12px;color:#475569;"><?= h($log['details'] ?? '-') ?></td>
                <td style="font-family:monospace;font-size:11px;color:var(--muted);"><?= h($log['ip_address'] ?? '-') ?></td>
                <td style="font-size:12px;color:var(--muted);white-space:nowrap;"><?= h(substr($log['created_at'],0,16)) ?></td>
            </tr>
            <?php endforeach; ?>
            <?php endif; ?>
        </tbody>
    </table>

    <?php if ($pages > 1): ?>
    <div class="pagination">
        <?php for ($p=1; $p<=$pages && $p<=20; $p++): ?>
        <a href="?page=<?= $p ?>&q=<?= urlencode($search) ?>" class="page-btn <?= $p==$page?'active':'' ?>"><?= $p ?></a>
        <?php endfor; ?>
    </div>
    <?php endif; ?>
</div>
</body>
</html>
