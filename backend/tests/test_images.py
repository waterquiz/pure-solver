import io
from backend.app.config import settings


def test_upload_image_success(client, test_api_key, sample_png_bytes):
    raw_key, api_key_obj = test_api_key

    files = {
        "file": ("test.png", sample_png_bytes, "image/png")
    }
    data = {
        "client_id": "test-device",
        "description": "Integration test snapshot"
    }
    headers = {
        "X-API-Key": raw_key
    }

    response = client.post("/api/v1/images", headers=headers, files=files, data=data)
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["success"] is True
    assert "image" in json_data
    assert json_data["image"]["filename"] == "test.png"
    assert json_data["image"]["mime_type"] == "image/png"
    assert json_data["image"]["width"] == 100
    assert json_data["image"]["height"] == 100


def test_upload_image_invalid_api_key(client, sample_png_bytes):
    files = {"file": ("test.png", sample_png_bytes, "image/png")}
    headers = {"X-API-Key": "sk_live_invalid_bad_key_123"}

    response = client.post("/api/v1/images", headers=headers, files=files)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


def test_upload_image_missing_api_key(client, sample_png_bytes):
    files = {"file": ("test.png", sample_png_bytes, "image/png")}

    response = client.post("/api/v1/images", files=files)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


def test_upload_image_invalid_file_signature(client, test_api_key):
    raw_key, _ = test_api_key
    # Send plaintext pretending to be PNG
    fake_bytes = b"Hello, this is just plain text, not a real image!"
    files = {"file": ("fake.png", fake_bytes, "image/png")}
    headers = {"X-API-Key": raw_key}

    response = client.post("/api/v1/images", headers=headers, files=files)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


def test_upload_image_oversized(client, test_api_key, monkeypatch):
    raw_key, _ = test_api_key
    # Temporarily set MAX_IMAGE_SIZE_MB to 0.001 (approx 1 KB) to test limit
    monkeypatch.setattr(settings, "MAX_IMAGE_SIZE_MB", 0.001)

    # 10 KB file
    big_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10000
    files = {"file": ("large.png", big_bytes, "image/png")}
    headers = {"X-API-Key": raw_key}

    response = client.post("/api/v1/images", headers=headers, files=files)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_get_and_delete_image(client, test_user, test_api_key, sample_png_bytes):
    raw_key, _ = test_api_key

    # Upload an image first
    files = {"file": ("delete_me.png", sample_png_bytes, "image/png")}
    headers = {"X-API-Key": raw_key}
    upload_res = client.post("/api/v1/images", headers=headers, files=files)
    assert upload_res.status_code == 201
    img_id = upload_res.json()["image"]["id"]

    # Log in as user to view/delete
    login_res = client.post("/api/v1/auth/login", json={
        "username_or_email": "tester",
        "password": "testpass123"
    })
    token = login_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {token}"}

    # Fetch image details
    get_res = client.get(f"/api/v1/images/{img_id}", headers=user_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == img_id

    # Download image
    dl_res = client.get(f"/api/v1/images/{img_id}/download", headers=user_headers)
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "image/png"

    # Delete image
    del_res = client.delete(f"/api/v1/images/{img_id}", headers=user_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Verify 404 after deletion
    get_after_del = client.get(f"/api/v1/images/{img_id}", headers=user_headers)
    assert get_after_del.status_code == 404


def test_auto_delete_after_ai_result(client, test_user, test_api_key, sample_png_bytes):
    import time
    raw_key, _ = test_api_key

    # Upload an image
    files = {"file": ("auto_del.png", sample_png_bytes, "image/png")}
    headers = {"X-API-Key": raw_key}
    upload_res = client.post("/api/v1/images?wait_for_ai=false&auto_delete_seconds=1", headers=headers, files=files)
    assert upload_res.status_code == 201
    img_id = upload_res.json()["image"]["id"]

    # Log in
    login_res = client.post("/api/v1/auth/login", json={
        "username_or_email": "tester",
        "password": "testpass123"
    })
    token = login_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {token}"}

    # Verify image exists
    get_res = client.get(f"/api/v1/images/{img_id}", headers=user_headers)
    assert get_res.status_code == 200

    # Post AI result with auto_delete_seconds=1
    ai_res = client.post(
        f"/api/v1/images/{img_id}/ai-result?auto_delete_seconds=1",
        headers=user_headers,
        json={"matched_cells": [1, 5, 9], "raw_output": "1, 5, 9", "model": "gemini-2.5-flash-lite"}
    )
    assert ai_res.status_code == 200
    assert ai_res.json()["ai_result"]["matched_cells"] == [1, 5, 9]

    # Directly run worker or wait for background task (sleep 1.2s)
    time.sleep(1.2)

    # Image should now be deleted from website
    get_after = client.get(f"/api/v1/images/{img_id}", headers=user_headers)
    assert get_after.status_code == 404


def test_multi_browser_isolated_outputs(client, test_user, test_api_key, sample_png_bytes):
    raw_key, _ = test_api_key
    headers = {"X-API-Key": raw_key}

    # Browser 1 sends image
    files1 = {"file": ("b1_img.png", sample_png_bytes, "image/png")}
    data1 = {"text": "Blone and moon", "client_id": "browser-1"}
    res1 = client.post("/api/v1/images?wait_for_ai=false&auto_delete_seconds=0", headers=headers, files=files1, data=data1)
    assert res1.status_code == 201
    img1_id = res1.json()["image_id"]
    assert res1.json()["client_id"] == "browser-1"

    # Browser 2 sends image
    files2 = {"file": ("b2_img.png", sample_png_bytes, "image/png")}
    data2 = {"text": "House", "client_id": "browser-2"}
    res2 = client.post("/api/v1/images?wait_for_ai=false&auto_delete_seconds=0", headers=headers, files=files2, data=data2)
    assert res2.status_code == 201
    img2_id = res2.json()["image_id"]
    assert res2.json()["client_id"] == "browser-2"

    # Log in as user to post AI results
    login_res = client.post("/api/v1/auth/login", json={"username_or_email": "tester", "password": "testpass123"})
    user_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Solve Browser 1 with cells [1, 3]
    client.post(
        f"/api/v1/images/{img1_id}/ai-result?auto_delete_seconds=0",
        headers=user_headers,
        json={"matched_cells": [1, 3], "raw_output": "1, 3"}
    )

    # Solve Browser 2 with cells [6, 8, 9]
    client.post(
        f"/api/v1/images/{img2_id}/ai-result?auto_delete_seconds=0",
        headers=user_headers,
        json={"matched_cells": [6, 8, 9], "raw_output": "6, 8, 9"}
    )

    # Query browser-1 isolated endpoint: must return [1, 3], NEVER browser-2's cells!
    b1_result = client.get("/api/v1/images/by-client/browser-1/latest/result")
    assert b1_result.status_code == 200
    assert b1_result.json()["client_id"] == "browser-1"
    assert b1_result.json()["matched_cells"] == [1, 3]
    assert b1_result.json()["matched_cells"] != [6, 8, 9]

    # Query browser-2 isolated endpoint: must return [6, 8, 9], NEVER browser-1's cells!
    b2_result = client.get("/api/v1/images/by-client/browser-2/latest/result")
    assert b2_result.status_code == 200
    assert b2_result.json()["client_id"] == "browser-2"
    assert b2_result.json()["matched_cells"] == [6, 8, 9]
    assert b2_result.json()["matched_cells"] != [1, 3]


def test_queue_buffering_and_promotion(client, test_user, test_api_key, sample_png_bytes, monkeypatch):
    from backend.app.config import settings
    # Set limit to 2 active images for test
    monkeypatch.setattr(settings, "MAX_ACTIVE_ON_SCREEN", 2)

    raw_key, _ = test_api_key
    headers = {"X-API-Key": raw_key}

    # Upload Image 1 (Slot 1 -> Active)
    files1 = {"file": ("q1.png", sample_png_bytes, "image/png")}
    res1 = client.post("/api/v1/images?wait_for_ai=false&auto_delete_seconds=0", headers=headers, files=files1, data={"client_id": "b-1"})
    assert res1.status_code == 201
    img1_id = res1.json()["image_id"]
    assert res1.json()["status"] == "active"

    # Upload Image 2 (Slot 2 -> Active)
    files2 = {"file": ("q2.png", sample_png_bytes, "image/png")}
    res2 = client.post("/api/v1/images?wait_for_ai=false&auto_delete_seconds=0", headers=headers, files=files2, data={"client_id": "b-2"})
    assert res2.status_code == 201
    img2_id = res2.json()["image_id"]
    assert res2.json()["status"] == "active"

    # Upload Image 3 (Limit 2 reached -> Queued in backend buffer!)
    files3 = {"file": ("q3.png", sample_png_bytes, "image/png")}
    res3 = client.post("/api/v1/images?wait_for_ai=false&auto_delete_seconds=0", headers=headers, files=files3, data={"client_id": "b-3"})
    assert res3.status_code == 201
    img3_id = res3.json()["image_id"]
    assert res3.json()["status"] == "queued"

    # Log in as user
    login_res = client.post("/api/v1/auth/login", json={"username_or_email": "tester", "password": "testpass123"})
    user_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Delete Image 1 -> Slot freed up! Image 3 should be promoted automatically!
    del_res = client.delete(f"/api/v1/images/{img1_id}", headers=user_headers)
    assert del_res.status_code == 200

    # Verify Image 3 was promoted to active
    get_img3 = client.get(f"/api/v1/images/{img3_id}", headers=user_headers)
    assert get_img3.status_code == 200
    assert get_img3.json()["status"] == "active"


def test_clear_all_images(client, test_user, test_api_key, sample_png_bytes):
    raw_key, _ = test_api_key
    headers = {"X-API-Key": raw_key}

    # Upload 2 images
    files1 = {"file": ("c1.png", sample_png_bytes, "image/png")}
    res1 = client.post("/api/v1/images?wait_for_ai=false&auto_delete_seconds=0", headers=headers, files=files1)
    assert res1.status_code == 201

    files2 = {"file": ("c2.png", sample_png_bytes, "image/png")}
    res2 = client.post("/api/v1/images?wait_for_ai=false&auto_delete_seconds=0", headers=headers, files=files2)
    assert res2.status_code == 201

    # Login and call clear/all
    login_res = client.post("/api/v1/auth/login", json={"username_or_email": "tester", "password": "testpass123"})
    user_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    del_all = client.delete("/api/v1/images/clear/all", headers=user_headers)
    assert del_all.status_code == 200
    assert del_all.json()["success"] is True

    # Check images list is empty
    list_res = client.get("/api/v1/images", headers=user_headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 0




