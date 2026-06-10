<?php
$currentPage = basename($_SERVER['PHP_SELF'], '.php');
$navItems = [
    'panel'       => ['icon' => '📊', 'label' => 'داشبورد',    'href' => 'panel.php'],
    'create_exam' => ['icon' => '📝', 'label' => 'آزمون‌ها',   'href' => 'create_exam.php'],
    'results'     => ['icon' => '📈', 'label' => 'نتایج',       'href' => 'results.php'],
    'attendance'  => ['icon' => '📋', 'label' => 'حضور‌وغیاب',  'href' => 'attendance.php'],
    'question_bank'=> ['icon' => '🏦', 'label' => 'بانک سوال',  'href' => 'question_bank.php'],
];
?>
<!-- نوار بالای موبایل + دکمهٔ منوی کشویی -->
<div class="mobile-topbar">
    <button class="hamburger" type="button" onclick="toggleSidebar()" aria-label="منو">☰</button>
    <span class="mt-title">📘 سامانه آزمون</span>
</div>
<div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>

<nav class="sidebar" id="appSidebar">
    <div class="sidebar-header">
        <span class="logo-icon">📘</span>
        <div>
            <div class="logo-title">سامانه آزمون</div>
            <div class="logo-sub"><?= h($teacher['name'] ?? '') ?></div>
        </div>
    </div>

    <div class="nav-menu">
        <?php foreach ($navItems as $page => $item): ?>
        <a href="<?= $item['href'] ?>"
           class="nav-item <?= $currentPage === $page ? 'active' : '' ?>">
            <span class="nav-icon"><?= $item['icon'] ?></span>
            <span><?= $item['label'] ?></span>
        </a>
        <?php endforeach; ?>
    </div>

    <div class="sidebar-footer">
        <a href="../logout.php" class="nav-item logout-item">
            <span class="nav-icon">🚪</span>
            <span>خروج</span>
        </a>
    </div>
</nav>
<script>
function toggleSidebar() {
    document.getElementById('appSidebar')?.classList.toggle('open');
    document.getElementById('sidebarOverlay')?.classList.toggle('open');
}
</script>
