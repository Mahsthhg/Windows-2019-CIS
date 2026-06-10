<?php
/**
 * teacher/results.php - نتایج پیشرفته با آنالیتیکس + خروجی CSV
 */
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../config/security.php';
$teacher = requireTeacherAuth();
$tid = $teacher['id'];

// Export CSV
if (isset($_GET['export_csv']) && isset($_GET['form'])) {
    $fid = validateInt($_GET['form'], 1);
    if (!$fid) die('');
    $s = $pdo->prepare("SELECT id FROM forms WHERE id=? AND teacher_id=?");
    $s->execute([$fid, $tid]);
    if (!$s->fetch()) die('');

    $s = $pdo->prepare("SELECT a.*, f.title as exam_title FROM answers a JOIN forms f ON a.form_id=f.id WHERE a.form_id=? AND a.status='completed' ORDER BY a.submitted_at DESC");
    $s->execute([$fid]);
    $rows = $s->fetchAll();

    header('Content-Type: text/csv; charset=UTF-8');
    header('Content-Disposition: attachment; filename="results_' . $fid . '.csv"');
    header('Cache-Control: no-cache');
    echo "\xEF\xBB\xBF"; // UTF-8 BOM for Excel
    $out = fopen('php://output', 'w');
    fputcsv($out, ['نام', 'کد ملی', 'شماره تماس', 'نمره', 'حداکثر نمره', 'درصد', 'صحیح', 'غلط', 'خالی', 'تقلب', 'زمان', 'IP']);
    foreach ($rows as $r) {
        $pct = $r['max_score'] > 0 ? round($r['score']/$r['max_score']*100) : 0;
        fputcsv($out, [$r['user_name'], $r['user_national'], $r['user_phone'], $r['score'], $r['max_score'], "$pct%", $r['correct_count'], $r['wrong_count'], $r['empty_count'], $r['cheat_count'], $r['submitted_at'], $r['user_ip']]);
    }
    fclose($out);
    exit();
}

// ریست تلاش یک شرکت‌کننده — فقط POST با CSRF و بررسی مالکیت (قبل از هر خروجی)
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['reset_attempt'])) {
    requireCsrf();
    $rid  = validateInt($_POST['reset_attempt'], 1);
    $rfid = validateInt($_POST['form'] ?? 0, 1);
    if ($rid && $rfid) {
        // فقط اگر آزمون متعلق به همین معلم باشد
        $s = $pdo->prepare("
            SELECT a.id FROM answers a
            JOIN forms f ON f.id = a.form_id
            WHERE a.id=? AND a.form_id=? AND f.teacher_id=?
        ");
        $s->execute([$rid, $rfid, $tid]);
        if ($s->fetch()) {
            $pdo->prepare("DELETE FROM answers WHERE id=?")->execute([$rid]);
        }
    }
    redirect('results.php?form=' . (int)$rfid . '&msg=reset');
}

// دریافت لیست آزمون‌های معلم
$s = $pdo->prepare("SELECT f.*, COUNT(a.id) as participant_count FROM forms f LEFT JOIN answers a ON a.form_id=f.id AND a.status='completed' WHERE f.teacher_id=? GROUP BY f.id ORDER BY f.id DESC");
$s->execute([$tid]);
$forms = $s->fetchAll();

$selectedForm = null;
$results      = [];
$analytics    = [];

$fid = validateInt($_GET['form'] ?? 0, 0) ?? 0;
if ($fid) {
    $s = $pdo->prepare("SELECT * FROM forms WHERE id=? AND teacher_id=?");
    $s->execute([$fid, $tid]);
    $selectedForm = $s->fetch();

    if ($selectedForm) {
        $s = $pdo->prepare("SELECT * FROM answers WHERE form_id=? AND status='completed' ORDER BY submitted_at DESC");
        $s->execute([$fid]);
        $results = $s->fetchAll();

        // Analytics
        if ($results) {
            $scores   = array_column($results, 'score');
            $maxScore = max(array_column($results, 'max_score')) ?: 1;
            $analytics = [
                'total'     => count($results),
                'avg_score' => round(array_sum($scores) / count($scores), 2),
                'max_score' => max($scores),
                'min_score' => min($scores),
                'avg_pct'   => round(array_sum(array_map(fn($r) => $r['max_score']>0 ? $r['score']/$r['max_score']*100 : 0, $results)) / count($results), 1),
                'pass_count'=> count(array_filter($results, fn($r) => $r['max_score']>0 && ($r['score']/$r['max_score']*100) >= ($selectedForm['pass_threshold'] ?: 0))),
                'cheat_total'=> array_sum(array_column($results, 'cheat_count')),
                'distribution'=> [0=>0,10=>0,20=>0,30=>0,40=>0,50=>0,60=>0,70=>0,80=>0,90=>0],
            ];
            foreach ($results as $r) {
                $pct = $r['max_score']>0 ? $r['score']/$r['max_score']*100 : 0;
                $bucket = min(90, floor($pct / 10) * 10);
                $analytics['distribution'][$bucket]++;
            }
        }

        // Question performance
        $s = $pdo->prepare("SELECT * FROM questions WHERE form_id=? ORDER BY order_index");
        $s->execute([$fid]);
        $questions = $s->fetchAll();
    }
}
?>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>نتایج آزمون‌ها</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
<?php include __DIR__ . '/../assets/css/panel.css'; ?>
.analytics-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:24px;}
.an-card{background:white;border:1px solid var(--border);border-radius:20px;padding:20px;text-align:center;}
.an-value{font-size:32px;font-weight:800;color:var(--primary);}
.an-label{font-size:12px;color:var(--text-muted);margin-top:4px;}
.chart-bar-wrap{display:flex;align-items:flex-end;gap:6px;height:120px;padding:0 8px;}
.chart-bar{flex:1;background:var(--primary);border-radius:4px 4px 0 0;transition:.3s;cursor:default;position:relative;}
.chart-bar:hover::after{content:attr(data-val);position:absolute;top:-24px;left:50%;transform:translateX(-50%);background:#0f172a;color:white;padding:2px 6px;border-radius:6px;font-size:11px;white-space:nowrap;}
.chart-labels{display:flex;gap:6px;padding:4px 8px 0;}
.chart-label{flex:1;font-size:10px;text-align:center;color:var(--text-muted);}
.table-wrap{overflow-x:auto;}
.highlight-row td{background:#fffbeb;}
.score-pct{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:700;}
.score-pct.high{background:#dcfce7;color:#166534;}
.score-pct.mid {background:#dbeafe;color:#1e40af;}
.score-pct.low {background:#fee2e2;color:#991b1b;}
.cheat-badge{background:#fee2e2;color:#dc2626;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:700;}
.answer-detail{font-size:12px;color:var(--text-muted);max-width:300px;}
.form-selector{display:flex;gap:12px;flex-wrap:wrap;padding:16px 24px;}
.form-btn{padding:10px 18px;border:2px solid var(--border);border-radius:40px;font-size:13px;font-weight:600;cursor:pointer;background:white;color:var(--text);transition:.2s;text-decoration:none;font-family:inherit;}
.form-btn:hover,.form-btn.active{border-color:var(--primary);background:#ede9fe;color:var(--primary);}
.charts-2col{display:grid;grid-template-columns:1fr 1fr;gap:24px;}
@media(max-width:768px){
  .charts-2col{grid-template-columns:1fr;}
  .data-table{min-width:720px;}
}
</style>
</head>
<body>
<?php include __DIR__ . '/includes/sidebar.php'; ?>
<div class="main-content">

<div class="page-header">
    <div><h1>📊 نتایج آزمون‌ها</h1><p>مشاهده، آنالیز و خروجی نتایج</p></div>
</div>

<!-- آزمون selector -->
<div class="card" style="margin-bottom:24px;">
    <div class="card-header"><h3>انتخاب آزمون</h3></div>
    <div class="form-selector">
        <?php foreach ($forms as $f): ?>
        <a href="results.php?form=<?= $f['id'] ?>"
           class="form-btn <?= $fid===$f['id']?'active':'' ?>">
            <?= h($f['title']) ?>
            <span style="background:#f1f5f9;padding:2px 8px;border-radius:20px;margin-right:6px;font-size:11px;"><?= $f['participant_count'] ?></span>
        </a>
        <?php endforeach; ?>
        <?php if (!$forms): ?>
        <p style="color:var(--text-muted);">هنوز آزمونی ساخته نشده</p>
        <?php endif; ?>
    </div>
</div>

<?php if ($selectedForm && $results): ?>

<!-- Analytics Cards -->
<div class="analytics-grid">
    <div class="an-card"><div class="an-value"><?= $analytics['total'] ?></div><div class="an-label">👥 کل شرکت‌کننده</div></div>
    <div class="an-card"><div class="an-value"><?= $analytics['avg_score'] ?></div><div class="an-label">📊 میانگین نمره</div></div>
    <div class="an-card"><div class="an-value"><?= $analytics['avg_pct'] ?>%</div><div class="an-label">📈 میانگین درصد</div></div>
    <div class="an-card"><div class="an-value"><?= $analytics['pass_count'] ?></div><div class="an-label">✅ قبول شده</div></div>
    <div class="an-card" style="<?= $analytics['cheat_total']>0?'border-color:#fca5a5':'' ?>">
        <div class="an-value" style="<?= $analytics['cheat_total']>0?'color:var(--danger)':'' ?>"><?= $analytics['cheat_total'] ?></div>
        <div class="an-label">⚠️ کل تقلب</div>
    </div>
    <div class="an-card"><div class="an-value"><?= $analytics['max_score'] ?></div><div class="an-label">🏆 بالاترین نمره</div></div>
    <div class="an-card"><div class="an-value"><?= $analytics['min_score'] ?></div><div class="an-label">📉 پایین‌ترین نمره</div></div>
</div>

<!-- Distribution Chart + Analytics Charts -->
<div class="card" style="margin-bottom:24px;">
    <div class="card-header">
        <h3>📊 آنالیتیکس پیشرفته</h3>
        <div style="display:flex;gap:8px;">
            <a href="results.php?form=<?= $fid ?>&export_csv=1" class="btn btn-success btn-sm">📥 خروجی Excel/CSV</a>
        </div>
    </div>
    <div class="card-body">
        <div class="charts-2col">
            <div>
                <div style="font-size:13px;font-weight:700;color:var(--text-muted);margin-bottom:12px;">توزیع نمرات</div>
                <canvas id="distChart" height="200"></canvas>
            </div>
            <div>
                <div style="font-size:13px;font-weight:700;color:var(--text-muted);margin-bottom:12px;">قبول/مردود</div>
                <canvas id="passChart" height="200"></canvas>
            </div>
        </div>
        <?php
        // Answer similarity detection
        $similarPairs = [];
        if (count($results) >= 2) {
            foreach ($results as $i => $a) {
                if (!$a['answers']) continue;
                $aAns = json_decode($a['answers'], true) ?: [];
                foreach ($results as $j => $b) {
                    if ($j <= $i || !$b['answers']) continue;
                    $bAns = json_decode($b['answers'], true) ?: [];
                    $common = 0;
                    $total  = 0;
                    foreach ($aAns as $qid => $val) {
                        if (!isset($bAns[$qid])) continue;
                        $total++;
                        if (trim(strtolower((string)$val)) === trim(strtolower((string)$bAns[$qid]))) $common++;
                    }
                    if ($total >= 3 && $common / $total >= 0.85) {
                        $similarPairs[] = [
                            'a' => $a['user_name'] ?: $a['user_ip'],
                            'b' => $b['user_name'] ?: $b['user_ip'],
                            'similarity' => round($common / $total * 100),
                        ];
                    }
                }
            }
        }
        ?>
        <?php if (!empty($similarPairs)): ?>
        <div style="margin-top:20px;background:#fff5f5;border:2px solid #fecaca;border-radius:16px;padding:16px;">
            <div style="font-size:14px;font-weight:800;color:#991b1b;margin-bottom:10px;">🚨 تشخیص پاسخ‌های مشابه (احتمال رونویسی)</div>
            <?php foreach ($similarPairs as $pair): ?>
            <div style="font-size:13px;color:#dc2626;padding:4px 0;border-bottom:1px solid #fecaca;">
                ⚠️ <strong><?= h($pair['a']) ?></strong> و <strong><?= h($pair['b']) ?></strong> — <?= $pair['similarity'] ?>% شباهت
            </div>
            <?php endforeach; ?>
        </div>
        <?php endif; ?>
    </div>
</div>

<!-- Results Table -->
<div class="card">
    <div class="card-header">
        <h3>📋 پاسخنامه کامل (<?= count($results) ?> نفر)</h3>
        <a href="results.php?form=<?= $fid ?>&export_csv=1" class="btn btn-secondary btn-sm">📥 CSV</a>
    </div>
    <div class="table-wrap">
        <table class="data-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>نام و نام خانوادگی</th>
                    <th>کد ملی</th>
                    <th>نمره</th>
                    <th>درصد</th>
                    <th>✅</th>
                    <th>❌</th>
                    <th>📭</th>
                    <th>تقلب</th>
                    <th>زمان</th>
                    <th>📍</th>
                    <th>عملیات</th>
                </tr>
            </thead>
            <tbody>
                <?php
                // Pre-load snapshot counts and GPS flags
                $snapCounts = [];
                $gpsFlagged = [];
                if ($fid) {
                    $sc = $pdo->prepare("SELECT user_ip, COUNT(*) as cnt FROM exam_snapshots WHERE form_id=? GROUP BY user_ip");
                    $sc->execute([$fid]);
                    foreach ($sc->fetchAll() as $s) $snapCounts[$s['user_ip']] = $s['cnt'];
                    $gf = $pdo->prepare("SELECT DISTINCT user_ip FROM gps_locations WHERE form_id=? AND flagged=1");
                    $gf->execute([$fid]);
                    foreach ($gf->fetchAll() as $s) $gpsFlagged[$s['user_ip']] = true;
                }
                foreach ($results as $i => $r):
                    $pct = $r['max_score']>0 ? round($r['score']/$r['max_score']*100) : 0;
                    $pctClass = $pct>=70?'high':($pct>=40?'mid':'low');
                    $hasCheat = $r['cheat_count']>0;
                    $snapCnt = $snapCounts[$r['user_ip']] ?? 0;
                    $gflag   = $gpsFlagged[$r['user_ip']] ?? false;
                ?>
                <tr class="<?= ($hasCheat || $gflag) ? 'highlight-row' : '' ?>">
                    <td><?= $i+1 ?></td>
                    <td><strong><?= h($r['user_name'] ?: '(ناشناس)') ?></strong></td>
                    <td style="font-family:monospace;"><?= h($r['user_national'] ?: '—') ?></td>
                    <td><strong><?= $r['score'] ?>/<?= $r['max_score'] ?></strong></td>
                    <td><span class="score-pct <?= $pctClass ?>"><?= $pct ?>%</span></td>
                    <td style="color:var(--success);font-weight:700;"><?= $r['correct_count'] ?></td>
                    <td style="color:var(--danger);font-weight:700;"><?= $r['wrong_count'] ?></td>
                    <td style="color:var(--warning);font-weight:700;"><?= $r['empty_count'] ?></td>
                    <td>
                        <?= $hasCheat ? '<span class="cheat-badge">⚠️ '.$r['cheat_count'].'</span>' : '—' ?>
                        <?= $snapCnt ? '<span style="background:#ede9fe;color:#4f46e5;padding:2px 6px;border-radius:10px;font-size:11px;font-weight:700;margin-right:4px;">📷 '.$snapCnt.'</span>' : '' ?>
                    </td>
                    <td style="font-size:12px;color:var(--text-muted);"><?= substr($r['submitted_at'],0,16) ?></td>
                    <td>
                        <?= $gflag ? '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;">🚨 GPS</span>' : '<span style="color:#94a3b8;font-size:12px;">—</span>' ?>
                    </td>
                    <td>
                        <div style="display:flex;gap:6px;align-items:center;">
                        <button class="btn btn-secondary btn-sm" onclick="showDetail(<?= $r['id'] ?>)">جزئیات</button>
                        <form method="POST" style="display:inline;" onsubmit="return confirm('این تلاش حذف شود تا شرکت‌کننده دوباره آزمون دهد؟')">
                            <input type="hidden" name="csrf_token" value="<?= h(generateCsrfToken()) ?>">
                            <input type="hidden" name="form" value="<?= $fid ?>">
                            <input type="hidden" name="reset_attempt" value="<?= $r['id'] ?>">
                            <button type="submit" class="btn btn-warning btn-sm">🔄</button>
                        </form>
                        </div>
                    </td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</div>

<?php elseif ($selectedForm): ?>
<div class="card"><div class="card-body empty-state">هنوز کسی در این آزمون شرکت نکرده است.</div></div>
<?php elseif ($fid): ?>
<div class="card"><div class="card-body empty-state">آزمون یافت نشد یا دسترسی ندارید.</div></div>
<?php else: ?>
<div class="card"><div class="card-body empty-state">یک آزمون از بالا انتخاب کنید تا نتایج آن نمایش داده شود.</div></div>
<?php endif; ?>

</div><!-- main-content -->

<!-- Detail Modal -->
<div class="modal-overlay" id="detailModal">
    <div class="modal" style="max-width:700px;">
        <div class="modal-header">
            <h3>📋 جزئیات پاسخنامه</h3>
            <button class="modal-close" onclick="document.getElementById('detailModal').classList.remove('open')">×</button>
        </div>
        <div id="detailContent" style="font-size:14px;color:var(--text-muted);">در حال بارگذاری...</div>
    </div>
</div>

<script>
<?php if ($results): ?>
const RESULTS = <?= json_encode(array_map(fn($r) => [
    'id' => $r['id'],
    'name' => $r['user_name'],
    'answers' => $r['answers'],
    'score' => $r['score'],
    'max_score' => $r['max_score'],
    'submitted_at' => $r['submitted_at'],
    'cheat_count' => $r['cheat_count'],
], $results), JSON_UNESCAPED_UNICODE) ?>;
const QUESTIONS = <?= json_encode(array_map(fn($q) => [
    'id' => $q['id'],
    'title' => $q['title'],
    'type' => $q['type'],
    'correct_answer' => $q['correct_answer'],
    'options' => $q['options'] ? json_decode($q['options'], true) : null,
    'points' => $q['points'],
], $questions ?? []), JSON_UNESCAPED_UNICODE) ?>;

const DIST_DATA = <?= json_encode(array_values($analytics['distribution']), JSON_UNESCAPED_UNICODE) ?>;
const DIST_LABELS = <?= json_encode(array_map(fn($b) => $b.'-'.($b+10).'%', array_keys($analytics['distribution'])), JSON_UNESCAPED_UNICODE) ?>;
const PASS_COUNT = <?= $analytics['pass_count'] ?>;
const FAIL_COUNT = <?= $analytics['total'] - $analytics['pass_count'] ?>;

// Distribution bar chart
new Chart(document.getElementById('distChart'), {
    type: 'bar',
    data: {
        labels: DIST_LABELS,
        datasets: [{
            label: 'تعداد دانش‌آموزان',
            data: DIST_DATA,
            backgroundColor: 'rgba(99,102,241,0.7)',
            borderColor: '#6366f1',
            borderWidth: 1,
            borderRadius: 6,
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, ticks: { stepSize: 1 } },
            x: { ticks: { font: { family: 'Vazirmatn' } } }
        }
    }
});

// Pass/fail doughnut
new Chart(document.getElementById('passChart'), {
    type: 'doughnut',
    data: {
        labels: ['قبول', 'مردود'],
        datasets: [{
            data: [PASS_COUNT, FAIL_COUNT],
            backgroundColor: ['rgba(16,185,129,0.8)', 'rgba(239,68,68,0.8)'],
            borderWidth: 0,
        }]
    },
    options: {
        responsive: true,
        plugins: {
            legend: { position: 'bottom', labels: { font: { family: 'Vazirmatn', size: 13 } } }
        }
    }
});

function showDetail(rid) {
    const r = RESULTS.find(x => x.id === rid);
    if (!r) return;
    const answers = JSON.parse(r.answers || '{}');
    let html = `<div style="margin-bottom:16px;"><strong>${r.name || 'ناشناس'}</strong> | نمره: ${r.score}/${r.max_score} | ${r.submitted_at}</div><hr style="margin-bottom:16px;">`;

    QUESTIONS.forEach((q, i) => {
        if (q.type === 'section_title') return;
        const ans = answers[q.id] ?? '—';
        const correct = q.correct_answer;
        let isCorrect = null;
        if (correct && ans && ans !== '—') {
            isCorrect = String(ans) === String(correct);
        }
        const color = isCorrect === true ? '#166534' : isCorrect === false ? '#991b1b' : '#475569';
        const icon  = isCorrect === true ? '✅' : isCorrect === false ? '❌' : '📭';

        html += `<div style="padding:10px 0;border-bottom:1px solid #e2e8f0;">
            <div style="font-weight:700;color:#0f172a;">${i+1}. ${q.title}</div>
            <div style="margin-top:4px;color:${color};">${icon} پاسخ: ${ans}</div>
            ${correct ? `<div style="font-size:12px;color:#64748b;">پاسخ صحیح: ${correct}</div>` : ''}
        </div>`;
    });

    document.getElementById('detailContent').innerHTML = html;
    document.getElementById('detailModal').classList.add('open');
}
<?php endif; ?>

document.getElementById('detailModal').addEventListener('click', function(e) {
    if (e.target === this) this.classList.remove('open');
});
</script>
</body>
</html>
