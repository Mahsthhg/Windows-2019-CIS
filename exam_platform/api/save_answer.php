<?php
/**
 * api/save_answer.php - ذخیره خودکار پاسخ‌ها
 */
require_once __DIR__ . '/../config/database.php';
header('Content-Type: application/json');

// فقط auto-save
$fid = validateInt($_POST['form_id'] ?? 0, 1);
if (!$fid) { echo '{}'; exit(); }

// ذخیره در session (lightweight, no DB write for auto-save)
$_SESSION['autosave_' . $fid] = [
    'data' => $_POST,
    'ts'   => time(),
];
echo json_encode(['ok' => true, 'ts' => time()]);
