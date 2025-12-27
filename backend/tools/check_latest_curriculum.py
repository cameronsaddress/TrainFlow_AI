
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def check():
    print("Checking for latest curriculum...")
    sql = text("SELECT id, title, created_at FROM training_curricula ORDER BY id DESC LIMIT 1")
    result = db.execute(sql).fetchone()
    
    if result:
        print(f"FOUND: ID={result[0]} | Title='{result[1]}' | Created={result[2]}")
    else:
        print("NO CURRICULUM FOUND.")

if __name__ == "__main__":
    check()
