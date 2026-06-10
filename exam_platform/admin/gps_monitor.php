<?php
/**
 * admin/gps_monitor.php - مانیتورینگ GPS و تشخیص خوشه‌های تقلب
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
requireAdminAuth();

$form_id = validateInt($_GET['form_id'] ?? 0, 0);

$exams = $pdo->query("
    SELECT f.id, f.title, COUNT(g.id) as gps_count, SUM(g.flagged) as flagged_count
    FROM forms f
    LEFT JOIN gps_locations g ON g.form_id=f.id
    GROUP BY f.id
    ORDER BY gps_count DESC
    LIMIT 50
")->fetchAll();

$gpsData = [];
$clusters = [];
$formInfo = null;

if ($form_id) {
    $stmt = $pdo->prepare("SELECT f.*, u.fullname as teacher_name FROM forms f JOIN users u ON u.id=f.teacher_id WHERE f.id=?");
    $stmt->execute([$form_id]);
    $formInfo = $stmt->fetch();

    $stmt = $pdo->prepare("
        SELECT user_ip, student_name, latitude, longitude, accuracy, flagged, created_at,
               out_of_bounds
        FROM gps_locations
        WHERE form_id=?
        GROUP BY user_ip
        ORDER BY created_at DESC
    ");
    $stmt->execute([$form_id]);
    $gpsData = $stmt->fetchAll();

    // Cluster detection (Haversine)
    $threshold = 50;
    $visited   = [];
    $clusterIdx = 0;
    foreach ($gpsData as $i => &$a) {
        if (isset($visited[$i])) continue;
        $clusterMembers = [$i];
        foreach ($gpsData as $j => $b) {
            if ($i === $j || isset($visited[$j])) continue;
            $dist = haversineDistance((float)$a['latitude'], (float)$a['longitude'], (float)$b['latitude'], (float)$b['longitude']);
            if ($dist < $threshold) {
                $clusterMembers[] = $j;
                $visited[$j] = true;
            }
        }
        $visited[$i] = true;
        if (count($clusterMembers) > 1) {
            $clusters[] = ['id' => ++$clusterIdx, 'members' => $clusterMembers, 'flagged' => true];
            foreach ($clusterMembers as $mi) $gpsData[$mi]['cluster_id'] = $clusterIdx;
        }
    }
    unset($a);
}

function haversineDistance(float $lat1, float $lng1, float $lat2, float $lng2): float {
    $R = 6371000;
    $dLat = deg2rad($lat2 - $lat1);
    $dLng = deg2rad($lng2 - $lng1);
    $a = sin($dLat/2) * sin($dLat/2)
       + cos(deg2rad($lat1)) * cos(deg2rad($lat2))
       * sin($dLng/2) * sin($dLng/2);
    return $R * 2 * atan2(sqrt($a), sqrt(1-$a));
}
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>نقشه GPS آزمون | ادمین</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{--primary:#6366f1;--danger:#ef4444;--success:#10b981;--warning:#f59e0b;--bg:#f1f5f9;--border:#e2e8f0;--muted:#64748b;}
body{font-family:'Vazirmatn',sans-serif;background:var(--bg);}
.topbar{background:linear-gradient(135deg,#1e293b,#0f172a);color:white;padding:16px 24px;display:flex;align-items:center;gap:16px;}
.topbar h1{font-size:20px;font-weight:800;}
.topbar a{color:rgba(255,255,255,.7);text-decoration:none;}
.layout{display:grid;grid-template-columns:320px 1fr;height:calc(100vh - 60px);}
.sidebar{background:white;border-left:1px solid var(--border);padding:16px;overflow-y:auto;}
.sidebar h2{font-size:13px;font-weight:700;color:var(--muted);letter-spacing:1px;margin-bottom:12px;}
.exam-item{padding:10px 12px;border-radius:10px;cursor:pointer;margin-bottom:6px;border:2px solid transparent;transition:.2s;}
.exam-item:hover{background:#f8fafc;}
.exam-item.active{background:#ede9fe;border-color:var(--primary);}
.exam-item .title{font-size:13px;font-weight:700;}
.exam-item .meta{font-size:11px;color:var(--muted);margin-top:3px;}
#map{flex:1;height:100%;}
.cluster-alert{background:#fee2e2;border:2px solid #fecaca;border-radius:12px;padding:12px 16px;margin-bottom:12px;}
.cluster-alert strong{color:#991b1b;font-size:13px;display:block;margin-bottom:4px;}
.cluster-alert ul{list-style:none;font-size:12px;color:#dc2626;}
.cluster-alert ul li::before{content:'⚠️ ';}
.info-panel{position:absolute;top:80px;right:20px;z-index:1000;background:white;border-radius:16px;padding:16px;min-width:200px;box-shadow:0 8px 24px rgba(0,0,0,.15);}
.stat-row{display:flex;gap:8px;margin-bottom:12px;}
.stat-box{flex:1;text-align:center;background:#f8fafc;border-radius:10px;padding:10px;}
.stat-box .num{font-size:24px;font-weight:800;}
.stat-box .lbl{font-size:11px;color:var(--muted);}
.student-row{padding:8px 12px;border-radius:10px;border:2px solid var(--border);margin-bottom:6px;cursor:pointer;font-size:12px;}
.student-row:hover{border-color:var(--primary);}
.student-row.flagged{border-color:var(--danger);background:#fff5f5;}
.student-row strong{display:block;font-size:13px;}
.badge{padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;}
</style>
</head>
<body>
<div class="topbar">
    <a href="index.php">← ادمین</a>
    <h1>🗺️ نقشه GPS آزمون</h1>
    <div style="flex:1"></div>
    <?php if ($form_id && $formInfo): ?>
    <span style="font-size:13px;opacity:.7;"><?= h($formInfo['title']) ?></span>
    <?php endif; ?>
</div>
<div class="layout">
    <div class="sidebar">
        <h2>آزمون‌ها</h2>
        <?php foreach ($exams as $ex): ?>
        <div class="exam-item <?= $form_id==$ex['id']?'active':'' ?>" onclick="location.href='gps_monitor.php?form_id=<?= $ex['id'] ?>'">
            <div class="title"><?= h($ex['title']) ?></div>
            <div class="meta">
                📍 <?= $ex['gps_count'] ?> موقعیت
                <?php if ($ex['flagged_count'] > 0): ?>
                | <span style="color:var(--danger);">⚠️ <?= $ex['flagged_count'] ?> مشکوک</span>
                <?php endif; ?>
            </div>
        </div>
        <?php endforeach; ?>

        <?php if ($form_id && !empty($clusters)): ?>
        <h2 style="margin-top:16px;">خوشه‌های مشکوک (<?= count($clusters) ?>)</h2>
        <?php foreach ($clusters as $cl): ?>
        <div class="cluster-alert">
            <strong>🚨 خوشه #<?= $cl['id'] ?> — <?= count($cl['members']) ?> دانش‌آموز</strong>
            <ul>
                <?php foreach ($cl['members'] as $mi): ?>
                <?php $m = $gpsData[$mi]; ?>
                <li><?= h($m['student_name'] ?: $m['user_ip']) ?></li>
                <?php endforeach; ?>
            </ul>
        </div>
        <?php endforeach; ?>
        <?php endif; ?>

        <?php if ($form_id && !empty($gpsData)): ?>
        <h2 style="margin-top:16px;">شرکت‌کنندگان (<?= count($gpsData) ?>)</h2>
        <?php foreach ($gpsData as $g): ?>
        <div class="student-row <?= ($g['flagged'] || isset($g['cluster_id'])) ? 'flagged' : '' ?>"
             onclick="flyToStudent(<?= $g['latitude'] ?>, <?= $g['longitude'] ?>, '<?= h(addslashes($g['student_name'] ?: $g['user_ip'])) ?>')">
            <strong><?= h($g['student_name'] ?: 'ناشناس') ?></strong>
            <span style="font-family:monospace;color:var(--muted);font-size:10px;"><?= h($g['user_ip']) ?></span>
            <div style="margin-top:4px;display:flex;gap:4px;flex-wrap:wrap;">
                <?php if ($g['out_of_bounds']): ?>
                <span class="badge" style="background:#fee2e2;color:#991b1b;">خارج از محدوده</span>
                <?php endif; ?>
                <?php if (isset($g['cluster_id'])): ?>
                <span class="badge" style="background:#fef3c7;color:#92400e;">خوشه #<?= $g['cluster_id'] ?></span>
                <?php endif; ?>
                <?php if ($g['accuracy']): ?>
                <span class="badge" style="background:#f1f5f9;color:var(--muted);">±<?= round($g['accuracy']) ?>m</span>
                <?php endif; ?>
            </div>
        </div>
        <?php endforeach; ?>
        <?php endif; ?>
    </div>

    <div id="map"></div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map = L.map('map').setView([35.6892, 51.3890], 10);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

const GPS_DATA = <?= json_encode($gpsData, JSON_UNESCAPED_UNICODE) ?>;
const CLUSTERS = <?= json_encode($clusters, JSON_UNESCAPED_UNICODE) ?>;
const FORM_INFO = <?= json_encode($formInfo ? ['gps_lat'=>$formInfo['gps_lat'],'gps_lng'=>$formInfo['gps_lng'],'gps_radius'=>$formInfo['gps_radius']] : null) ?>;

const markers = [];

// Add exam center marker
if (FORM_INFO && FORM_INFO.gps_lat && FORM_INFO.gps_lng) {
    const centerIcon = L.divIcon({
        html: '<div style="background:#6366f1;color:white;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 8px rgba(0,0,0,.3);">🏫</div>',
        className: '',
        iconSize: [32,32],
        iconAnchor: [16,16]
    });
    L.marker([FORM_INFO.gps_lat, FORM_INFO.gps_lng], {icon: centerIcon})
     .addTo(map)
     .bindPopup('<strong>مرکز آزمون</strong><br>شعاع مجاز: ' + (FORM_INFO.gps_radius||500) + 'm');
    if (FORM_INFO.gps_radius) {
        L.circle([FORM_INFO.gps_lat, FORM_INFO.gps_lng], {
            radius: FORM_INFO.gps_radius,
            color: '#6366f1', fillColor: '#6366f1', fillOpacity: 0.05, weight: 2
        }).addTo(map);
    }
}

// Add student markers
GPS_DATA.forEach((g, i) => {
    if (!g.latitude || !g.longitude) return;
    const isFlagged = g.flagged || g.cluster_id;
    const color     = isFlagged ? '#ef4444' : (g.out_of_bounds ? '#f59e0b' : '#10b981');
    const icon = L.divIcon({
        html: `<div style="background:${color};color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;box-shadow:0 2px 8px rgba(0,0,0,.3);border:2px solid white;">${i+1}</div>`,
        className: '',
        iconSize: [28,28],
        iconAnchor: [14,14]
    });

    const warnings = [];
    if (g.out_of_bounds) warnings.push('⚠️ خارج از محدوده مجاز');
    if (g.cluster_id) warnings.push(`🚨 مشکوک به تقلب گروهی (خوشه #${g.cluster_id})`);
    if (g.flagged) warnings.push('🚩 علامت‌گذاری شده');

    const popup = `
        <div style="font-family:Vazirmatn,sans-serif;direction:rtl;min-width:180px;">
            <strong style="font-size:14px;">${g.student_name || 'ناشناس'}</strong><br>
            <span style="font-size:11px;color:#64748b;font-family:monospace;">${g.user_ip}</span>
            ${warnings.length ? '<br><br>' + warnings.join('<br>') : ''}
            <br><span style="font-size:11px;color:#94a3b8;">${g.created_at}</span>
        </div>
    `;

    const m = L.marker([g.latitude, g.longitude], {icon}).addTo(map).bindPopup(popup);
    markers.push({marker: m, lat: g.latitude, lng: g.longitude, name: g.student_name});
});

// Draw cluster circles
CLUSTERS.forEach(cl => {
    const members = cl.members.map(mi => GPS_DATA[mi]).filter(Boolean);
    if (members.length < 2) return;
    const avgLat = members.reduce((s,m) => s + parseFloat(m.latitude), 0) / members.length;
    const avgLng = members.reduce((s,m) => s + parseFloat(m.longitude), 0) / members.length;
    L.circle([avgLat, avgLng], {
        radius: 60,
        color: '#ef4444',
        fillColor: '#ef4444',
        fillOpacity: 0.1,
        weight: 2,
        dashArray: '6'
    }).addTo(map).bindPopup(`🚨 خوشه مشکوک: ${members.length} دانش‌آموز در کمتر از ۵۰ متر`);
});

// Fit map to markers
if (GPS_DATA.length > 0) {
    const validPoints = GPS_DATA.filter(g => g.latitude && g.longitude).map(g => [g.latitude, g.longitude]);
    if (validPoints.length > 0) map.fitBounds(validPoints, {padding: [50, 50]});
}

function flyToStudent(lat, lng, name) {
    map.flyTo([lat, lng], 16, {duration: 1});
    markers.forEach(m => {
        if (Math.abs(m.lat - lat) < 0.0001 && Math.abs(m.lng - lng) < 0.0001) {
            setTimeout(() => m.marker.openPopup(), 1000);
        }
    });
}
</script>
</body>
</html>
