
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import knowledge as k_models

# Setup DB
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

TARGET_FILES = [
    "Jiu_Jitsu_For_Dummies_-_An_Introduction_To_Brazilian_Jiu_Jitsu.mp4",
    "An_Alternative_To_Pulling_Guard_When_Grappling_On_The_Knees.mp4",
    "The_Best_Jiujitsu_Move_for_Total_Beginners_KEENANONLINE.COM.mp4",
    "The_3_Most_Important_Jiu_Jitsu_Techniques_For_A_BJJ_White_Belt_by_John_Danaher.mp4"
]

def inspect():
    print(f"{'ID':<5} | {'Status':<10} | {'Docs?':<5} | {'Transcript Len':<15} | {'Filename'}")
    print("-" * 100)
    
    videos = db.query(k_models.VideoCorpus).filter(k_models.VideoCorpus.filename.in_(TARGET_FILES)).all()
    
    for v in videos:
        t_text = v.transcript_text or ""
        o_text = v.ocr_text or ""
        t_len = len(t_text)
        has_docs = "YES" if t_len > 0 else "NO"
        
        print(f"{v.id:<5} | {v.status:<10} | {has_docs:<5} | {t_len:<15} | {v.filename}")

if __name__ == "__main__":
    inspect()
