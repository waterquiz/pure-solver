<?php
/**
 * PHP cURL Upload Example for Remote Image Display API
 */

$apiUrl = "http://localhost:8000/api/v1/images";
$apiKey = "YOUR_API_KEY";
$filePath = "image.png";

if (!file_exists($filePath)) {
    die("File not found: " . $filePath . "\n");
}

$curl = curl_init();

$postFields = [
    "file" => new CURLFile(
        $filePath,
        "image/png",
        basename($filePath)
    ),
    "client_id" => "php-client",
    "description" => "Image uploaded via PHP cURL script"
];

curl_setopt_array($curl, [
    CURLOPT_URL => $apiUrl,
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => $postFields,
    CURLOPT_HTTPHEADER => [
        "X-API-Key: " . $apiKey
    ],
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 30
]);

$response = curl_exec($curl);
$httpCode = curl_getinfo($curl, CURLINFO_HTTP_CODE);

if (curl_errno($curl)) {
    echo "cURL Error: " . curl_error($curl) . "\n";
} else {
    echo "HTTP Status: " . $httpCode . "\n";
    echo "Response:\n" . $response . "\n";
}

curl_close($curl);
?>
