<?php
/**
 * admin/snapshots.php - مشاهده و مدیریت اسنپشات‌های وب‌کم
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
requireAdminAuth();

$form_id = validateInt($_GET['form_id'] ?? 0, 0);
$filter  = sanitizeString($_GET['filter'] ?? 'all', 20);
$page    = max(1, validateInt($_GET['page'] ?? 1, 1) ?? 1);
$perPage = 24;
$offset  = ($page - 1) * $perPage;

// Handle actions
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    requireCsrf();
    $action = sanitizeString($_POST['action'] ?? '', 20);
    $snapId = validateInt($_POST['snap_id'] ?? 0, 1);

    if ($action === 'flag' && $snapId) {
        $pdo->prepare("UPDATE exam_snapshots SET flagged=1-flagged WHERE id=?")->execute([$snapId]);
        $pdo->prepare("INSERT INTO admin_audit_log (admin_id, action, target_type, target_id, ip_address) VALUES (?,?,?,?,?)")
            ->execute([$_SESSION['admin_id'], 'toggle_flag_snapshot', 'snapshot', $snapId, getClientIP()]);
    }
    if ($action === 'delete' && $snapId) {
        $stmt = $pdo->prepare("SELECT image_path FROM exam_snapshots WHERE id=?");
        $stmt->execute([$snapId]);
        $snap = $stmt->fetch();
        if ($snap) {
            $fullPath = __DIR__ . '/../' . $snap['image_path'];
            if (file_exists($fullPath)) unlink($fullPath);
            $pdo->prepare("DELETE FROM exam_snapshots WHERE id=?")->execute([$snapId]);
        }
    }
    header('Location: snapshots.php?form_id=' . $form_id . '&filter=' . $filter . '&page=' . $page);
    exit();
}

// Get exams list
$exams = $pdo->query("SELECT f.id, f.title, COUNT(s.id) as snap_count FROM forms f LEFT JOIN exam_snapshots s ON s.form_id=f.id GROUP BY f.id ORDER BY snap_count DESC LIMIT 50")->fetchAll();

// Build query with named conditions (safe)
$conditions = ['1=1'];
$params      = [];
if ($form_id) { $conditions[] = 's.form_id = ?'; $params[] = $form_id; }
if ($filter === 'flagged')   $conditions[] = 's.flagged=1';
if ($filter === 'no_face')   $conditions[] = 's.face_detected=0';
if ($filter === 'admin_req') $conditions[] = "s.trigger_type='admin_request'";
$where = 'WHERE ' . implode(' AND ', $conditions);

$countStmt = $pdo->prepare("SELECT COUNT(*) FROM exam_snapshots s $where");
$countStmt->execute($params);
$total = (int)$countStmt->fetchColumn();
$pages = max(1, ceil($total / $perPage));

$listParams = array_merge($params, [$perPage, $offset]);
$stmt = $pdo->prepare("
    SELECT s.*, f.title as exam_title
    FROM exam_snapshots s
    JOIN forms f ON f.id=s.form_id
    $where
    ORDER BY s.created_at DESC
    LIMIT ? OFFSET ?
");
$stmt->execute($listParams);
$snapshots = $stmt->fetchAll();

$csrf = generateCsrfToken();
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>اسنپشات‌های وب‌کم | ادمین</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{--primary:#6366f1;--danger:#ef4444;--success:#10b981;--bg:#f1f5f9;--border:#e2e8f0;--muted:#64748b;}
body{font-family:'Vazirmatn',sans-serif;background:var(--bg);}
.topbar{background:linear-gradient(135deg,#1e293b,#0f172a);color:white;padding:16px 24px;display:flex;align-items:center;gap:16px;}
.topbar h1{font-size:20px;font-weight:800;}
.topbar a{color:rgba(255,255,255,.7);text-decoration:none;}
.topbar a:hover{color:white;}
.main{padding:24px;max-width:1400px;margin:0 auto;}
.filters{background:white;border-radius:16px;padding:16px 20px;margin-bottom:20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
.filter-btn{padding:8px 16px;border-radius:20px;font-size:13px;font-weight:700;cursor:pointer;text-decoration:none;border:2px solid var(--border);color:var(--muted);transition:.2s;font-family:inherit;background:white;}
.filter-btn:hover,.filter-btn.active{background:var(--primary);color:white;border-color:var(--primary);}
.filter-btn.danger-btn.active{background:var(--danger);border-color:var(--danger);}
.snap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;}
.snap-card{background:white;border-radius:16px;overflow:hidden;border:2px solid var(--border);transition:.2s;}
.snap-card:hover{border-color:var(--primary);}
.snap-card.flagged{border-color:var(--danger);background:#fff5f5;}
.snap-img{width:100%;aspect-ratio:4/3;object-fit:cover;cursor:zoom-in;background:#f8fafc;}
.snap-info{padding:12px;}
.snap-name{font-size:13px;font-weight:700;margin-bottom:4px;}
.snap-meta{font-size:11px;color:var(--muted);margin-bottom:8px;}
.snap-tags{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px;}
.tag{padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;}
.tag-face{background:#dcfce7;color:#166534;}
.tag-noface{background:#fee2e2;color:#991b1b;}
.tag-admin{background:#ede9fe;color:#4f46e5;}
.tag-auto{background:#f1f5f9;color:var(--muted);}
.tag-cheat{background:#fef3c7;color:#92400e;}
.snap-actions{display:flex;gap:6px;}
.btn{padding:6px 12px;border-radius:12px;font-size:11px;font-weight:700;cursor:pointer;border:none;font-family:inherit;transition:.2s;}
.btn-flag{background:#fef3c7;color:#92400e;}
.btn-del{background:#fee2e2;color:#991b1b;}
.btn-flag:hover{background:#fde68a;}
.btn-del:hover{background:#fecaca;}
.pagination{display:flex;gap:8px;justify-content:center;margin-top:24px;}
.page-btn{padding:8px 16px;border-radius:12px;text-decoration:none;font-size:13px;font-weight:700;background:white;color:var(--muted);border:2px solid var(--border);}
.page-btn.active{background:var(--primary);color:white;border-color:var(--primary);}
.exam-select{padding:8px 16px;border-radius:12px;border:2px solid var(--border);font-family:inherit;font-size:13px;font-weight:700;}
.empty{text-align:center;padding:80px;color:var(--muted);}
.empty .icon{font-size:64px;margin-bottom:16px;}
/* Lightbox */
#lightbox{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:9999;align-items:center;justify-content:center;}
#lightbox.show{display:flex;}
#lightbox img{max-width:90vw;max-height:90vh;border-radius:12px;}
#lightbox .close{position:fixed;top:20px;left:20px;background:white;border:none;border-radius:50%;width:40px;height:40px;font-size:20px;cursor:pointer;display:flex;align-items:center;justify-content:center;}
</style>
</head>
<body>
<div class="topbar">
    <a href="index.php">← ادمین</a>
    <h1>📷 اسنپشات‌های وب‌کم</h1>
    <div style="flex:1"></div>
    <span style="font-size:14px;opacity:.7;">مجموع: <?= $total ?> تصویر</span>
</div>

<div class="main">
    <div class="filters">
        <select class="exam-select" onchange="location.href='snapshots.php?form_id='+this.value+'&filter=<?= h($filter) ?>'">
            <option value="0" <?= !$form_id?'selected':'' ?>>همه آزمون‌ها</option>
            <?php foreach ($exams as $ex): ?>
            <option value="<?= $ex['id'] ?>" <?= $form_id==$ex['id']?'selected':'' ?>><?= h($ex['title']) ?> (<?= $ex['snap_count'] ?>)</option>
            <?php endforeach; ?>
        </select>
        <a href="?form_id=<?= $form_id ?>&filter=all" class="filter-btn <?= $filter==='all'?'active':'' ?>">همه</a>
        <a href="?form_id=<?= $form_id ?>&filter=flagged" class="filter-btn danger-btn <?= $filter==='flagged'?'active':'' ?>">🚩 علامت‌گذاری شده</a>
        <a href="?form_id=<?= $form_id ?>&filter=no_face" class="filter-btn <?= $filter==='no_face'?'active':'' ?>">😶 بدون چهره</a>
        <a href="?form_id=<?= $form_id ?>&filter=admin_req" class="filter-btn <?= $filter==='admin_req'?'active':'' ?>">📩 درخواست ادمین</a>
    </div>

    <?php if (empty($snapshots)): ?>
    <div class="empty">
        <div class="icon">📷</div>
        <p style="font-size:18px;font-weight:700;">اسنپشاتی یافت نشد</p>
        <p style="margin-top:8px;font-size:14px;">آزمون باید وب‌کم را فعال داشته باشد</p>
    </div>
    <?php else: ?>
    <div class="snap-grid">
        <?php foreach ($snapshots as $snap): ?>
        <div class="snap-card <?= $snap['flagged'] ? 'flagged' : '' ?>">
            <img class="snap-img" src="../<?= h($snap['image_path']) ?>" alt="اسنپشات" onclick="openLightbox(this.src)" loading="lazy">
            <div class="snap-info">
                <div class="snap-name"><?= h($snap['student_name'] ?: 'ناشناس') ?></div>
                <div class="snap-meta">
                    <span style="font-family:monospace;font-size:10px;"><?= h($snap['user_ip']) ?></span> |
                    <?= h($snap['exam_title']) ?><br>
                    <?= h(substr($snap['created_at'],0,16)) ?>
                </div>
                <div class="snap-tags">
                    <?php if ($snap['face_detected']): ?>
                    <span class="tag tag-face">✅ چهره شناسایی شد</span>
                    <?php else: ?>
                    <span class="tag tag-noface">❌ بدون چهره</span>
                    <?php endif; ?>
                    <?php if ($snap['trigger_type'] === 'admin_request'): ?>
                    <span class="tag tag-admin">📩 درخواست ادمین</span>
                    <?php elseif ($snap['trigger_type'] === 'cheat_detect'): ?>
                    <span class="tag tag-cheat">⚠️ تقلب</span>
                    <?php else: ?>
                    <span class="tag tag-auto">🤖 خودکار</span>
                    <?php endif; ?>
                    <?php if ($snap['flagged']): ?><span class="tag" style="background:#fee2e2;color:#991b1b;">🚩 علامت‌گذاری</span><?php endif; ?>
                </div>
                <div class="snap-actions">
                    <form method="POST" style="display:inline;">
                        <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
                        <input type="hidden" name="action" value="flag">
                        <input type="hidden" name="snap_id" value="<?= $snap['id'] ?>">
                        <button class="btn btn-flag"><?= $snap['flagged'] ? '🏳️ رفع علامت' : '🚩 علامت' ?></button>
                    </form>
                    <form method="POST" style="display:inline;" onsubmit="return confirm('حذف شود؟')">
                        <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
                        <input type="hidden" name="action" value="delete">
                        <input type="hidden" name="snap_id" value="<?= $snap['id'] ?>">
                        <button class="btn btn-del">🗑️ حذف</button>
                    </form>
                </div>
            </div>
        </div>
        <?php endforeach; ?>
    </div>

    <!-- Pagination -->
    <?php if ($pages > 1): ?>
    <div class="pagination">
        <?php for ($p=1; $p<=$pages; $p++): ?>
        <a href="?form_id=<?= $form_id ?>&filter=<?= h($filter) ?>&page=<?= $p ?>" class="page-btn <?= $p==$page?'active':'' ?>"><?= $p ?></a>
        <?php endfor; ?>
    </div>
    <?php endif; ?>
    <?php endif; ?>
</div>

<!-- Lightbox -->
<div id="lightbox">
    <button class="close" onclick="closeLightbox()">✕</button>
    <img id="lightboxImg" src="" alt="">
</div>

<script>
function openLightbox(src) {
    document.getElementById('lightboxImg').src = src;
    document.getElementById('lightbox').classList.add('show');
}
function closeLightbox() {
    document.getElementById('lightbox').classList.remove('show');
}
document.getElementById('lightbox').addEventListener('click', function(e) {
    if (e.target === this) closeLightbox();
});
</script>
</body>
</html>
