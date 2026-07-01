from app.core.security import hash_password
from app.database.session import Base, SessionLocal, engine
from app.models.admin import Admin

# Make sure tables exist if this is run before the app has started once.
Base.metadata.create_all(bind=engine)


def create_admin():
    db = SessionLocal()
    try:
        existing = db.query(Admin).filter(Admin.email == "admin@wayneesolutions.com").first()
        if existing:
            print("Admin already exists.")
            return

        admin = Admin(
            full_name="Wayne E Solutions Admin",
            email="admin@wayneesolutions.com",
            password=hash_password("wayne123"),
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print("Admin created successfully!")
        print("  email:    admin@wayneesolutions.com")
        print("  password: wayne123")
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
