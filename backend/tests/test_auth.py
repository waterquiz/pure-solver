def test_login_success(client, test_user):
    res = client.post("/api/v1/auth/login", json={
        "username_or_email": "tester",
        "password": "testpass123"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["username"] == "tester"
    assert data["is_admin"] is True


def test_login_with_email(client, test_user):
    res = client.post("/api/v1/auth/login", json={
        "username_or_email": "tester@example.com",
        "password": "testpass123"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_invalid_password(client, test_user):
    res = client.post("/api/v1/auth/login", json={
        "username_or_email": "tester",
        "password": "wrongpassword"
    })
    assert res.status_code == 401


def test_login_nonexistent_user(client):
    res = client.post("/api/v1/auth/login", json={
        "username_or_email": "ghost",
        "password": "any"
    })
    assert res.status_code == 401


def test_logout(client):
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 200
    assert res.json()["success"] is True
