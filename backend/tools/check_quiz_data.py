import os
import sys
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:2028/trainflow")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_quizzes():
    db = SessionLocal()
    try:
        # Get latest curriculum
        sql = text("SELECT id, title, structured_json FROM training_curricula ORDER BY created_at DESC LIMIT 1")
        result = db.execute(sql).fetchone()
        
        if not result:
            print("No curriculum found.")
            return

        curr_id, title, data = result
        print(f"Checking Curriculum ID: {curr_id}, Title: {title}")
        
        modules = data.get('modules', [])
        total_lessons = 0
        lessons_with_quiz = 0
        
        for m_idx, m in enumerate(modules):
            print(f"Module {m_idx+1}: {m.get('title')}")
            for l_idx, l in enumerate(m.get('lessons', [])):
                total_lessons += 1
                quiz = l.get('quiz')
                if quiz:
                    lessons_with_quiz += 1
                    print(f"  [x] Lesson {l_idx+1}: Has Quiz ({len(quiz.get('questions', []))} qs)")
                else:
                    print(f"  [ ] Lesson {l_idx+1}: No Quiz")
                    
        print(f"\nStatus: {lessons_with_quiz}/{total_lessons} lessons have quizzes.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_quizzes()
