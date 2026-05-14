# FreelanceLeads

## Lead Generation SaaS Platform

###### ─────────────────────────────

### Technical Product Specification

##### For Development Team

###### Version 1.0 | May 2026

###### Prepared by: Product Owner


## 1. Product Overview

###### FreelanceLeads is an AI-powered local lead generation SaaS platform built for freelancers and

###### agency owners who need to find and close local business clients. The platform automates the

###### entire workflow from discovering potential clients to sending personalized outreach — replacing

###### tools like FreelanceLeads.io with an enhanced, South-Asia-friendly alternative.

#### 1.1 Target Users

- Web designers looking for local business clients
- Local SEO freelancers and agency owners
- Google Business Profile (GBP) optimization specialists
- WordPress developers and rank-and-rent operators
- Cold email outreach professionals

#### 1.2 Core Value Proposition

###### A freelancer enters a niche (e.g., "plumber") and a city (e.g., "Toronto"), and the platform

###### instantly returns scored leads with website audit data, competitor comparisons, AI-generated

###### cold email pitches, and one-click outreach — all in one dashboard.

#### 1.3 Competitive Reference

###### FreelanceLeads.io is the primary competitor. Key observations from analysis:

- Returns ~960 results per search for popular niches (e.g., Real Estate Agent + Toronto)

###### by combining Google Places, Yelp, Yellow Pages, BBB, LinkedIn, and other data

###### sources into a pre-built database.

- Google Places API alone returns max 60 results per query. All 960+ result tools use pre-

###### aggregated multi-source databases.

- Scores businesses 0–100 using weighted algorithms across technical and local SEO

###### signals.

- FreelanceLeads.io gaps we will fill: WhatsApp outreach, deep social media audit,

###### Google Reviews sentiment analysis, Urdu/Hindi language support, local payment

###### methods (JazzCash, EasyPaisa), technology stack detection, and local search volume

###### data.


## 2. System Architecture

#### 2.1 Technology Stack

###### Layer Technology Hosting / Service

###### Frontend Next.js + Tailwind CSS Vercel (free hobby / $20/mo pro)

###### Backend API

```
Django + Django REST
```
###### Framework Railway / DigitalOcean / Render^

###### Main Database PostgreSQL Supabase or Railway ($10/mo)

###### Cache + Queue Broker Redis Upstash Redis (free 10k req/day)

###### Background Tasks Celery + Celery Beat Self-hosted on backend server

###### Object Storage Cloudflare R2 (S3-compatible) Free 10GB/mo — no egress fees

###### CDN Cloudflare Free

###### Auth

```
JWT (djangorestframework-
```
###### simplejwt)

###### Self-managed

###### Payments Stripe 2.9% + $0.30 per transaction

###### Transactional Email Resend / SendGrid Resend free 3k/mo; $20/mo after

###### Error Tracking Sentry Free tier

###### Container / Deploy Docker + GitHub Actions CI/CD pipeline

#### 2.2 Django Project Structure

###### The project follows a modular Django application structure:

###### Directory / File Responsibility

###### config/settings/ Base, development, and production Django settings

###### config/celery.py Celery app initialization and task routing

###### apps/accounts/

```
Module 1 — User registration, JWT auth, team seats, usage
```
###### counters

###### apps/billing/ Module 2 — Stripe subscriptions, plan quotas, webhook handling

###### apps/leads/ Module 3 — Business discovery, opportunity scoring, caching

###### apps/audits/ Module 4 —^ Website audit, PageSpeed, SSL, SEO checks, PDF

###### reports

###### apps/ai_engine/ Module 5 —^ Claude API integration, pitch generation, sentiment

###### analysis

###### apps/outreach/ Module 6 — Email campaigns, SMTP, follow-up sequences, inbox


###### apps/pipeline/ Module 7 — Kanban CRM, deal tracking, proposals, CSV export

###### apps/backlinks/ Module 8 — Competitor backlinks, NAP audit, guest post finder

###### apps/site_builder/ Module 9 —^ AI demo website generator, portfolio pages, case

###### studies

###### services/ Thin wrappers for external APIs: Google Places, PageSpeed,

###### DataForSEO, Anthropic, Hunter.io, Stripe, Moz

###### core/ Shared utilities: quota_guard, rate_limiter, permissions, pagination


## 3. Lead Discovery & Scoring Flow

#### 3.1 How Leads Are Fetched

###### The leads module is the core of the product. When a user searches for a niche and city, the

###### following sequence executes:

###### Step Component Action

###### 1 Frontend User enters niche "plumber" + city "Toronto, ON"

###### 2 JWT Middleware Verify user token and extract user ID

###### 3 quota_guard.py Check if user has remaining searches for their plan (Redis counter)

###### 4 Cache Layer 1

```
Check Redis for cache key "leads:plumber:toronto:CA" — TTL 24
```
###### hours

###### 5 Cache Layer 2 If Redis miss, check PostgreSQL SearchCache table — TTL 7 days

###### 6 Google Places API

```
If DB miss, call Text Search API ($0.032/1000). Returns up to 20
```
###### businesses with place_id, name, address, phone, website, rating

###### 7 Celery Group

```
Launch 20 parallel Celery tasks — one per business for audit +
```
###### enrichment

###### 8 Scoring Engine Calculate 0–100 opportunity score per business (see Section 3.2)

###### 9 PostgreSQL + Redis Save results to SearchCache table. Write to Redis with 24hr TTL

###### 10 API Response

```
Return sorted leads to frontend with source flag: "redis_cache" /
```
###### "db_cache" / "google_api"

#### 3.2 Opportunity Score Algorithm (0 – 100)

###### Each lead receives a composite opportunity score. Higher score = more opportunity for the

###### freelancer to pitch services:

###### Signal Weight Logic

###### No website exists − 30 pts^ Business has no web presence at all

###### No SSL certificate − 20 pts HTTP only — security risk

###### PageSpeed score < 50 − 20 pts Google PageSpeed Insights API (mobile)

###### Rating < 3.5 stars − 15 pts Low rating signals reputation opportunity

###### Review count < 10 − 15 pts

```
Few reviews — reputation building
```
###### needed

###### Missing meta title/description − 10 pts Detected via HTML scraping

###### No schema markup − 10 pts^ JSON-LD / structured data missing


###### No social media presence − 10 pts No FB/Instagram/Twitter detected

###### Score interpretation: 80–100 = Hot Lead (many problems to fix), 50–79 = Warm Lead, 0–49 =

###### Low opportunity.

#### 3.3 Caching Strategy — Cost Optimization

###### Google Places API costs $32 per 1,000 searches. Without caching, 1,000 daily searches =

###### $32/day. With 3-layer caching, the same traffic costs approximately $3–5/day (80–90%

###### savings).

###### Layer Storage TTL Hit Cost

###### Layer 1 Redis (Upstash) 24 hours Free — response < 5ms

###### Layer 2

```
PostgreSQL
```
###### (SearchCache)

###### 7 days

```
Free — also writes back to
```
###### Redis

###### Layer 3 Google Places API No cache

```
$0.032 per search — cold
```
###### miss only

###### Cache key format: leads:{niche}:{city}:{country_code} — all lowercase, spaces replaced with

###### underscores. Example: leads:plumber:toronto:CA

###### Popular searches are refreshed automatically at 2am via Celery Beat before they expire, so

###### users always get fresh data without triggering API calls.


## 4. External APIs & Data Sources

#### 4.1 Lead Data Sources

###### To return 500–1000+ leads per search (matching competitor volume), the platform aggregates

###### data from multiple sources into a pre-built database. Google Places alone returns a maximum of

###### 60 results.

###### Source Max Results Cost Data Provided

###### Google Places API 60 / query $32/

```
Name, address, phone, website, rating,
```
###### reviews, GBP status

###### Yelp API 200+ Freemium

```
Business details, reviews, photos,
```
###### categories

###### Yellow Pages (scrape) 500+ Free

```
Business name, address, phone,
```
###### category

###### BBB Directory (scrape) 200+ Free

```
Accreditation status, reviews, contact
```
###### info

###### Foursquare API 300+ Free tier Business data, categories, tips

#### 4.2 Enrichment APIs

###### API Input Cost/Call Output

###### Google PageSpeed Website URL FREE

```
Mobile/desktop score, load time,
```
###### Core Web Vitals

```
Hunter.io — Combined
```
###### Enrichment

###### Email address

```
0.2 credits
```
###### (~$0.008)

```
Owner name, LinkedIn URL,
```
###### Twitter, job title, company info

```
Hunter.io — Domain
```
###### Search

###### Domain name

```
1 credit
```
###### ($0.04)

```
All email addresses + names +
```
###### roles at that domain

###### Outscraper — Reviews Google Place ID $3/1000 50+ reviews with text, rating,

###### date

###### Twilio Lookup Phone number $0.005 Carrier info, number type

###### (mobile/landline), validation

###### DataForSEO Domain / keyword ~$0.05/task Backlinks, SERP rankings,

###### domain authority, keyword data

#### 4.3 Waterfall Enrichment Strategy

###### To minimize API costs, enrichment follows a waterfall — free sources are tried first, paid APIs

###### only fire when free sources return nothing:

- Step 1: Google Places API — gets phone + website (FREE)


- Step 2: Crawl /contact page of website — extract email (FREE)
- Step 3: Hunter.io Domain Search — if no email found ($0.04)
- Step 4: Hunter.io Combined Enrichment — LinkedIn + owner name ($0.008)
- Step 5: Outscraper — deep reviews only on user request ($0.003/review)

###### Result: 60–70% of leads are fully enriched at zero cost. Total cost per fully enriched lead

###### averages $0.015.


## 5. Feature Specification — All 42 Features

###### Features are organized into 4 build phases. Each phase depends on the previous one being

###### stable.

#### Phase 1 — Foundation (Build First)

###### Everything depends on this phase. No other module works without accounts and billing.

###### Module: accounts

###### Feature Technical Notes

###### User model with plan field

```
Extend AbstractUser. Add plan field
```
###### (free/pro/max), team_id FK, created_at

###### JWT login & register APIs

```
djangorestframework-simplejwt. Endpoints: POST
/auth/register/, POST /auth/login/, POST
```
###### /auth/refresh/

###### Google OAuth (allauth)

```
django-allauth + dj-rest-auth. Social login via
```
###### Google — reduces signup friction

###### Team seats model

```
TeamSeat model: team_id, user_id, role
```
###### (owner/member). Pro = 1 seat, Max = 3 seats

###### UsageCounter + monthly reset

```
Redis keys: quota:{user_id}:{action}. Celery Beat
resets at billing cycle start. Actions: search,
```
###### email_send, ai_pitch, backlink_search

###### Module: billing

###### Feature Technical Notes

###### Stripe checkout session API

```
POST /billing/checkout/ — creates Stripe
Checkout Session. Returns session URL for
```
###### redirect

###### Stripe webhook handler

```
POST /billing/webhook/ — handles:
checkout.session.completed,
customer.subscription.deleted,
invoice.payment_failed. Updates UserPlan
```
###### accordingly

###### PlanQuota model (3 plans)

```
Free: 3 searches, 0 AI pitches, 0 email sends/mo.
Pro: 100 searches, 100 pitches, 2000 sends.
Max: 1500 searches, unlimited pitches, unlimited
```
###### sends

###### Quota guard middleware

```
core/quota_guard.py — check(user, action) raises
HTTP 429 with plan upgrade prompt if limit hit.
```
###### Uses Redis atomic INCR


###### Usage stats API

```
GET /billing/usage/ — returns current period
```
###### usage vs limits for all quota types

#### Phase 2 — Core Product (Leads & Audits)

###### This IS the product. Users come for leads and audits. Build this phase completely before Phase

###### 3.

###### Module: leads

###### Feature Technical Notes

###### Google Places service wrapper

```
services/google_places.py — wraps Text Search
+ Place Details APIs. Handles pagination, error
```
###### retry, response normalization

###### Lead search API (niche + city)

```
POST /api/leads/search/ {niche, city}. Runs 3-
layer cache check before API call. Returns 20
```
###### scored leads sorted by opportunity score desc

###### Opportunity score algorithm (0–100)

```
4 - factor weighted algorithm: no website (−30), no
SSL (−20), slow PageSpeed (−20), poor reviews
```
###### (−15). See Section 3.2 for full breakdown

###### Save lead + list API

```
POST /api/leads/{id}/save/ and GET
/api/leads/saved/ — user saves promising leads
```
###### for later action. Links to pipeline

###### Niche scanner (5×5 matrix)

```
POST /api/leads/niche-scan/ {niches[5], cities[5]}
— fires 25 searches in parallel via Celery group.
```
###### Returns heatmap data of opportunity scores

###### Bulk city search

```
POST /api/leads/bulk-search/ {niche, cities[10]} —
1 niche × 10 cities. Pro plan feature. Runs async,
```
###### notifies via webhook/email when done

###### Celery async scoring task

```
score_lead_batch.delay(place_ids) — runs
PageSpeed + SSL + meta checks for all 20
businesses in parallel. Results pushed to Redis
```
###### and DB

###### Module: audits

###### Feature Technical Notes

###### PageSpeed API service

```
services/pagespeed.py — calls Google
PageSpeed Insights API (FREE). Fetches mobile
```
###### + desktop scores, load time, Core Web Vitals

###### On-page SEO checker

```
HTML scrape via requests + BeautifulSoup: SSL
(HTTP check), meta title/description present, H
tag, schema markup (JSON-LD), mobile viewport
```
###### meta


###### Social presence detector

```
Checks if business has Facebook, Instagram,
Twitter/X profiles — searches website HTML for
```
###### social links + Google search cross-check

###### NAP citation audit (30+ dirs)

```
Checks Name, Address, Phone consistency
across: Yelp, BBB, YellowPages, Foursquare,
Apple Maps, Bing Places, and 25+ others. Uses
fuzzy matching (fuzz.ratio > 85). Returns
```
###### nap_score 0– 100

###### PDF audit report generator

```
WeasyPrint converts audit data to white-label
PDF. Stored on Cloudflare R2. User downloads or
sends to client. White-label = user can add their
```
###### own logo

###### Lost revenue calculator

```
Heuristic estimate based on industry averages ×
website issues × local search volume. Displayed
as pitch hook ("$3,200/mo in missed leads").
```
###### Labeled as estimate in UI

#### Phase 3 — Intelligence (AI Engine & CRM)

###### These are the differentiating features. Build after core lead search and audits are stable.

###### Module: ai_engine

###### Feature Technical Notes

###### Anthropic service wrapper

```
services/anthropic_ai.py — wraps /v1/messages
endpoint. Model: claude-haiku- 4 - 5 (cheapest,
fastest). Handles prompt building, response
```
###### parsing, error retry

###### AI pitch email generator

```
POST /api/ai/generate-pitch/ {lead_id, tone}.
Feeds audit weaknesses into Claude prompt.
Generates personalized cold email referencing
```
###### specific issues found (slow load, no SSL, etc.)

###### AI proposal generator

```
POST /api/ai/generate-proposal/ {lead_id,
services[], price}. Creates professional proposal
```
###### document. Exported as PDF via WeasyPrint

###### AI chat assistant

```
Multi-turn conversation stored in session. Full
message history sent with each API call (stateless
Claude). Used for help with pitches, objection
```
###### handling, pricing advice

###### Bulk pitch generation (Max plan)

```
POST /api/ai/bulk-pitch/ {lead_ids[]} — fires
Claude API calls in parallel via Celery group. Max
```
###### plan only. 40+ leads at once

###### Module: pipeline


###### Feature Technical Notes

###### Pipeline stages model

```
PipelineStage: user FK, name, color, position.
Default stages: New → Contacted → Interested
```
###### → Proposal Sent → Closed Won → Closed Lost

###### Kanban board API

```
GET /api/pipeline/board/ — returns full board
state: all stages with their leads nested. Single
```
###### query with prefetch_related for performance

###### Drag-drop stage update

```
PATCH /api/pipeline/leads/{id}/stage/ {stage_id}
— atomic update. Logs activity entry. Frontend
```
###### handles optimistic UI update

###### Deal value + follow-up date

```
PipelineLead model fields: deal_value
(DecimalField), follow_up_date (DateField), notes
(TextField). Celery Beat sends follow-up
```
###### reminders via email

###### CSV export

```
GET /api/pipeline/export/?format=csv — streams
CSV response. Includes all pipeline leads with
```
###### stage, deal value, contact info, follow-up date

#### Phase 4 — Growth (Outreach, Backlinks & Sites)

###### Build after the core product is stable and has paying users. These features increase stickiness

###### and ARPU.

###### Module: outreach

###### Feature Technical Notes

###### SMTP account setup

```
Users connect their Gmail/Outlook via SMTP
credentials (stored encrypted). Separate from
transactional email — this is for cold outreach
```
###### sent from user's own address

###### Campaign create + launch

```
Campaign model: name, lead_ids[],
email_template_id, status. POST
/api/outreach/campaigns/ to create. PATCH
```
###### /campaigns/{id}/launch/ to start

###### Celery daily email task

```
Celery Beat fires send_campaign_emails daily at
configured time. Respects daily send limit per
```
###### SMTP account to avoid spam flags

###### Open tracking pixel

```
1×1 transparent PNG at GET
/track/open/{message_id}.png. Sets
EmailMessage.opened_at = now() on first
```
###### request. Invisible to recipient

###### Follow-up sequences

```
SequenceStep model: campaign FK, delay_days,
email_template. Celery checks daily for leads due
```
###### for next step. Stops if reply detected


###### Campaign analytics API

```
GET /api/outreach/campaigns/{id}/stats/ —
returns: sent, delivered, open_rate, click_rate,
```
###### reply_rate, unsubscribe_count

###### Unified inbox

```
Polls SMTP inbox for replies. Matches reply to
lead by email address. Shows all replies grouped
```
###### by lead in single inbox view

###### Module: backlinks

###### Feature Technical Notes

###### DataForSEO service wrapper

```
services/dataforseo.py — wraps backlinks/live,
serp/google/organic/live, domain-analytics
```
###### endpoints. Auth: HTTP Basic with login:password

###### Backlinks hub (4 pipelines)

```
Celery group runs 4 parallel tasks: (1) competitor
backlink analysis via DataForSEO, (2) NAP
citation audit across 30+ directories, (3) guest
post finder via SERP "write for us" searches, (4)
local alliance finder (chambers, BBB, trade
```
###### associations)

###### Brand mention scanner

```
Brave Search API — searches for business name
mentions across the web. Identifies unlinked
mentions (sites that mention but do not link). Pitch
```
###### angle: ask them to add a link

###### Broken link checker

```
HEAD-request crawl of competitor backlink URLs.
If URL returns 404, it is a broken link opportunity.
Pitch to replacement site owner with working
```
###### content

###### Module: site_builder

###### Feature Technical Notes

###### AI demo site generator

```
POST /api/sites/generate/ {lead_id} — Claude
generates 4-section HTML: Hero, Services,
About, Contact. Pre-fills with business name,
niche, city. Stored on R2 at
```
###### demo.domain.com/{slug}

###### Portfolio page + public URL

```
Freelancer's own portfolio page hosted on
platform. Public URL:
app.com/portfolio/{username}. Used in email
```
###### signature and outreach

###### Case study pages

```
Before/after case study: show old audit scores vs
new scores after freelancer's work. Public URL
```
###### shared in proposals to build credibility


## 6. Infrastructure & Hosting

#### 6.1 MVP Hosting Stack (~$15/month)

###### Service What For Cost/mo Provider

###### Frontend hosting Next.js app Free Vercel

###### Backend + Celery Django + workers $5 Railway

###### PostgreSQL Main database $5 Railway / Supabase

###### Redis Cache + Celery broker Free Upstash (10k req/day)

###### Object storage PDFs, AI websites Free Cloudflare R2 (10GB)

###### Transactional email System emails Free Resend (3k/mo)

###### Error tracking Bug monitoring Free Sentry

###### TOTAL MVP running cost ~$10 – 15 Per month

#### 6.2 Scaled Hosting Stack (100+ Users, ~$150/month)

###### Service What For Cost/mo Provider

###### Backend servers (×2) Django + Celery workers $24 DigitalOcean Droplets

###### PostgreSQL Managed database $25 Supabase Pro

###### Redis Cache + queue ~$10 Upstash pay-as-you-go

###### Object storage Files at scale ~$

```
Cloudflare R
```
###### ($0.015/GB)

###### Email (transactional) System + notifications $20 SendGrid

###### Monitoring Performance + logs $15 Datadog / Grafana

###### Nginx + Gunicorn Reverse proxy + WSGI Included Self-managed


## 7. Features FreelanceLeads.io Does NOT Have

###### These are our differentiation opportunities. FreelanceLeads.io is entirely Western-market

###### focused. Our platform targets South Asia and emerging markets where there is zero

###### competition.

###### Missing Feature Priority Our Implementation Plan

###### WhatsApp Outreach 🔥 High

```
WhatsApp message templates + direct wa.me/
link generator. Pakistan/India market closes deals
```
###### via WhatsApp, not email

###### Deep Social Media Audit 🔥 High

```
Check last post date, follower count, engagement
rate for FB/Instagram/TikTok. FreelanceLeads
```
###### only checks "exists or not"

###### Google Reviews Sentiment AI 🔥 High

```
Claude API analyzes review text for top
complaints + praises. Generates pitch angle: "8 of
```
###### your 23 reviews mention slow response time"

###### Technology Stack Detection 🔥 High

```
Detect if site runs on
Wix/WordPress/Shopify/Squarespace. Customize
pitch: "I can migrate your Wix site to WordPress
```
###### for better SEO"

###### Urdu / Hindi / Arabic Support 🔥 Very High

```
Generate pitches in Urdu, Hindi, Arabic. Full
Urdu/Hindi UI. FreelanceLeads.io will never build
```
###### this — massive untapped market

###### Local Payment Methods 🔥 Very High

```
JazzCash, EasyPaisa, Razorpay integration
alongside Stripe. Removes biggest barrier for
```
###### South Asian freelancers

###### Payment Inside Proposals Medium^

```
Stripe "Pay Now" button embedded in proposal
PDF/page. Client pays without leaving the
```
###### document

###### Competitor Monitoring / Alerts Medium

```
Weekly Celery Beat job alerts user: "Your
prospect's competitor gained 5 new backlinks this
```
###### week"

###### Local Search Volume Data Medium

```
Show client how many people search their niche
monthly in their city. DataForSEO keyword data.
```
###### Strengthens pitch

###### Client Onboarding Portal Medium

```
After deal closes: onboarding checklist, contract
template, invoice — all in one place.
```
###### FreelanceLeads has nothing after lead closing


## 8. Build Roadmap

#### 8.1 Phase Timeline

###### Phase Duration Deliverable Success Metric

###### Phase 1 2 – 3 weeks Auth + Billing working

```
User can register, subscribe,
```
###### quota tracked

###### Phase 2 3 – 4 weeks Search + Audit live

```
User searches niche + city, gets
```
###### 20 scored leads with audit

###### Phase 3 2 – 3 weeks AI + CRM live

```
User generates pitch email,
```
###### moves lead through pipeline

###### Phase 4 4 – 6 weeks Full platform Outreach campaigns running,

###### backlinks hub, demo sites

#### 8.2 API Keys Required at Launch

###### Service

```
Phase
```
###### Needed

###### Get From

###### Google Places API Phase 2

```
console.cloud.google.com — enable Places API +
```
###### PageSpeed API. First $200/mo free

###### Stripe API keys Phase 1 dashboard.stripe.com —^ test keys for dev, live

###### keys for production

###### Anthropic (Claude) API Phase 3

```
console.anthropic.com — use claude-haiku- 4 - 5
```
###### model (cheapest, ~$0.003/pitch)

###### Hunter.io API Phase 2

```
hunter.io/api — free 25 credits/mo to start. Growth
```
###### plan $104/mo for scale

###### DataForSEO Phase 4

```
dataforseo.com — pay-per-use. ~$50/mo for
```
###### moderate backlinks usage

###### Outscraper (reviews) Phase 2

```
outscraper.com — $3 per 1000 reviews. Only fire
```
###### on user request, not automatically

###### Resend (transactional email) Phase 1

```
resend.com — free 3,000 emails/mo. $20/mo for
```
###### 50k

#### 8.3 Important Implementation Notes

- All background tasks (audits, email sends, bulk searches) must run via Celery — never

###### block the Django request thread.

- The quota_guard.py must be called at the start of EVERY API view that consumes a

###### quota action — not just the expensive ones.

- Cache keys must use normalized, lowercase inputs. "Electrician" and "electrician" must

###### hit the same cache key.


- All S3/R2 uploads must go through a service wrapper — never expose bucket URLs

###### directly. Use pre-signed URLs with expiry.

- Stripe webhook endpoint must be idempotent — the same webhook can fire multiple

###### times. Use the event ID to prevent double-processing.

- Google Places API: deduplicate results using place_id field — the same business can

###### appear in multiple query result pages.

- Revenue loss calculator values must be clearly labeled as "estimated" in the UI — they

###### are heuristics, not real figures.

- Hunter.io combined enrichment is 0.2 credits (not 1 credit) — use this endpoint for email-

###### to-profile lookups, not the standard enrichment endpoint.

###### FreelanceLeads — Technical Product Specification

###### Version 1.0 | May 2026 | Confidential


