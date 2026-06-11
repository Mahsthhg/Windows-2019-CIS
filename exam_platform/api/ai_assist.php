<?php
/**
 * api/ai_assist.php — دستیار هوش مصنوعی پشتیبانی
 *
 * action=chat        : گفتگوی پشتیبانی (معلم یا ادمین)
 * action=diagnose    : (فقط ادمین) خواندن یک فایل پروژه + توضیح خطا → تشخیص و پیشنهاد اصلاح
 * action=apply_fix   : (فقط ادمین، فقط اگر AI_ALLOW_FILE_WRITE روشن باشد) نوشتن فایل با پشتیبان‌گیری
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
require_once __DIR__ . '/../config/ai.php';

header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'Method not allowed']);
    exit();
}

// فقط معلم یا ادمینِ واردشده
$isTeacher = isTeacher();
$isAdmin   = isAdmin();
if (!$isTeacher && !$isAdmin) {
    http_response_code(403);
    echo json_encode(['ok' => false, 'error' => 'دسترسی غیرمجاز']);
    exit();
}

$input  = json_decode(file_get_contents('php://input'), true) ?: [];
$action = $input['action'] ?? 'chat';

// CSRF
$token = $input['csrf_token'] ?? ($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
if (!verifyCsrfToken($token)) {
    http_response_code(403);
    echo json_encode(['ok' => false, 'error' => 'توکن امنیتی نامعتبر']);
    exit();
}

// ── دانش پایه دربارهٔ سامانه (برای پاسخ دقیق دستیار) ──
$PLATFORM_INFO = <<<TXT
این یک «سامانهٔ آزمون و حضوروغیاب آنلاین» با PHP و MySQL است. امکانات کلیدی:
- فرم‌ساز آزمون با بیش از ۱۲ نوع سوال (چندگزینه‌ای، چندانتخابی، صحیح/غلط، جای‌خالی، عددی، تشریحی، ستاره‌بندی، کشویی، فیلدهای نام/کدملی/تلفن، عنوان بخش).
- ضدتقلب: تمام‌صفحهٔ اجباری، تشخیص تعویض تب، مسدودسازی کپی/راست‌کلیک، تشخیص چهره با هوش مصنوعی (خروج سر از کادر یا چند نفر = تقلب)، کنترل موقعیت GPS و تشخیص تقلب گروهی.
- پنل ادمین: مانیتورینگ زنده، نقشهٔ GPS، اسنپشات وب‌کم، لیست سیاه IP، لاگ عملکرد، ساخت معلم و کلید دسترسی.
- پنل معلم: ساخت آزمون، نتایج و آنالیز سوالات، خروجی Excel/CSV، چاپ کارنامه، بانک سوال، حضوروغیاب.
- نمره‌دهی کاملاً سمت سرور و امن است.
- دانش‌آموز با «لینک اختصاصی» وارد آزمون می‌شود (نیازی به ثبت‌نام ندارد).
TXT;

// ──────────────────────────────────────────────────────────────
// خواندن و اعتبارسنجی پیام‌های گفتگو
// ──────────────────────────────────────────────────────────────
function readMessages(array $input): array {
    $raw = $input['messages'] ?? [];
    if (!is_array($raw)) return [];
    $msgs = [];
    foreach (array_slice($raw, -20) as $m) {  // حداکثر ۲۰ پیام آخر
        $role = ($m['role'] ?? '') === 'assistant' ? 'assistant' : 'user';
        $content = (string)($m['content'] ?? '');
        $content = mb_substr(trim($content), 0, 4000);
        if ($content !== '') $msgs[] = ['role' => $role, 'content' => $content];
    }
    // پیام اول باید user باشد
    while (!empty($msgs) && $msgs[0]['role'] !== 'user') array_shift($msgs);
    return $msgs;
}

// ── محدودیت نرخ سادهٔ مبتنی بر session (جلوگیری از مصرف بیش از حد) ──
$rlKey = 'ai_calls';
$_SESSION[$rlKey] = array_filter($_SESSION[$rlKey] ?? [], fn($t) => $t > time() - 60);
if (count($_SESSION[$rlKey]) >= 15) {
    echo json_encode(['ok' => false, 'error' => 'درخواست‌های زیاد در زمان کوتاه. کمی صبر کنید.']);
    exit();
}
$_SESSION[$rlKey][] = time();

// ──────────────────────────────────────────────────────────────
// اکشن‌ها
// ──────────────────────────────────────────────────────────────
if ($action === 'chat') {
    $messages = readMessages($input);
    if (empty($messages)) {
        echo json_encode(['ok' => false, 'error' => 'پیامی ارسال نشد']);
        exit();
    }
    if ($isAdmin) {
        $system = "تو دستیار هوش مصنوعی پشتیبانی فنی برای مدیر سامانه هستی. مثل یک مهندس ارشد PHP/MySQL کمک کن: تشخیص خطا، راهنمایی پیکربندی، امنیت، و بهبود. پاسخ‌ها فارسی، دقیق، عملی و کوتاه باشد. اگر کاربر کد یا خطا داد، علت و راه‌حل مشخص بده.\n\n" . $PLATFORM_INFO;
    } else {
        $system = "تو دستیار هوش مصنوعی پشتیبانی برای معلمان این سامانه هستی. به معلم در استفاده از سامانه کمک کن (ساخت آزمون، انواع سوال، تنظیمات ضدتقلب، GPS و وب‌کم، نتایج، حضوروغیاب). پاسخ‌ها فارسی، دوستانه، گام‌به‌گام و کوتاه باشد. تو به داده‌های کاربر دسترسی نداری؛ فقط راهنمایی بده.\n\n" . $PLATFORM_INFO;
    }
    $result = aiChat($messages, $system, 1500);
    echo json_encode($result, JSON_UNESCAPED_UNICODE);
    exit();
}

// ──────────────────────────────────────────────────────────────
// سوال‌ساز هوش مصنوعی (معلم) — تولید خودکار سوال برای یک آزمون
// ──────────────────────────────────────────────────────────────
if ($action === 'generate_questions') {
    if (!$isTeacher) {
        http_response_code(403);
        echo json_encode(['ok' => false, 'error' => 'فقط معلم می‌تواند سوال بسازد']);
        exit();
    }
    $tid    = (int)$_SESSION['teacher_id'];
    $formId = validateInt($input['form_id'] ?? 0, 1);
    $topic  = mb_substr(trim((string)($input['topic'] ?? '')), 0, 300);
    $count  = max(1, min(15, (int)($input['count'] ?? 5)));
    $qtype  = in_array($input['qtype'] ?? '', ['multiple_choice', 'true_false', 'short_text'], true)
              ? $input['qtype'] : 'multiple_choice';
    $level  = mb_substr(trim((string)($input['difficulty'] ?? 'متوسط')), 0, 20);

    if (!$formId || $topic === '') {
        echo json_encode(['ok' => false, 'error' => 'موضوع و آزمون را مشخص کنید']);
        exit();
    }
    // بررسی مالکیت آزمون
    $s = $pdo->prepare("SELECT id FROM forms WHERE id=? AND teacher_id=?");
    $s->execute([$formId, $tid]);
    if (!$s->fetch()) {
        echo json_encode(['ok' => false, 'error' => 'این آزمون متعلق به شما نیست']);
        exit();
    }

    // ساخت دستور بر اساس نوع سوال
    if ($qtype === 'multiple_choice') {
        $schema = 'هر سوال: {"title": متن سوال, "options": [۴ گزینه], "correct": شمارهٔ گزینهٔ درست از ۱ تا ۴}';
    } elseif ($qtype === 'true_false') {
        $schema = 'هر سوال: {"title": یک جملهٔ قابل‌داوری, "correct": "true" یا "false"}';
    } else {
        $schema = 'هر سوال: {"title": متن سوال تشریحی کوتاه}';
    }
    $sys = "تو یک طراح سوال آزمون حرفه‌ای و فارسی‌زبان هستی. فقط و فقط یک JSON معتبر برگردان، بدون هیچ توضیح اضافه. "
         . "ساختار: {\"questions\": [ ... ]} که آرایه‌ای از سوالات است. " . $schema . " "
         . "سوالات باید دقیق، بدون ابهام، و متناسب با سطح خواسته‌شده باشند.";
    $userPrompt = "تعداد {$count} سوال {$qtype} با سطح «{$level}» دربارهٔ موضوع زیر بساز:\n{$topic}";

    $result = aiChat([['role' => 'user', 'content' => $userPrompt]], $sys, 3000, true);
    if (!$result['ok']) {
        echo json_encode($result, JSON_UNESCAPED_UNICODE);
        exit();
    }
    $parsed = json_decode($result['text'], true);
    $list   = $parsed['questions'] ?? (is_array($parsed) ? $parsed : []);
    if (!is_array($list) || empty($list)) {
        echo json_encode(['ok' => false, 'error' => 'هوش مصنوعی سوال معتبری برنگرداند. دوباره تلاش کنید.']);
        exit();
    }

    // ایندکس فعلی برای ادامهٔ ترتیب
    $s = $pdo->prepare("SELECT COALESCE(MAX(order_index), -1) FROM questions WHERE form_id=?");
    $s->execute([$formId]);
    $order = (int)$s->fetchColumn();

    $ins = $pdo->prepare("INSERT INTO questions (form_id, type, title, options, correct_answer, points, required, order_index) VALUES (?,?,?,?,?,?,1,?)");
    $inserted = 0;
    foreach ($list as $q) {
        $title = mb_substr(trim((string)($q['title'] ?? '')), 0, 1000);
        if ($title === '') continue;
        $options = null; $correct = null;

        if ($qtype === 'multiple_choice') {
            $opts = $q['options'] ?? [];
            if (!is_array($opts) || count($opts) < 2) continue;
            $opts = array_values(array_map(fn($o) => mb_substr(trim((string)$o), 0, 300), array_slice($opts, 0, 6)));
            $ci   = (int)($q['correct'] ?? 0);
            if ($ci < 1 || $ci > count($opts)) $ci = 1;
            $options = json_encode($opts, JSON_UNESCAPED_UNICODE);
            $correct = (string)$ci;
        } elseif ($qtype === 'true_false') {
            $c = strtolower(trim((string)($q['correct'] ?? '')));
            $correct = in_array($c, ['true', 'درست', '1'], true) ? 'true' : 'false';
        }
        // short_text: بدون گزینه و پاسخ

        $order++;
        $ins->execute([$formId, $qtype, $title, $options, $correct, 1, $order]);
        $inserted++;
    }

    echo json_encode(['ok' => true, 'count' => $inserted, 'msg' => "{$inserted} سوال ساخته و اضافه شد"], JSON_UNESCAPED_UNICODE);
    exit();
}

// ── از این به بعد فقط ادمین ──
if (!$isAdmin) {
    http_response_code(403);
    echo json_encode(['ok' => false, 'error' => 'این عملیات فقط برای ادمین است']);
    exit();
}

if ($action === 'diagnose') {
    $rel  = (string)($input['file'] ?? '');
    $desc = mb_substr(trim((string)($input['description'] ?? '')), 0, 2000);
    $path = aiSafeProjectPath($rel);
    if (!$path) {
        echo json_encode(['ok' => false, 'error' => 'مسیر فایل نامعتبر یا غیرمجاز است (پوشهٔ config مجاز نیست).']);
        exit();
    }
    $code = file_get_contents($path);
    if ($code === false) {
        echo json_encode(['ok' => false, 'error' => 'خطا در خواندن فایل']);
        exit();
    }
    if (strlen($code) > 60000) $code = substr($code, 0, 60000) . "\n... [بریده شد]";

    $system = "تو یک مهندس ارشد PHP هستی. کد یک فایل از سامانهٔ آزمون آنلاین به تو داده می‌شود به‌همراه شرح مشکل. "
            . "ابتدا علت دقیق مشکل را به‌صورت کوتاه توضیح بده، سپس راه‌حل را شرح بده و در صورت لزوم نسخهٔ اصلاح‌شدهٔ بخش مربوطه را در یک بلوک کد بده. "
            . "فارسی پاسخ بده. اگر مطمئن نیستی، صادقانه بگو.\n\n" . $PLATFORM_INFO;

    $userMsg = "فایل: `" . basename($path) . "`\n";
    if ($desc !== '') $userMsg .= "شرح مشکل از طرف ادمین:\n" . $desc . "\n";
    $userMsg .= "\nمحتوای فایل:\n```php\n" . $code . "\n```";

    $result = aiChat([['role' => 'user', 'content' => $userMsg]], $system, 2500);
    echo json_encode($result, JSON_UNESCAPED_UNICODE);
    exit();
}

if ($action === 'apply_fix') {
    if (!AI_ALLOW_FILE_WRITE) {
        echo json_encode(['ok' => false, 'error' => 'نوشتن فایل غیرفعال است. برای فعال‌سازی AI_ALLOW_FILE_WRITE=1 را تنظیم کنید (فقط در محیط توسعه).']);
        exit();
    }
    $rel     = (string)($input['file'] ?? '');
    $content = (string)($input['content'] ?? '');
    $path    = aiSafeProjectPath($rel);
    if (!$path) {
        echo json_encode(['ok' => false, 'error' => 'مسیر فایل نامعتبر یا غیرمجاز است.']);
        exit();
    }
    if ($content === '' || strlen($content) > 500000) {
        echo json_encode(['ok' => false, 'error' => 'محتوای نامعتبر']);
        exit();
    }
    // پشتیبان‌گیری قبل از نوشتن
    $backup = $path . '.bak.' . date('Ymd_His');
    if (!copy($path, $backup)) {
        echo json_encode(['ok' => false, 'error' => 'خطا در ساخت نسخهٔ پشتیبان']);
        exit();
    }
    if (file_put_contents($path, $content) === false) {
        echo json_encode(['ok' => false, 'error' => 'خطا در نوشتن فایل']);
        exit();
    }
    // ثبت در لاگ ادمین
    $pdo->prepare("INSERT INTO admin_audit_log (admin_id, action, target_type, details, ip_address) VALUES (?,?,?,?,?)")
        ->execute([$_SESSION['admin_id'], 'ai_apply_fix', 'file', basename($path) . ' (backup: ' . basename($backup) . ')', getClientIP()]);

    echo json_encode(['ok' => true, 'msg' => 'فایل با موفقیت به‌روزرسانی شد. نسخهٔ پشتیبان: ' . basename($backup)]);
    exit();
}

echo json_encode(['ok' => false, 'error' => 'اکشن نامعتبر']);
