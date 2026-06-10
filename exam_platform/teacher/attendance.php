<?php
/**
 * teacher/attendance.php - مدیریت حضور و غیاب
 * Fixed: teacher_id in attendance_records
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
$teacher = requireTeacherAuth();
$tid = $teacher['id'];
$msg = ''; $msgType = 'success';

// Export CSV
if (isset($_GET['export']) && isset($_GET['att'])) {
    $aid = validateInt($_GET['att'], 1);
    $s = $pdo->prepare("SELECT a.id FROM attendances a WHERE a.id=? AND a.teacher_id=?");
    $s->execute([$aid, $tid]);
    if ($s->fetch()) {
        $s = $pdo->prepare("SELECT * FROM attendance_records WHERE attendance_id=? ORDER BY submitted_at");
        $s->execute([$aid]);
        $rows = $s->fetchAll();
        header('Content-Type: text/csv; charset=UTF-8');
        header('Content-Disposition: attachment; filename="attendance_' . $aid . '.csv"');
        echo "\xEF\xBB\xBF";
        $out = fopen('php://output', 'w');
        fputcsv($out, ['ردیف','نام','کد ملی','کلاس','آی‌پی','زمان']);
        foreach ($rows as $i => $r) fputcsv($out, [$i+1, $r['student_name'], $r['national_code']??'', $r['class_number'], $r['ip_address'], $r['submitted_at']]);
        fclose($out); exit();
    }
}

// ساخت جلسه جدید
if (isset($_POST['create_attendance'])) {
    requireCsrf();
    $title    = sanitizeString($_POST['title'] ?? '', 200);
    $duration = validateInt($_POST['duration'] ?? 20, 1, 240) ?? 20;
    $class    = sanitizeString($_POST['class_name'] ?? '', 100);
    if ($title) {
        $link = 'att_' . bin2hex(random_bytes(6));
        $pdo->prepare("INSERT INTO attendances (teacher_id,title,class_name,unique_link,duration_minutes) VALUES (?,?,?,?,?)")
            ->execute([$tid, $title, $class, $link, $duration]);
        $msg = '✅ جلسه جدید ساخته شد';
    }
}

// فعال کردن جلسه
if (isset($_POST['activate_attendance'])) {
    requireCsrf();
    $aid = validateInt($_POST['att_id'] ?? 0, 1);
    $dur = validateInt($_POST['duration'] ?? 20, 1, 240) ?? 20;
    if ($aid) {
        $start = date('Y-m-d H:i:s');
        $end   = date('Y-m-d H:i:s', time() + $dur * 60);
        $pdo->prepare("UPDATE attendances SET is_active=1, duration_minutes=?, start_time=?, end_time=? WHERE id=? AND teacher_id=?")
            ->execute([$dur, $start, $end, $aid, $tid]);
        $msg = '✅ جلسه فعال شد';
    }
}

// غیرفعال کردن
if (isset($_POST['deactivate'])) {
    requireCsrf();
    $aid = validateInt($_POST['deactivate'], 1);
    if ($aid) $pdo->prepare("UPDATE attendances SET is_active=0 WHERE id=? AND teacher_id=?")->execute([$aid, $tid]);
    redirect('attendance.php?msg=deactivated');
}

// حذف جلسه
if (isset($_POST['delete'])) {
    requireCsrf();
    $aid = validateInt($_POST['delete'], 1);
    if ($aid) $pdo->prepare("DELETE FROM attendances WHERE id=? AND teacher_id=?")->execute([$aid, $tid]);
    redirect('attendance.php?msg=deleted');
}

if (isset($_GET['msg'])) {
    $msgs = ['deactivated'=>'✅ غیرفعال شد','deleted'=>'✅ حذف شد'];
    $msg = $msgs[$_GET['msg']] ?? '';
}

// دریافت جلسات
$s = $pdo->prepare("SELECT a.*, COUNT(r.id) as record_count FROM attendances a LEFT JOIN attendance_records r ON r.attendance_id=a.id WHERE a.teacher_id=? GROUP BY a.id ORDER BY a.id DESC");
$s->execute([$tid]);
$sessions = $s->fetchAll();

// جزئیات جلسه
$viewId = validateInt($_GET['view'] ?? 0, 0) ?? 0;
$viewSession = null; $attendees = [];
if ($viewId) {
    $s = $pdo->prepare("SELECT * FROM attendances WHERE id=? AND teacher_id=?");
    $s->execute([$viewId, $tid]);
    $viewSession = $s->fetch();
    if ($viewSession) {
        $s = $pdo->prepare("SELECT * FROM attendance_records WHERE attendance_id=? ORDER BY submitted_at");
        $s->execute([$viewId]);
        $attendees = $s->fetchAll();
    }
}
$csrf = generateCsrfToken();
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>مدیریت حضور‌وغیاب</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<style>
<?php include __DIR__ . '/../assets/css/panel.css'; ?>
.att-card{background:white;border:1px solid var(--border);border-radius:20px;padding:20px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;}
.att-info strong{display:block;font-size:16px;font-weight:700;}
.att-info small{font-size:12px;color:var(--text-muted);}
.att-status{display:inline-block;padding:4px 12px;border-radius:30px;font-size:12px;font-weight:700;}
.att-active{background:#dcfce7;color:#166534;}
.att-expired{background:#fee2e2;color:#991b1b;}
.att-draft{background:#f1f5f9;color:#64748b;}
.att-count{background:#ede9fe;color:#5b21b6;padding:4px 14px;border-radius:30px;font-size:13px;font-weight:700;}
.attendee-table{width:100%;border-collapse:collapse;}
.attendee-table th,.attendee-table td{padding:12px 16px;text-align:right;border-bottom:1px solid var(--border);font-size:13px;}
.attendee-table th{background:#f8fafc;font-weight:700;}
.link-box{background:#f0fdf4;border:1.5px solid #86efac;border-radius:16px;padding:14px 18px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;}
.link-url{font-family:monospace;font-size:13px;color:#166534;word-break:break-all;}
.table-scroll,.table-wrap{overflow-x:auto;}
@media(max-width:768px){
  .attendee-table{min-width:560px;}
  .att-card .item-actions, .att-card{flex-wrap:wrap;}
}
</style>
</head>
<body>
<?php include __DIR__ . '/includes/sidebar.php'; ?>
<div class="main-content">

<?php if ($msg): ?>
<div class="alert alert-success" id="flashMsg"><?= h($msg) ?></div>
<script>setTimeout(()=>document.getElementById('flashMsg')?.remove(),4000)</script>
<?php endif; ?>

<div class="page-header">
    <div><h1>📋 مدیریت حضور‌وغیاب</h1><p>ساخت، فعال‌سازی و مشاهده جلسات</p></div>
</div>

<div class="grid-2col">
    <!-- ساخت جلسه -->
    <div class="card">
        <div class="card-header"><h3>➕ جلسه جدید</h3></div>
        <div class="card-body">
            <form method="POST">
                <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
                <div class="form-group">
                    <label>عنوان جلسه</label>
                    <input class="form-control" name="title" placeholder="مثال: حضور ریاضی سه‌شنبه" required>
                </div>
                <div class="form-group">
                    <label>کلاس/گروه</label>
                    <input class="form-control" name="class_name" placeholder="مثال: نهم الف">
                </div>
                <div class="form-group">
                    <label>مدت زمان (دقیقه)</label>
                    <input class="form-control" type="number" name="duration" value="20" min="1" max="240">
                </div>
                <button type="submit" name="create_attendance" class="btn btn-primary">ساخت جلسه</button>
            </form>
        </div>
    </div>

    <!-- راهنما -->
    <div class="card">
        <div class="card-header"><h3>📖 راهنما</h3></div>
        <div class="card-body">
            <ol style="padding-right:20px;color:#475569;font-size:14px;line-height:2.2;">
                <li>جلسه جدید بسازید</li>
                <li>روی "فعال کردن" کلیک کنید</li>
                <li>لینک جلسه را برای دانش‌آموزان ارسال کنید</li>
                <li>دانش‌آموزان حضور خود را ثبت می‌کنند</li>
                <li>لیست را از "جزئیات" مشاهده و Export کنید</li>
            </ol>
        </div>
    </div>
</div>

<!-- لیست جلسات -->
<div class="card">
    <div class="card-header"><h3>📋 جلسات موجود (<?= count($sessions) ?>)</h3></div>
    <div class="card-body">
        <?php if ($sessions): ?>
        <?php foreach ($sessions as $att):
            $now = time();
            $status = 'draft';
            if ($att['start_time'] && $att['end_time']) {
                if ($now < strtotime($att['start_time'])) $status = 'not_started';
                elseif ($now > strtotime($att['end_time'])) $status = 'expired';
                elseif ($att['is_active']) $status = 'active';
                else $status = 'inactive';
            }
            $remaining = $att['end_time'] ? max(0, strtotime($att['end_time']) - $now) : 0;
        ?>
        <div class="att-card">
            <div class="att-info">
                <strong><?= h($att['title']) ?></strong>
                <small>
                    <?= $att['class_name'] ? h($att['class_name']) . ' | ' : '' ?>
                    مدت: <?= $att['duration_minutes'] ?> دقیقه
                    <?php if ($att['start_time']): ?>
                    | <?= substr($att['start_time'],11,5) ?> - <?= substr($att['end_time'],11,5) ?>
                    <?php endif; ?>
                    <?php if ($status === 'active' && $remaining > 0): ?>
                    | ⏱️ <?= sprintf('%02d:%02d', floor($remaining/60), $remaining%60) ?> باقی مانده
                    <?php endif; ?>
                </small>
            </div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                <span class="att-count">👥 <?= $att['record_count'] ?> نفر</span>
                <?php if ($status === 'active'): ?>
                    <span class="att-status att-active">✅ فعال</span>
                <?php elseif ($status === 'expired'): ?>
                    <span class="att-status att-expired">⏰ پایان یافته</span>
                <?php else: ?>
                    <span class="att-status att-draft">⏳ پیش‌نویس</span>
                <?php endif; ?>

                <?php if ($att['is_active'] && $att['end_time'] && strtotime($att['end_time']) > $now): ?>
                    <!-- لینک -->
                    <button class="btn btn-secondary btn-sm" onclick="showLink('<?= h($att['unique_link']) ?>')">🔗 لینک</button>
                    <form method="POST" style="display:inline;" onsubmit="return confirm('این جلسه غیرفعال شود؟')">
                        <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
                        <input type="hidden" name="deactivate" value="<?= $att['id'] ?>">
                        <button type="submit" class="btn btn-warning btn-sm">⛔</button>
                    </form>
                <?php else: ?>
                    <!-- فعال‌سازی -->
                    <button class="btn btn-success btn-sm" onclick="openActivateModal(<?= $att['id'] ?>, <?= $att['duration_minutes'] ?>)">🚀 فعال کردن</button>
                <?php endif; ?>
                <a href="?view=<?= $att['id'] ?>" class="btn btn-primary btn-sm">📊 جزئیات</a>
                <form method="POST" style="display:inline;" onsubmit="return confirm('این جلسه و همهٔ رکوردهایش حذف شود؟')">
                    <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
                    <input type="hidden" name="delete" value="<?= $att['id'] ?>">
                    <button type="submit" class="btn btn-danger btn-sm">🗑️</button>
                </form>
            </div>
        </div>
        <?php endforeach; ?>
        <?php else: ?>
        <div class="empty-state">هنوز جلسه‌ای ساخته نشده</div>
        <?php endif; ?>
    </div>
</div>

<!-- نمایش جزئیات -->
<?php if ($viewSession): ?>
<div class="card">
    <div class="card-header">
        <h3>📊 جزئیات: <?= h($viewSession['title']) ?></h3>
        <div style="display:flex;gap:8px;">
            <a href="?att=<?= $viewId ?>&export=1" class="btn btn-success btn-sm">📥 خروجی CSV</a>
            <a href="attendance.php" class="btn btn-secondary btn-sm">← بازگشت</a>
        </div>
    </div>
    <div class="table-wrap">
        <?php if ($attendees): ?>
        <table class="attendee-table">
            <thead><tr><th>#</th><th>نام</th><th>کد ملی</th><th>کلاس</th><th>آی‌پی</th><th>زمان ثبت</th></tr></thead>
            <tbody>
                <?php foreach ($attendees as $i => $a): ?>
                <tr>
                    <td><?= $i+1 ?></td>
                    <td><strong><?= h($a['student_name']) ?></strong></td>
                    <td style="font-family:monospace;"><?= h($a['national_code'] ?? '—') ?></td>
                    <td><?= h($a['class_number']) ?></td>
                    <td style="font-family:monospace;font-size:11px;"><?= h($a['ip_address']) ?></td>
                    <td><?= substr($a['submitted_at'],11,8) ?></td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
        <?php else: ?>
        <div class="empty-state">هنوز کسی حضور خود را ثبت نکرده</div>
        <?php endif; ?>
    </div>
</div>
<?php endif; ?>

</div>

<!-- Activate Modal -->
<div class="modal-overlay" id="activateModal">
    <div class="modal" style="max-width:440px;">
        <div class="modal-header"><h3>🚀 فعال‌سازی جلسه</h3><button class="modal-close" onclick="closeActivate()">×</button></div>
        <form method="POST">
            <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
            <input type="hidden" name="activate_attendance" value="1">
            <input type="hidden" name="att_id" id="activateAttId" value="">
            <div class="form-group" style="margin-top:16px;">
                <label>مدت زمان جلسه (دقیقه)</label>
                <input class="form-control" type="number" name="duration" id="activateDuration" value="20" min="1" max="240">
            </div>
            <div style="display:flex;gap:12px;margin-top:16px;">
                <button type="submit" class="btn btn-success" style="flex:1">✅ فعال کردن</button>
                <button type="button" class="btn btn-secondary" onclick="closeActivate()">انصراف</button>
            </div>
        </form>
    </div>
</div>

<!-- Link Modal -->
<div class="modal-overlay" id="linkModal">
    <div class="modal" style="max-width:440px;">
        <div class="modal-header"><h3>🔗 لینک حضور‌وغیاب</h3><button class="modal-close" onclick="document.getElementById('linkModal').classList.remove('open')">×</button></div>
        <div class="link-box" style="margin-top:16px;">
            <div class="link-url" id="attLinkDisplay"></div>
            <button class="copy-btn" style="background:#dcfce7;color:#166534;border:none;border-radius:8px;padding:6px 14px;cursor:pointer;" onclick="copyAttLink()">📋 کپی</button>
        </div>
        <p style="font-size:12px;color:var(--text-muted);margin-top:12px;text-align:center;">این لینک را برای دانش‌آموزان ارسال کنید</p>
    </div>
</div>

<script>
function openActivateModal(id, dur) {
    document.getElementById('activateAttId').value = id;
    document.getElementById('activateDuration').value = dur;
    document.getElementById('activateModal').classList.add('open');
}
function closeActivate() { document.getElementById('activateModal').classList.remove('open'); }

function showLink(link) {
    const host = window.location.origin;
    const url  = host + '/attendance.php?link=' + link;
    document.getElementById('attLinkDisplay').textContent = url;
    document.getElementById('linkModal').classList.add('open');
}
function copyAttLink() {
    const el = document.getElementById('attLinkDisplay');
    navigator.clipboard.writeText(el.textContent);
    el.nextElementSibling.textContent = '✅ کپی شد!';
    setTimeout(() => el.nextElementSibling.textContent = '📋 کپی', 2000);
}

document.querySelectorAll('.modal-overlay').forEach(m => {
    m.addEventListener('click', function(e) { if(e.target===this) this.classList.remove('open'); });
});
</script>
</body>
</html>
