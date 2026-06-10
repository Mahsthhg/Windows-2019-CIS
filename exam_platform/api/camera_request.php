<?php
/**
 * api/camera_request.php - بررسی و ارسال درخواست وب‌کم از ادمین به دانش‌آموز
 * GET: بررسی درخواست (دانش‌آموز polls)
 * POST: ارسال درخواست جدید (ادمین)
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

header('Content-Type: application/json; charset=utf-8');

$method = $_SERVER['REQUEST_METHOD'];

// ── ادمین: ارسال درخواست ─────────────────────────────────────────────
if ($method === 'POST') {
    requireAdminAuth();
    requireCsrf();

    $input    = json_decode(file_get_contents('php://input'), true) ?: [];
    $form_id  = validateInt($input['form_id'] ?? $_POST['form_id'] ?? 0, 1);
    $target_ip= sanitizeString($input['target_ip'] ?? $_POST['target_ip'] ?? '', 45);

    if (!$form_id || empty($target_ip)) {
        echo json_encode(['ok' => false, 'error' => 'پارامتر ناقص']);
        exit();
    }

    // Cancel old pending requests for same IP+form
    $pdo->prepare("UPDATE camera_requests SET status='cancelled' WHERE form_id=? AND user_ip=? AND status='pending'")
        ->execute([$form_id, $target_ip]);

    // Insert new request
    $pdo->prepare("INSERT INTO camera_requests (form_id, user_ip, requested_by) VALUES (?,?,?)")
        ->execute([$form_id, $target_ip, $_SESSION['admin_id']]);

    // Audit log
    $pdo->prepare("INSERT INTO admin_audit_log (admin_id, action, target_type, details, ip_address) VALUES (?,?,?,?,?)")
        ->execute([$_SESSION['admin_id'], 'camera_request', 'exam', 'درخواست تصویر از IP: ' . $target_ip . ' در آزمون #' . $form_id, getClientIP()]);

    echo json_encode(['ok' => true, 'msg' => 'درخواست وب‌کم ارسال شد']);
    exit();
}

// ── دانش‌آموز: بررسی درخواست ─────────────────────────────────────────
if ($method === 'GET') {
    $form_id = validateInt($_GET['form_id'] ?? 0, 1);
    $ip      = getClientIP();

    if (!$form_id) {
        echo json_encode(['requested' => false]);
        exit();
    }

    $stmt = $pdo->prepare("SELECT id FROM camera_requests WHERE form_id=? AND user_ip=? AND status='pending' AND requested_at > DATE_SUB(NOW(), INTERVAL 5 MINUTE) LIMIT 1");
    $stmt->execute([$form_id, $ip]);
    $req = $stmt->fetch();

    echo json_encode([
        'requested'  => (bool)$req,
        'request_id' => $req ? $req['id'] : null,
    ]);
    exit();
}

http_response_code(405);
echo json_encode(['ok' => false]);
