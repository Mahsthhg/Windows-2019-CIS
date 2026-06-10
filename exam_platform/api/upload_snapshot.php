<?php
/**
 * api/upload_snapshot.php - دریافت و ذخیره اسنپشات وب‌کم
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'Method not allowed']);
    exit();
}

$input    = json_decode(file_get_contents('php://input'), true) ?: [];
$form_id  = validateInt($input['form_id'] ?? 0, 1);
$imageData= $input['image'] ?? '';
$trigger  = $input['trigger'] ?? 'auto';
$ip       = getClientIP();
$name     = sanitizeString($input['student_name'] ?? '', 200);
$answerId = validateInt($input['answer_id'] ?? 0, 0) ?: null;

if (!$form_id || empty($imageData)) {
    echo json_encode(['ok' => false, 'error' => 'داده ناقص است']);
    exit();
}

// Verify form exists and is active
$stmt = $pdo->prepare("SELECT id, require_camera FROM forms WHERE id=? AND is_active=1");
$stmt->execute([$form_id]);
$form = $stmt->fetch();
if (!$form) {
    echo json_encode(['ok' => false, 'error' => 'آزمون یافت نشد']);
    exit();
}

// Rate limit: max 30 snapshots per IP per form per hour
$stmt = $pdo->prepare("SELECT COUNT(*) FROM exam_snapshots WHERE form_id=? AND user_ip=? AND created_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)");
$stmt->execute([$form_id, $ip]);
if ((int)$stmt->fetchColumn() >= 30) {
    echo json_encode(['ok' => false, 'error' => 'محدودیت تعداد تصویر']);
    exit();
}

// Parse base64 image
if (!preg_match('/^data:image\/(jpeg|jpg|png|webp);base64,/', $imageData, $matches)) {
    echo json_encode(['ok' => false, 'error' => 'فرمت تصویر نامعتبر است']);
    exit();
}
$ext      = $matches[1] === 'jpeg' ? 'jpg' : $matches[1];
$b64      = preg_replace('/^data:image\/[a-z]+;base64,/', '', $imageData);
$decoded  = base64_decode($b64);
if (!$decoded || strlen($decoded) < 1000) {
    echo json_encode(['ok' => false, 'error' => 'تصویر خالی یا نامعتبر است']);
    exit();
}
if (strlen($decoded) > 2 * 1024 * 1024) {
    echo json_encode(['ok' => false, 'error' => 'حجم تصویر بیش از حد مجاز است']);
    exit();
}

// Save to disk
$dir = __DIR__ . '/../uploads/snapshots/' . $form_id . '/';
if (!is_dir($dir)) {
    mkdir($dir, 0755, true);
}
// Write index.html to prevent directory listing
if (!file_exists($dir . 'index.html')) {
    file_put_contents($dir . 'index.html', '');
}
$filename = 'snap_' . preg_replace('/[^a-f0-9]/', '', bin2hex(random_bytes(8))) . '_' . time() . '.' . $ext;
$filepath = $dir . $filename;

if (file_put_contents($filepath, $decoded) === false) {
    echo json_encode(['ok' => false, 'error' => 'خطا در ذخیره تصویر']);
    exit();
}

// Basic face detection heuristic: check image size (not blank)
$faceDetected = (strlen($decoded) > 5000) ? 1 : 0;

// Valid trigger types
$validTriggers = ['auto', 'admin_request', 'cheat_detect', 'exam_start', 'exam_end'];
$trigger = in_array($trigger, $validTriggers) ? $trigger : 'auto';

// Save to DB
$relPath = 'uploads/snapshots/' . $form_id . '/' . $filename;
$pdo->prepare("INSERT INTO exam_snapshots (form_id, answer_id, user_ip, student_name, image_path, face_detected, trigger_type) VALUES (?,?,?,?,?,?,?)")
    ->execute([$form_id, $answerId, $ip, $name, $relPath, $faceDetected, $trigger]);

$snapshotId = (int)$pdo->lastInsertId();

// Mark camera_request as fulfilled if this was triggered by admin
if ($trigger === 'admin_request') {
    $pdo->prepare("UPDATE camera_requests SET status='fulfilled', fulfilled_at=NOW() WHERE form_id=? AND user_ip=? AND status='pending'")
        ->execute([$form_id, $ip]);
}

echo json_encode([
    'ok'           => true,
    'snapshot_id'  => $snapshotId,
    'face_detected'=> $faceDetected === 1,
]);
