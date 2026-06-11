<?php
/**
 * api/submit_exam.php - ثبت نهایی پاسخ‌های آزمون
 * Fixed: session keys, negative marking, multi-select scoring, proper validation
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405); exit('Method Not Allowed');
}

requireCsrf();

$fid = validateInt($_POST['form_id'] ?? 0, 1);
if (!$fid) die(renderError('شناسه فرم نامعتبر'));

// دریافت فرم
$stmt = $pdo->prepare("SELECT * FROM forms WHERE id=? AND is_active=1");
$stmt->execute([$fid]);
$form = $stmt->fetch();
if (!$form) die(renderError('آزمون یافت نشد'));

$tid = (int)$form['teacher_id'];

$clientIP = getClientIP();

// IPهای مسدود نباید بتوانند پاسخ ثبت کنند
if (isIpBlacklisted($pdo, $clientIP)) {
    die(renderError('دسترسی شما مسدود شده است.'));
}

// زمان آزمون: اگر آزمون به پایان رسیده، ثبت پذیرفته نشود
if ($form['end_time'] && strtotime($form['end_time']) + 60 < time()) {
    die(renderError('زمان آزمون به پایان رسیده است.'));
}

// بررسی تعداد تلاش مجاز (بر اساس IP)
$stmt = $pdo->prepare("SELECT COUNT(*) FROM answers WHERE form_id=? AND user_ip=? AND status='completed'");
$stmt->execute([$fid, $clientIP]);
$existingAttempts = (int)$stmt->fetchColumn();
if ($existingAttempts >= $form['max_attempts']) {
    die(renderError('تعداد تلاش‌های مجاز به پایان رسیده است'));
}

// دریافت همه سوالات
$stmt = $pdo->prepare("SELECT * FROM questions WHERE form_id=? ORDER BY order_index");
$stmt->execute([$fid]);
$questions = $stmt->fetchAll();

// پردازش پاسخ‌ها
$answers     = [];
$user_name   = '';
$user_national = '';
$user_phone  = '';

$score       = 0.0;
$maxScore    = 0.0;
$correct     = 0;
$wrong       = 0;
$empty       = 0;

foreach ($questions as $q) {
    $qid  = $q['id'];
    $type = $q['type'];
    $pts  = (float)$q['points'];

    // Collect answer
    $rawAnswer = null;
    if ($type === 'multi_select') {
        $arr = $_POST['q_' . $qid] ?? [];
        $rawAnswer = is_array($arr) ? implode(',', array_map('intval', $arr)) : null;
    } elseif ($type === 'fill_blank') {
        // جای‌خالی می‌تواند چند ورودی داشته باشد (q_ID[]) — با | به هم می‌چسبند
        $fb = $_POST['q_' . $qid] ?? '';
        if (is_array($fb)) {
            $fb = implode('|', array_map(fn($x) => sanitizeString((string)$x, 200), $fb));
        } else {
            $fb = sanitizeString($fb, 500);
        }
        $rawAnswer = trim($fb, '|') === '' ? '' : $fb;
    } else {
        $rawAnswer = isset($_POST['q_' . $qid]) ? sanitizeString($_POST['q_' . $qid], 5000) : null;
    }

    $answers[$qid] = $rawAnswer;

    // Extract info fields
    if ($type === 'name_family')   $user_name     = $rawAnswer ?? '';
    if ($type === 'national_code') $user_national = $rawAnswer ?? '';
    if ($type === 'phone')         $user_phone    = $rawAnswer ?? '';

    // Skip non-scoreable types
    if (in_array($type, ['name_family','national_code','phone','short_text','long_text','section_title','rating'])) continue;

    // Scoring
    $maxScore += $pts;
    $correctAns = $q['correct_answer'];

    if ($rawAnswer === null || $rawAnswer === '') {
        $empty++;
        // Negative marking for empty: don't subtract
    } elseif ($type === 'true_false' || $type === 'numeric' || $type === 'fill_blank' || $type === 'multiple_choice' || $type === 'dropdown') {
        $isCorrect = false;
        if ($type === 'fill_blank') {
            // مقایسهٔ بدون‌حساسیت به حروف/فاصله؛ پشتیبانی از چند جای‌خالی با جداکنندهٔ |
            $norm = fn($s) => mb_strtolower(trim(preg_replace('/\s*\|\s*/u', '|', $s ?? '')));
            $isCorrect = $norm($rawAnswer) !== '' && $norm($rawAnswer) === $norm($correctAns);
        } elseif ($type === 'numeric') {
            $isCorrect = abs((float)$rawAnswer - (float)$correctAns) < 0.0001;
        } else {
            $isCorrect = $rawAnswer == $correctAns;
        }
        if ($isCorrect) {
            $score += $pts;
            $correct++;
        } else {
            $score -= (float)$form['negative_marking'];
            $wrong++;
        }
    } elseif ($type === 'multi_select') {
        // Multi-select: parse correct answers (JSON array)
        try {
            $correctArr = json_decode($correctAns, true);
        } catch(Exception $e) { $correctArr = [$correctAns]; }
        if (!is_array($correctArr)) $correctArr = [$correctAns];
        $correctArr  = array_map('strval', $correctArr);
        sort($correctArr);

        $userArr = $rawAnswer ? explode(',', $rawAnswer) : [];
        $userArr = array_map('strval', $userArr);
        sort($userArr);

        if ($userArr === $correctArr) {
            $score += $pts;
            $correct++;
        } else {
            $score -= (float)$form['negative_marking'];
            $wrong++;
        }
    }
}

$score = max(0, round($score, 2));
$maxScore = round($maxScore, 2);

// ضد دور زدن با VPN/تعویض IP: اگر این کد ملی به تعداد مجاز قبلاً آزمون داده، رد کن
if ($user_national !== '' && validateNationalCode($user_national)) {
    $s2 = $pdo->prepare("SELECT COUNT(*) FROM answers WHERE form_id=? AND user_national=? AND status='completed'");
    $s2->execute([$fid, $user_national]);
    if ((int)$s2->fetchColumn() >= (int)$form['max_attempts']) {
        // رکورد در حال انجام را باطل کن تا به‌عنوان آزمون ناتمام نماند
        $sessAid = (int)($_SESSION['exam_answer_id_' . $fid] ?? 0);
        if ($sessAid) {
            $pdo->prepare("UPDATE answers SET status='void' WHERE id=? AND form_id=? AND status='started'")
                ->execute([$sessAid, $fid]);
        }
        die(renderError('با این کد ملی قبلاً در این آزمون شرکت شده است.'));
    }
}

// تقلب از لاگ
$stmt = $pdo->prepare("SELECT COUNT(*) FROM cheat_logs WHERE form_id=? AND user_ip=? AND created_at > DATE_SUB(NOW(), INTERVAL 2 HOUR)");
$stmt->execute([$fid, $clientIP]);
$cheatFromLog = (int)$stmt->fetchColumn();
$cheatFromPost = (int)($_POST['cheat_count'] ?? 0);
$totalCheat = max($cheatFromLog, $cheatFromPost);

// زمان صرف شده
$startTime   = (int)($_POST['start_time'] ?? 0);
$durationTaken = $startTime > 0 ? min(time() - $startTime, $form['duration'] * 60 + 300) : null;

// browser fingerprint (basic)
$ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
$fp = substr(hash('sha256', $clientIP . $ua), 0, 16);

// ذخیره در دیتابیس — اگر رکورد «started» این شرکت‌کننده موجود است همان را تکمیل کن،
// در غیر این صورت رکورد جدید بساز (جلوگیری از ردیف‌های تکراری در مانیتورینگ)
$sessAnswerId = (int)($_SESSION['exam_answer_id_' . $fid] ?? 0);
$useUpdate    = false;
if ($sessAnswerId) {
    $chk = $pdo->prepare("SELECT id FROM answers WHERE id=? AND form_id=? AND status='started'");
    $chk->execute([$sessAnswerId, $fid]);
    if ($chk->fetch()) $useUpdate = true;
}

$timePerQuestion = sanitizeString($_POST['time_per_question'] ?? '{}', 2000);
$answersJson     = json_encode($answers, JSON_UNESCAPED_UNICODE);

if ($useUpdate) {
    $stmt = $pdo->prepare("
        UPDATE answers SET
            user_agent=?, browser_fp=?, user_name=?, user_national=?, user_phone=?,
            answers=?, time_per_question=?, score=?, max_score=?,
            correct_count=?, wrong_count=?, empty_count=?, cheat_count=?,
            attempt_number=?, status='completed', submitted_at=NOW(), duration_taken=?
        WHERE id=? AND form_id=?
    ");
    $stmt->execute([
        substr($ua, 0, 500), $fp, $user_name, $user_national, $user_phone,
        $answersJson, $timePerQuestion, $score, $maxScore,
        $correct, $wrong, $empty, $totalCheat,
        $existingAttempts + 1, $durationTaken,
        $sessAnswerId, $fid
    ]);
    $answerId = $sessAnswerId;
} else {
    $stmt = $pdo->prepare("
        INSERT INTO answers
        (form_id, teacher_id, user_ip, user_agent, browser_fp,
         user_name, user_national, user_phone,
         answers, time_per_question,
         score, max_score, correct_count, wrong_count, empty_count, cheat_count,
         attempt_number, status, submitted_at, duration_taken)
        VALUES (?,?,?,?,?, ?,?,?, ?,?, ?,?,?,?,?,?, ?,   'completed', NOW(), ?)
    ");
    $stmt->execute([
        $fid, $tid, $clientIP, substr($ua, 0, 500), $fp,
        $user_name, $user_national, $user_phone,
        $answersJson, $timePerQuestion,
        $score, $maxScore, $correct, $wrong, $empty, $totalCheat,
        $existingAttempts + 1,
        $durationTaken
    ]);
    $answerId = (int)$pdo->lastInsertId();
}

// ذخیره نام دانش‌آموز برای watermark و webcam در آزمون بعدی
if ($user_name) $_SESSION['exam_student_name_' . $fid] = $user_name;
$_SESSION['exam_answer_id_' . $fid] = $answerId;

// تمیز کردن session
unset(
    $_SESSION['exam_start_' . $fid],
    $_SESSION['exam_order_' . $fid],
    $_SESSION['exam_auth_'  . $fid]
);
// تمیز کردن opt_orders
foreach ($questions as $q) unset($_SESSION['opt_order_' . $q['id']]);

// ذخیره نتیجه در session برای صفحه result
$_SESSION['exam_result'] = [
    'answer_id'  => $answerId,
    'score'      => $score,
    'max_score'  => $maxScore,
    'correct'    => $correct,
    'wrong'      => $wrong,
    'empty'      => $empty,
    'cheat'      => $totalCheat,
    'form_title' => $form['title'],
    'show_results'=> $form['show_results'],
    'pass_threshold' => $form['pass_threshold'],
    'total_q'    => count(array_filter($questions, fn($q) => $q['type'] !== 'section_title')),
];

header('Location: ../exam/result.php');
exit();

function renderError(string $msg): never {
    echo '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>خطا</title></head>
    <body style="font-family:sans-serif;text-align:center;padding:60px;background:#0f172a;color:white;">
    <h2>⚠️ ' . htmlspecialchars($msg) . '</h2></body></html>';
    exit();
}
