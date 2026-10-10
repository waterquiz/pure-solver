from backend.app.services.rate_limiter import rate_limiter


def test_rate_limiter_exceeded(client, test_api_key, sample_png_bytes, monkeypatch):
    raw_key, api_key_obj = test_api_key

    # Temporarily set limit to 2 requests per 60 seconds
    rate_limiter.limit = 2
    rate_limiter.window = 60
    rate_limiter.reset()

    files = {"file": ("test.png", sample_png_bytes, "image/png")}
    headers = {"X-API-Key": raw_key}

    # Request 1: Allowed
    res1 = client.post("/api/v1/images", headers=headers, files=files)
    assert res1.status_code == 201

    # Request 2: Allowed
    files = {"file": ("test.png", sample_png_bytes, "image/png")}
    res2 = client.post("/api/v1/images", headers=headers, files=files)
    assert res2.status_code == 201

    # Request 3: Exceeded -> HTTP 429
    files = {"file": ("test.png", sample_png_bytes, "image/png")}
    res3 = client.post("/api/v1/images", headers=headers, files=files)
    assert res3.status_code == 429
    assert res3.json()["error"]["code"] == "RATE_LIMITED"
