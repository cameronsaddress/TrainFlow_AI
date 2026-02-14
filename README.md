# TrainFlow AI

**Multimodal AI training content generator** — transforms raw video footage into structured, step-by-step training guides using speech recognition, computer vision, and LLM reasoning.

Built with FastAPI, Next.js, PostgreSQL + pgvector, NeMo ASR, YOLOv8, and Docker.

---

## Overview

TrainFlow AI is an enterprise "Field-to-Office" automation system. It watches raw training videos, understands the content through multiple AI modalities, and generates complete training curricula — including lesson structures, quizzes, and searchable knowledge bases.

**Pipeline:**

1. **Ingest** — Upload raw training videos to MinIO object storage
2. **Transcribe** — NeMo Parakeet 1.1B extracts word-level speech transcripts (GPU-accelerated)
3. **Analyze** — YOLOv8-World + EasyOCR detect on-screen text, tools, and procedures
4. **Synthesize** — LLM (Grok via OpenRouter) fuses transcript + vision data into structured curricula
5. **Enrich** — Auto-generate quizzes, AI instructor voiceover, and RAG-indexed knowledge base
6. **Deliver** — Premium dashboard with video player, PDF streaming, and AI assistant

Each training module is generated end-to-end with minimal human intervention.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      TRAINFLOW AI PIPELINE                      │
│                                                                 │
│  ┌──────────┐    ┌─────────┐   ┌─────────┐   ┌─────────┐      │
│  │ Next.js  │◄───│ FastAPI │◄──│  Redis  │──►│  Worker │      │
│  │Dashboard │    │ Backend │   │  Queue  │   │  (GPU)  │      │
│  └──────────┘    └────┬────┘   └─────────┘   └────┬────┘      │
│                       │                            │            │
│                       ▼                            ▼            │
│                  ┌─────────┐        ┌─────────────────────┐    │
│                  │PostgreSQL│        │   GPU AI Services    │    │
│                  │+ pgvector│        │  NeMo Parakeet ASR  │    │
│                  └─────────┘        │  YOLOv8-World + OCR │    │
│                       │             │  LLM via OpenRouter  │    │
│                  ┌─────────┐        └─────────────────────┘    │
│                  │  MinIO  │                                    │
│                  │ Storage │                                    │
│                  └─────────┘                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14 (TypeScript), TailwindCSS, Framer Motion |
| **Backend** | FastAPI (Python 3.10+), Uvicorn |
| **Database** | PostgreSQL 15 + pgvector (vector embeddings) |
| **Queue** | Redis (Pub/Sub) |
| **Storage** | MinIO (S3-compatible object store) |
| **ASR** | NVIDIA NeMo Parakeet 1.1B |
| **Computer Vision** | YOLOv8-World + EasyOCR |
| **LLM** | Grok (x-ai/grok-4.1-fast via OpenRouter, 2M context window) |
| **Voice** | ElevenLabs Turbo v2 (AI instructor audio) |
| **Monitoring** | Prometheus + Grafana |
| **Infrastructure** | Docker Compose (8 containers), NVIDIA GPU |

---

## Features

### Multimodal Video Analysis
- **Speech-to-Text**: NeMo Parakeet 1.1B with word-level timestamps for precise lesson alignment
- **Visual Understanding**: YOLOv8-World detects tools, equipment, and on-screen text via EasyOCR
- **LLM Synthesis**: Grok 4.1 fuses transcript + vision data into structured training modules

### Curriculum Architect
- Automatically generates multi-module course structures from raw video
- Creates lesson hierarchies with learning objectives and key concepts
- Generates 3-15 quiz questions per lesson during enrichment phase
- PDF knowledge base with RAG-powered deep linking

### Premium AI Instructor
- ElevenLabs voice generation for human-like instruction delivery
- Web Audio API real-time frequency visualizer
- Static audio architecture (generated once, served with zero latency)

### Learning Dashboard
- Glassmorphic course command center with radial progress gauges
- Custom video player with time-tracking and lesson alignment
- Smart Assist AI sidebar with contextual help
- Weighted completion metrics: Watch Time (80%) + Quiz Performance (20%)

### Smart PDF Streaming
- Buffered streaming with instant PDF access (no downloads)
- AI citations link directly to specific page offsets
- Full-text search with fuzzy matching

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── routers/             # API endpoints (curriculum, knowledge, api)
│   │   ├── services/
│   │   │   ├── curriculum_architect.py  # Core pipeline orchestrator
│   │   │   ├── asr.py                  # NeMo Parakeet speech engine
│   │   │   ├── cv.py                   # YOLOv8 + EasyOCR vision
│   │   │   ├── llm.py                  # LLM gateway (OpenRouter)
│   │   │   ├── field_assistant.py      # RAG Q&A engine
│   │   │   └── video_clip.py           # FFmpeg video processing
│   │   └── models/              # SQLAlchemy ORM models
│   ├── tools/                   # Admin CLI scripts
│   └── Dockerfile               # NVIDIA PyTorch base image
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js pages (App Router)
│   │   └── components/          # React components (Dashboard, Quiz, Player)
│   └── Dockerfile
├── docker/
│   └── prometheus/              # Monitoring configuration
├── docker-compose.yml           # 8-container orchestration
└── .env.example                 # Required environment variables
```

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with CUDA support
- NVIDIA Container Toolkit installed

### Setup

```bash
# Clone the repository
git clone https://github.com/cameronsaddress/TrainFlow_AI.git
cd TrainFlow_AI

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Build and start all services
docker-compose up --build -d

# Access the dashboard
open http://localhost:2026
```

### Required API Keys

| Service | Purpose | Get Key |
|---------|---------|---------|
| OpenRouter | LLM inference (Grok 4.1) | [openrouter.ai](https://openrouter.ai) |
| ElevenLabs | AI instructor voice generation | [elevenlabs.io](https://elevenlabs.io) |

---

## Infrastructure

**Docker Services (8 containers):**

| Container | Port | Purpose |
|-----------|------|---------|
| `trainflow-backend` | 2027 | FastAPI REST API |
| `trainflow-worker` | -- | GPU pipeline worker (NeMo, YOLOv8, LLM) |
| `trainflow-frontend` | 2026 | Next.js dashboard |
| `trainflow-db` | 2028 | PostgreSQL 15 + pgvector |
| `trainflow-redis` | 2029 | Redis message queue |
| `trainflow-minio` | 2030/2031 | MinIO object storage |
| `trainflow-prometheus` | 9090 | Metrics collection |
| `trainflow-grafana` | 3001 | Monitoring dashboards |

**GPU Configuration:**
- Worker runs with NVIDIA GPU access for NeMo ASR and YOLOv8 inference
- 16GB shared memory allocation for PyTorch dataloaders
- Optimized for NVIDIA Grace Blackwell (GB10) infrastructure

---

## License

MIT
