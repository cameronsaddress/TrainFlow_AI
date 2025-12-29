
import sys
sys.path.append("/app")
from app.db import SessionLocal, engine
from app.models import knowledge
from app.services import hybrid_publisher
import sys

# 1. Create Table (if not exists)
print("Creating tables...")
knowledge.Base.metadata.create_all(bind=engine)

# 2. Publish
db = SessionLocal()
try:
    print("Publishing Course 14...")
    pub = hybrid_publisher.publish_course(db, 14)
    print(f"Success! Published ID: {pub.id}")
    print(f"Title: {pub.title}")
    print(f"Modules: {pub.total_modules}")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
