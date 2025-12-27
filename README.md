# TrainFlow AI: Enterprise Multimodal Workflow Agent

**Version**: 8.0.0 (Elite Architecture)
**Architecture**: Hybrid Agentic (FastAPI + Next.js + GPU Microservices)

TrainFlow AI is an advanced "Field-to-Office" automation system that transforms raw video footage of industrial procedures into verifiable, step-by-step training guides. It leverages a sophisticated multimodal pipeline (ASR, Computer Vision, LLM Reasoning) and a **Knowledge Engine** to autonomously "watch" a video, understand the intent, and generate succinct, rule-compliant training modules.

---

## 🚀 Recent Feature Updates (v8.0)

### 1. Elite UI & Learning Command Center
-   **Curriculum Dashboard**: A premium, glassmorphic "Command Center" (`/curriculum/[id]`) offering radial progress gauges, neon data visualization, and a "Mission Unit" layout.
-   **Smart Assist Sidebar**: A floating, non-intrusive AI companion that provides contextual help and compliance guardrails for every lesson.
-   **Instant Load Architecture**: Optimized backend queries ("Smart Load") that filter and defer heavy text payloads, reducing load times by 95%.

### 2. AI Lesson Quizzes
-   **Automated Generation**: The pipeline automatically generates 3-15 question "Knowledge Checks" for every lesson during the enrichment phase.
-   **Interactive Tiles**: Quizzes are embedded directly in the lesson list with immediate feedback.
-   **Weighted Metrics**: Course completion is now a weighted average of **Watch Time (80%)** and **Quiz Performance (20%)**.

### 3. Smart PDF Streaming & RAG
-   **Buffered Streaming**: "Smart Stream" technology delivers instant PDF access without downloads.
-   **Deep Links**: AI citations link directly to specific page offsets.

---

## 🏗 System Architecture

The system follows a microservices event-driven architecture optimized for NVIDIA Grace Blackwell (GB10) infrastructure.

```mermaid
graph TD
    Client[Next.js Frontend] -->|Upload/View| Gateway[FastAPI Backend]
    
    Gateway -->|Store| MinIO[MinIO Object Store]
    Gateway -->|Meta| PG[(PostgreSQL + pgvector)]
    Gateway -->|Queue| Redis[Redis Queue]
    
    subgraph "GPU Worker Cluster"
        Worker[Python Worker] -->|Pop| Redis
        Worker -->|Pull| MinIO
        
        ASR[NeMo Parakeet 1.1B]
        CV[YOLOv8-World + EasyOCR]
        LLM[x-ai/grok-4.1-fast]
        
        Worker --> ASR
        Worker --> CV
        Worker --> LLM
    end
    
    Gateway -->|Stream| Client
```

---

## 🛠 Technology Stack

### Frontend (`/frontend`)
-   **Framework**: Next.js 14 (App Router, TypeScript)
-   **Styling**: TailwindCSS, Framer Motion, Lucide Icons.
-   **State**: React Hooks + LocalStorage Persistence.
-   **Key Components**:
    -   `CourseDashboard`: The main hero view for a curriculum.
    -   `LessonQuizTile`: Interactive quiz engine.
    -   `SmartAssistSidebar`: Floating RAG context panel.
    -   `VideoPlayer`: Custom interactive player with time-tracking.

### Backend API (`/backend`)
-   **Framework**: FastAPI (Python 3.10+)
-   **Database**: PostgreSQL 15 + `pgvector` (Vector Search).
-   **Queue**: Redis (Pub/Sub).
-   **Storage**: MinIO (S3 Compatible).

### Core AI Services (`backend/app/services`)
| Service | Module | Description |
| :--- | :--- | :--- |
| **Curriculum Architect** | `curriculum_architect.py` | The "Brain". Aggregates videos, generates course structures, and creates quizzes. |
| **ASR Engine** | `asr.py` | NeMo Parakeet 1.1B for speech-to-text. |
| **Computer Vision** | `cv.py` | YOLOv8-World + EasyOCR for screen text and object detection. |
| **LLM Gateway** | `llm.py` | Interface for x-ai/grok-4.1-fast and Gemini Flash. |
| **Field Assistant** | `field_assistant.py` | RAG engine for Q&A. |
| **Video Clipper** | `video_clip.py` | FFmpeg wrapper for slicing and streaming. |

---

## 🚀 Setup & Deployment

### Prerequisites
-   Docker Engine + Docker Compose.
-   NVIDIA Container Toolkit (for GPU acceleration).
-   API Keys: `OPENAI_API_KEY` (or OpenRouter equivalent) in `.env`.

### 1. Build and Run
```bash
# Start all services (Backend, Frontend, DB, Redis, MinIO)
docker-compose up --build -d
```

### 2. Access Points
-   **Frontend**: `http://localhost:2026`
-   **Backend API**: `http://localhost:2027/docs`
-   **MinIO Console**: `http://localhost:2031` (User/Pass: `minioadmin`)
-   **Database**: `localhost:2028`

---

## 🧪 Development & Tools

### CLI Tools
The system includes utility scripts in `backend/tools/` for management and debugging:

-   **Backfill Quizzes**: Hydrate an existing course with AI quizzes.
    ```bash
    docker exec trainflow-backend python3 /app/tools/hydrate_quizzes.py
    ```

-   **Audit Curriculum**: Check payload sizes and module counts.
    ```bash
    docker exec trainflow-backend python3 /app/tools/audit_curriculum_final.py
    ```

-   **Repair Video Summaries**: Regenerate missing summaries.
    ```bash
    docker exec trainflow-backend python3 /app/tools/repair_video_summaries.py
    ```

### Testing
Run the test suite inside the container:
```bash
docker exec trainflow-backend pytest tests/
```

---

## 📂 Project Structure

```text
/
├── backend/
│   ├── app/
│   │   ├── main.py              # Entry point
│   │   ├── routers/             # API Endpoints (curriculum, api, knowledge)
│   │   ├── services/            # Core Business Logic (AI, RAG, Parsing)
│   │   └── models/              # SQLAlchemy Tables
│   ├── tools/                   # Admin Scripts
│   └── tests/                   # Pytest Suite
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js Pages
│   │   ├── components/          # Reusable UI (QuizTile, Dashboard)
│   │   └── lib/                 # Utilities
├── docker-compose.yml           # Infrastructure Definition
└── README.md                    # System Documentation
```
