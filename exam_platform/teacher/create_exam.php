<?php
/**
 * teacher/create_exam.php
 * فرم‌ساز پیشرفته آزمون با 12+ نوع سوال
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
$teacher = requireTeacherAuth();
$tid = $teacher['id'];

$msg = '';
$msgType = 'success';

// ── ساخت فرم جدید ────────────────────────────────────────────────
if (isset($_POST['create_form'])) {
    requireCsrf();
    $title = sanitizeString($_POST['title'] ?? '', 255);
    $desc  = sanitizeString($_POST['description'] ?? '', 1000);
    if ($title) {
        $code = strtoupper(substr(md5(uniqid(rand(), true)), 0, 8));
        $pdo->prepare("INSERT INTO forms (teacher_id,title,description,access_code) VALUES (?,?,?,?)")
            ->execute([$tid, $title, $desc, $code]);
        redirect('create_exam.php?edit=' . $pdo->lastInsertId());
    }
}

// ── آپدیت تنظیمات آزمون ──────────────────────────────────────────
if (isset($_POST['save_settings'])) {
    requireCsrf();
    $fid = validateInt($_POST['form_id'] ?? 0, 1);
    if ($fid) {
        // بررسی مالکیت
        $s = $pdo->prepare("SELECT id FROM forms WHERE id=? AND teacher_id=?");
        $s->execute([$fid, $tid]);
        if ($s->fetch()) {
            $fields = [
                'title'             => sanitizeString($_POST['title'] ?? '', 255),
                'description'       => sanitizeString($_POST['description'] ?? '', 1000),
                'duration'          => validateInt($_POST['duration'] ?? 60, 1, 600) ?? 60,
                'start_time'        => $_POST['start_time'] ?: null,
                'end_time'          => $_POST['end_time'] ?: null,
                'shuffle_questions' => (int)(bool)($_POST['shuffle_questions'] ?? 0),
                'shuffle_options'   => (int)(bool)($_POST['shuffle_options'] ?? 0),
                'allow_back'        => (int)(bool)($_POST['allow_back'] ?? 0),
                'show_results'      => in_array($_POST['show_results']??'', ['always','never','after_deadline']) ? $_POST['show_results'] : 'always',
                'negative_marking'  => max(0, min(5, (float)($_POST['negative_marking'] ?? 0))),
                'pass_threshold'    => validateInt($_POST['pass_threshold'] ?? 0, 0, 100) ?? 0,
                'max_attempts'      => validateInt($_POST['max_attempts'] ?? 1, 1, 99) ?? 1,
                'require_fullscreen'=> (int)(bool)($_POST['require_fullscreen'] ?? 1),
                'require_camera'    => (int)(bool)($_POST['require_camera'] ?? 0),
                'gps_required'      => (int)(bool)($_POST['gps_required'] ?? 0),
                'gps_lat'           => ($_POST['gps_lat'] ?? '') !== '' ? (float)$_POST['gps_lat'] : null,
                'gps_lng'           => ($_POST['gps_lng'] ?? '') !== '' ? (float)$_POST['gps_lng'] : null,
                'gps_radius'        => validateInt($_POST['gps_radius'] ?? 500, 10, 10000) ?? 500,
                'password'          => sanitizeString($_POST['exam_password'] ?? '', 100) ?: null,
            ];
            $set = implode(', ', array_map(fn($k) => "`$k`=?", array_keys($fields)));
            $pdo->prepare("UPDATE forms SET $set WHERE id=? AND teacher_id=?")
                ->execute([...array_values($fields), $fid, $tid]);
            $msg = '✅ تنظیمات ذخیره شد';
        }
    }
}

// ── فعال/غیرفعال ────────────────────────────────────────────────
if (isset($_GET['activate'])) {
    $fid = validateInt($_GET['activate'], 1);
    if ($fid) {
        $s = $pdo->prepare("SELECT id FROM forms WHERE id=? AND teacher_id=?");
        $s->execute([$fid, $tid]);
        if ($s->fetch()) {
            $link = 'exam_' . strtolower(bin2hex(random_bytes(6)));
            $pdo->prepare("UPDATE forms SET exam_link=?,is_active=1 WHERE id=?")->execute([$link, $fid]);
        }
    }
    redirect('create_exam.php');
}

if (isset($_GET['deactivate'])) {
    $fid = validateInt($_GET['deactivate'], 1);
    if ($fid) $pdo->prepare("UPDATE forms SET is_active=0 WHERE id=? AND teacher_id=?")->execute([$fid, $tid]);
    redirect('create_exam.php');
}

if (isset($_GET['delete_form'])) {
    $fid = validateInt($_GET['delete_form'], 1);
    if ($fid) $pdo->prepare("DELETE FROM forms WHERE id=? AND teacher_id=?")->execute([$fid, $tid]);
    redirect('create_exam.php');
}

if (isset($_GET['duplicate'])) {
    $fid = validateInt($_GET['duplicate'], 1);
    if ($fid) {
        $s = $pdo->prepare("SELECT * FROM forms WHERE id=? AND teacher_id=?");
        $s->execute([$fid, $tid]);
        $orig = $s->fetch();
        if ($orig) {
            $code = strtoupper(substr(md5(uniqid(rand(), true)), 0, 8));
            $pdo->prepare("INSERT INTO forms (teacher_id,title,description,access_code,duration,shuffle_questions,shuffle_options,allow_back,show_results,negative_marking,pass_threshold,max_attempts,require_fullscreen,require_camera,gps_required,gps_lat,gps_lng,gps_radius) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
                ->execute([$tid, 'کپی: ' . $orig['title'], $orig['description'], $code, $orig['duration'], $orig['shuffle_questions'], $orig['shuffle_options'], $orig['allow_back'], $orig['show_results'], $orig['negative_marking'], $orig['pass_threshold'], $orig['max_attempts'], $orig['require_fullscreen'], $orig['require_camera'] ?? 0, $orig['gps_required'] ?? 0, $orig['gps_lat'] ?? null, $orig['gps_lng'] ?? null, $orig['gps_radius'] ?? 500]);
            $newId = (int)$pdo->lastInsertId();
            // کپی سوالات
            $qs = $pdo->prepare("SELECT * FROM questions WHERE form_id=? ORDER BY order_index");
            $qs->execute([$fid]);
            $ins = $pdo->prepare("INSERT INTO questions (form_id,type,title,description,options,correct_answer,points,required,hint,image_url,order_index) VALUES (?,?,?,?,?,?,?,?,?,?,?)");
            foreach ($qs->fetchAll() as $q) {
                $ins->execute([$newId, $q['type'], $q['title'], $q['description'], $q['options'], $q['correct_answer'], $q['points'], $q['required'], $q['hint'], $q['image_url'], $q['order_index']]);
            }
            redirect('create_exam.php?edit=' . $newId . '&msg=duplicated');
        }
    }
    redirect('create_exam.php');
}

// ── حذف سوال ────────────────────────────────────────────────────
if (isset($_GET['delete_q'])) {
    $qid = validateInt($_GET['delete_q'], 1);
    $fid = validateInt($_GET['form_id'], 1);
    if ($qid && $fid) {
        $pdo->prepare("DELETE FROM questions WHERE id=? AND form_id IN (SELECT id FROM forms WHERE teacher_id=?)")
            ->execute([$qid, $tid]);
    }
    redirect('create_exam.php?edit=' . $fid);
}

// ── AJAX: ذخیره ترتیب ──────────────────────────────────────────
if (isset($_POST['reorder'])) {
    header('Content-Type: application/json');
    $order = json_decode($_POST['order'] ?? '[]', true);
    if (is_array($order)) {
        $upd = $pdo->prepare("UPDATE questions SET order_index=? WHERE id=? AND form_id IN (SELECT id FROM forms WHERE teacher_id=?)");
        foreach ($order as $i => $qid) $upd->execute([$i, (int)$qid, $tid]);
    }
    echo json_encode(['ok' => true]);
    exit();
}

// ── AJAX: افزودن/ویرایش سوال ────────────────────────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['save_question'])) {
    header('Content-Type: application/json; charset=utf-8');
    $body = json_decode(file_get_contents('php://input'), true) ?? $_POST;

    $fid    = validateInt($body['form_id'] ?? 0, 1);
    $qid    = validateInt($body['question_id'] ?? 0, 0);
    $type   = sanitizeString($body['type'] ?? '', 50);
    $title  = trim($body['title'] ?? '');
    $desc   = sanitizeString($body['description'] ?? '', 500);
    $opts   = $body['options'] ?? null;
    $correct= $body['correct_answer'] ?? null;
    $points = max(0, min(100, (float)($body['points'] ?? 1)));
    $req    = (int)(bool)($body['required'] ?? 1);
    $hint   = sanitizeString($body['hint'] ?? '', 300);

    $VALID_TYPES = ['name_family','national_code','phone','multiple_choice','multi_select','true_false','fill_blank','short_text','long_text','numeric','rating','dropdown','section_title'];

    if (!$fid || !in_array($type, $VALID_TYPES) || empty($title)) {
        jsonResponse(['success' => false, 'error' => 'داده نامعتبر'], 400);
    }

    // بررسی مالکیت فرم
    $s = $pdo->prepare("SELECT id FROM forms WHERE id=? AND teacher_id=?");
    $s->execute([$fid, $tid]); if (!$s->fetch()) jsonResponse(['success' => false, 'error' => 'دسترسی ندارید'], 403);

    $opts_json   = is_array($opts) ? json_encode($opts, JSON_UNESCAPED_UNICODE) : null;
    $correct_str = is_array($correct) ? json_encode($correct, JSON_UNESCAPED_UNICODE) : ($correct !== null ? (string)$correct : null);

    if ($qid > 0) {
        // ویرایش
        $s = $pdo->prepare("SELECT id FROM questions WHERE id=? AND form_id=?");
        $s->execute([$qid, $fid]); if (!$s->fetch()) jsonResponse(['success' => false, 'error' => 'سوال یافت نشد'], 404);

        $pdo->prepare("UPDATE questions SET type=?,title=?,description=?,options=?,correct_answer=?,points=?,required=?,hint=? WHERE id=?")
            ->execute([$type, $title, $desc, $opts_json, $correct_str, $points, $req, $hint, $qid]);
        jsonResponse(['success' => true, 'question_id' => $qid]);
    } else {
        // اضافه کردن
        $s = $pdo->prepare("SELECT COALESCE(MAX(order_index),0)+1 FROM questions WHERE form_id=?");
        $s->execute([$fid]); $ord = (int)$s->fetchColumn();

        $pdo->prepare("INSERT INTO questions (form_id,type,title,description,options,correct_answer,points,required,hint,order_index) VALUES (?,?,?,?,?,?,?,?,?,?)")
            ->execute([$fid, $type, $title, $desc, $opts_json, $correct_str, $points, $req, $hint, $ord]);
        jsonResponse(['success' => true, 'question_id' => (int)$pdo->lastInsertId()]);
    }
}

// ── دریافت داده برای نمایش ──────────────────────────────────────
$s = $pdo->prepare("SELECT * FROM forms WHERE teacher_id=? ORDER BY id DESC");
$s->execute([$tid]); $myForms = $s->fetchAll();

$editId   = validateInt($_GET['edit'] ?? 0, 0) ?? 0;
$editForm = null;
$questions = [];

if ($editId) {
    $s = $pdo->prepare("SELECT * FROM forms WHERE id=? AND teacher_id=?");
    $s->execute([$editId, $tid]);
    $editForm = $s->fetch();
    if ($editForm) {
        $s = $pdo->prepare("SELECT * FROM questions WHERE form_id=? ORDER BY order_index");
        $s->execute([$editId]);
        $questions = $s->fetchAll();
    }
}

if (isset($_GET['msg']) && $_GET['msg'] === 'duplicated') $msg = '✅ آزمون با موفقیت کپی شد';

$csrf = generateCsrfToken();

// ── نوع‌های سوال با توضیحات ────────────────────────────────────
$questionTypes = [
    'section_title'  => ['label' => '📌 بخش‌بندی',           'color' => '#64748b', 'hasAnswer' => false],
    'name_family'    => ['label' => '👤 نام و نام خانوادگی', 'color' => '#3b82f6', 'hasAnswer' => false],
    'national_code'  => ['label' => '🆔 کد ملی',              'color' => '#8b5cf6', 'hasAnswer' => false],
    'phone'          => ['label' => '📱 شماره تماس',          'color' => '#06b6d4', 'hasAnswer' => false],
    'short_text'     => ['label' => '✏️ متن کوتاه',           'color' => '#10b981', 'hasAnswer' => false],
    'long_text'      => ['label' => '📄 متن بلند (تشریحی)',   'color' => '#059669', 'hasAnswer' => false],
    'numeric'        => ['label' => '🔢 عددی',                 'color' => '#0ea5e9', 'hasAnswer' => true],
    'multiple_choice'=> ['label' => '🔘 چندگزینه‌ای (یک)',    'color' => '#f59e0b', 'hasAnswer' => true],
    'multi_select'   => ['label' => '☑️ چندگزینه‌ای (چند)', 'color' => '#d97706', 'hasAnswer' => true],
    'true_false'     => ['label' => '✅ صحیح/غلط',            'color' => '#ef4444', 'hasAnswer' => true],
    'dropdown'       => ['label' => '🔽 لیست کشویی',          'color' => '#ec4899', 'hasAnswer' => true],
    'rating'         => ['label' => '⭐ ستاره‌بندی',           'color' => '#f97316', 'hasAnswer' => false],
    'fill_blank'     => ['label' => '📝 جای‌خالی',            'color' => '#6366f1', 'hasAnswer' => true],
];
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>فرم‌ساز آزمون | <?= h($teacher['name']) ?></title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<style>
<?php include __DIR__ . '/../assets/css/panel.css'; ?>

/* ── Form Builder Specific ── */
.builder-layout { display: grid; grid-template-columns: 280px 1fr 320px; gap: 24px; align-items: start; }

/* Left: Question Types Palette */
.qtype-palette { position: sticky; top: 24px; }
.palette-section { margin-bottom: 16px; }
.palette-title { font-size: 11px; font-weight: 700; color: var(--text-muted); letter-spacing: 1px; text-transform: uppercase; margin-bottom: 10px; padding-right: 4px; }
.qtype-btn {
    display: flex; align-items: center; gap: 10px;
    width: 100%; padding: 11px 14px;
    border: 1.5px solid var(--border);
    border-radius: 14px; background: white;
    font-size: 13px; font-weight: 600;
    cursor: pointer; transition: .2s;
    font-family: inherit; text-align: right;
    margin-bottom: 6px;
}
.qtype-btn:hover { transform: translateX(-3px); border-color: currentColor; }
.qtype-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-right: 4px; }

/* Center: Questions List */
.questions-canvas { min-height: 300px; }
.q-item {
    background: white;
    border: 2px solid var(--border);
    border-radius: 20px;
    padding: 20px;
    margin-bottom: 14px;
    transition: .2s;
    position: relative;
}
.q-item:hover { border-color: var(--primary); box-shadow: 0 4px 16px rgba(99,102,241,.1); }
.q-item.dragging { opacity: .5; border-style: dashed; }
.q-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.q-num { background: var(--primary); color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; }
.q-title-text { flex: 1; font-weight: 700; font-size: 15px; line-height: 1.5; }
.q-actions { display: flex; gap: 6px; flex-shrink: 0; }
.q-type-tag { display: inline-block; padding: 3px 10px; border-radius: 30px; font-size: 10px; font-weight: 700; background: #f1f5f9; color: var(--text-muted); margin-top: 4px; }
.q-options-preview { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.q-opt-tag { padding: 4px 12px; background: #f8fafc; border: 1px solid var(--border); border-radius: 20px; font-size: 12px; }
.q-opt-tag.correct { background: #dcfce7; border-color: #86efac; color: #166534; }
.q-pts { position: absolute; left: 20px; top: 20px; background: #ede9fe; color: #5b21b6; padding: 3px 10px; border-radius: 30px; font-size: 11px; font-weight: 700; }
.empty-canvas { border: 2px dashed var(--border); border-radius: 20px; padding: 60px; text-align: center; color: var(--text-muted); }
.empty-canvas .icon { font-size: 48px; display: block; margin-bottom: 12px; }

/* Right: Settings Panel */
.settings-panel { position: sticky; top: 24px; }
.settings-tabs { display: flex; gap: 4px; margin-bottom: 16px; }
.settings-tab { flex: 1; padding: 8px; text-align: center; border-radius: 12px; cursor: pointer; font-size: 12px; font-weight: 700; border: none; background: #f1f5f9; color: var(--text-muted); font-family: inherit; transition: .2s; }
.settings-tab.active { background: var(--primary); color: white; }
.setting-section { display: none; }
.setting-section.active { display: block; }
.setting-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--border); }
.setting-row:last-child { border-bottom: none; }
.setting-label { font-size: 13px; font-weight: 600; }
.setting-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

/* Forms Grid */
.forms-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
.form-card {
    background: white; border-radius: 20px; padding: 20px;
    border: 1.5px solid var(--border); transition: .2s;
    display: flex; flex-direction: column; gap: 12px;
}
.form-card:hover { border-color: var(--primary); box-shadow: 0 4px 16px rgba(99,102,241,.1); }
.form-card-title { font-size: 16px; font-weight: 800; color: var(--text); }
.form-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.form-meta .meta-tag { font-size: 11px; background: #f1f5f9; padding: 4px 10px; border-radius: 20px; color: var(--text-muted); }
.form-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }

/* Modal content */
.q-modal-body { display: flex; flex-direction: column; gap: 16px; }
.options-editor { background: #f8fafc; border-radius: 16px; padding: 16px; }
.option-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.option-row input[type=text] { flex: 1; }
.option-correct { width: 20px; height: 20px; cursor: pointer; accent-color: var(--success); }
.option-del { background: #fee2e2; color: #dc2626; border: none; border-radius: 8px; padding: 4px 10px; cursor: pointer; font-size: 13px; }
.add-option-btn { background: #ede9fe; color: #5b21b6; border: none; border-radius: 12px; padding: 8px 16px; font-size: 13px; font-weight: 700; cursor: pointer; font-family: inherit; width: 100%; margin-top: 8px; transition: .2s; }
.add-option-btn:hover { background: #ddd6fe; }

/* Fill-blank editor */
.blank-editor { padding: 12px 16px; background: #f8fafc; border-radius: 16px; }
.blank-hint { font-size: 12px; color: var(--text-muted); margin-bottom: 10px; }
.blank-preview { padding: 12px; background: white; border: 1px solid var(--border); border-radius: 12px; font-size: 14px; line-height: 2; }
.blank-preview .blank-slot { display: inline-block; min-width: 60px; border-bottom: 2px solid var(--primary); margin: 0 4px; padding: 0 4px; color: var(--primary); font-weight: 700; }

/* Points input */
.points-input { width: 80px; text-align: center; }

/* Exam link display */
.exam-link-box { background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 16px; padding: 16px; }
.exam-link-url { font-family: monospace; font-size: 13px; color: #166534; word-break: break-all; margin-bottom: 8px; }
.copy-btn { background: #dcfce7; color: #166534; border: none; border-radius: 8px; padding: 6px 14px; font-size: 12px; cursor: pointer; font-family: inherit; transition: .2s; }
.copy-btn:hover { background: #bbf7d0; }

@media (max-width: 1200px) {
    .builder-layout { grid-template-columns: 240px 1fr; }
    .settings-panel { display: none; }
}
@media (max-width: 900px) {
    .builder-layout { grid-template-columns: 1fr; }
    .qtype-palette { position: static; }
}
</style>
</head>
<body>
<?php include __DIR__ . '/includes/sidebar.php'; ?>
<div class="main-content">

<?php if ($msg): ?>
<div class="alert alert-<?= $msgType ?>" id="topMsg"><?= h($msg) ?></div>
<script>setTimeout(()=>document.getElementById('topMsg')?.remove(), 4000)</script>
<?php endif; ?>

<!-- ── صفحه اصلی: لیست آزمون‌ها ───────────────────────────── -->
<?php if (!$editForm): ?>

<div class="page-header">
    <div><h1>📝 آزمون‌های من</h1><p>ایجاد و مدیریت آزمون‌های شما</p></div>
</div>

<!-- فرم ساخت آزمون جدید -->
<div class="card" style="margin-bottom:24px;">
    <div class="card-header"><h3>➕ ساخت آزمون جدید</h3></div>
    <div class="card-body">
        <form method="POST" style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;">
            <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
            <div class="form-group" style="flex:1;min-width:200px;margin:0;">
                <label>عنوان آزمون</label>
                <input class="form-control" name="title" placeholder="مثال: آزمون ریاضی فصل سوم" required>
            </div>
            <div class="form-group" style="flex:2;min-width:250px;margin:0;">
                <label>توضیح (اختیاری)</label>
                <input class="form-control" name="description" placeholder="توضیحات آزمون برای دانش‌آموزان">
            </div>
            <button type="submit" name="create_form" class="btn btn-primary btn-lg">🚀 ساخت و ویرایش</button>
        </form>
    </div>
</div>

<!-- لیست آزمون‌ها -->
<div class="card">
    <div class="card-header"><h3>📋 آزمون‌های موجود (<?= count($myForms) ?>)</h3></div>
    <div class="card-body">
        <?php if ($myForms): ?>
        <div class="forms-grid">
            <?php foreach ($myForms as $f):
                $s = $pdo->prepare("SELECT COUNT(*) FROM questions WHERE form_id=?");
                $s->execute([$f['id']]); $qCount = $s->fetchColumn();
                $s = $pdo->prepare("SELECT COUNT(*) FROM answers WHERE form_id=? AND status='completed'");
                $s->execute([$f['id']]); $aCount = $s->fetchColumn();
            ?>
            <div class="form-card">
                <div>
                    <div class="form-card-title"><?= h($f['title']) ?></div>
                    <?php if ($f['description']): ?>
                    <div style="font-size:12px;color:var(--text-muted);margin-top:4px;"><?= h(mb_substr($f['description'],0,80)) ?><?= mb_strlen($f['description'])>80 ? '...' : '' ?></div>
                    <?php endif; ?>
                </div>
                <div class="form-meta">
                    <span class="meta-tag">❓ <?= $qCount ?> سوال</span>
                    <span class="meta-tag">👥 <?= $aCount ?> شرکت‌کننده</span>
                    <span class="meta-tag">⏱️ <?= $f['duration'] ?> دقیقه</span>
                    <span class="badge <?= $f['is_active'] ? 'badge-green' : 'badge-gray' ?>">
                        <?= $f['is_active'] ? '✅ فعال' : '⏳ پیش‌نویس' ?>
                    </span>
                </div>
                <?php if ($f['is_active'] && $f['exam_link']): ?>
                <div class="exam-link-box">
                    <div class="exam-link-url" id="link_<?= $f['id'] ?>"><?= htmlspecialchars($_SERVER['HTTP_HOST'] ?? 'yoursite.com') ?>/exam/<?= h($f['exam_link']) ?></div>
                    <button class="copy-btn" onclick="copyLink(<?= $f['id'] ?>)">📋 کپی لینک</button>
                </div>
                <?php endif; ?>
                <div class="form-actions">
                    <a href="?edit=<?= $f['id'] ?>" class="btn btn-primary btn-sm">✏️ ویرایش</a>
                    <?php if (!$f['is_active']): ?>
                    <a href="?activate=<?= $f['id'] ?>" class="btn btn-success btn-sm" onclick="return confirm('آزمون فعال شود؟')">🚀 فعال</a>
                    <?php else: ?>
                    <a href="?deactivate=<?= $f['id'] ?>" class="btn btn-warning btn-sm" onclick="return confirm('غیرفعال شود؟')">⛔</a>
                    <?php endif; ?>
                    <a href="results.php?form=<?= $f['id'] ?>" class="btn btn-secondary btn-sm">📊 نتایج</a>
                    <a href="?duplicate=<?= $f['id'] ?>" class="btn btn-secondary btn-sm" onclick="return confirm('کپی شود؟')">📋 کپی</a>
                    <a href="?delete_form=<?= $f['id'] ?>" class="btn btn-danger btn-sm" onclick="return confirm('⚠️ حذف شود؟ پاسخ‌ها هم حذف میشن!')">🗑️</a>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
        <?php else: ?>
        <div class="empty-state">
            <div style="font-size:56px;margin-bottom:16px;">📝</div>
            هنوز آزمونی ساخته نشده. از فرم بالا شروع کنید.
        </div>
        <?php endif; ?>
    </div>
</div>

<?php else: /* ───── صفحه ویرایش آزمون ───── */ ?>

<div class="page-header">
    <div>
        <h1>✏️ فرم‌ساز: <?= h($editForm['title']) ?></h1>
        <p><?= count($questions) ?> سوال | <?= $editForm['duration'] ?> دقیقه | <?= $editForm['is_active'] ? '✅ فعال' : '⏳ پیش‌نویس' ?></p>
    </div>
    <div class="header-actions">
        <?php if (!$editForm['is_active']): ?>
        <a href="?activate=<?= $editId ?>" class="btn btn-success" onclick="return confirm('آزمون فعال شود؟')">🚀 فعال‌سازی</a>
        <?php else: ?>
        <a href="?deactivate=<?= $editId ?>" class="btn btn-warning">⛔ غیرفعال</a>
        <?php endif; ?>
        <a href="create_exam.php" class="btn btn-secondary">← بازگشت</a>
    </div>
</div>

<div class="builder-layout">

    <!-- ── ستون چپ: پالت نوع سوال ── -->
    <div class="qtype-palette card" style="padding:20px;">
        <div style="font-size:14px;font-weight:800;margin-bottom:16px;">➕ افزودن سوال</div>

        <div class="palette-section">
            <div class="palette-title">اطلاعات دانش‌آموز</div>
            <?php foreach (['name_family','national_code','phone'] as $t): ?>
            <button class="qtype-btn" style="color:<?= $questionTypes[$t]['color'] ?>" onclick="openAddModal('<?= $t ?>')">
                <span class="qtype-dot" style="background:<?= $questionTypes[$t]['color'] ?>"></span>
                <?= $questionTypes[$t]['label'] ?>
            </button>
            <?php endforeach; ?>
        </div>

        <div class="palette-section">
            <div class="palette-title">سوالات متنی</div>
            <?php foreach (['short_text','long_text','fill_blank'] as $t): ?>
            <button class="qtype-btn" style="color:<?= $questionTypes[$t]['color'] ?>" onclick="openAddModal('<?= $t ?>')">
                <span class="qtype-dot" style="background:<?= $questionTypes[$t]['color'] ?>"></span>
                <?= $questionTypes[$t]['label'] ?>
            </button>
            <?php endforeach; ?>
        </div>

        <div class="palette-section">
            <div class="palette-title">سوالات با پاسخ صحیح</div>
            <?php foreach (['multiple_choice','multi_select','true_false','dropdown','numeric','rating'] as $t): ?>
            <button class="qtype-btn" style="color:<?= $questionTypes[$t]['color'] ?>" onclick="openAddModal('<?= $t ?>')">
                <span class="qtype-dot" style="background:<?= $questionTypes[$t]['color'] ?>"></span>
                <?= $questionTypes[$t]['label'] ?>
            </button>
            <?php endforeach; ?>
        </div>

        <div class="palette-section">
            <div class="palette-title">ساختار</div>
            <button class="qtype-btn" style="color:#64748b" onclick="openAddModal('section_title')">
                <span class="qtype-dot" style="background:#64748b"></span>
                📌 بخش‌بندی / عنوان
            </button>
        </div>
    </div>

    <!-- ── ستون وسط: بوم سوالات ── -->
    <div>
        <div id="questionsCanvas" class="questions-canvas">
            <?php if ($questions): ?>
                <?php foreach ($questions as $idx => $q):
                    $opts = $q['options'] ? json_decode($q['options'], true) : [];
                    $correct = $q['correct_answer'];
                    $typeInfo = $questionTypes[$q['type']] ?? ['label' => $q['type'], 'color' => '#64748b'];
                ?>
                <div class="q-item" id="qitem_<?= $q['id'] ?>" draggable="true" data-id="<?= $q['id'] ?>">
                    <?php if ($q['type'] !== 'section_title'): ?>
                    <span class="q-pts"><?= (float)$q['points'] ?> pt</span>
                    <?php endif; ?>

                    <div class="q-header">
                        <span class="drag-handle" title="درگ کنید">⠿</span>
                        <?php if ($q['type'] !== 'section_title'): ?>
                        <div class="q-num"><?= $idx + 1 ?></div>
                        <?php endif; ?>
                        <div style="flex:1">
                            <?php if ($q['type'] === 'section_title'): ?>
                            <div style="font-size:18px;font-weight:800;color:#0f172a;border-right:4px solid #6366f1;padding-right:12px;"><?= h($q['title']) ?></div>
                            <?php else: ?>
                            <div class="q-title-text"><?= h($q['title']) ?></div>
                            <?php if ($q['description']): ?>
                            <div style="font-size:12px;color:var(--text-muted);margin-top:4px;"><?= h($q['description']) ?></div>
                            <?php endif; ?>
                            <span class="q-type-tag" style="color:<?= $typeInfo['color'] ?>"><?= $typeInfo['label'] ?></span>
                            <?php if (!$q['required']): ?><span class="q-type-tag" style="margin-right:4px;">اختیاری</span><?php endif; ?>
                            <?php endif; ?>
                        </div>
                        <div class="q-actions">
                            <button class="btn btn-secondary btn-sm" onclick='openEditModal(<?= $q["id"] ?>, <?= json_encode($q) ?>)'>✏️</button>
                            <a href="?delete_q=<?= $q['id'] ?>&form_id=<?= $editId ?>" class="btn btn-danger btn-sm" onclick="return confirm('حذف شود؟')">🗑️</a>
                        </div>
                    </div>

                    <?php if ($opts && in_array($q['type'], ['multiple_choice','multi_select','dropdown'])): ?>
                    <div class="q-options-preview">
                        <?php
                        $corrects = is_string($correct) && str_starts_with($correct, '[') ? json_decode($correct, true) : [$correct];
                        foreach ($opts as $oi => $opt):
                            $isCorrect = in_array((string)($oi+1), array_map('strval', $corrects ?? []));
                        ?>
                        <span class="q-opt-tag <?= $isCorrect ? 'correct' : '' ?>"><?= h($opt) ?></span>
                        <?php endforeach; ?>
                    </div>
                    <?php elseif ($q['type'] === 'true_false'): ?>
                    <div class="q-options-preview">
                        <span class="q-opt-tag <?= $correct==='true' ? 'correct' : '' ?>">✅ درست</span>
                        <span class="q-opt-tag <?= $correct==='false' ? 'correct' : '' ?>">❌ غلط</span>
                    </div>
                    <?php elseif ($q['type'] === 'fill_blank'): ?>
                    <div style="font-size:12px;background:#f8fafc;padding:8px 12px;border-radius:10px;margin-top:8px;">
                        جواب: <strong style="color:var(--success)"><?= h($correct ?? '—') ?></strong>
                    </div>
                    <?php elseif ($q['type'] === 'rating'): ?>
                    <div style="font-size:18px;margin-top:8px;">⭐⭐⭐⭐⭐</div>
                    <?php endif; ?>
                </div>
                <?php endforeach; ?>
            <?php else: ?>
            <div class="empty-canvas">
                <span class="icon">📋</span>
                <strong>هنوز سوالی اضافه نشده</strong><br>
                <small>از پانل چپ نوع سوال را انتخاب کنید</small>
            </div>
            <?php endif; ?>
        </div>

        <!-- کد دسترسی -->
        <?php if ($editForm['is_active'] && $editForm['exam_link']): ?>
        <div class="card" style="margin-top:16px;">
            <div class="card-body">
                <strong>🔗 لینک آزمون:</strong>
                <div class="exam-link-box" style="margin-top:12px;">
                    <div class="exam-link-url" id="editExamLink"><?= htmlspecialchars(($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? 'http') . '://' . ($_SERVER['HTTP_HOST'] ?? 'localhost') . '/exam/' . $editForm['exam_link']) ?></div>
                    <button class="copy-btn" onclick="copyText('editExamLink')">📋 کپی</button>
                </div>
            </div>
        </div>
        <?php endif; ?>
    </div>

    <!-- ── ستون راست: تنظیمات ── -->
    <div class="settings-panel card" style="padding:20px;">
        <div class="settings-tabs">
            <button class="settings-tab active" onclick="switchTab('general',this)">عمومی</button>
            <button class="settings-tab" onclick="switchTab('security',this)">امنیت</button>
            <button class="settings-tab" onclick="switchTab('scoring',this)">نمره</button>
        </div>

        <form method="POST" id="settingsForm">
            <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
            <input type="hidden" name="save_settings" value="1">
            <input type="hidden" name="form_id" value="<?= $editId ?>">

            <!-- General -->
            <div class="setting-section active" id="tab-general">
                <div class="form-group">
                    <label>عنوان آزمون</label>
                    <input class="form-control" name="title" value="<?= h($editForm['title']) ?>" required>
                </div>
                <div class="form-group">
                    <label>توضیحات</label>
                    <textarea class="form-control" name="description" rows="2"><?= h($editForm['description'] ?? '') ?></textarea>
                </div>
                <div class="form-group">
                    <label>مدت زمان (دقیقه)</label>
                    <input class="form-control" type="number" name="duration" value="<?= $editForm['duration'] ?>" min="1" max="600">
                </div>
                <div class="form-group">
                    <label>شروع (اختیاری)</label>
                    <input class="form-control" type="datetime-local" name="start_time" value="<?= $editForm['start_time'] ? date('Y-m-d\TH:i', strtotime($editForm['start_time'])) : '' ?>">
                </div>
                <div class="form-group">
                    <label>پایان (اختیاری)</label>
                    <input class="form-control" type="datetime-local" name="end_time" value="<?= $editForm['end_time'] ? date('Y-m-d\TH:i', strtotime($editForm['end_time'])) : '' ?>">
                </div>
                <div class="setting-row">
                    <div><div class="setting-label">ترتیب تصادفی سوالات</div></div>
                    <label class="toggle"><input type="checkbox" name="shuffle_questions" value="1" <?= $editForm['shuffle_questions'] ? 'checked' : '' ?>><span class="toggle-slider"></span></label>
                </div>
                <div class="setting-row">
                    <div><div class="setting-label">ترتیب تصادفی گزینه‌ها</div></div>
                    <label class="toggle"><input type="checkbox" name="shuffle_options" value="1" <?= $editForm['shuffle_options'] ? 'checked' : '' ?>><span class="toggle-slider"></span></label>
                </div>
                <div class="setting-row">
                    <div><div class="setting-label">اجازه بازگشت</div></div>
                    <label class="toggle"><input type="checkbox" name="allow_back" value="1" <?= $editForm['allow_back'] ? 'checked' : '' ?>><span class="toggle-slider"></span></label>
                </div>
                <div class="form-group" style="margin-top:16px;">
                    <label>نمایش نتایج</label>
                    <select class="form-control" name="show_results">
                        <option value="always" <?= $editForm['show_results']==='always'?'selected':'' ?>>همیشه</option>
                        <option value="never"  <?= $editForm['show_results']==='never'?'selected':'' ?>>هرگز</option>
                        <option value="after_deadline" <?= $editForm['show_results']==='after_deadline'?'selected':'' ?>>بعد از پایان زمان</option>
                    </select>
                </div>
            </div>

            <!-- Security -->
            <div class="setting-section" id="tab-security">
                <div class="setting-row">
                    <div><div class="setting-label">اجبار به تمام‌صفحه</div><div class="setting-sub">خروج = تقلب</div></div>
                    <label class="toggle"><input type="checkbox" name="require_fullscreen" value="1" <?= $editForm['require_fullscreen'] ? 'checked' : '' ?>><span class="toggle-slider"></span></label>
                </div>
                <div class="setting-row" style="margin-top:16px;">
                    <div>
                        <div class="setting-label">📷 آنتی‌چیت وب‌کم</div>
                        <div class="setting-sub">درخواست دوربین از دانش‌آموزان — اسنپشات خودکار</div>
                    </div>
                    <label class="toggle"><input type="checkbox" name="require_camera" value="1" <?= ($editForm['require_camera'] ?? 0) ? 'checked' : '' ?> id="toggleCamera" onchange="toggleCameraSettings()"><span class="toggle-slider"></span></label>
                </div>
                <div class="setting-row" style="margin-top:16px;">
                    <div>
                        <div class="setting-label">📍 آنتی‌چیت GPS</div>
                        <div class="setting-sub">تشخیص دانش‌آموزان کنار هم — خوشه‌بندی تقلب</div>
                    </div>
                    <label class="toggle"><input type="checkbox" name="gps_required" value="1" <?= ($editForm['gps_required'] ?? 0) ? 'checked' : '' ?> id="toggleGps" onchange="toggleGpsSettings()"><span class="toggle-slider"></span></label>
                </div>
                <div id="gpsSettings" style="<?= ($editForm['gps_required'] ?? 0) ? '' : 'display:none' ?>;background:#f8fafc;border-radius:12px;padding:16px;margin-top:12px;">
                    <div class="form-group">
                        <label>مرکز آزمون (عرض جغرافیایی)</label>
                        <input class="form-control" type="number" step="any" name="gps_lat" placeholder="مثال: 35.6892" value="<?= $editForm['gps_lat'] ?? '' ?>">
                    </div>
                    <div class="form-group">
                        <label>مرکز آزمون (طول جغرافیایی)</label>
                        <input class="form-control" type="number" step="any" name="gps_lng" placeholder="مثال: 51.3890" value="<?= $editForm['gps_lng'] ?? '' ?>">
                    </div>
                    <div class="form-group">
                        <label>شعاع مجاز (متر) — 500 پیش‌فرض</label>
                        <input class="form-control" type="number" name="gps_radius" value="<?= $editForm['gps_radius'] ?? 500 ?>" min="10" max="10000">
                    </div>
                    <p style="font-size:12px;color:#64748b;">💡 می‌توانید مختصات را از Google Maps دریافت کنید. اگر خالی بگذارید فقط تقلب گروهی (کنار هم) بررسی می‌شود.</p>
                </div>
                <div class="form-group" style="margin-top:16px;">
                    <label>حداکثر تلاش مجاز</label>
                    <input class="form-control" type="number" name="max_attempts" value="<?= $editForm['max_attempts'] ?>" min="1" max="99">
                </div>
                <div class="form-group">
                    <label>رمز عبور آزمون (اختیاری)</label>
                    <input class="form-control" type="password" name="exam_password" placeholder="خالی = بدون رمز" value="<?= $editForm['password'] ? '••••••' : '' ?>">
                </div>
                <!-- QR Code -->
                <?php if ($editForm['exam_link']): ?>
                <div style="margin-top:16px;text-align:center;">
                    <div style="font-size:13px;font-weight:700;margin-bottom:8px;color:#0f172a;">🔗 QR Code لینک آزمون</div>
                    <div id="qrcode" style="display:inline-block;background:white;padding:12px;border-radius:12px;border:2px solid #e2e8f0;"></div>
                    <div style="font-size:11px;color:#64748b;margin-top:8px;word-break:break-all;"><?= h($_SERVER['HTTP_HOST'] . '/exam_platform/exam/' . $editForm['exam_link']) ?></div>
                </div>
                <?php endif; ?>
            </div>

            <!-- Scoring -->
            <div class="setting-section" id="tab-scoring">
                <div class="form-group">
                    <label>نمره منفی به ازای جواب غلط (0 = بدون)</label>
                    <input class="form-control" type="number" name="negative_marking" value="<?= $editForm['negative_marking'] ?>" min="0" max="5" step="0.25">
                </div>
                <div class="form-group">
                    <label>حد قبولی (درصد - 0 = ندارد)</label>
                    <input class="form-control" type="number" name="pass_threshold" value="<?= $editForm['pass_threshold'] ?>" min="0" max="100">
                </div>
            </div>

            <button type="submit" class="btn btn-primary" style="width:100%;margin-top:16px;">💾 ذخیره تنظیمات</button>
        </form>
    </div>

</div><!-- /builder-layout -->

<?php endif; ?>
</div><!-- /main-content -->

<!-- ════ مودال افزودن/ویرایش سوال ════ -->
<div class="modal-overlay" id="qModal">
<div class="modal" style="max-width:640px;">
    <div class="modal-header">
        <h3 id="modalTitle">افزودن سوال</h3>
        <button class="modal-close" onclick="closeModal()">×</button>
    </div>
    <div class="q-modal-body" id="qModalBody">
        <!-- dynamic content -->
    </div>
    <div style="display:flex;gap:12px;margin-top:24px;">
        <button class="btn btn-primary" style="flex:1" onclick="saveQuestion()">💾 ذخیره</button>
        <button class="btn btn-secondary" onclick="closeModal()">انصراف</button>
    </div>
</div>
</div>

<script>
const FORM_ID = <?= $editId ?>;
let editingQid = 0;
let currentType = '';

function toggleGpsSettings() {
    const el = document.getElementById('gpsSettings');
    if (el) el.style.display = document.getElementById('toggleGps')?.checked ? 'block' : 'none';
}
function toggleCameraSettings() { /* placeholder for future per-exam camera settings */ }

// QR Code (pure JS - no external lib)
<?php if ($editForm['exam_link'] ?? ''): ?>
(function(){
    const url = window.location.protocol + '//' + window.location.host + '/exam_platform/exam/<?= h($editForm['exam_link']) ?>';
    const container = document.getElementById('qrcode');
    if (!container) return;
    // Use qrserver.com API (free, no login required)
    const img = document.createElement('img');
    img.src = 'https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=' + encodeURIComponent(url);
    img.alt = 'QR Code';
    img.style.borderRadius = '8px';
    container.appendChild(img);
})();
<?php endif; ?>

const typeNames = <?= json_encode(array_map(fn($t) => $t['label'], $questionTypes), JSON_UNESCAPED_UNICODE) ?>;
const typesWithOptions = ['multiple_choice','multi_select','dropdown'];
const typesWithCorrect = ['multiple_choice','multi_select','true_false','dropdown','numeric','fill_blank'];

// ── Open/Close Modal ──────────────────────────────────────────────
function openAddModal(type) {
    editingQid = 0;
    currentType = type;
    document.getElementById('modalTitle').textContent = 'افزودن: ' + (typeNames[type] || type);
    renderModalBody(type, null);
    document.getElementById('qModal').classList.add('open');
}

function openEditModal(qid, qData) {
    editingQid = qid;
    currentType = qData.type;
    document.getElementById('modalTitle').textContent = 'ویرایش سوال';
    renderModalBody(qData.type, qData);
    document.getElementById('qModal').classList.add('open');
}

function closeModal() {
    document.getElementById('qModal').classList.remove('open');
    editingQid = 0;
}

// ── Render Modal Body ─────────────────────────────────────────────
function renderModalBody(type, data) {
    const body = document.getElementById('qModalBody');
    const title = data?.title || '';
    const desc  = data?.description || '';
    const pts   = data?.points || 1;
    const req   = data?.required !== false;
    const hint  = data?.hint || '';
    const opts  = (() => { try { return typeof data?.options === 'string' ? JSON.parse(data.options) : (data?.options || []); } catch(e){ return []; } })();
    const correct = data?.correct_answer || '';

    let html = '';

    // ── Title ──
    if (type === 'section_title') {
        html += `<div class="form-group">
            <label>عنوان بخش</label>
            <input class="form-control" id="q_title" value="${esc(title)}" placeholder="عنوان بخش جدید..." required>
        </div>`;
    } else {
        html += `<div class="form-group">
            <label>متن سوال <span style="color:red">*</span></label>
            <textarea class="form-control" id="q_title" rows="3" placeholder="سوال خود را بنویسید...">${esc(title)}</textarea>
        </div>
        <div class="form-group">
            <label>توضیحات اضافی (اختیاری)</label>
            <input class="form-control" id="q_desc" value="${esc(desc)}" placeholder="راهنمایی برای دانش‌آموز...">
        </div>`;
    }

    // ── Type-specific ──
    if (type === 'true_false') {
        html += `<div class="form-group">
            <label>پاسخ صحیح</label>
            <div style="display:flex;gap:16px;margin-top:8px;">
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;padding:12px 20px;border:2px solid var(--border);border-radius:16px;transition:.2s;" id="lbl_true">
                    <input type="radio" name="tf_correct" value="true" ${correct==='true'?'checked':''}> ✅ درست
                </label>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;padding:12px 20px;border:2px solid var(--border);border-radius:16px;transition:.2s;" id="lbl_false">
                    <input type="radio" name="tf_correct" value="false" ${correct==='false'?'checked':''}> ❌ غلط
                </label>
            </div>
        </div>`;
    } else if (typesWithOptions.includes(type)) {
        const isMulti = type === 'multi_select';
        let corrects = [];
        if (correct) {
            try { corrects = typeof correct === 'string' && correct.startsWith('[') ? JSON.parse(correct) : [String(correct)]; }
            catch(e) { corrects = [String(correct)]; }
        }
        html += `<div class="form-group">
            <label>گزینه‌ها</label>
            <div class="options-editor" id="optsList">`;
        if (opts.length > 0) {
            opts.forEach((opt,i) => {
                const iC = corrects.includes(String(i+1));
                html += renderOptionRow(i, opt, type, iC);
            });
        }
        html += `</div>
            <button type="button" class="add-option-btn" onclick="addOptionRow('${type}')">+ افزودن گزینه</button>
        </div>
        <div class="form-group">
            <label>${isMulti ? 'گزینه‌های صحیح (چند تا انتخاب کنید)' : 'گزینه صحیح'}</label>
            <p style="font-size:12px;color:var(--text-muted);margin-top:4px;">${isMulti ? 'چند چک‌باکس را تیک بزنید' : 'رادیوباتن کنار گزینه را انتخاب کنید'}</p>
        </div>`;
    } else if (type === 'numeric') {
        html += `<div class="form-group">
            <label>پاسخ عددی صحیح</label>
            <input class="form-control" type="number" id="q_numeric_answer" step="any" value="${esc(correct)}" placeholder="عدد صحیح را وارد کنید">
        </div>`;
    } else if (type === 'fill_blank') {
        html += `<div class="blank-editor">
            <div class="blank-hint">متن سوال را بالا بنویسید. پاسخ جای‌خالی را اینجا وارد کنید:</div>
            <input class="form-control" id="q_blank_answer" value="${esc(correct)}" placeholder="کلمه یا عبارت جای‌خالی">
        </div>`;
    } else if (type === 'rating') {
        html += `<div class="form-group">
            <label>حداکثر ستاره</label>
            <select class="form-control" id="q_rating_max">
                ${[3,4,5,6,7,8,9,10].map(n=>`<option ${(opts[0]||5)==n?'selected':''}>${n}</option>`).join('')}
            </select>
        </div>`;
    }

    // ── Points & Required (not for info fields or section_title) ──
    if (!['name_family','national_code','phone','section_title'].includes(type)) {
        html += `<div style="display:flex;gap:16px;">
            <div class="form-group" style="flex:1">
                <label>امتیاز سوال</label>
                <input class="form-control points-input" type="number" id="q_points" value="${pts}" min="0" max="100" step="0.5">
            </div>
            <div class="form-group" style="flex:1">
                <label>اجباری؟</label>
                <select class="form-control" id="q_required">
                    <option value="1" ${req?'selected':''}>بله</option>
                    <option value="0" ${!req?'selected':''}>خیر</option>
                </select>
            </div>
        </div>
        <div class="form-group">
            <label>راهنمایی (Hint) - اختیاری</label>
            <input class="form-control" id="q_hint" value="${esc(hint)}" placeholder="مثلاً: به فصل سوم مراجعه کنید">
        </div>`;
    }

    body.innerHTML = html;
}

function renderOptionRow(i, text, type, isCorrect) {
    const isMulti = type === 'multi_select';
    const inputType = isMulti ? 'checkbox' : 'radio';
    const name = isMulti ? `opt_correct[]` : `opt_correct`;
    return `<div class="option-row" id="optrow_${i}">
        <span style="font-size:12px;font-weight:700;color:var(--text-muted);width:20px;">${i+1}</span>
        <input class="form-control" type="text" id="opttext_${i}" value="${esc(text)}" placeholder="گزینه ${i+1}" style="flex:1;">
        <input type="${inputType}" name="${name}" value="${i+1}" class="option-correct" title="پاسخ صحیح" ${isCorrect?'checked':''}>
        <button type="button" class="option-del" onclick="removeOption(${i})">✕</button>
    </div>`;
}

let optCount = 0;
function addOptionRow(type) {
    const container = document.getElementById('optsList');
    const rows = container.querySelectorAll('.option-row');
    const idx = rows.length;
    optCount = idx;
    const div = document.createElement('div');
    div.innerHTML = renderOptionRow(idx, '', type, false);
    container.appendChild(div.firstElementChild);
}

function removeOption(i) {
    const el = document.getElementById('optrow_' + i);
    if (el) el.remove();
    // renumber
    document.querySelectorAll('.option-row').forEach((row, ni) => {
        row.id = 'optrow_' + ni;
        const sp = row.querySelector('span'); if(sp) sp.textContent = ni+1;
        const inp = row.querySelector('input[type=text]'); if(inp) { inp.id = 'opttext_'+ni; inp.placeholder = 'گزینه '+(ni+1); }
        const radio = row.querySelector('input[type=radio],input[type=checkbox]'); if(radio) radio.value = ni+1;
        const del = row.querySelector('.option-del'); if(del) del.setAttribute('onclick', 'removeOption('+ni+')');
    });
}

// ── Save Question ────────────────────────────────────────────────
async function saveQuestion() {
    const titleEl = document.getElementById('q_title');
    if (!titleEl || !titleEl.value.trim()) { alert('لطفاً متن سوال را وارد کنید'); return; }

    const payload = {
        save_question: true,
        form_id: FORM_ID,
        question_id: editingQid,
        type: currentType,
        title: titleEl.value.trim(),
        description: document.getElementById('q_desc')?.value?.trim() || '',
        points: parseFloat(document.getElementById('q_points')?.value || '1'),
        required: parseInt(document.getElementById('q_required')?.value || '1'),
        hint: document.getElementById('q_hint')?.value?.trim() || '',
        options: null,
        correct_answer: null,
    };

    // ── collect options & correct ──
    if (currentType === 'true_false') {
        const sel = document.querySelector('input[name=tf_correct]:checked');
        if (!sel) { alert('پاسخ صحیح را انتخاب کنید'); return; }
        payload.correct_answer = sel.value;

    } else if (typesWithOptions.includes(currentType)) {
        const rows = document.querySelectorAll('#optsList .option-row');
        if (rows.length < 2) { alert('حداقل ۲ گزینه نیاز است'); return; }
        payload.options = [];
        rows.forEach((row, i) => {
            const inp = row.querySelector('input[type=text]');
            if (inp) payload.options.push(inp.value.trim() || '...');
        });
        const checked = document.querySelectorAll('input[name="opt_correct"]:checked, input[name="opt_correct[]"]:checked');
        if (checked.length === 0) { alert('پاسخ صحیح را مشخص کنید'); return; }
        const vals = Array.from(checked).map(c => c.value);
        payload.correct_answer = vals.length === 1 ? vals[0] : JSON.stringify(vals);

    } else if (currentType === 'numeric') {
        const v = document.getElementById('q_numeric_answer')?.value;
        if (v === '' || v === null) { alert('پاسخ عددی را وارد کنید'); return; }
        payload.correct_answer = v;

    } else if (currentType === 'fill_blank') {
        const v = document.getElementById('q_blank_answer')?.value?.trim();
        if (!v) { alert('پاسخ جای‌خالی را وارد کنید'); return; }
        payload.correct_answer = v;

    } else if (currentType === 'rating') {
        const max = document.getElementById('q_rating_max')?.value || '5';
        payload.options = [max];
    }

    try {
        const res = await fetch('create_exam.php', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('input[name=csrf_token]')?.value || ''},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            closeModal();
            location.reload();
        } else {
            alert('خطا: ' + (data.error || 'نامشخص'));
        }
    } catch(e) {
        alert('خطای ارتباط: ' + e.message);
    }
}

// ── Settings Tabs ────────────────────────────────────────────────
function switchTab(tab, btn) {
    document.querySelectorAll('.setting-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.settings-tab').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    btn.classList.add('active');
}

// ── Copy Link ────────────────────────────────────────────────────
function copyLink(fid) {
    const el = document.getElementById('link_' + fid);
    if (el) copyText(el.id);
}

function copyText(id) {
    const el = document.getElementById(id);
    if (!el) return;
    navigator.clipboard.writeText(el.textContent).then(() => {
        const original = el.nextElementSibling?.textContent;
        if (el.nextElementSibling) {
            el.nextElementSibling.textContent = '✅ کپی شد!';
            setTimeout(() => { if (el.nextElementSibling) el.nextElementSibling.textContent = original; }, 2000);
        }
    });
}

// ── Drag & Drop Reorder ──────────────────────────────────────────
(function initDrag() {
    const canvas = document.getElementById('questionsCanvas');
    if (!canvas) return;
    let dragged = null;
    canvas.addEventListener('dragstart', e => {
        dragged = e.target.closest('[data-id]');
        if (dragged) dragged.classList.add('dragging');
    });
    canvas.addEventListener('dragover', e => {
        e.preventDefault();
        const target = e.target.closest('[data-id]');
        if (target && dragged && target !== dragged) {
            const rect = target.getBoundingClientRect();
            const mid = rect.top + rect.height / 2;
            if (e.clientY < mid) canvas.insertBefore(dragged, target);
            else canvas.insertBefore(dragged, target.nextSibling);
        }
    });
    canvas.addEventListener('dragend', () => {
        if (dragged) dragged.classList.remove('dragging');
        // Save new order
        const ids = Array.from(canvas.querySelectorAll('[data-id]')).map(el => el.dataset.id);
        fetch('create_exam.php', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'reorder=1&order=' + JSON.stringify(ids)
        });
    });
})();

// ── Close modal on backdrop click ────────────────────────────────
document.getElementById('qModal').addEventListener('click', e => {
    if (e.target === document.getElementById('qModal')) closeModal();
});

// ── Escape HTML ──────────────────────────────────────────────────
function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
</script>
</body>
</html>
