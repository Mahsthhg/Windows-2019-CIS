<?php
require_once __DIR__ . '/config/database.php';
require_once __DIR__ . '/config/security.php';
if (isTeacher()) redirect('teacher/panel.php');
if (isAdmin())   redirect('admin/index.php');
redirect('login.php');
