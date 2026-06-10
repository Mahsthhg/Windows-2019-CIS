<?php
/**
 * api/ban_ip.php - مسدود کردن IP از مانیتور
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

header('Content-Type: application/json; charset=utf-8');

requireAdminAuth();

$input  = json_decode(file_get_contents('php://input'), true) ?: [];
$ip     = filter_var(trim($input['ip'] ?? ''), FILTER_VALIDATE_IP);
$reason = sanitizeString($input['reason'] ?? 'مسدود از پنل مانیتور', 500);

if (!$ip) {
    echo json_encode(['ok' => false, 'error' => 'IP نامعتبر']);
    exit();
}

$pdo->prepare("INSERT INTO ip_blacklist (ip_address, reason, blocked_by) VALUES (?,?,?) ON DUPLICATE KEY UPDATE reason=VALUES(reason), is_active=1")
    ->execute([$ip, $reason, $_SESSION['admin_id']]);

$pdo->prepare("INSERT INTO admin_audit_log (admin_id, action, details, ip_address) VALUES (?,?,?,?)")
    ->execute([$_SESSION['admin_id'], 'ban_ip', 'مسدود: '.$ip.' | دلیل: '.$reason, getClientIP()]);

echo json_encode(['ok' => true, 'ip' => $ip]);
