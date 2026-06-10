<?php
/**
 * api/save_location.php - ذخیره موقعیت GPS و بررسی تقلب گروهی
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false]);
    exit();
}

$input    = json_decode(file_get_contents('php://input'), true) ?: [];
$form_id  = validateInt($input['form_id'] ?? 0, 1);
$lat      = isset($input['lat']) ? (float)$input['lat'] : null;
$lng      = isset($input['lng']) ? (float)$input['lng'] : null;
$accuracy = isset($input['accuracy']) ? (float)$input['accuracy'] : null;
$ip       = getClientIP();
$name     = sanitizeString($input['student_name'] ?? '', 200);
$answerId = validateInt($input['answer_id'] ?? 0, 0) ?: null;

if (!$form_id || $lat === null || $lng === null) {
    echo json_encode(['ok' => false, 'error' => 'داده ناقص']);
    exit();
}
if ($lat < -90 || $lat > 90 || $lng < -180 || $lng > 180) {
    echo json_encode(['ok' => false, 'error' => 'مختصات نامعتبر']);
    exit();
}

// Verify form
$stmt = $pdo->prepare("SELECT id, gps_required, gps_lat, gps_lng, gps_radius FROM forms WHERE id=?");
$stmt->execute([$form_id]);
$form = $stmt->fetch();
if (!$form) {
    echo json_encode(['ok' => false, 'error' => 'آزمون یافت نشد']);
    exit();
}

// Check if already saved recently (don't spam)
$stmt = $pdo->prepare("SELECT COUNT(*) FROM gps_locations WHERE form_id=? AND user_ip=? AND created_at > DATE_SUB(NOW(), INTERVAL 5 MINUTE)");
$stmt->execute([$form_id, $ip]);
if ((int)$stmt->fetchColumn() > 0) {
    echo json_encode(['ok' => true, 'updated' => false, 'msg' => 'موقعیت اخیراً ذخیره شده']);
    exit();
}

// Check proximity to exam center (if configured)
$outOfBounds = false;
if ($form['gps_required'] && $form['gps_lat'] && $form['gps_lng']) {
    $dist = haversineDistance($lat, $lng, (float)$form['gps_lat'], (float)$form['gps_lng']);
    if ($dist > (int)$form['gps_radius']) {
        $outOfBounds = true;
    }
}

// Save location
$pdo->prepare("INSERT INTO gps_locations (form_id, answer_id, user_ip, student_name, latitude, longitude, accuracy, out_of_bounds) VALUES (?,?,?,?,?,?,?,?)")
    ->execute([$form_id, $answerId, $ip, $name, $lat, $lng, $accuracy, $outOfBounds ? 1 : 0]);

// Check proximity to other students (GPS collusion detection)
$threshold = 50; // meters — if within 50m of another student, flag
$stmt = $pdo->prepare("
    SELECT user_ip, student_name, latitude, longitude
    FROM gps_locations
    WHERE form_id = ?
      AND user_ip != ?
      AND created_at > DATE_SUB(NOW(), INTERVAL 30 MINUTE)
    GROUP BY user_ip
");
$stmt->execute([$form_id, $ip]);
$others = $stmt->fetchAll();

$collusionSuspects = [];
foreach ($others as $other) {
    $dist = haversineDistance($lat, $lng, (float)$other['latitude'], (float)$other['longitude']);
    if ($dist < $threshold) {
        $collusionSuspects[] = [
            'ip'       => $other['user_ip'],
            'name'     => $other['student_name'],
            'distance' => round($dist),
        ];
    }
}

// Auto-flag collusion in cheat_logs
if (!empty($collusionSuspects)) {
    $names = implode(', ', array_column($collusionSuspects, 'name'));
    $pdo->prepare("INSERT INTO cheat_logs (form_id, user_ip, type, details) VALUES (?,?,'gps_collusion',?)")
        ->execute([$form_id, $ip, 'نزدیکی GPS با: ' . $names]);

    // Flag the GPS records for both parties
    $pdo->prepare("UPDATE gps_locations SET flagged=1 WHERE form_id=? AND user_ip=? AND created_at > DATE_SUB(NOW(), INTERVAL 1 MINUTE)")
        ->execute([$form_id, $ip]);
    foreach ($collusionSuspects as $s) {
        $pdo->prepare("UPDATE gps_locations SET flagged=1 WHERE form_id=? AND user_ip=? AND created_at > DATE_SUB(NOW(), INTERVAL 30 MINUTE)")
            ->execute([$form_id, $s['ip']]);
    }
}

echo json_encode([
    'ok'             => true,
    'out_of_bounds'  => $outOfBounds,
    'collusion'      => !empty($collusionSuspects),
    'suspects'       => count($collusionSuspects),
]);

// ── Haversine formula ─────────────────────────────────────────────────
function haversineDistance(float $lat1, float $lng1, float $lat2, float $lng2): float {
    $R = 6371000; // Earth radius in meters
    $dLat = deg2rad($lat2 - $lat1);
    $dLng = deg2rad($lng2 - $lng1);
    $a = sin($dLat/2) * sin($dLat/2)
       + cos(deg2rad($lat1)) * cos(deg2rad($lat2))
       * sin($dLng/2) * sin($dLng/2);
    $c = 2 * atan2(sqrt($a), sqrt(1-$a));
    return $R * $c;
}
