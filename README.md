# Stat Analyzer MVP

A rule-based statistical analysis platform for clinical research.
Combines a strictly validated Python statistical engine with a user-friendly React interface.

## Project Structure

- `backend/`: FastAPI application (Python)
- `frontend/`: React application (Vite + Tailwind)
- `docs/`: Project documentation and specifications

## Getting Started

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
