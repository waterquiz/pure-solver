def test_create_and_list_api_key(client, test_user):
    # Log in
    login_res = client.post("/api/v1/auth/login", json={
        "username_or_email": "tester",
        "password": "testpass123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create new API Key
    create_res = client.post(
        "/api/v1/api-keys",
        json={"name": "New Client Key", "scopes": "images:upload,images:read"},
        headers=headers
    )
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["raw_key"].startswith("PS_")
    assert len(created_data["raw_key"]) == 43
    assert created_data["masked_key"].startswith("PS_************")
    key_id = created_data["id"]

    # List API Keys
    list_res = client.get("/api/v1/api-keys", headers=headers)
    assert list_res.status_code == 200
    keys = list_res.json()
    assert any(k["id"] == key_id for k in keys)

    # Toggle status to disabled
    status_res = client.patch(
        f"/api/v1/api-keys/{key_id}/status",
        json={"is_active": False},
        headers=headers
    )
    assert status_res.status_code == 200
    assert status_res.json()["is_active"] is False

    # Delete / revoke key
    del_res = client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert del_res.status_code == 200
