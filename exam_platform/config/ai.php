<?php
/**
 * config/ai.php — دستیار هوش مصنوعی (DeepSeek)
 *
 * اتصال با cURL به API دیپ‌سیک (سازگار با OpenAI). بدون نیاز به Composer/SDK.
 *
 * تنظیم کلید (یکی از روش‌ها):
 *   - متغیر محیطی: AI_API_KEY=...  یا  DEEPSEEK_API_KEY=...
 *   - یا مستقیم در همین فایل، مقدار '' را با کلید خود جایگزین کنید.
 *
 * اختیاری:
 *   AI_BASE_URL  پیش‌فرض: https://api.deepseek.com/chat/completions
 *   AI_MODEL     پیش‌فرض: deepseek-chat   (یا deepseek-reasoner)
 */

if (!defined('DB_HOST')) {
    require_once __DIR__ . '/database.php';
}

// 👇 اگر متغیر محیطی نداری، کلید دیپ‌سیک را مستقیم بین '' بگذار:  '' → 'sk-...'
define('AI_API_KEY',  getenv('AI_API_KEY') ?: (getenv('DEEPSEEK_API_KEY') ?: ''));
define('AI_BASE_URL', getenv('AI_BASE_URL') ?: 'https://api.deepseek.com/chat/completions');
define('AI_MODEL',    getenv('AI_MODEL')    ?: 'deepseek-chat');
define('AI_ENABLED',  AI_API_KEY !== '');

// اجازهٔ نوشتن فایل توسط فیکسر ادمین — برای امنیت پیش‌فرض خاموش است.
define('AI_ALLOW_FILE_WRITE', getenv('AI_ALLOW_FILE_WRITE') === '1');

/**
 * فراخوانی سرویس هوش مصنوعی دیپ‌سیک (سازگار با OpenAI Chat Completions).
 * @param array  $messages  [['role'=>'user'|'assistant','content'=>'...'], ...]
 * @param string $system    دستور سیستمی
 * @param int    $maxTokens سقف توکن خروجی
 * @param bool   $jsonMode  اگر true، خروجی JSON معتبر اجبار می‌شود
 */
function aiChat(array $messages, string $system, int $maxTokens = 1500, bool $jsonMode = false): array {
    if (!AI_ENABLED) {
        return ['ok' => false, 'error' => 'سرویس هوش مصنوعی پیکربندی نشده است. کلید دیپ‌سیک را در config/ai.php تنظیم کنید.'];
    }

    $allMsgs = array_merge([['role' => 'system', 'content' => $system]], array_values($messages));
    $payload = [
        'model'       => AI_MODEL,
        'messages'    => $allMsgs,
        'max_tokens'  => $maxTokens,
        'temperature' => $jsonMode ? 0.3 : 0.6,
        'stream'      => false,
    ];
    if ($jsonMode) {
        $payload['response_format'] = ['type' => 'json_object'];
    }

    $ch = curl_init(AI_BASE_URL);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 120,
        CURLOPT_HTTPHEADER     => [
            'Content-Type: application/json',
            'Authorization: Bearer ' . AI_API_KEY,
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
    $text = $data['choices'][0]['message']['content'] ?? '';
    if ($text === '') {
        return ['ok' => false, 'error' => 'پاسخی از سرویس دریافت نشد'];
    }
    return ['ok' => true, 'text' => trim($text)];
}

/**
 * مسیر امن فایل پروژه برای فیکسر ادمین.
 * فقط داخل پوشهٔ پروژه، پسوندهای مجاز، و خارج از پوشهٔ config (جلوگیری از نشت کلید/رمز).
 */
function aiSafeProjectPath(string $rel): ?string {
    $base = realpath(__DIR__ . '/..');
    if ($base === false) return null;

    $rel  = ltrim(str_replace('\\', '/', $rel), '/');
    $full = realpath($base . '/' . $rel);
    if ($full === false) return null;
    if (strpos($full, $base . DIRECTORY_SEPARATOR) !== 0) return null;
    if (strpos($full, $base . DIRECTORY_SEPARATOR . 'config') === 0) return null;

    $ext = strtolower(pathinfo($full, PATHINFO_EXTENSION));
    if (!in_array($ext, ['php', 'css', 'js', 'html', 'htaccess', 'md'], true)
        && basename($full) !== '.htaccess') {
        return null;
    }
    return is_file($full) ? $full : null;
}
