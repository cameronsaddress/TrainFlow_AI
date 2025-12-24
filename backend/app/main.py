from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="TrainFlow_AI API",
    description="Enterprise AI-Assisted Training & Work Order Creation Guide Generator",
    version="7.33.0"
)

from fastapi.staticfiles import StaticFiles

# CORS Middleware setup
origins = [
    "http://localhost:3000",
    "http://localhost:2026",
    "*", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)

# Serve Static Files (Screenshots/Clips)
import os
os.makedirs("/app/data", exist_ok=True) # Ensure dir exists
app.mount("/data", StaticFiles(directory="/app/data"), name="data")

# Include Routers with Auth
from .routers import api
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException, status
import os

security = HTTPBearer()

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Base token verification. Returns role ('admin' or 'viewer').
    """
    token = credentials.credentials
    admin_token = os.getenv("API_KEY_ADMIN", "dev-admin-token")
    viewer_token = os.getenv("API_KEY_VIEWER", "dev-viewer-token")
    
    if token == admin_token:
        return "admin"
    elif token == viewer_token:
        return "viewer"
    else:
        # Fallback for legacy single-token dev env
        legacy = os.getenv("API_KEY", "dev-secure-token")
        if token == legacy:
            return "admin" # Legacy is admin by default
            
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

def verify_admin(role: str = Depends(verify_token)):
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return role

def verify_viewer(role: str = Depends(verify_token)):
    # Viewers and Admins can view
    return role  

# Public endpoints
@app.get("/")
def read_root():
    return {"message": "Welcome to TrainFlow_AI API", "status": "active"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Protected Routers security assignment
# Processing: Mixed (Get=Viewer, Put/Post=Admin)
# Since router-level applies to all, we might need to be semantic or split router.
# Ideally, we modify api.py to use `Depends(verify_admin)` on specific endpoints, 
# but for this scaffold, let's allow Viewers to see progress/flows, but only Admins to Generate WO/Save.
# Quick fix: Apply Viewer to Processing Router generally, but override in api.py if supports... 
# actually FastAPI dependencies on router apply to all. 
# Better Strategy: Apply verify_token (generic) to router, and specific checks inside endpoints? 
# Or just split usage.
# Given complexity of editing `api.py` everywhere, let's make a tradeoff:
# Uploads = Admin
# Processing = Viewer (Read-only mostly, but Save/WO is write). 
# Let's apply 'verify_viewer' to Processing/Export (Read access), 
# AND we will modify `api.py` to add `verify_admin` to critical WRITE endpoints.

app.include_router(api.processing_router, prefix="/api")
app.include_router(api.export_router, prefix="/api", dependencies=[Depends(verify_viewer)])
app.include_router(api.glossary_router, prefix="/api")
# app.include_router(api.uploads_router) # Removed duplicate
app.include_router(api.uploads_router, prefix="/api")
app.include_router(api.analysis_router, prefix="/api") # New AI Field Assistant
app.include_router(api.public_router, prefix="/api") # GPU Status, etc.

from .routers import realtime, knowledge, curriculum
app.include_router(realtime.realtime_router)
app.include_router(knowledge.router, prefix="/api") # Knowledge API
app.include_router(curriculum.router, prefix="/api") # Curriculum API

# Create Tables (for dev/prototype simplicity, usually use Alembic)
from .db import engine, Base
from .models import models, knowledge # Register Knowledge models
Base.metadata.create_all(bind=engine)
