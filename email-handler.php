<?php
require_once 'db_config.php';

$token = $_SERVER['HTTP_X_DIGEST_TOKEN'] ?? '';
if ($token !== $expected_token) {
    http_response_code(403);
    echo json_encode(['error' => 'Unauthorized']);
    exit;
}

$html_content = $_POST['html_content'] ?? '';
$error_report = $_POST['error_report'] ?? null;

$conn = new mysqli($db_host, $db_user, $db_pass, $db_name);
if ($conn->connect_error) {
    http_response_code(500);
    echo json_encode(['error' => 'DB connection failed']);
    exit;
}

$result = $conn->query("SELECT email FROM news_recipients WHERE active = 1");

$headers  = "MIME-Version: 1.0\r\n";
$headers .= "Content-type:text/html;charset=UTF-8\r\n";
$headers .= "From: Daily News <noreply@qrofeus.dev>\r\n";

$success_count = 0;
$failed = [];

while ($row = $result->fetch_assoc()) {
    $to = $row['email'];
    $subject = "Daily News Digest - " . date('F j, Y');
    if (mail($to, $subject, $html_content, $headers)) {
        $success_count++;
    } else {
        $failed[] = $to;
    }
}

if ($error_report || count($failed) > 0) {
    $admin_subject = "News Digest System Alert";
    $admin_body = "Errors:\n" . $error_report . "\n\nFailed deliveries: " . implode(', ', $failed);
    mail($admin_email, $admin_subject, $admin_body);
}

$conn->close();

echo json_encode([
    'success' => count($failed) === 0,
    'sent'    => $success_count,
    'failed'  => count($failed),
]);
?>
