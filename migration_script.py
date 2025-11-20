# migration_script.py
from app import app, db
from models import Task
from sqlalchemy import text

with app.app_context():
    # Add new columns
    with db.engine.connect() as conn:
        try:
            conn.execute(text('ALTER TABLE tasks ADD COLUMN deadline DATETIME'))
            conn.execute(text('ALTER TABLE tasks ADD COLUMN completed_at DATETIME'))
            conn.commit()
            print("✅ Database migration successful!")
        except Exception as e:
            print(f"Migration error (columns may already exist): {e}")
