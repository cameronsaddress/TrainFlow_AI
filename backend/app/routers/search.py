
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List
from ..services import search_service
from ..worker import redis_conn
import json

router = APIRouter(
    prefix="/curriculum",
    tags=["curriculum"]
)

class SearchRequest(BaseModel):
    subject: str

class SearchResponse(BaseModel):
    message: str
    queued_count: int
    videos: List[dict]

@router.post("/search_and_queue", response_model=SearchResponse)
async def search_and_queue(request: SearchRequest):
    """
    Searches for videos via LLM and queues them for ingestion.
    """
    print(f"Searching for: {request.subject}")
    
    # 1. Search (LLM)
    videos = await search_service.search_youtube_videos(request.subject)
    
    if not videos:
        return SearchResponse(message="No videos found.", queued_count=0, videos=[])
    
    # 2. Queue (Redis)
    queued_count = 0
    for vid in videos:
        url = vid.get("url")
        if url and "youtube.com" in url or "youtu.be" in url:
            # Add to Redis Queue
            # We mimic the logic from /api/uploads/ingest_youtube in routers/curriculum.py?
            # Actually, standard pattern is to push to 'video_jobs' list.
            # Payload matching worker.py expectations.
            job_payload = {
                "type": "youtube",
                "url": url,
                "user_email": "system_queued@trainflow.ai" 
            }
            redis_conn.rpush("video_jobs", json.dumps(job_payload))
            queued_count += 1
            
    return SearchResponse(
        message=f"Successfully queued {queued_count} videos.",
        queued_count=queued_count,
        videos=videos
    )
