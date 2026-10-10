# Remote Image Display API & Real-Time Web Dashboard

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Railway Ready](https://img.shields.io/badge/Deploy-Railway-0B0D0E.svg)](https://railway.app/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A production-ready web application and REST API enabling external clients (Python, JavaScript, Node.js, PHP, cURL, Go, Java, C#, Swift, Kotlin, and any HTTP-capable system) to securely upload images via API keys and have them immediately appear on a live web dashboard without page refreshes.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Features](#2-features)
3. [System Architecture](#3-system-architecture)
4. [Installation](#4-installation)
5. [Environment Variables](#5-environment-variables)
6. [Local Development](#6-local-development)
7. [PostgreSQL Setup](#7-postgresql-setup)
8. [Storage Setup (Local & S3 / R2 / MinIO)](#8-storage-setup)
9. [Running the Application](#9-running-the-application)
10. [Frontend & Dashboard Pages](#10-frontend--dashboard-pages)
11. [API Authentication](#11-api-authentication)
12. [API Specification (POST /api/v1/images)](#12-api-specification)
13. [JavaScript Example](#13-javascript-example)
14. [Python Example](#14-python-example)
15. [PHP Example](#15-php-example)
16. [cURL Example](#16-curl-example)
17. [Node.js Example](#17-nodejs-example)
18. [C# (.NET) Example](#18-c-net-example)
19. [Java Example](#19-java-example)
20. [Go Example](#20-go-example)
21. [Ruby Example](#21-ruby-example)
22. [Swift (iOS) Example](#22-swift-ios-example)
23. [Kotlin (Android) Example](#23-kotlin-android-example)
24. [Postman Configuration](#24-postman-configuration)
25. [WebSocket Real-Time Behavior](#25-websocket-real-time-behavior)
26. [Security & Protection Mechanisms](#26-security--protection-mechanisms)
27. [Railway Deployment Guide](#27-railway-deployment-guide)
28. [Troubleshooting & FAQ](#28-troubleshooting--faq)

---

## 1. Project Overview

The **Remote Image Display API** decouples the image sender from the image display station:
- **Computer A (Sender):** An automated Python program, CCTV system, Raspberry Pi, serverless worker, or mobile app sends an image to the API using HTTP and an `X-API-Key` header.
- **API Server:** Validates the API key, checks rate limits, inspects the true binary file signature (magic bytes), saves the image to persistent/cloud storage, logs the audit trail, and broadcasts a WebSocket notification.
- **Computer B (Viewer):** A browser dashboard currently open on a monitoring screen receives the real-time WebSocket push event and instantly renders the newly arrived image, its resolution, size, and source identity without requiring any manual reload.

---

## 2. Features

- **Language-Agnostic REST API:** Any language capable of issuing multipart `POST` requests can upload images.
- **Real-Time WebSockets:** Multi-tenant connection management broadcasting live `image_received` and `image_deleted` events.
- **Automatic Reconnection:** Frontend WebSocket client includes exponential backoff retry loops and heartbeat ping/pong keepalives.
- **Hashed API Key System:** High-security API key management. Raw keys (`PS_...`) are shown only once upon generation, hashed using SHA-256 for zero-plaintext storage, and displayed masked (`PS_************abcd`).
- **Pluggable Persistent Storage:** Configurable storage abstraction supporting local disk storage for development and S3-compatible object storage (AWS S3, Cloudflare R2, MinIO, Backblaze B2, Supabase) for Railway/cloud production.
- **True Image Validation:** Binary magic signature checks prevent executable masquerading; Pillow validates dimensions and image integrity.
- **Sliding-Window Rate Limiter:** Protects endpoints against flood attacks (configurable, default 100 req/min per key/IP).
- **Comprehensive Dashboard:** Modern, responsive UI featuring real-time statistics cards, large latest image display showcase, image metadata inspector, lazy loaded/paginated history grid, fullscreen modal, download, and delete.
- **Interactive API Test Console:** Built-in web debugger allowing operators to drag-and-drop images, test API keys, and inspect response status, latency, and JSON bodies.
- **User & RBAC Management:** Secure session cookies, bcrypt password hashing, operator vs administrator roles.
- **Railway & Docker Ready:** Includes `Dockerfile`, `railway.json`, `Procfile`, and automated database migrations/seeding.

---

## 3. System Architecture

```text
  +-----------------------------------------------------------------------+
  |              CLIENTS (Python, Node, PHP, Go, cURL, IoT)               |
  +-----------------------------------------------------------------------+
                                     |
                                     | HTTPS POST /api/v1/images
                                     | Headers: X-API-Key: PS_...
                                     v
  +-----------------------------------------------------------------------+
  |                             FASTAPI CORE                              |
  |  +--------------------+  +-------------------+  +------------------+  |
  |  | Rate Limiter (429) |  | Auth / Keys (401) |  | Security Headers |  |
  |  +--------------------+  +-------------------+  +------------------+  |
  |  +-----------------------------------------------------------------+  |
  |  | Image Validator (Magic bytes signature, Pillow integrity check) |  |
  |  +-----------------------------------------------------------------+  |
  +-----------------------------------------------------------------------+
             |                                              |
             v                                              v
  +-----------------------+                      +-----------------------+
  |   STORAGE PROVIDER    |                      |      DATABASE         |
  |  (Local Disk or S3 /  |                      | (PostgreSQL / SQLite) |
  |   Cloudflare R2 / B2) |                      | Images, Keys, Users   |
  +-----------------------+                      +-----------------------+
             \                                              /
              \                                            /
               v                                          v
  +-----------------------------------------------------------------------+
  |                 WEBSOCKET BROADCASTER (/ws/dashboard)                 |
  +-----------------------------------------------------------------------+
                                     |
                                     | Real-Time Event: "image_received"
                                     v
  +-----------------------------------------------------------------------+
  |                       LIVE BROWSER DASHBOARD                          |
  |             (Instant Image Display + Metadata + History)              |
  +-----------------------------------------------------------------------+
```

---

## 4. Installation

### Prerequisites
- Python 3.10+
- PostgreSQL (or SQLite for local development)

### Clone & Install
```bash
git clone <repository_url>
cd "Pure Reciver"

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 5. Environment Variables

Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `production` | Environment mode (`development`, `production`, `test`). |
| `SECRET_KEY` | `super-secret...` | Secret key used for signing JWT access tokens. |
| `DATABASE_URL` | `sqlite:///./data.db` | PostgreSQL connection URL (automatically supplied by Railway). |
| `PUBLIC_BASE_URL` | `http://localhost:8000`| Base URL for public image links. |
| `MAX_IMAGE_SIZE_MB` | `10` | Maximum allowed upload size in megabytes. |
| `RATE_LIMIT` | `100` | Allowed requests per window per API key. |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit sliding window duration in seconds. |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed origins. |
| `STORAGE_PROVIDER` | `local` | `local` or `s3`. |
| `STORAGE_LOCAL_DIR` | `./uploads` | Directory for local file storage if `local` provider is selected. |
| `STORAGE_BUCKET` | *(None)* | S3 / R2 bucket name (required if `s3`). |
| `STORAGE_ENDPOINT` | *(None)* | S3 endpoint URL (e.g. `https://<account>.r2.cloudflarestorage.com`). |
| `STORAGE_ACCESS_KEY` | *(None)* | S3 access key ID. |
| `STORAGE_SECRET_KEY` | *(None)* | S3 secret access key. |

---

## 6. Local Development

1. **Seed Initial Admin Account & API Key:**
   ```bash
   python seed.py
   ```
   *Output:*
   ```text
   [*] Initializing database schema...
   [+] Creating default admin user...
       Admin created: username='admin', password='admin123', email='admin@example.com'
   [+] Generating initial production API key...
   API Key: PS_900a2dbb943ac30d39ba1993ca3614379a04bb
   Masked:  PS_************1f3e
   ```

2. **Run Development Server:**
   ```bash
   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Open in Browser:**
   - Dashboard: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
   - Login: [http://localhost:8000/login](http://localhost:8000/login)
   - Interactive Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   - API Test Console: [http://localhost:8000/dashboard/api-test](http://localhost:8000/dashboard/api-test)

---

## 7. PostgreSQL Setup

For production deployments, specify a PostgreSQL connection string in `DATABASE_URL`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/remote_image_db
```

The application automatically supports Railway and Heroku style `postgres://` URLs by converting them internally to `postgresql://`.

---

## 8. Storage Setup

### Local Storage (Default for development)
```env
STORAGE_PROVIDER=local
STORAGE_LOCAL_DIR=./uploads
```
Files are stored locally in `./uploads` with path traversal protections. Served through `GET /media/{storage_key}`.

### S3 / Cloudflare R2 / MinIO / Backblaze B2 (Required for Railway)
Because Railway container filesystems are ephemeral upon deployment redeploys, configure an external object store:

```env
STORAGE_PROVIDER=s3
STORAGE_BUCKET=my-production-images
STORAGE_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=your-r2-access-key
STORAGE_SECRET_KEY=your-r2-secret-key
STORAGE_REGION=auto
STORAGE_PUBLIC_URL_PREFIX=https://cdn.yourdomain.com
```

---

## 9. Running the Application

### Using Python
```bash
python seed.py
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### Using Docker
```bash
docker build -t remote-image-api .
docker run -p 8000:8000 --env-file .env remote-image-api
```

---

## 10. Frontend & Dashboard Pages

| Route | Access | Purpose |
|---|---|---|
| `/login` | Public | Secure session login form. |
| `/dashboard` | Protected | Live image showcase, statistics cards, image history, view/download/delete. |
| `/dashboard/api-keys` | Protected | Create API keys, view masked keys, toggle status, revoke keys. |
| `/dashboard/api-test` | Protected | Interactive debugger to upload images, test keys, and measure latency. |
| `/dashboard/users` | Admin | Account provisioning, role assignments, password resets. |
| `/docs` | Public | Complete multi-language developer guide and SDK examples. |
| `/health` | Public | Healthcheck endpoint (`{"status": "ok", "database": "connected", "storage": "available"}`). |

---

## 11. API Authentication

All upload requests must pass an authorized API key via the `X-API-Key` HTTP header:

```http
X-API-Key: PS_900a2dbb943ac30d39ba1993ca3614379a04bb
```

*(Alternatively, `Authorization: Bearer PS_...` is accepted).*

---

## 12. API Specification

### Upload Image
**Endpoint:** `POST /api/v1/images`  
**Content-Type:** `multipart/form-data`  
**Headers:** `X-API-Key: YOUR_API_KEY`

#### Form Parameters
- `file` *(Binary, Required)*: Image file (JPEG, PNG, WEBP, GIF, BMP, TIFF up to 10MB).
- `filename` *(String, Optional)*: Override original filename.
- `client_id` *(String, Optional)*: Origin client/device identifier (e.g., `Camera-01`).
- `description` *(String, Optional)*: Caption or text annotation.
- `metadata` *(String / JSON, Optional)*: Custom sensor telemetry.

#### Success Response (HTTP 201 Created)
```json
{
  "success": true,
  "message": "Image uploaded successfully.",
  "image": {
    "id": "img_a84f3c0192e4",
    "filename": "camera_capture.png",
    "mime_type": "image/png",
    "size": 245123,
    "url": "http://localhost:8000/media/8f2c91a7-4b21-4e4a-91a2.png",
    "width": 1920,
    "height": 1080,
    "client_id": "Camera-01",
    "description": "Motion detected at main entrance",
    "created_at": "2026-10-07T11:20:30.123456Z",
    "api_key_masked": "PS_************1f3e",
    "api_key_name": "Default Production Key"
  }
}
```

#### Error Responses
- **401 Unauthorized:** `{"success": false, "error": {"code": "INVALID_API_KEY", "message": "Invalid or missing API key."}}`
- **400 Bad Request:** `{"success": false, "error": {"code": "INVALID_IMAGE", "message": "Uploaded file is not a valid image."}}`
- **413 Payload Too Large:** `{"success": false, "error": {"code": "FILE_TOO_LARGE", "message": "Maximum image size is 10 MB."}}`
- **429 Too Many Requests:** `{"success": false, "error": {"code": "RATE_LIMITED", "message": "Too many requests. Rate limit exceeded."}}`
- **500 Internal Error:** `{"success": false, "error": {"code": "SERVER_ERROR", "message": "Internal server error."}}`

---

## 13. JavaScript Example

```javascript
const API_URL = "http://localhost:8000/api/v1/images";
const API_KEY = "YOUR_API_KEY";

async function uploadImage(file) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("client_id", "web-browser");
  formData.append("description", "Uploaded from client browser");

  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      "X-API-Key": API_KEY
    },
    body: formData
  });

  const result = await response.json();
  console.log("Response:", result);
}
```

---

## 14. Python Example

```python
import requests

API_URL = "http://localhost:8000/api/v1/images"
API_KEY = "YOUR_API_KEY"
image_path = "image.png"

headers = {
    "X-API-Key": API_KEY
}

with open(image_path, "rb") as image:
    files = {
        "file": (image_path, image, "image/png")
    }
    data = {
        "client_id": "python-script",
        "description": "Uploaded via Python requests"
    }

    response = requests.post(API_URL, headers=headers, files=files, data=data, timeout=30)

print(response.status_code)
print(response.json())
```

---

## 15. PHP Example

```php
<?php
$apiUrl = "http://localhost:8000/api/v1/images";
$apiKey = "YOUR_API_KEY";
$filePath = "image.png";

$curl = curl_init();

$postFields = [
    "file" => new CURLFile($filePath, "image/png", basename($filePath)),
    "client_id" => "php-client",
    "description" => "Image uploaded via PHP"
];

curl_setopt_array($curl, [
    CURLOPT_URL => $apiUrl,
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => $postFields,
    CURLOPT_HTTPHEADER => ["X-API-Key: " . $apiKey],
    CURLOPT_RETURNTRANSFER => true
]);

$response = curl_exec($curl);
curl_close($curl);

echo $response;
?>
```

---

## 16. cURL Example

```bash
curl -X POST "http://localhost:8000/api/v1/images" \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "file=@image.png" \
  -F "client_id=curl-cli" \
  -F "description=Test upload from cURL"
```

---

## 17. Node.js Example

```javascript
import fs from "fs";

const API_URL = "http://localhost:8000/api/v1/images";
const API_KEY = "YOUR_API_KEY";

async function upload() {
  const fileBuffer = fs.readFileSync("image.png");
  const blob = new Blob([fileBuffer], { type: "image/png" });

  const form = new FormData();
  form.append("file", blob, "image.png");
  form.append("client_id", "nodejs-agent");

  const response = await fetch(API_URL, {
    method: "POST",
    headers: { "X-API-Key": API_KEY },
    body: form
  });

  console.log(await response.json());
}

upload();
```

---

## 18. C# (.NET) Example

```csharp
using System;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;

class Program {
    static async Task Main() {
        var client = new HttpClient();
        client.DefaultRequestHeaders.Add("X-API-Key", "YOUR_API_KEY");

        using var form = new MultipartFormDataContent();
        using var stream = File.OpenRead("image.png");
        form.Add(new StreamContent(stream), "file", "image.png");
        form.Add(new StringContent("csharp-client"), "client_id");

        var response = await client.PostAsync("http://localhost:8000/api/v1/images", form);
        Console.WriteLine(await response.Content.ReadAsStringAsync());
    }
}
```

---

## 19. Java Example

```java
import java.net.URI;
import java.net.http.*;
import java.nio.file.Files;
import java.nio.file.Path;

public class Upload {
    public static void main(String[] args) throws Exception {
        String boundary = "---" + System.currentTimeMillis();
        byte[] fileBytes = Files.readAllBytes(Path.of("image.png"));
        // Build multipart boundary body and execute HttpClient send...
    }
}
// See examples/java/Upload.java for complete implementation
```

---

## 20. Go Example

```go
package main

import (
	"bytes"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
)

func main() {
	file, _ := os.Open("image.png")
	defer file.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	part, _ := writer.CreateFormFile("file", "image.png")
	io.Copy(part, file)
	writer.Close()

	req, _ := http.NewRequest("POST", "http://localhost:8000/api/v1/images", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	req.Header.Set("X-API-Key", "YOUR_API_KEY")

	resp, _ := http.DefaultClient.Do(req)
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(resp.Body)
	fmt.Println(string(respBody))
}
```

---

## 21. Ruby Example

```ruby
require 'net/http'
require 'uri'

uri = URI.parse("http://localhost:8000/api/v1/images")
# See examples/ruby/upload.rb for full multipart script
```

---

## 22. Swift (iOS) Example

```swift
import Foundation

func uploadImage(fileURL: URL, apiKey: String) {
    var request = URLRequest(url: URL(string: "http://localhost:8000/api/v1/images")!)
    request.httpMethod = "POST"
    request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
    // See examples/swift/Upload.swift for full URLSession implementation
}
```

---

## 23. Kotlin (Android) Example

```kotlin
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File

val client = OkHttpClient()
val file = File("image.png")
val body = MultipartBody.Builder()
    .setType(MultipartBody.FORM)
    .addFormDataPart("file", file.name, file.asRequestBody("image/png".toMediaTypeOrNull()))
    .build()

val request = Request.Builder()
    .url("http://localhost:8000/api/v1/images")
    .addHeader("X-API-Key", "YOUR_API_KEY")
    .post(body)
    .build()

val response = client.newCall(request).execute()
println(response.body?.string())
```

---

## 24. Postman Configuration

Import the ready-made collection located at:  
`examples/postman/Remote_Image_Display_API.postman_collection.json`

1. Set collection variable `base_url` to your domain.
2. Set collection variable `api_key` to your generated secret key.
3. Open `Images -> Upload Image`, choose a file, and click **Send**.

---

## 25. WebSocket Real-Time Behavior

- **Endpoint:** `/ws/dashboard`
- **Authentication:** Token passed via query string `?token=<jwt>` or session cookie.
- **Heartbeat:** Sends `ping` every 25 seconds; responds with `{"type": "pong"}`.
- **Event: `image_received`:**
  ```json
  {
    "type": "image_received",
    "data": {
      "id": "img_123456",
      "filename": "camera_01.png",
      "url": "http://localhost:8000/media/8f2c91a7.png",
      "mime_type": "image/png",
      "size": 245123,
      "width": 1920,
      "height": 1080,
      "created_at": "2026-10-07T11:20:30Z",
      "api_key_masked": "PS_************1f3e",
      "api_key_name": "Office Cam"
    }
  }
  ```
- **Event: `image_deleted`:**
  ```json
  {
    "type": "image_deleted",
    "data": { "id": "img_123456" }
  }
  ```

---

## 26. Security & Protection Mechanisms

1. **Deterministic O(1) Key Hashing:** API keys are hashed with SHA-256 upon generation. Plaintext keys are never stored.
2. **Magic Bytes Validation:** Files are verified using byte signatures rather than relying on extension or client-reported headers.
3. **Pillow Deep Inspection:** Validates that image bytes actually decode into valid raster data without embedded corruption.
4. **Random UUID Filenames:** Files are stored under random UUID names (`8f2c91a7-...`), eliminating path traversal and overwriting risks.
5. **Masked Audit Logs:** `api_requests` table records endpoints, duration, IP, and status while keeping sensitive credentials hidden.
6. **Rate Limiting:** Prevents abuse with a sliding window counter.

---

## 27. Railway Deployment Guide

1. **Push Code to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit of Remote Image Display API"
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

2. **Deploy on Railway:**
   - Log in to [Railway](https://railway.app/).
   - Click **New Project** ➔ **Deploy from GitHub repo**.
   - Add a **PostgreSQL Database** service inside your project.
   - Railway will automatically expose `DATABASE_URL` to your application service.

3. **Set Environment Variables in Railway:**
   - `SECRET_KEY`: Random 64-character string.
   - `STORAGE_PROVIDER`: `s3`
   - `STORAGE_BUCKET`: Your bucket name
   - `STORAGE_ENDPOINT`: Your S3/R2 endpoint
   - `STORAGE_ACCESS_KEY`: Access key ID
   - `STORAGE_SECRET_KEY`: Secret access key
   - `PUBLIC_BASE_URL`: `https://${{RAILWAY_PUBLIC_DOMAIN}}`

4. **Verify Deployment:**
   - Check the healthcheck URL: `https://your-railway-url.up.railway.app/health`
   - The response should show `{"status": "ok", "database": "connected", "storage": "available"}`.

---

## 28. Troubleshooting & FAQ

### Q: Why do I receive HTTP 401 `INVALID_API_KEY`?
Ensure you are passing the header `X-API-Key: PS_...` and that the key is currently marked as **Active** in `/dashboard/api-keys`.

### Q: Why do I receive HTTP 400 `INVALID_IMAGE`?
The uploaded file was either empty or failed binary magic signature verification (e.g., text file renamed to `.png`).

### Q: Why do I receive HTTP 413 `FILE_TOO_LARGE`?
The image exceeds `MAX_IMAGE_SIZE_MB` (default 10 MB). Adjust this variable in your `.env` configuration.

### Q: How do I run automated tests?
```bash
pytest -v
```
All 15 automated unit and integration tests will execute against an in-memory test database.
