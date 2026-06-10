<?php
/**
 * api/anti_cheat.php - ثبت رویدادهای تقلب
 */
require_once __DIR__ . '/../config/database.php';

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405); echo '{}'; exit();
}

$body = json_decode(file_get_contents('php://input'), true) ?? [];
$fid  = validateInt($body['form_id'] ?? 0, 1);
if (!$fid) { echo '{}'; exit(); }

$VALID_TYPES = ['tab_switch','window_blur','fullscreen_exit','copy_paste','right_click','devtools','screenshot_key','context_menu','keyboard_shortcut','mouse_out','multiple_submit','time_anomaly','gps_collusion','no_face','multiple_faces','camera_denied'];
$type    = in_array($body['type'] ?? '', $VALID_TYPES) ? $body['type'] : 'tab_switch';
$details = sanitizeString($body['details'] ?? '', 200);
$ip      = getClientIP();

// Rate limit cheat logs (max 50 per form per IP per hour)
$stmt = $pdo->prepare("SELECT COUNT(*) FROM cheat_logs WHERE form_id=? AND user_ip=? AND created_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)");
$stmt->execute([$fid, $ip]);
if ((int)$stmt->fetchColumn() < 50) {
    $pdo->prepare("INSERT INTO cheat_logs (form_id, user_ip, type, details) VALUES (?,?,?,?)")
        ->execute([$fid, $ip, $type, $details]);
}

echo json_encode(['ok' => true]);
