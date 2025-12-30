import sys
sys.path.append("/app")
from app.db import SessionLocal
from app.models import knowledge as k_models

def main():
    db = SessionLocal()
    try:
        # Fetch all videos
        videos = db.query(k_models.VideoCorpus).all()
        
        # Define exclusion keywords (BJJ/Jiu Jitsu related)
        bjj_keywords = ["bjj", "jiu", "grappling", "guard"]
        
        utility_videos = []
        for v in videos:
            # Check if video is NOT BJJ related
            if not any(k in v.filename.lower() for k in bjj_keywords):
                utility_videos.append(v)
        
        print(f"Total Videos in DB: {len(videos)}")
        print(f"Found {len(utility_videos)} Utility Videos:")
        print("-" * 40)
        for v in utility_videos:
            print(f"{v.filename}")
        print("-" * 40)
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
