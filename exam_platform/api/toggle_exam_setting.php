<?php
/**
 * api/toggle_exam_setting.php - تغییر تنظیمات آزمون در لحظه (ادمین)
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

header('Content-Type: application/json; charset=utf-8');
requireAdminAuth();

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405); echo json_encode(['ok' => false]); exit();
}

$input   = json_decode(file_get_contents('php://input'), true) ?: [];
$form_id = validateInt($input['form_id'] ?? 0, 1);
$setting = sanitizeString($input['setting'] ?? '', 50);
$value   = isset($input['value']) ? (int)(bool)$input['value'] : null;

$allowed = ['require_camera', 'gps_required', 'require_fullscreen', 'is_active'];
if (!$form_id || !in_array($setting, $allowed) || $value === null) {
    echo json_encode(['ok' => false, 'error' => 'پارامتر نامعتبر']);
    exit();
}

// Verify form exists
$stmt = $pdo->prepare("SELECT id, title FROM forms WHERE id=?");
$stmt->execute([$form_id]);
$form = $stmt->fetch();
if (!$form) {
    echo json_encode(['ok' => false, 'error' => 'آزمون یافت نشد']);
    exit();
}

$pdo->prepare("UPDATE forms SET `$setting`=? WHERE id=?")
    ->execute([$value, $form_id]);

// Audit log
$labels = ['require_camera'=>'وب‌کم','gps_required'=>'GPS','require_fullscreen'=>'تمام‌صفحه','is_active'=>'وضعیت آزمون'];
$pdo->prepare("INSERT INTO admin_audit_log (admin_id, action, target_type, target_id, details, ip_address) VALUES (?,?,?,?,?,?)")
    ->execute([
        $_SESSION['admin_id'],
        'toggle_exam_setting',
        'form',
        $form_id,
        ($labels[$setting] ?? $setting) . ' آزمون «' . $form['title'] . '» → ' . ($value ? 'فعال' : 'غیرفعال'),
        getClientIP()
    ]);

echo json_encode(['ok' => true, 'setting' => $setting, 'value' => $value]);
