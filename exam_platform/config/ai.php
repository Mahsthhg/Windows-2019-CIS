<?php
/**
 * config/ai.php — دستیار هوش مصنوعی پشتیبانی
 *
 * اتصال به سرویس هوش مصنوعی با cURL (بدون نیاز به Composer/SDK).
 * پیش‌فرض روی Claude (Anthropic Messages API) تنظیم شده، ولی آدرس/کلید/مدل
 * از طریق متغیرهای محیطی قابل تغییر است تا با هر درگاه سازگار باشد.
 *
 * تنظیم (در XAMPP می‌توانید این مقادیر را اینجا مستقیم بگذارید):
 *   AI_API_KEY   کلید سرویس
 *   AI_BASE_URL  آدرس endpoint (پیش‌فرض: Anthropic)
 *   AI_MODEL     نام مدل (پیش‌فرض: claude-opus-4-8)
 */

if (!defined('DB_HOST')) {
    require_once __DIR__ . '/database.php';
}

define('AI_API_KEY',  getenv('AI_API_KEY')  ?: (getenv('ANTHROPIC_API_KEY') ?: ''));
define('AI_BASE_URL', getenv('AI_BASE_URL') ?: 'https://api.anthropic.com/v1/messages');
define('AI_MODEL',    getenv('AI_MODEL')    ?: 'claude-opus-4-8');
define('AI_ENABLED',  AI_API_KEY !== '');

// اجازهٔ نوشتن فایل توسط دستیار ادمین — برای امنیت پیش‌فرض خاموش است.
// فقط در محیط توسعه و با آگاهی کامل روشن کنید (getenv('AI_ALLOW_FILE_WRITE')=1).
define('AI_ALLOW_FILE_WRITE', getenv('AI_ALLOW_FILE_WRITE') === '1');

/**
 * فراخوانی سرویس هوش مصنوعی (Anthropic Messages API).
 * $messages: آرایه‌ای از ['role'=>'user'|'assistant','content'=>'...']
 */
function aiChat(array $messages, string $system, int $maxTokens = 1500): array {
    if (!AI_ENABLED) {
        return ['ok' => false, 'error' => 'سرویس هوش مصنوعی پیکربندی نشده است. کلید AI_API_KEY را در config/ai.php تنظیم کنید.'];
    }
    $payload = [
        'model'      => AI_MODEL,
        'max_tokens' => $maxTokens,
        'system'     => $system,
        'messages'   => array_values($messages),
    ];

    $ch = curl_init(AI_BASE_URL);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 90,
        CURLOPT_HTTPHEADER     => [
            'Content-Type: application/json',
            'x-api-key: ' . AI_API_KEY,
            'anthropic-version: 2023-06-01',
        ],
        CURLOPT_POSTFIELDS     => json_encode($payload, JSON_UNESCAPED_UNICODE),
    ]);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $cerr = curl_error($ch);
    curl_close($ch);

    if ($resp === false) {
        return ['ok' => false, 'error' => 'خطای اتصال به سرویس هوش مصنوعی: ' . $cerr];
    }
    $data = json_decode($resp, true);
    if ($code !== 200) {
        $msg = $data['error']['message'] ?? ('کد خطا: ' . $code);
        return ['ok' => false, 'error' => 'سرویس هوش مصنوعی: ' . $msg];
    }
    $text = '';
    foreach (($data['content'] ?? []) as $block) {
        if (($block['type'] ?? '') === 'text') $text .= $block['text'];
    }
    return ['ok' => true, 'text' => trim($text)];
}

/**
 * مسیر امن فایل پروژه برای دستیار ادمین.
 * فقط داخل پوشهٔ پروژه، فقط پسوندهای مجاز، و خارج از پوشهٔ config (جلوگیری از نشت اطلاعات حساس).
 * در صورت نامعتبر بودن، null برمی‌گرداند.
 */
function aiSafeProjectPath(string $rel): ?string {
    $base = realpath(__DIR__ . '/..');
    if ($base === false) return null;

    $rel = str_replace('\\', '/', $rel);
    $rel = ltrim($rel, '/');
    $full = realpath($base . '/' . $rel);
    if ($full === false) return null;

    // باید واقعاً داخل پوشهٔ پروژه باشد
    if (strpos($full, $base . DIRECTORY_SEPARATOR) !== 0) return null;

    // پوشهٔ config حاوی کلید/رمز است — هرگز ارسال/بازنویسی نشود
    if (strpos($full, $base . DIRECTORY_SEPARATOR . 'config') === 0) return null;

    $ext = strtolower(pathinfo($full, PATHINFO_EXTENSION));
    if (!in_array($ext, ['php', 'css', 'js', 'html', 'htaccess', 'md'], true)
        && basename($full) !== '.htaccess') {
        return null;
    }
    if (!is_file($full)) return null;
    return $full;
}
