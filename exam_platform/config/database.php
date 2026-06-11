<?php
/**
 * config/database.php - اتصال امن به دیتابیس + توابع پایه
 */

define('DB_HOST', getenv('DB_HOST') ?: 'localhost');
define('DB_NAME', getenv('DB_NAME') ?: 'exam_platform');
define('DB_USER', getenv('DB_USER') ?: 'root');
define('DB_PASS', getenv('DB_PASS') ?: '');
define('APP_VERSION', '2.0.0');
define('APP_NAME', 'سامانه آزمون‌آنلاین');
define('SESSION_TIMEOUT', 7200); // 2 hours

// شروع امن Session
if (session_status() === PHP_SESSION_NONE) {
    ini_set('session.cookie_httponly', 1);
    ini_set('session.cookie_samesite', 'Strict');
    ini_set('session.use_strict_mode', 1);
    session_start();
}

// اتصال PDO
try {
    $pdo = new PDO(
        "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=utf8mb4",
        DB_USER,
        DB_PASS,
        [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]
    );
    // سازگاری با MySQL 5.7+/8: حذف ONLY_FULL_GROUP_BY تا کوئری‌های GROUP BY قدیمی ارور ندهند
    $pdo->exec("SET SESSION sql_mode = (SELECT REPLACE(@@sql_mode, 'ONLY_FULL_GROUP_BY', ''))");
} catch (PDOException $e) {
    error_log('DB connection failed: ' . $e->getMessage());
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    die(json_encode(['error' => 'خطای اتصال به دیتابیس'], JSON_UNESCAPED_UNICODE));
}

// ============================================================
//  توابع امنیتی پایه
// ============================================================

/** HTML-escape safe output */
function h(string $s): string {
    return htmlspecialchars($s, ENT_QUOTES | ENT_HTML5, 'UTF-8');
}

/** Get real client IP */
function getClientIP(): string {
    foreach (['HTTP_CF_CONNECTING_IP','HTTP_X_FORWARDED_FOR','REMOTE_ADDR'] as $key) {
        if (!empty($_SERVER[$key])) {
            $ip = trim(explode(',', $_SERVER[$key])[0]);
            if (filter_var($ip, FILTER_VALIDATE_IP)) return $ip;
        }
    }
    return '0.0.0.0';
}

/** Validate national code (Iran) */
function validateNationalCode(string $code): bool {
    $code = trim($code);
    if (!preg_match('/^\d{10}$/', $code)) return false;
    if (preg_match('/^(\d)\1{9}$/', $code)) return false;
    $sum = 0;
    for ($i = 0; $i < 9; $i++) $sum += (int)$code[$i] * (10 - $i);
    $rem = $sum % 11;
    $check = (int)$code[9];
    return ($rem < 2) ? $check === $rem : $check === (11 - $rem);
}

/** Regenerate session ID safely */
function regenerateSession(): void {
    if (session_status() === PHP_SESSION_ACTIVE) {
        session_regenerate_id(true);
    }
}

/** Set secure HTTP headers */
function setSecureHeaders(): void {
    if (headers_sent()) return;
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: SAMEORIGIN');
    header('X-XSS-Protection: 1; mode=block');
    header('Referrer-Policy: strict-origin-when-cross-origin');
    header('Permissions-Policy: camera=(self), microphone=(), geolocation=(self)');
    // Content Security Policy — منابع مجاز محدود (فقط خود سایت + CDNهای لازم)
    header(
        "Content-Security-Policy: " .
        "default-src 'self'; " .
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; " .
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; " .
        "font-src 'self' https://fonts.gstatic.com data:; " .
        "img-src 'self' data: blob: https://*.tile.openstreetmap.org https://unpkg.com; " .
        "connect-src 'self' https://cdn.jsdelivr.net; " .
        "media-src 'self' blob:; " .
        "base-uri 'self'; form-action 'self'; frame-ancestors 'self'; object-src 'none'"
    );
}

/** JSON response helper */
function jsonResponse(array $data, int $code = 200): void {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit();
}

/** Redirect helper */
function redirect(string $url): void {
    header("Location: $url");
    exit();
}

/** Check session timeout */
function checkSessionTimeout(): void {
    if (isset($_SESSION['last_activity'])) {
        if (time() - $_SESSION['last_activity'] > SESSION_TIMEOUT) {
            session_unset();
            session_destroy();
            redirect('../login.php?expired=1');
        }
    }
    $_SESSION['last_activity'] = time();
}

// Set secure headers on every request
setSecureHeaders();
