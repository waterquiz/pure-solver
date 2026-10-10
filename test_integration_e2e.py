"""
Complete End-to-End Live Integration Verification Script
Validates:
1. Database initial seed
2. Authentication (login / token)
3. API key generation and masking
4. Image upload with valid API key (HTTP 201)
5. Image storage verification
6. Audit request log verification
7. Health check endpoint
8. Rejection of invalid API key (HTTP 401)
9. Rejection of invalid image format (HTTP 400)
10. Rate limiting (HTTP 429)
11. Image download
12. Image deletion
"""
import os
import sys
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal, init_db
from backend.app.models.user import User
from backend.app.models.api_key import ApiKey
from backend.app.models.image import Image
from backend.app.models.api_request import ApiRequest
from backend.app.services.rate_limiter import rate_limiter

def run_integration_test():
    print("=" * 65)
    print("RUNNING FINAL PRODUCTION INTEGRATION VERIFICATION")
    print("=" * 65)

    client = TestClient(app)

    # 1. Health check
    print("\n[STEP 1] Testing Health Check GET /health...")
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    print(f" -> Status: {health_data['status']}, DB: {health_data['database']}, Storage: {health_data['storage']}")

    # 2. Login
    print("\n[STEP 2] Testing Admin Login POST /api/v1/auth/login...")
    res = client.post("/api/v1/auth/login", json={
        "username_or_email": "admin",
        "password": "admin123"
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {token}"}
    print(f" -> Logged in successfully. Token acquired.")

    # 3. Create new API Key
    print("\n[STEP 3] Creating new API Key POST /api/v1/api-keys...")
    res = client.post("/api/v1/api-keys", json={
        "name": "E2E Verification Client",
        "scopes": "images:upload,images:read,images:delete"
    }, headers=user_headers)
    assert res.status_code == 201, f"API key creation failed: {res.text}"
    key_data = res.json()
    raw_api_key = key_data["raw_key"]
    masked_key = key_data["masked_key"]
    key_id = key_data["id"]
    print(f" -> Generated raw key: {raw_api_key}")
    print(f" -> Masked key: {masked_key}")

    # 4. Upload test.png using raw API key
    print("\n[STEP 4] Uploading test.png with API Key POST /api/v1/images...")
    with open("test.png", "rb") as f:
        file_bytes = f.read()

    res = client.post(
        "/api/v1/images",
        headers={"X-API-Key": raw_api_key},
        files={"file": ("test.png", file_bytes, "image/png")},
        data={"client_id": "IntegrationTester", "description": "Verification capture"}
    )
    assert res.status_code == 201, f"Upload failed: {res.text}"
    upload_data = res.json()
    image_id = upload_data["image"]["id"]
    image_url = upload_data["image"]["url"]
    print(f" -> Upload SUCCESS HTTP 201!")
    print(f" -> Image ID: {image_id}")
    print(f" -> Image URL: {image_url}")
    print(f" -> Dimensions: {upload_data['image']['width']}x{upload_data['image']['height']} px")

    # 5. Verify Database Record & Storage
    print("\n[STEP 5] Verifying Database Record and Audit Log...")
    db = SessionLocal()
    db_img = db.query(Image).filter(Image.id == image_id).first()
    assert db_img is not None, "Image record not found in database!"
    print(f" -> Database record verified. Storage key: {db_img.storage_key}")

    db_req = db.query(ApiRequest).filter(ApiRequest.api_key_id == key_id).first()
    assert db_req is not None, "ApiRequest audit record not found!"
    print(f" -> Audit log verified: status={db_req.status_code}, duration={db_req.request_duration_ms}ms")
    db.close()

    # 6. Verify Statistics Endpoint
    print("\n[STEP 6] Testing Dashboard Statistics GET /api/v1/stats...")
    res = client.get("/api/v1/stats", headers=user_headers)
    assert res.status_code == 200
    stats = res.json()
    print(f" -> Total images: {stats['total_images']}, Requests: {stats['total_api_requests']}, Active keys: {stats['active_api_keys']}")
    assert stats["total_images"] >= 1

    # 7. Test Invalid API Key Rejection (HTTP 401)
    print("\n[STEP 7] Testing Invalid API Key Rejection...")
    res = client.post(
        "/api/v1/images",
        headers={"X-API-Key": "sk_live_bogus_key_9999999"},
        files={"file": ("test.png", file_bytes, "image/png")}
    )
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    assert res.json()["error"]["code"] == "INVALID_API_KEY"
    print(f" -> Correctly rejected with HTTP 401 INVALID_API_KEY")

    # 8. Test Invalid Image Rejection (HTTP 400)
    print("\n[STEP 8] Testing Invalid Fake Image Format Rejection...")
    res = client.post(
        "/api/v1/images",
        headers={"X-API-Key": raw_api_key},
        files={"file": ("fake.png", b"NOT AN IMAGE FILE AT ALL", "image/png")}
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert res.json()["error"]["code"] == "INVALID_IMAGE"
    print(f" -> Correctly rejected with HTTP 400 INVALID_IMAGE")

    # 9. Test Rate Limiting (HTTP 429)
    print("\n[STEP 9] Testing Sliding Window Rate Limiting (HTTP 429)...")
    rate_limiter.limit = 2
    rate_limiter.window = 60
    rate_limiter.reset()

    # Request 1 & 2 pass
    client.post("/api/v1/images", headers={"X-API-Key": raw_api_key}, files={"file": ("test.png", file_bytes, "image/png")})
    client.post("/api/v1/images", headers={"X-API-Key": raw_api_key}, files={"file": ("test.png", file_bytes, "image/png")})
    # Request 3 should hit 429
    res_rl = client.post("/api/v1/images", headers={"X-API-Key": raw_api_key}, files={"file": ("test.png", file_bytes, "image/png")})
    assert res_rl.status_code == 429, f"Expected 429, got {res_rl.status_code}"
    assert res_rl.json()["error"]["code"] == "RATE_LIMITED"
    print(f" -> Correctly throttled with HTTP 429 RATE_LIMITED")
    rate_limiter.limit = 100
    rate_limiter.reset()

    # 10. Test Download
    print("\n[STEP 10] Testing Image Download GET /api/v1/images/{id}/download...")
    dl_res = client.get(f"/api/v1/images/{image_id}/download", headers=user_headers)
    assert dl_res.status_code == 200
    assert len(dl_res.content) == len(file_bytes)
    print(f" -> Download verified ({len(dl_res.content)} bytes received)")

    # 11. Test Delete Image
    print("\n[STEP 11] Testing Image Deletion DELETE /api/v1/images/{id}...")
    del_res = client.delete(f"/api/v1/images/{image_id}", headers=user_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True
    print(f" -> Image deleted successfully.")

    # Verify 404 after deletion
    check_del = client.get(f"/api/v1/images/{image_id}", headers=user_headers)
    assert check_del.status_code == 404
    print(f" -> Confirmed 404 Not Found after deletion.")

    print("\n" + "=" * 65)
    print("ALL PRODUCTION INTEGRATION VERIFICATION CHECKS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_integration_test()
