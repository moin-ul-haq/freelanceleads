# FreelanceLeads 🚀

An **AI-powered local lead generation SaaS platform** tailored for freelancers, agency owners, and digital marketers. It automates the entire workflow from discovering high-quality local business clients to auditing their online presence and sending highly personalized, AI-generated outreach.

## 🎯 Target Audience
- Web designers seeking local business clients
- Local SEO freelancers and agencies
- Google Business Profile (GBP) optimization specialists
- Cold email outreach professionals

## ✨ Core Features

- **Advanced Lead Discovery**: Find leads by niche and city (e.g., "Plumbers in Toronto"). Multi-source gathering backed by Google Places, caching, and custom heuristics.
- **Smart Opportunity Scoring (0-100)**: Automatically prioritizes leads based on missing websites, poor PageSpeed, missing SSL, low ratings, and weak SEO.
- **Automated Audits**: Generates detailed, white-labeled PDF website audits (PageSpeed, SEO, Social Presence).
- **AI-Powered Outreach**: Uses Anthropic's Claude to generate hyper-personalized cold email pitches and proposals.
- **Integrated CRM (Pipeline)**: Kanban-style deal tracking, pipeline stages, and CSV exports.
- **Campaign Management**: Unified inbox, email campaign sequences, and follow-up tracking.

## 🛠️ Technology Stack

- **Backend**: Django 6.0+ & Django REST Framework (DRF)
- **Database**: PostgreSQL (SQLite for local dev)
- **Cache & Message Broker**: Redis
- **Background Tasks**: Celery & Celery Beat
- **Authentication**: JWT (djangorestframework-simplejwt)
- **AI Engine**: Anthropic API (Claude)
- **Payments**: Stripe

## 📁 Project Structure

The project is modularized into several Django apps:

- `accounts/` - User authentication, team seats, and JWT.
- `billing/` - Stripe subscriptions, plan limits, and quotas.
- `leads/` - Business discovery, opportunity scoring, and caching.
- `ai_engine/` - AI pitch generation and sentiment analysis.
- `outreach/` - Email campaigns, follow-ups, and inbox tracking.
- `pipeline/` - Kanban CRM for tracking deals and client statuses.
- `services/` - Thin wrappers for external APIs (Google Places, Stripe, Anthropic).

## 🚀 Getting Started (Local Development)

### Prerequisites
- Python 3.12+ (Django 6 requirement)
- Node.js or Bun (for the React frontend)
- Redis Server — **optional in dev**: without `REDIS_URL` the backend falls back to an
  in-process cache and runs Celery tasks eagerly (synchronously), so no broker is needed.

### Backend

1. **Create a virtual environment and install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment variables**
   Copy `.env.example` to `.env` and fill in what you have. Everything is optional in dev:
   - `SERP_API_KEY` — SerpAPI key for live lead search (Google Maps)
   - `OPENAI_API_KEY` — AI pitch/proposal/chat generation
   - `PAGESPEED_API_KEY` — Google PageSpeed scores in audits
   - `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` — billing
   - `FERNET_ENCRYPTION_KEY` — required before connecting outreach email accounts
   - `FRONTEND_URL` — CORS + Stripe redirects (default `http://localhost:5173`)

3. **Database, plans, and demo data**
   ```bash
   python manage.py migrate
   python manage.py seed_plans        # free / pro / max plans
   python manage.py seed_demo_leads   # optional: demo leads so search works without SerpAPI
   ```

4. **Run the API server**
   ```bash
   python manage.py runserver 8001
   ```
   API docs: http://localhost:8001/api/docs/ · Health: http://localhost:8001/api/health/

5. **Celery (only when `REDIS_URL` is set)**
   ```bash
   celery -A freelanceleads worker -l info --pool=solo
   celery -A freelanceleads beat -l info
   ```

### Frontend (React + Vite, in `frontend/`)

```bash
cd frontend
npm install        # or: bun install
npm run dev        # or: bun run dev
```

Open http://localhost:5173 — the dev server proxies `/api` to the backend on port 8001
(override with `VITE_API_PROXY=http://localhost:<port>`).

Demo searches after `seed_demo_leads`: **plumber / toronto**, **dentist / austin**,
**electrician / lahore**.

## 📜 License
*Proprietary - All rights reserved.*
