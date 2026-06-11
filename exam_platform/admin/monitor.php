<?php
/**
 * admin/monitor.php - مانیتورینگ زنده آزمون‌ها
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
requireAdminAuth();

$form_id = validateInt($_GET['form_id'] ?? 0, 0);

// List of active exams
$stmt = $pdo->query("
    SELECT f.id, f.title, u.fullname as teacher_name,
           COUNT(DISTINCT a.id) as participant_count,
           SUM(CASE WHEN a.status='started' THEN 1 ELSE 0 END) as active_count,
           SUM(a.cheat_count) as total_cheats,
           f.start_time, f.end_time, f.is_active
    FROM forms f
    JOIN users u ON u.id = f.teacher_id
    LEFT JOIN answers a ON a.form_id = f.id
    GROUP BY f.id
    ORDER BY f.is_active DESC, f.id DESC
    LIMIT 50
");
$exams = $stmt->fetchAll();

$selectedExam = null;
if ($form_id) {
    $stmt = $pdo->prepare("SELECT f.*, u.fullname as teacher_name FROM forms f JOIN users u ON u.id=f.teacher_id WHERE f.id=?");
    $stmt->execute([$form_id]);
    $selectedExam = $stmt->fetch();
}

$csrf = generateCsrfToken();
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>مانیتورینگ زنده | پنل ادمین</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{--primary:#6366f1;--success:#10b981;--danger:#ef4444;--warning:#f59e0b;--bg:#f1f5f9;--card:#ffffff;--text:#0f172a;--muted:#64748b;--border:#e2e8f0;}
body{font-family:'Vazirmatn',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}
.topbar{background:linear-gradient(135deg,#1e293b,#0f172a);color:white;padding:16px 24px;display:flex;align-items:center;gap:16px;}
.topbar h1{font-size:20px;font-weight:800;}
.topbar a{color:rgba(255,255,255,.7);text-decoration:none;font-size:14px;}
.topbar a:hover{color:white;}
.layout{display:grid;grid-template-columns:300px 1fr;gap:0;min-height:calc(100vh - 60px);}
.sidebar{background:white;border-left:1px solid var(--border);padding:20px;overflow-y:auto;}
.sidebar h2{font-size:14px;font-weight:700;color:var(--muted);letter-spacing:1px;margin-bottom:12px;}
.exam-item{padding:12px;border-radius:12px;cursor:pointer;border:2px solid transparent;margin-bottom:8px;transition:.2s;}
.exam-item:hover{background:#f8fafc;border-color:var(--border);}
.exam-item.active{background:#ede9fe;border-color:var(--primary);}
.exam-item .title{font-size:14px;font-weight:700;margin-bottom:4px;}
.exam-item .meta{font-size:12px;color:var(--muted);display:flex;gap:10px;align-items:center;}
.badge{padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700;}
.badge-active{background:#dcfce7;color:#166534;}
.badge-inactive{background:#f1f5f9;color:var(--muted);}
.badge-cheat{background:#fee2e2;color:#991b1b;}
.main{padding:24px;overflow-y:auto;}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;}
.stat-card{background:white;border-radius:16px;padding:20px;text-align:center;}
.stat-card .num{font-size:36px;font-weight:800;}
.stat-card .lbl{font-size:12px;color:var(--muted);margin-top:4px;}
.stat-card.danger .num{color:var(--danger);}
.stat-card.success .num{color:var(--success);}
.stat-card.primary .num{color:var(--primary);}
.stat-card.warning .num{color:var(--warning);}
.section{background:white;border-radius:16px;padding:20px;margin-bottom:20px;}
.section h3{font-size:16px;font-weight:800;margin-bottom:16px;display:flex;align-items:center;gap:8px;}
.participant-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;}
.p-card{border:2px solid var(--border);border-radius:12px;padding:16px;transition:.2s;}
.p-card:hover{border-color:var(--primary);}
.p-card.cheat-flag{border-color:var(--danger);background:#fff5f5;}
.p-card .p-name{font-size:15px;font-weight:700;margin-bottom:6px;}
.p-card .p-ip{font-size:12px;color:var(--muted);font-family:monospace;}
.p-card .p-stats{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;}
.p-stat{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700;}
.p-stat.info{background:#ede9fe;color:#4f46e5;}
.p-stat.warn{background:#fef3c7;color:#92400e;}
.p-stat.danger{background:#fee2e2;color:#991b1b;}
.p-stat.success{background:#dcfce7;color:#166534;}
.p-actions{margin-top:12px;display:flex;gap:8px;}
.btn{padding:7px 14px;border-radius:20px;font-size:12px;font-weight:700;cursor:pointer;border:none;font-family:inherit;transition:.2s;}
.btn-cam{background:#6366f1;color:white;}
.btn-cam:hover{background:#4f46e5;}
.btn-ban{background:#fee2e2;color:#991b1b;}
.btn-ban:hover{background:#fecaca;}
.btn-term{background:#1e293b;color:white;}
.btn-term:hover{background:#0f172a;}
.cheat-table{width:100%;border-collapse:collapse;font-size:13px;}
.cheat-table th{text-align:right;padding:10px 12px;background:#f8fafc;font-weight:700;font-size:12px;color:var(--muted);}
.cheat-table td{padding:10px 12px;border-top:1px solid var(--border);}
.cheat-type{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#fee2e2;color:#991b1b;}
.refresh-indicator{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--muted);}
.pulse-dot{width:8px;height:8px;border-radius:50%;background:var(--success);animation:pulse 1.5s ease infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.5;transform:scale(.8);}}
.no-exam{display:flex;flex-direction:column;align-items:center;justify-content:center;height:400px;color:var(--muted);}
.no-exam .icon{font-size:64px;margin-bottom:16px;}
.live-bar{background:linear-gradient(135deg,#dcfce7,#bbf7d0);border:1px solid #86efac;border-radius:12px;padding:12px 16px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;}
@media(max-width:768px){
  .layout{grid-template-columns:1fr;}
  .sidebar{border-left:none;border-bottom:1px solid var(--border);max-height:42vh;}
  .main{padding:16px;}
  .stats-row{grid-template-columns:repeat(2,1fr);gap:12px;}
  .participant-grid{grid-template-columns:1fr;}
  .topbar{flex-wrap:wrap;padding:12px 16px;}
  .topbar h1{font-size:16px;}
  .cheat-table{display:block;overflow-x:auto;white-space:nowrap;}
}
</style>
</head>
<body>
<div class="topbar">
    <a href="index.php">← ادمین</a>
    <h1>🎥 مانیتورینگ زنده آزمون</h1>
    <div style="flex:1"></div>
    <div class="refresh-indicator">
        <div class="pulse-dot"></div>
        <span id="lastUpdate">در حال بارگذاری...</span>
    </div>
</div>
<div class="layout">
    <!-- Sidebar: exam list -->
    <div class="sidebar">
        <h2>آزمون‌ها (<?= count($exams) ?>)</h2>
        <?php foreach ($exams as $ex): ?>
        <div class="exam-item <?= $form_id == $ex['id'] ? 'active' : '' ?>" onclick="selectExam(<?= $ex['id'] ?>)">
            <div class="title"><?= h($ex['title']) ?></div>
            <div class="meta">
                <span><?= h($ex['teacher_name']) ?></span>
                <?php if ($ex['is_active']): ?>
                <span class="badge badge-active">● فعال</span>
                <?php else: ?>
                <span class="badge badge-inactive">غیرفعال</span>
                <?php endif; ?>
            </div>
            <div class="meta" style="margin-top:6px;">
                <span>👥 <?= $ex['participant_count'] ?></span>
                <span style="color:var(--success);">▶ <?= $ex['active_count'] ?? 0 ?></span>
                <?php if ($ex['total_cheats'] > 0): ?>
                <span class="badge badge-cheat">⚠️ <?= $ex['total_cheats'] ?> تقلب</span>
                <?php endif; ?>
            </div>
        </div>
        <?php endforeach; ?>
    </div>

    <!-- Main content -->
    <div class="main" id="mainContent">
        <?php if (!$form_id): ?>
        <div class="no-exam">
            <div class="icon">📊</div>
            <p style="font-size:18px;font-weight:700;">یک آزمون را از لیست انتخاب کنید</p>
            <p style="margin-top:8px;font-size:14px;">مانیتورینگ زنده شرکت‌کنندگان، تقلب‌ها و موقعیت GPS</p>
        </div>
        <?php else: ?>
        <div class="live-bar">
            <div>
                <strong style="font-size:16px;"><?= h($selectedExam['title'] ?? '') ?></strong>
                <span style="margin-right:12px;font-size:13px;color:var(--muted);">معلم: <?= h($selectedExam['teacher_name'] ?? '') ?></span>
            </div>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                <!-- Live toggles -->
                <div style="display:flex;align-items:center;gap:8px;background:white;border:2px solid var(--border);border-radius:20px;padding:6px 14px;">
                    <span style="font-size:12px;font-weight:700;color:var(--muted);">وب‌کم:</span>
                    <label style="position:relative;display:inline-block;width:36px;height:20px;cursor:pointer;">
                        <input type="checkbox" id="toggleCam" <?= ($selectedExam['require_camera'] ?? 0) ? 'checked' : '' ?> onchange="toggleSetting('require_camera', this.checked)" style="opacity:0;width:0;height:0;">
                        <span id="camSlider" style="position:absolute;inset:0;background:<?= ($selectedExam['require_camera'] ?? 0) ? '#6366f1' : '#cbd5e1' ?>;border-radius:20px;transition:.3s;"></span>
                        <span id="camThumb" style="position:absolute;width:14px;height:14px;background:white;border-radius:50%;top:3px;transition:.3s;left:<?= ($selectedExam['require_camera'] ?? 0) ? '19px' : '3px' ?>;"></span>
                    </label>
                </div>
                <div style="display:flex;align-items:center;gap:8px;background:white;border:2px solid var(--border);border-radius:20px;padding:6px 14px;">
                    <span style="font-size:12px;font-weight:700;color:var(--muted);">GPS:</span>
                    <label style="position:relative;display:inline-block;width:36px;height:20px;cursor:pointer;">
                        <input type="checkbox" id="toggleGps" <?= ($selectedExam['gps_required'] ?? 0) ? 'checked' : '' ?> onchange="toggleSetting('gps_required', this.checked)" style="opacity:0;width:0;height:0;">
                        <span id="gpsSlider" style="position:absolute;inset:0;background:<?= ($selectedExam['gps_required'] ?? 0) ? '#10b981' : '#cbd5e1' ?>;border-radius:20px;transition:.3s;"></span>
                        <span id="gpsThumb" style="position:absolute;width:14px;height:14px;background:white;border-radius:50%;top:3px;transition:.3s;left:<?= ($selectedExam['gps_required'] ?? 0) ? '19px' : '3px' ?>;"></span>
                    </label>
                </div>
                <a href="snapshots.php?form_id=<?= $form_id ?>" class="btn btn-cam" style="text-decoration:none;padding:8px 16px;">📷 اسنپشات‌ها</a>
                <a href="gps_monitor.php?form_id=<?= $form_id ?>" class="btn" style="background:#10b981;color:white;text-decoration:none;padding:8px 16px;">🗺️ نقشه GPS</a>
            </div>
        </div>

        <!-- Stats -->
        <div class="stats-row" id="statsRow">
            <div class="stat-card primary"><div class="num" id="statTotal">-</div><div class="lbl">کل شرکت‌کننده</div></div>
            <div class="stat-card success"><div class="num" id="statActive">-</div><div class="lbl">در حال آزمون</div></div>
            <div class="stat-card"><div class="num" id="statCompleted">-</div><div class="lbl">پایان یافته</div></div>
            <div class="stat-card danger"><div class="num" id="statCheats">-</div><div class="lbl">کل تقلب</div></div>
        </div>

        <!-- Participants -->
        <div class="section">
            <h3>👥 شرکت‌کنندگان <span id="partCountBadge" style="background:#ede9fe;color:#4f46e5;padding:2px 10px;border-radius:20px;font-size:13px;font-weight:700;"></span></h3>
            <div class="participant-grid" id="participantGrid">
                <div style="text-align:center;padding:40px;color:var(--muted);grid-column:1/-1;">در حال بارگذاری...</div>
            </div>
        </div>

        <!-- Recent Cheats -->
        <div class="section">
            <h3>⚠️ تقلب‌های اخیر</h3>
            <table class="cheat-table">
                <thead><tr><th>نوع</th><th>جزئیات</th><th>IP</th><th>زمان</th></tr></thead>
                <tbody id="cheatTableBody">
                    <tr><td colspan="4" style="text-align:center;color:var(--muted);padding:20px;">در حال بارگذاری...</td></tr>
                </tbody>
            </table>
        </div>
        <?php endif; ?>
    </div>
</div>

<script>
const FORM_ID    = <?= $form_id ?>;
const CSRF_TOKEN = '<?= h($csrf) ?>';
let refreshTimer;
let prevCheatTotal = null;

// بوقِ هشدار هنگام ثبت تقلب جدید (WebAudio — بدون فایل صوتی)
function playAlertBeep() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.type = 'square'; osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.08, ctx.currentTime);
        osc.start();
        osc.frequency.setValueAtTime(660, ctx.currentTime + 0.12);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.3);
        osc.stop(ctx.currentTime + 0.3);
    } catch (e) {}
}

function selectExam(id) {
    window.location.href = 'monitor.php?form_id=' + id;
}

function toggleSetting(setting, enabled) {
    const colors = { require_camera: '#6366f1', gps_required: '#10b981' };
    const sliderId = setting === 'require_camera' ? 'camSlider' : 'gpsSlider';
    const thumbId  = setting === 'require_camera' ? 'camThumb'  : 'gpsThumb';
    const slider   = document.getElementById(sliderId);
    const thumb    = document.getElementById(thumbId);
    if (slider) slider.style.background = enabled ? (colors[setting] || '#6366f1') : '#cbd5e1';
    if (thumb)  thumb.style.left = enabled ? '19px' : '3px';

    fetch('../api/toggle_exam_setting.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ form_id: FORM_ID, setting: setting, value: enabled ? 1 : 0, csrf_token: CSRF_TOKEN })
    })
    .then(r => r.json())
    .then(d => {
        const label = { require_camera: 'وب‌کم', gps_required: 'GPS' }[setting] || setting;
        if (d.ok) showToast((enabled ? '✅ ' : '⛔ ') + label + (enabled ? ' فعال شد' : ' غیرفعال شد'), enabled ? 'success' : 'info');
        else      showToast('❌ خطا: ' + (d.error || 'نامشخص'), 'error');
    })
    .catch(() => showToast('❌ خطای شبکه', 'error'));
}

<?php if ($form_id): ?>
function loadData() {
    fetch('../api/monitor_data.php?form_id=' + FORM_ID)
        .then(r => r.json())
        .then(data => {
            if (!data.ok) return;
            document.getElementById('lastUpdate').textContent = 'آخرین بروزرسانی: ' + data.timestamp;

            // Stats
            document.getElementById('statTotal').textContent     = data.stats.total || 0;
            document.getElementById('statActive').textContent    = data.stats.active || 0;
            document.getElementById('statCompleted').textContent = data.stats.completed || 0;
            const cheatTotal = parseInt(data.stats.total_cheats || 0);
            document.getElementById('statCheats').textContent    = cheatTotal;
            // هشدار زنده هنگام افزایش تقلب
            if (prevCheatTotal !== null && cheatTotal > prevCheatTotal) {
                playAlertBeep();
                showToast('🚨 تقلب جدید ثبت شد! (مجموع: ' + cheatTotal + ')', 'error');
            }
            prevCheatTotal = cheatTotal;

            // Participants
            const grid = document.getElementById('participantGrid');
            document.getElementById('partCountBadge').textContent = data.participants.length;
            if (data.participants.length === 0) {
                grid.innerHTML = '<div style="text-align:center;padding:40px;color:#64748b;grid-column:1/-1;">هنوز کسی شرکت نکرده</div>';
            } else {
                grid.innerHTML = data.participants.map(p => buildParticipantCard(p)).join('');
            }

            // Cheats
            const tbody = document.getElementById('cheatTableBody');
            if (data.recent_cheats.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#64748b;padding:20px;">تقلبی ثبت نشده</td></tr>';
            } else {
                tbody.innerHTML = data.recent_cheats.map(c => `
                    <tr>
                        <td><span class="cheat-type">${c.type}</span></td>
                        <td>${c.details || '-'}</td>
                        <td style="font-family:monospace;font-size:11px;">${c.user_ip}</td>
                        <td style="font-size:12px;color:#64748b;">${c.created_at}</td>
                    </tr>
                `).join('');
            }
        })
        .catch(() => {
            document.getElementById('lastUpdate').textContent = 'خطا در بارگذاری';
        });
}

function buildParticipantCard(p) {
    const hasCheat = p.cheat_count > 0;
    const elapsed  = p.elapsed_seconds ? Math.floor(p.elapsed_seconds / 60) : 0;
    const status   = p.status === 'started' ? 'در حال آزمون' : p.status === 'completed' ? 'پایان یافت' : p.status;
    const statusColor = p.status === 'started' ? 'success' : 'info';
    const gpsAvail = p.gps_lat && p.gps_lng;
    return `
        <div class="p-card ${hasCheat ? 'cheat-flag' : ''}">
            <div class="p-name">${p.user_name || 'ناشناس'}</div>
            <div class="p-ip">${p.user_ip}</div>
            <div class="p-stats">
                <span class="p-stat ${statusColor}">${status}</span>
                <span class="p-stat info">${elapsed} دقیقه</span>
                ${p.cheat_count > 0 ? `<span class="p-stat danger">⚠️ ${p.cheat_count} تقلب</span>` : ''}
                ${p.snapshot_count > 0 ? `<span class="p-stat info">📷 ${p.snapshot_count}</span>` : ''}
                ${gpsAvail ? `<span class="p-stat ${p.gps_flagged ? 'danger' : 'success'}">📍 GPS</span>` : '<span class="p-stat warn">📍 بدون GPS</span>'}
            </div>
            <div class="p-actions">
                <button class="btn btn-cam" onclick="requestCamera('${p.user_ip}')">📷 درخواست وب‌کم</button>
                <button class="btn btn-ban" onclick="banIP('${p.user_ip}')">🚫 بن</button>
            </div>
        </div>
    `;
}

function requestCamera(ip) {
    if (!confirm('درخواست وب‌کم از ' + ip + ' ارسال شود؟')) return;
    fetch('../api/camera_request.php', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({form_id: FORM_ID, target_ip: ip, csrf_token: CSRF_TOKEN})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            showToast('✅ درخواست وب‌کم ارسال شد. منتظر پاسخ دانش‌آموز باشید.', 'success');
        } else {
            showToast('❌ خطا: ' + (d.error || 'نامشخص'), 'error');
        }
    });
}

function banIP(ip) {
    const reason = prompt('دلیل مسدودسازی IP ' + ip + ':');
    if (reason === null) return;
    fetch('../api/ban_ip.php', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ip: ip, reason: reason, csrf_token: CSRF_TOKEN})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) showToast('✅ IP مسدود شد', 'success');
        else showToast('❌ خطا', 'error');
    });
}

function showToast(msg, type = 'info') {
    const t = document.createElement('div');
    t.style.cssText = `position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:14px 24px;border-radius:20px;font-weight:700;font-size:14px;z-index:9999;
        background:${type==='success'?'#10b981':type==='error'?'#ef4444':'#6366f1'};color:white;box-shadow:0 8px 24px rgba(0,0,0,.2);`;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

// Load & auto-refresh every 10 seconds
loadData();
refreshTimer = setInterval(loadData, 10000);
<?php endif; ?>
</script>
</body>
</html>
