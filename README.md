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
- Python 3.10+
- Redis Server (for Celery and Caching)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd freelanceleads
   ```

2. **Create a virtual environment and activate it**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**
   Create a `.env` file in the root directory (alongside `manage.py`). You will need keys for:
   - Django `SECRET_KEY`
   - Stripe API keys
   - Anthropic API Key
   - Google Places/PageSpeed API Keys

5. **Database Setup**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create a Superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the Development Server**
   ```bash
   python manage.py runserver
   ```

8. **Start Celery (in a separate terminal)**
   ```bash
   celery -A freelanceleads worker -l info --pool=solo
   ```
   *(Note: `--pool=solo` is recommended for Windows development.)*

## 📜 License
*Proprietary - All rights reserved.*
