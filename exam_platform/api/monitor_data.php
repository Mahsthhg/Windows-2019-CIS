<?php
/**
 * api/monitor_data.php - داده‌های زنده مانیتورینگ آزمون (برای ادمین)
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

requireAdminAuth();
header('Content-Type: application/json; charset=utf-8');

$form_id = validateInt($_GET['form_id'] ?? 0, 1);
if (!$form_id) {
    echo json_encode(['ok' => false, 'error' => 'آزمون مشخص نشده']);
    exit();
}

// ── شرکت‌کنندگان فعال (شروع کرده اما ثبت نکرده) ─────────────────────
$stmt = $pdo->prepare("
    SELECT
        a.id,
        a.user_ip,
        a.user_name,
        a.user_national,
        a.cheat_count,
        a.status,
        a.started_at,
        TIMESTAMPDIFF(SECOND, a.started_at, NOW()) as elapsed_seconds,
        (SELECT COUNT(*) FROM exam_snapshots s WHERE s.form_id=a.form_id AND s.user_ip=a.user_ip) as snapshot_count,
        (SELECT MAX(s.created_at) FROM exam_snapshots s WHERE s.form_id=a.form_id AND s.user_ip=a.user_ip) as last_snapshot,
        (SELECT g.latitude FROM gps_locations g WHERE g.form_id=a.form_id AND g.user_ip=a.user_ip ORDER BY g.created_at DESC LIMIT 1) as gps_lat,
        (SELECT g.longitude FROM gps_locations g WHERE g.form_id=a.form_id AND g.user_ip=a.user_ip ORDER BY g.created_at DESC LIMIT 1) as gps_lng,
        (SELECT g.flagged FROM gps_locations g WHERE g.form_id=a.form_id AND g.user_ip=a.user_ip ORDER BY g.created_at DESC LIMIT 1) as gps_flagged
    FROM answers a
    WHERE a.form_id = ?
    ORDER BY a.started_at DESC
");
$stmt->execute([$form_id]);
$participants = $stmt->fetchAll();

// ── آمار کلی ──────────────────────────────────────────────────────────
$stmt = $pdo->prepare("
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN status='started' THEN 1 ELSE 0 END) as active,
        SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
        SUM(cheat_count) as total_cheats
    FROM answers WHERE form_id=?
");
$stmt->execute([$form_id]);
$stats = $stmt->fetch();

// ── تقلب‌های اخیر ─────────────────────────────────────────────────────
$stmt = $pdo->prepare("
    SELECT type, details, user_ip, created_at
    FROM cheat_logs
    WHERE form_id = ?
    ORDER BY created_at DESC
    LIMIT 20
");
$stmt->execute([$form_id]);
$recentCheats = $stmt->fetchAll();

// ── خوشه‌های GPS ──────────────────────────────────────────────────────
$stmt = $pdo->prepare("
    SELECT user_ip, student_name, latitude, longitude, flagged, created_at
    FROM gps_locations
    WHERE form_id = ?
      AND created_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)
    GROUP BY user_ip
    ORDER BY created_at DESC
");
$stmt->execute([$form_id]);
$gpsData = $stmt->fetchAll();

// ── درخواست‌های وب‌کم در انتظار ─────────────────────────────────────
$stmt = $pdo->prepare("
    SELECT user_ip, requested_at
    FROM camera_requests
    WHERE form_id=? AND status='pending'
");
$stmt->execute([$form_id]);
$pendingCameraReqs = $stmt->fetchAll();

echo json_encode([
    'ok'           => true,
    'stats'        => $stats,
    'participants' => $participants,
    'recent_cheats'=> $recentCheats,
    'gps_data'     => $gpsData,
    'pending_cams' => $pendingCameraReqs,
    'timestamp'    => date('H:i:s'),
], JSON_UNESCAPED_UNICODE);
