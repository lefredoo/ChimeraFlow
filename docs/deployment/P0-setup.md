# P0 Setup Guide

## Phase P0 - Foundations Complete

**Date:** November 13-14, 2026  
**Duration:** 8 hours  
**Status:** ✓ Complete

---

## What Was Built

### Backend (FastAPI)
- ✓ Main API with health check and sources endpoints
- ✓ Docker containerization (384MB mem_limit, 0.5 CPU)
- ✓ Structured logging
- ✓ CORS configuration
- ✓ Test suite foundation
- ✓ Spike Access script for .mdb reading validation

### Frontend (Next.js)
- ✓ Hello-world page with glassmorphism design
- ✓ API connection test
- ✓ IBM Plex fonts integration
- ✓ Tailwind CSS v4 configuration
- ✓ Responsive layout

### Infrastructure
- ✓ Docker Compose (API + Redis)
- ✓ Memory and CPU limits configured
- ✓ Health checks for both services
- ✓ Read-only data volume mount

### Kiro Artifacts
- ✓ 3 specs: connectors, rule-engine, ui
- ✓ 2 steering files: connectors, security
- ✓ Directory structure ready for hooks and agents

### Data Generation
- ✓ Excel generator (tarifs_fournisseurs.xlsx)
- ✓ WhatsApp generator (commandes_clients.txt)
- ✓ Intentional variations for testing normalization

---

## Local Development Setup

### Prerequisites
```bash
# Backend
Python 3.11+
pip install -r backend/requirements.txt

# Frontend
Node.js 18+
cd frontend && npm install

# Infrastructure
Docker & Docker Compose
```

### Generate Synthetic Data
```bash
# Excel price list
python scripts/generate_excel.py

# WhatsApp export
python scripts/generate_whatsapp.py
```

### Run Backend
```bash
cd backend
cp .env.example .env
# Edit .env with your values
uvicorn main:app --reload
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Run Frontend
```bash
cd frontend
cp .env.example .env.local
# Edit .env.local (NEXT_PUBLIC_API_URL)
npm run dev
# App: http://localhost:3000
```

### Run with Docker Compose
```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## Spike Access - Critical Test

**Status:** Ready to execute (requires mdbtools or access_parser)

```bash
cd backend
python spike_access.py
```

**If spike fails:**
1. Document in `docs/decisions/TECH_DEBT.md`
2. Evaluate alternatives:
   - Option A: Generate .mdb with Jackcess (Java, Windows)
   - Option B: Use pre-generated .mdb file
   - Option C: CSV fallback for demo

---

## Verification Checklist

- [ ] `docker-compose up` starts without errors
- [ ] `curl http://localhost:8000/health` returns 200 OK
- [ ] Frontend displays "ChimeraFlow" with API status
- [ ] Backend logs are structured (JSON format)
- [ ] Redis responds to `redis-cli ping`
- [ ] Spike Access script executes (or failure documented)
- [ ] 3 Kiro specs exist in `.kiro/specs/`
- [ ] Synthetic data files generated in `data/`

---

## Exit Criteria - P0

✓ **Hello-world bout en bout en prod**: Frontend connects to backend  
✓ **Spike Access**: Script ready, waiting for .mdb file  
✓ **3 Specs approuvées**: connectors, rule-engine, ui

---

## Next Phase - P1

**P1 Connecteurs** (20h, Nov 15-19)
- Implement 4 MCP servers (Excel, Access, WhatsApp, Mobile Money)
- Unified record schema
- Contract tests + Property-based tests
- Hooks for parser validation

---

## Deployment Notes

### Vercel (Frontend)
- Build command: `cd frontend && npm run build`
- Output directory: `frontend/.next`
- Environment: `NEXT_PUBLIC_API_URL`

### VPS Hetzner (Backend via Dokploy)
- Dockerfile: `backend/Dockerfile`
- Port: 8000
- Redis: Managed service or separate container
- Volume: `/data` read-only

**Manual deployment steps will be documented in P4.**

---

Built for Kiroween 2026 | ZOBO Hardware Store Demo
