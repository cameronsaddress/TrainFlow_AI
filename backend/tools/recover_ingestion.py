
import os
import sys
import redis
from sqlalchemy import create_engine, text

# Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/trainflow") 
# Note: running inside container vs host. If running via `docker exec backend`, localhost is correct for that container? 
# No, backend connects to 'db'.
# If running this script from HOST, we need exposed port.
# Let's assume we run this via `docker exec -it trainflow-backend python3 tools/recover_ingestion.py`
# So DATABASE_URL should use 'db' or 'trainflow-db' hostname.
# Env var is usually set in backend container.

def recover_jobs():
    print("--- Ingestion Recovery Tool ---")
    
    # 1. Connect to DB
    # We rely on env vars inside the container
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set. Run this inside the backend container.")
        return

    engine = create_engine(db_url)
    conn = engine.connect()
    
    # 2. Connect to Redis
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    r = redis.from_url(redis_url)
    
    # 3. Find Stuck Jobs (INDEXING) and reset them
    print("Checking for stuck 'INDEXING' jobs...")
    # NOTE: Table is video_corpus for Ingestion, videos for main app.
    # We are fixing the Corpus Ingestion system.
    query_stuck = text("SELECT id, filename FROM video_corpus WHERE status = 'INDEXING'")
    stuck_jobs = conn.execute(query_stuck).fetchall()
    
    for job in stuck_jobs:
        print(f"Resetting STUCK job: {job.id} - {job.filename}")
        conn.execute(text("UPDATE video_corpus SET status = 'PENDING' WHERE id = :idx"), {"idx": job.id})
        conn.commit()
        
    # 4. Find Pending Jobs and Re-Queue
    print("Re-queueing 'PENDING' jobs...")
    query_pending = text("SELECT id, filename FROM video_corpus WHERE status = 'PENDING' ORDER BY id ASC")
    pending_jobs = conn.execute(query_pending).fetchall()
    
    count = 0
    for job in pending_jobs:
        print(f"queueing Video {job.id}: {job.filename}")
        r.publish("corpus_jobs", str(job.id))
        count += 1
        
    print(f"--- Recovery Complete. Re-queued {count} jobs. ---")
    conn.close()

if __name__ == "__main__":
    recover_jobs()
