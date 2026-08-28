# EvidenceLens

**S3: EvidenceLens** — A multimodal claim verification and provenance workbench.

EvidenceLens accepts a text claim (e.g. a social-media post) and an optional image/video,
then extracts atomic sub-claims, retrieves supporting or contradicting evidence from a corpus,
analyzes uploaded media for reuse/context mismatch, and produces a structured verdict with
full provenance so an analyst can inspect and correct results.

---

## Repository layout

```
├── backend/        # Python · FastAPI · PostgreSQL · pgvector
├── frontend/       # React · TypeScript · Vite · Tailwind CSS   (har_dev)
├── docs/
│   └── API_CONTRACT.md   # Source of truth between FE ↔ BE
├── .gitignore
└── README.md
```

---

## Branch strategy

| Branch | Owner | Purpose |
|--------|-------|---------|
| `main` | — | Stable releases |
| `dev` | Both | Integration branch |
| `var_dev` | Backend dev | Backend work |
| `har_dev` | Frontend dev | Frontend work |

**Never commit directly to `dev` or `main`.**  
Open a PR from your feature branch → `dev`.

---

## Quick start — Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# or: .venv\Scripts\activate    # Windows CMD/PowerShell

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in DATABASE_URL and GEMINI_API_KEY

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## Quick start — Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at: http://localhost:5173

> The frontend uses mock data while the backend is not running.  
> See `docs/API_CONTRACT.md` for the full API specification.

---

## Environment variables

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (supports Supabase) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `MAX_UPLOAD_BYTES` | Max media upload size in bytes (default 20 MB) |

**Never commit `.env`.**

---

## API

See [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) for the complete API specification.

Core endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/analyze` | Submit claim + optional media for verification |
| GET | `/evidence/{id}` | Retrieve a single evidence item |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI, Python 3.11+ |
| Database | PostgreSQL + pgvector |
| Migrations | Alembic |
| AI / Reasoning | Google Gemini |
| Embeddings | sentence-transformers |
| Media analysis | CLIP, perceptual hashing (imagehash) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
