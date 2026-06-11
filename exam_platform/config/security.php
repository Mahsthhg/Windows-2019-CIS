<?php
/**
 * config/security.php - CSRF + Rate Limiting + Input Validation
 */

if (!defined('DB_HOST')) {
    require_once __DIR__ . '/database.php';
}

// ============================================================
//  CSRF Protection
// ============================================================

function generateCsrfToken(): string {
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function verifyCsrfToken(string $token): bool {
    return isset($_SESSION['csrf_token']) && hash_equals($_SESSION['csrf_token'], $token);
}

function csrfField(): string {
    return '<input type="hidden" name="csrf_token" value="' . h(generateCsrfToken()) . '">';
}

function requireCsrf(): void {
    $token = $_POST['csrf_token'] ?? $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '';
    if (!verifyCsrfToken($token)) {
        http_response_code(403);
        die('<div style="color:red;padding:20px;font-family:sans-serif;">❌ خطای امنیتی: درخواست نامعتبر (CSRF)</div>');
    }
}

// ============================================================
//  Rate Limiting (DB-based)
// ============================================================

function checkRateLimit(string $action, string $identifier, int $maxAttempts = 5, int $windowSeconds = 300): bool {
    global $pdo;
    $key = $action . ':' . $identifier;
    $windowStart = date('Y-m-d H:i:s', time() - $windowSeconds);

    $stmt = $pdo->prepare(
        "SELECT COUNT(*) FROM rate_limits WHERE action_key = ? AND created_at > ?"
    );
    $stmt->execute([$key, $windowStart]);
    return (int)$stmt->fetchColumn() < $maxAttempts;
}

function recordRateLimitAttempt(string $action, string $identifier): void {
    global $pdo;
    $key = $action . ':' . $identifier;
    $pdo->prepare("INSERT INTO rate_limits (action_key, created_at) VALUES (?, NOW())")
        ->execute([$key]);
    // cleanup old entries
    $pdo->prepare("DELETE FROM rate_limits WHERE created_at < DATE_SUB(NOW(), INTERVAL 1 HOUR)")
        ->execute();
}

function getRemainingAttempts(string $action, string $identifier, int $maxAttempts = 5, int $windowSeconds = 300): int {
    global $pdo;
    $key = $action . ':' . $identifier;
    $windowStart = date('Y-m-d H:i:s', time() - $windowSeconds);
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM rate_limits WHERE action_key = ? AND created_at > ?");
    $stmt->execute([$key, $windowStart]);
    return max(0, $maxAttempts - (int)$stmt->fetchColumn());
}

// ============================================================
//  Input Validation
// ============================================================

function sanitizeString(string $input, int $maxLen = 255): string {
    return mb_substr(trim(strip_tags($input)), 0, $maxLen);
}

function validateInt(mixed $value, int $min = 0, int $max = PHP_INT_MAX): ?int {
    $v = filter_var($value, FILTER_VALIDATE_INT);
    if ($v === false) return null;
    return ($v >= $min && $v <= $max) ? $v : null;
}

function validateEmail(string $email): bool {
    return (bool)filter_var($email, FILTER_VALIDATE_EMAIL);
}

function validateUsername(string $username): bool {
    return (bool)preg_match('/^[a-zA-Z0-9_]{3,50}$/', $username);
}

// ============================================================
//  Auth Helpers
// ============================================================

function requireTeacherAuth(): array {
    if (!isset($_SESSION['teacher_id']) || !isset($_SESSION['teacher_role'])) {
        redirect(dirname($_SERVER['PHP_SELF']) . '/../login.php');
    }
    checkSessionTimeout();
    return [
        'id'      => (int)$_SESSION['teacher_id'],
        'name'    => $_SESSION['teacher_name'] ?? '',
        'subject' => $_SESSION['teacher_subject'] ?? '',
        'role'    => $_SESSION['teacher_role'] ?? 'teacher',
    ];
}

function requireAdminAuth(): void {
    if (!isset($_SESSION['admin_id'])) {
        redirect('../admin/login.php');
    }
    checkSessionTimeout();
}

function isAdmin(): bool {
    return isset($_SESSION['admin_id']);
}

function isTeacher(): bool {
    return isset($_SESSION['teacher_id']);
}

/** آیا این IP در لیست سیاه فعال است؟ */
function isIpBlacklisted(PDO $pdo, string $ip): bool {
    $stmt = $pdo->prepare("SELECT 1 FROM ip_blacklist WHERE ip_address=? AND is_active=1 AND (expires_at IS NULL OR expires_at > NOW()) LIMIT 1");
    $stmt->execute([$ip]);
    return (bool)$stmt->fetchColumn();
}
