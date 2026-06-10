<?php
/**
 * teacher/question_bank.php - بانک سوال
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
$teacher = requireTeacherAuth();
$tid = $teacher['id'];
$msg = '';

// حذف سوال
if (isset($_GET['delete'])) {
    $qid = validateInt($_GET['delete'], 1);
    if ($qid) $pdo->prepare("DELETE FROM question_bank WHERE id=? AND teacher_id=?")->execute([$qid, $tid]);
    redirect('question_bank.php?msg=deleted');
}
if (isset($_GET['msg'])) $msg = ['deleted'=>'✅ حذف شد', 'added'=>'✅ اضافه شد'][$_GET['msg']] ?? '';

// ذخیره سوال جدید (AJAX)
if ($_SERVER['REQUEST_METHOD']==='POST' && isset($_POST['save_bank_q'])) {
    header('Content-Type: application/json');
    requireCsrf();
    $type    = sanitizeString($_POST['type'] ?? '', 50);
    $title   = trim($_POST['title'] ?? '');
    $cat     = sanitizeString($_POST['category'] ?? '', 100);
    $diff    = in_array($_POST['difficulty']??'', ['easy','medium','hard']) ? $_POST['difficulty'] : 'medium';
    $opts    = $_POST['options'] ?? null;
    $correct = $_POST['correct_answer'] ?? null;
    $pts     = max(0, min(100, (float)($_POST['points'] ?? 1)));
    $tags    = sanitizeString($_POST['tags'] ?? '', 300);

    if (empty($title)) { echo json_encode(['success'=>false,'error'=>'متن سوال خالی است']); exit(); }

    $opts_json = is_array($opts) ? json_encode($opts, JSON_UNESCAPED_UNICODE) : null;
    $pdo->prepare("INSERT INTO question_bank (teacher_id,type,title,options,correct_answer,points,category,difficulty,tags) VALUES (?,?,?,?,?,?,?,?,?)")
        ->execute([$tid, $type, $title, $opts_json, $correct, $pts, $cat, $diff, $tags]);
    echo json_encode(['success'=>true, 'id'=>(int)$pdo->lastInsertId()]);
    exit();
}

// Import to exam
if ($_SERVER['REQUEST_METHOD']==='POST' && isset($_POST['import_to_exam'])) {
    requireCsrf();
    $fid  = validateInt($_POST['form_id'] ?? 0, 1);
    $qids = array_map('intval', $_POST['question_ids'] ?? []);
    if ($fid && $qids) {
        $s = $pdo->prepare("SELECT id FROM forms WHERE id=? AND teacher_id=?");
        $s->execute([$fid, $tid]);
        if ($s->fetch()) {
            $s = $pdo->prepare("SELECT COALESCE(MAX(order_index),0) FROM questions WHERE form_id=?");
            $s->execute([$fid]);
            $ord = (int)$s->fetchColumn() + 1;

            $qStmt = $pdo->prepare("SELECT * FROM question_bank WHERE id=? AND teacher_id=?");
            $ins   = $pdo->prepare("INSERT INTO questions (form_id,type,title,options,correct_answer,points,order_index) VALUES (?,?,?,?,?,?,?)");
            $upd   = $pdo->prepare("UPDATE question_bank SET use_count=use_count+1 WHERE id=?");

            foreach ($qids as $qid) {
                $qStmt->execute([$qid, $tid]);
                $bq = $qStmt->fetch();
                if ($bq) {
                    $ins->execute([$fid, $bq['type'], $bq['title'], $bq['options'], $bq['correct_answer'], $bq['points'], $ord++]);
                    $upd->execute([$qid]);
                }
            }
            $msg = '✅ سوالات به آزمون اضافه شدند';
        }
    }
}

// دریافت سوالات بانک
$search = sanitizeString($_GET['search'] ?? '', 100);
$cat    = sanitizeString($_GET['cat'] ?? '', 100);
$diff   = in_array($_GET['diff']??'', ['easy','medium','hard','']) ? ($_GET['diff']??'') : '';

$where = ["teacher_id=?"];
$params = [$tid];
if ($search) { $where[] = "title LIKE ?"; $params[] = "%$search%"; }
if ($cat)    { $where[] = "category=?"; $params[] = $cat; }
if ($diff)   { $where[] = "difficulty=?"; $params[] = $diff; }

$sql = "SELECT * FROM question_bank WHERE " . implode(' AND ', $where) . " ORDER BY id DESC";
$s = $pdo->prepare($sql); $s->execute($params);
$bankQs = $s->fetchAll();

// دریافت آزمون‌ها برای import
$s = $pdo->prepare("SELECT id,title FROM forms WHERE teacher_id=? ORDER BY id DESC");
$s->execute([$tid]);
$myForms = $s->fetchAll();

// کتگوری‌ها
$s = $pdo->prepare("SELECT DISTINCT category FROM question_bank WHERE teacher_id=? AND category IS NOT NULL AND category!='' ORDER BY category");
$s->execute([$tid]);
$categories = $s->fetchAll(PDO::FETCH_COLUMN);

$csrf = generateCsrfToken();
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>بانک سوال</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<style>
<?php include __DIR__ . '/../assets/css/panel.css'; ?>
.diff-badge{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;}
.diff-easy  {background:#dcfce7;color:#166534;}
.diff-medium{background:#fef3c7;color:#92400e;}
.diff-hard  {background:#fee2e2;color:#991b1b;}
.bank-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;}
.bank-card{background:white;border:1.5px solid var(--border);border-radius:16px;padding:18px;transition:.2s;}
.bank-card:hover{border-color:var(--primary);box-shadow:0 4px 16px rgba(99,102,241,.1);}
.bank-card input[type=checkbox]{width:18px;height:18px;margin-left:8px;accent-color:var(--primary);}
.use-count{font-size:11px;color:var(--text-muted);background:#f1f5f9;padding:2px 8px;border-radius:20px;}
</style>
</head>
<body>
<?php include __DIR__ . '/includes/sidebar.php'; ?>
<div class="main-content">

<?php if ($msg): ?>
<div class="alert alert-success" id="flashMsg"><?= h($msg) ?></div>
<script>setTimeout(()=>document.getElementById('flashMsg')?.remove(),4000)</script>
<?php endif; ?>

<div class="page-header">
    <div><h1>🏦 بانک سوال</h1><p>ذخیره و مدیریت سوالات قابل استفاده مجدد</p></div>
    <button class="btn btn-primary" onclick="document.getElementById('addModal').classList.add('open')">➕ سوال جدید</button>
</div>

<!-- Filter + Import -->
<div class="card" style="margin-bottom:24px;">
    <div class="card-body">
        <form method="GET" style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;">
            <div class="form-group" style="flex:2;margin:0;">
                <label>جستجو</label>
                <input class="form-control" name="search" value="<?= h($search) ?>" placeholder="متن سوال...">
            </div>
            <div class="form-group" style="flex:1;margin:0;">
                <label>دسته‌بندی</label>
                <select class="form-control" name="cat">
                    <option value="">همه</option>
                    <?php foreach ($categories as $c): ?>
                    <option <?= $cat===$c?'selected':'' ?>><?= h($c) ?></option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div class="form-group" style="flex:1;margin:0;">
                <label>سختی</label>
                <select class="form-control" name="diff">
                    <option value="">همه</option>
                    <option value="easy"   <?= $diff==='easy'?'selected':'' ?>>آسان</option>
                    <option value="medium" <?= $diff==='medium'?'selected':'' ?>>متوسط</option>
                    <option value="hard"   <?= $diff==='hard'?'selected':'' ?>>سخت</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary">🔍 فیلتر</button>
        </form>
    </div>
</div>

<!-- Import to exam form -->
<?php if ($myForms && $bankQs): ?>
<div class="card" style="margin-bottom:24px;">
    <div class="card-header"><h3>📤 افزودن به آزمون</h3></div>
    <div class="card-body">
        <form method="POST" id="importForm" style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;">
            <input type="hidden" name="csrf_token" value="<?= h($csrf) ?>">
            <input type="hidden" name="import_to_exam" value="1">
            <div class="form-group" style="flex:1;margin:0;">
                <label>انتخاب آزمون</label>
                <select class="form-control" name="form_id" required>
                    <option value="">انتخاب آزمون...</option>
                    <?php foreach ($myForms as $f): ?>
                    <option value="<?= $f['id'] ?>"><?= h($f['title']) ?></option>
                    <?php endforeach; ?>
                </select>
            </div>
            <button type="submit" class="btn btn-success">📤 افزودن سوالات انتخاب‌شده</button>
        </form>
    </div>
</div>
<?php endif; ?>

<!-- Bank Cards -->
<div class="card">
    <div class="card-header">
        <h3>📋 سوالات بانک (<?= count($bankQs) ?>)</h3>
        <?php if ($bankQs): ?><button class="btn btn-secondary btn-sm" onclick="toggleAll()">انتخاب همه</button><?php endif; ?>
    </div>
    <div class="card-body">
        <?php if ($bankQs): ?>
        <div class="bank-grid">
            <?php foreach ($bankQs as $q):
                $opts = $q['options'] ? json_decode($q['options'], true) : [];
            ?>
            <div class="bank-card">
                <div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:10px;">
                    <input type="checkbox" name="question_ids[]" value="<?= $q['id'] ?>" form="importForm" class="bank-cb">
                    <div style="flex:1;">
                        <div style="font-weight:700;font-size:14px;line-height:1.5;"><?= h(mb_substr($q['title'],0,100)) ?><?= mb_strlen($q['title'])>100?'...':'' ?></div>
                        <?php if ($q['category']): ?>
                        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;"><?= h($q['category']) ?></div>
                        <?php endif; ?>
                    </div>
                </div>
                <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
                    <span class="diff-badge diff-<?= $q['difficulty'] ?>"><?= ['easy'=>'آسان','medium'=>'متوسط','hard'=>'سخت'][$q['difficulty']] ?></span>
                    <span style="background:#ede9fe;color:#5b21b6;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:700;"><?= $q['points'] ?> pt</span>
                    <span class="use-count">استفاده: <?= $q['use_count'] ?></span>
                    <a href="?delete=<?= $q['id'] ?>" class="btn btn-danger btn-sm" style="margin-right:auto;" onclick="return confirm('حذف شود؟')">🗑️</a>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
        <?php else: ?>
        <div class="empty-state">
            <div style="font-size:48px;margin-bottom:12px;">🏦</div>
            هنوز سوالی در بانک وجود ندارد.<br>
            <button class="btn btn-primary" style="margin-top:16px;" onclick="document.getElementById('addModal').classList.add('open')">➕ اولین سوال را اضافه کنید</button>
        </div>
        <?php endif; ?>
    </div>
</div>

</div>

<!-- Add Question Modal -->
<div class="modal-overlay" id="addModal">
    <div class="modal" style="max-width:560px;">
        <div class="modal-header"><h3>➕ سوال جدید به بانک</h3><button class="modal-close" onclick="document.getElementById('addModal').classList.remove('open')">×</button></div>
        <div class="form-group">
            <label>نوع سوال</label>
            <select class="form-control" id="bqType" onchange="renderBankForm()">
                <option value="multiple_choice">چندگزینه‌ای</option>
                <option value="true_false">صحیح/غلط</option>
                <option value="short_text">متن کوتاه</option>
                <option value="numeric">عددی</option>
                <option value="fill_blank">جای‌خالی</option>
            </select>
        </div>
        <div class="form-group">
            <label>متن سوال</label>
            <textarea class="form-control" id="bqTitle" rows="3" placeholder="سوال خود را بنویسید..."></textarea>
        </div>
        <div id="bqExtraFields"></div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
            <div class="form-group">
                <label>دسته‌بندی</label>
                <input class="form-control" id="bqCat" placeholder="مثال: ریاضی">
            </div>
            <div class="form-group">
                <label>امتیاز</label>
                <input class="form-control" type="number" id="bqPts" value="1" min="0" max="100" step="0.5">
            </div>
            <div class="form-group">
                <label>سختی</label>
                <select class="form-control" id="bqDiff">
                    <option value="easy">آسان</option>
                    <option value="medium" selected>متوسط</option>
                    <option value="hard">سخت</option>
                </select>
            </div>
        </div>
        <div style="display:flex;gap:12px;margin-top:8px;">
            <button class="btn btn-primary" style="flex:1" onclick="saveBankQ()">💾 ذخیره در بانک</button>
            <button class="btn btn-secondary" onclick="document.getElementById('addModal').classList.remove('open')">انصراف</button>
        </div>
    </div>
</div>

<script>
let bqOpts = ['', '', '', ''];
let bqCorrect = 1;

function renderBankForm() {
    const type = document.getElementById('bqType').value;
    const el = document.getElementById('bqExtraFields');
    if (type === 'multiple_choice') {
        let html = '<div class="form-group"><label>گزینه‌ها (پاسخ صحیح را تیک بزنید)</label>';
        bqOpts.forEach((opt,i)=>{
            html += `<div style="display:flex;gap:8px;margin-bottom:8px;align-items:center;">
                <input type="radio" name="bq_correct" value="${i}" ${bqCorrect===i?'checked':''}  onchange="bqCorrect=${i}" style="accent-color:var(--success);">
                <input class="form-control" id="bqopt_${i}" value="${opt}" placeholder="گزینه ${i+1}" oninput="bqOpts[${i}]=this.value">
            </div>`;
        });
        html += `<button type="button" onclick="addBqOpt()" class="btn btn-secondary btn-sm" style="margin-top:6px;">+ گزینه</button></div>`;
        el.innerHTML = html;
    } else if (type === 'true_false') {
        el.innerHTML = `<div class="form-group"><label>پاسخ صحیح</label><select class="form-control" id="bqTF"><option value="true">درست</option><option value="false">غلط</option></select></div>`;
    } else if (type === 'numeric') {
        el.innerHTML = `<div class="form-group"><label>عدد صحیح</label><input class="form-control" type="number" id="bqNumeric" step="any"></div>`;
    } else if (type === 'fill_blank') {
        el.innerHTML = `<div class="form-group"><label>پاسخ جای‌خالی</label><input class="form-control" id="bqBlank" placeholder="کلمه یا عبارت"></div>`;
    } else {
        el.innerHTML = '';
    }
}

function addBqOpt() {
    bqOpts.push('');
    renderBankForm();
}

async function saveBankQ() {
    const type   = document.getElementById('bqType').value;
    const title  = document.getElementById('bqTitle').value.trim();
    const cat    = document.getElementById('bqCat').value.trim();
    const pts    = document.getElementById('bqPts').value;
    const diff   = document.getElementById('bqDiff').value;
    if (!title) { alert('متن سوال خالی است'); return; }

    const payload = new FormData();
    payload.append('save_bank_q', '1');
    payload.append('csrf_token', '<?= h($csrf) ?>');
    payload.append('type', type);
    payload.append('title', title);
    payload.append('category', cat);
    payload.append('points', pts);
    payload.append('difficulty', diff);

    if (type === 'multiple_choice') {
        bqOpts.forEach((o,i)=>payload.append('options[]', document.getElementById('bqopt_'+i)?.value.trim()||o));
        payload.append('correct_answer', String(bqCorrect+1));
    } else if (type === 'true_false') {
        payload.append('correct_answer', document.getElementById('bqTF')?.value || 'true');
    } else if (type === 'numeric') {
        payload.append('correct_answer', document.getElementById('bqNumeric')?.value || '');
    } else if (type === 'fill_blank') {
        payload.append('correct_answer', document.getElementById('bqBlank')?.value.trim() || '');
    }

    const res  = await fetch('question_bank.php', {method:'POST', body:payload});
    const data = await res.json();
    if (data.success) { location.reload(); }
    else alert('خطا: ' + data.error);
}

function toggleAll() {
    const cbs = document.querySelectorAll('.bank-cb');
    const anyUnchecked = Array.from(cbs).some(c=>!c.checked);
    cbs.forEach(c=>c.checked=anyUnchecked);
}

document.getElementById('addModal').addEventListener('click',function(e){if(e.target===this)this.classList.remove('open');});
renderBankForm();
</script>
</body>
</html>
