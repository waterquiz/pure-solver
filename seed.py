"""
Database seeding script to initialize default admin account and sample API key.
Usage:
    python seed.py
"""
import sys
from backend.app.database import SessionLocal, init_db
from backend.app.models.user import User
from backend.app.models.api_key import ApiKey
from backend.app.auth.security import hash_password, generate_api_key, hash_api_key, mask_api_key


def seed():
    print("[*] Initializing database schema...")
    init_db()

    db = SessionLocal()
    try:
        # Check if admin user already exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            print("[+] Creating default admin user...")
            admin = User(
                email="admin@example.com",
                username="admin",
                hashed_password=hash_password("admin123"),
                is_active=True,
                is_admin=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print("    Admin created: username='admin', password='admin123', email='admin@example.com'")
        else:
            print("[i] Admin user already exists.")

        # Check if an API key exists for admin
        key_count = db.query(ApiKey).filter(ApiKey.user_id == admin.id).count()
        if key_count == 0:
            print("[+] Generating initial production API key...")
            raw_key = generate_api_key()
            key_hash = hash_api_key(raw_key)
            masked = mask_api_key(raw_key)

            api_key = ApiKey(
                user_id=admin.id,
                name="Default Production Key",
                key_hash=key_hash,
                masked_key=masked,
                scopes="images:upload,images:read,images:delete",
                is_active=True
            )
            db.add(api_key)
            db.commit()
            print("\n=======================================================")
            print("INITIAL API KEY GENERATED (Save this now!):")
            print(f"API Key: {raw_key}")
            print(f"Masked:  {masked}")
            print("=======================================================\n")
        else:
            print("[i] API key already exists for admin.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
