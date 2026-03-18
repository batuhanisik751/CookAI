# CookAI — Development Plan

> AI-powered app that converts short-form cooking videos (TikTok, Instagram Reels) into structured, actionable recipes with ingredient substitution suggestions.

---

## Current Status

**Active Phase:** Phase 4 — Ingredient Substitution Engine

| Phase | Status |
|-------|--------|
| 1. Project Setup & Foundation | Complete (CI/CD deferred) |
| 2. Caption & Metadata Extraction | Complete (retry logic pending) |
| 3. AI-Powered Recipe Extraction | Complete (error reporting & native structured output pending) |
| 4. Ingredient Substitution Engine | Complete |
| 5. Backend API Design & Implementation | Not Started |
| 6. Frontend — Mobile UI | Not Started |
| 7. Testing & Quality Assurance | Not Started |
| 8. Deployment & Infrastructure | Not Started |
| 9. Polish & Launch Prep | Not Started |
| 10. Post-Launch & Future Features | Not Started |

---

## Phase 1: Project Setup & Foundation

### 1.1 — Tech Stack (Decided)
- **Frontend:** React Native (Expo) — cross-platform mobile (iOS + Android)
- **Backend:** Python (FastAPI) — tight AI/ML integration, async-native
- **Database:** PostgreSQL (structured recipe data) + Redis (caching & job queues)
- **ORM / Migrations:** SQLAlchemy + Alembic
- **AI/LLM:** Claude API (Anthropic) for recipe extraction, summarization, and substitution logic
- **Metadata & Captions:** yt-dlp (extract subtitles, captions, and video metadata — no video download)
- **Task Queue:** Celery + Redis as broker
- **Deployment:** Docker containers (target platform TBD — evaluate Railway, Fly.io, or AWS ECS)

### 1.2 — Initialize Project Structure
- [x] Monorepo with `backend/` and `frontend/` at the root
- [x] Configure linting: Ruff (backend), ESLint (frontend)
- [x] Configure formatting: Black (backend), Prettier (frontend)
- [x] TypeScript for frontend, type hints for all Python code
- [x] Add `.env.example` with required environment variables
- [ ] Set up Git branching strategy (main → dev → feature branches)

### 1.3 — CI/CD Pipeline (Deferred — no deployment yet)
- [ ] GitHub Actions for lint, test, and build on every PR
- [ ] Automated deployment to staging on merge to `dev`
- [ ] Production deploy on merge to `main`

### 1.4 — Development Environment
- [x] Docker Compose for local services (Postgres, Redis)
- [ ] Seed scripts for test data
- [x] Hot reload for both frontend and backend

**Deliverable:** Empty but fully scaffolded project that builds, lints, and deploys a "hello world" to staging.

---

## Phase 2: Caption & Metadata Extraction

### 2.1 — Video URL Input & Validation
- [x] Accept TikTok and Instagram Reels URLs
- [x] Validate URL format and platform detection (regex + HEAD request check)
- [x] Normalize URLs (strip tracking params, resolve redirects/short links)
- [x] Return clear error messages for unsupported or invalid URLs
- [x] SSRF prevention (hostname allowlist, private IP rejection)

### 2.2 — Platform Auto-Transcript Extraction (No Video Download)
- [x] Use `yt-dlp` with `--write-subs --write-auto-subs --skip-download` to pull platform-generated captions
- [x] Extract video metadata: title, creator handle, description/caption text, hashtags, duration
- [x] Handle platform-specific subtitle formats (SRT, VTT, JSON) and normalize to plain text
- [x] Fallback chain: manual captions → auto-generated captions → description-only mode
- [ ] Retry logic with exponential backoff for transient failures
- [x] Duration check — reject videos exceeding 300s limit (from metadata, no download needed)

### 2.3 — Transcript Cleanup
- [x] Parse and merge subtitle segments into a continuous transcript
- [x] Remove duplicate/overlapping subtitle segments
- [x] Clean up auto-caption artifacts: filler words, timing stutters, misheard cooking terms
- [x] Normalize measurements ("a cup" → "1 cup", "half a teaspoon" → "1/2 tsp")
- [x] Store raw and cleaned transcripts

### 2.4 — Job Queue & Status Tracking
- [x] Use Celery with Redis as message broker for async job processing
- [x] Job lifecycle: `pending → validating → extracting → synthesizing → complete / failed`
- [x] Expose status endpoint (`GET /api/jobs/{id}`) for frontend polling
- [x] Cache check — same URL returns existing completed job
- [x] No large media files to clean up — only lightweight transcript/metadata stored

**Deliverable:** Given a TikTok/IG URL, the system extracts platform auto-transcripts and metadata without downloading any video.

---

## Phase 3: AI-Powered Recipe Extraction

### 3.1 — Recipe Synthesis (Single LLM Call)
- [x] Combine cleaned transcript + video metadata (caption, hashtags, creator) into a single context
- [x] Send to Claude API with a structured prompt requesting:
  - **Recipe title** (inferred from content)
  - **Servings estimate**
  - **Prep time / Cook time estimates**
  - **Ingredient list** with quantities and units (standardized)
  - **Step-by-step instructions** (numbered, clear, actionable)
  - **Difficulty level** (easy / medium / hard)
  - **Cuisine tags** (e.g., Italian, Korean, Mexican)
- [x] Use structured output (prompt-based JSON + Pydantic validation)
- [x] Implement validation: check that all mentioned ingredients appear in steps, flag inconsistencies
- [x] Handle edge cases: transcript-only mode (no captions), description-only mode (no transcript)

### 3.2 — Confidence Scoring & Human Review Flags
- [x] Assign confidence scores to extracted fields (high/medium/low)
- [x] Lower confidence when working from auto-captions vs manual captions (via prompt guidance)
- [x] Lower confidence when working from description-only (via prompt guidance + `needs_review` flag)
- [x] Flag recipes where the AI is uncertain (e.g., quantities unclear, steps ambiguous)
- [ ] Allow users to report errors or suggest edits (future feature hook)

**Deliverable:** Given a transcript and metadata, produce a complete structured recipe in JSON with title, ingredients, steps, and metadata — using a single Claude API call.

---

## Phase 4: Ingredient Substitution Engine

### 4.1 — Substitution Knowledge Base
- [x] Build or source a substitution dataset (e.g., butter → coconut oil, heavy cream → coconut cream)
- [x] Categorize substitutions by: dietary restriction (vegan, gluten-free, dairy-free, nut-free), availability (common pantry items), flavor profile similarity
- [x] Store in a searchable format (Postgres table)

### 4.2 — Context-Aware Substitution via LLM
- [x] For each ingredient in the extracted recipe, query Claude for substitutions considering:
  - The role of the ingredient in the recipe (structural, flavor, moisture, leavening)
  - How the substitution affects cooking technique or timing
  - Ratio adjustments (e.g., "use 3/4 cup applesauce instead of 1 cup sugar")
- [x] Return substitutions with notes explaining trade-offs

### 4.3 — User Preference Integration
- [x] Allow users to set dietary preferences / allergies in their profile
- [x] Auto-highlight ingredients that conflict with preferences
- [x] Pre-populate substitution suggestions based on user profile

### 4.4 — "What's in My Pantry" Mode (Stretch)
- [x] Users input ingredients they have on hand
- [x] System highlights which recipe ingredients they already have
- [x] Suggests substitutions only for missing items

**Deliverable:** Each recipe includes per-ingredient substitution suggestions, personalized to user preferences.

---

## Phase 5: Backend API Design & Implementation

### 5.1 — API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/recipes/extract` | Submit a video URL for processing |
| GET | `/api/recipes/{id}/status` | Check processing status |
| GET | `/api/recipes/{id}` | Get the full extracted recipe |
| GET | `/api/recipes/{id}/substitutions` | Get ingredient substitutions |
| GET | `/api/recipes` | List user's saved recipes |
| DELETE | `/api/recipes/{id}` | Delete a saved recipe |
| POST | `/api/users/preferences` | Set dietary preferences |
| GET | `/api/users/preferences` | Get dietary preferences |

### 5.2 — Database Schema (SQLAlchemy + Alembic)
- [ ] **users** — id, email, name, created_at
- [ ] **user_preferences** — user_id, dietary_restrictions[], allergies[], pantry_items[]
- [ ] **recipes** — id, user_id, source_url, platform, title, servings, prep_time, cook_time, difficulty, cuisine_tags[], status, confidence_score, created_at
- [ ] **ingredients** — id, recipe_id, name, quantity, unit, order_index, notes
- [ ] **steps** — id, recipe_id, step_number, instruction, duration_estimate, tip
- [ ] **substitutions** — id, ingredient_id, substitute_name, ratio, notes, dietary_tags[]

### 5.3 — Authentication
- [ ] Email/password or OAuth (Google, Apple Sign-In)
- [ ] JWT-based session management
- [ ] Guest mode: allow recipe extraction without account, prompt to save

### 5.4 — Error Handling & Logging
- [ ] Consistent error response format (`{ error: { code, message, details } }`)
- [ ] Structured logging (JSON logs) with request IDs for tracing
- [ ] Log all AI API calls with latency, token usage, and cost tracking

**Deliverable:** Fully functional REST API with auth, recipe CRUD, and substitution endpoints.

---

## Phase 6: Frontend — Mobile UI

### 6.1 — Navigation & Layout
- [ ] Two-tab layout at the bottom:
  - **Steps** tab — step-by-step cooking instructions
  - **Ingredients** tab — full ingredient list with substitutions
- [ ] Top bar: recipe title, back button, share/save actions
- [ ] Home screen: URL input + recent recipes list

### 6.2 — Home / Input Screen
- [ ] Large text input for pasting video URL
- [ ] "Paste from clipboard" shortcut button
- [ ] Platform auto-detection badge (TikTok / Instagram icon)
- [ ] "Extract Recipe" CTA button
- [ ] Loading state: animated progress with status updates (downloading → analyzing → done)

### 6.3 — Steps Screen
- [ ] Numbered step cards with clear typography
- [ ] Each step shows: instruction text, estimated duration (if available), relevant tip or note
- [ ] Optional: "Start Cooking" mode with large text, step-by-step navigation, and voice readback
- [ ] Swipe or tap to advance between steps

### 6.4 — Ingredients Screen
- [ ] Ingredient list with checkboxes (for shopping list / tracking)
- [ ] Each ingredient shows: name, quantity, unit
- [ ] Tap an ingredient to expand substitution options
- [ ] Substitution cards show: alternative ingredient, adjusted ratio, flavor/texture notes
- [ ] Filter by dietary restriction (vegan, GF, etc.)
- [ ] "Copy as shopping list" action

### 6.5 — Recipe Detail Header
- [ ] Recipe title, cuisine tags, difficulty badge
- [ ] Prep time / cook time / servings
- [ ] Source video thumbnail (tap to open original video)
- [ ] Share button (deep link or image export)

### 6.6 — Saved Recipes & History
- [ ] Grid or list view of previously extracted recipes
- [ ] Search and filter by cuisine, difficulty, date
- [ ] Swipe to delete

**Deliverable:** Polished two-tab mobile UI that displays extracted recipes with steps, ingredients, and substitutions.

---

## Phase 7: Testing & Quality Assurance

### 7.1 — Unit Tests
- [ ] Backend: test each service in isolation (URL validator, caption extractor, transcript cleaner, recipe parser, substitution engine)
- [ ] Frontend: component tests with React Testing Library
- [ ] AI pipeline: snapshot tests comparing LLM output against known-good recipes for a set of reference videos

### 7.2 — Integration Tests
- [ ] End-to-end flow: URL input → caption extraction → AI synthesis → API response → UI render
- [ ] Database migration tests
- [ ] Auth flow tests (signup, login, token refresh, guest mode)

### 7.3 — AI Output Quality Testing
- [ ] Curate a test set of 20–30 cooking videos across cuisines and platforms
- [ ] Manually write "golden" recipes for each
- [ ] Score AI output against golden recipes on: ingredient completeness, step accuracy, quantity precision
- [ ] Track quality metrics over time as prompts evolve

### 7.4 — Performance & Load Testing
- [ ] Benchmark caption extraction + synthesis pipeline (target: < 15s per recipe)
- [ ] Load test API endpoints (target: 100 concurrent users)
- [ ] Monitor LLM API latency and cost per recipe

### 7.5 — Accessibility & Usability
- [ ] Screen reader compatibility
- [ ] Color contrast compliance (WCAG AA)
- [ ] Test on low-end devices and slow networks
- [ ] User testing with 5–10 real users, gather feedback

**Deliverable:** Comprehensive test suite with >80% code coverage and a quality benchmark for AI output.

---

## Phase 8: Deployment & Infrastructure

### 8.1 — Production Environment
- [ ] Containerize all services (Docker)
- [ ] Set up production database with backups and point-in-time recovery
- [ ] Configure environment variables and secrets management (e.g., AWS Secrets Manager, Doppler)
- [ ] SSL/TLS for all endpoints

### 8.2 — Monitoring & Alerting
- [ ] Application monitoring (Sentry for errors)
- [ ] Infrastructure monitoring (CPU, memory, disk — Grafana/Datadog)
- [ ] AI cost tracking dashboard (tokens used, cost per recipe, daily spend)
- [ ] Alerts for: error rate spikes, API latency > threshold, AI spend anomalies

### 8.3 — Scaling Strategy
- [ ] Horizontal scaling for API servers (stateless)
- [ ] Worker pool scaling for video processing jobs
- [ ] CDN for static frontend assets
- [ ] Database connection pooling (PgBouncer)
- [ ] Rate limiting per user (prevent abuse)

### 8.4 — Cost Management
- [ ] Cache repeated recipe extractions (same URL → same recipe)
- [ ] Implement LLM response caching for identical prompts
- [ ] Set daily/monthly spend caps on AI APIs
- [ ] Monitor and optimize token usage in prompts

**Deliverable:** Production-ready deployment with monitoring, alerting, and cost controls.

---

## Phase 9: Polish & Launch Prep

### 9.1 — UX Polish
- [ ] Smooth animations and transitions
- [ ] Haptic feedback on mobile interactions
- [ ] Empty states, error states, and edge case handling in UI
- [ ] Onboarding flow for first-time users (brief, skippable)

### 9.2 — Content & Branding
- [ ] App icon and splash screen
- [ ] In-app copy review (clear, friendly, concise)
- [ ] App Store / Play Store listing (screenshots, description, keywords)

### 9.3 — Legal & Compliance
- [ ] Terms of Service and Privacy Policy
- [ ] GDPR / data handling compliance
- [ ] Content attribution — link back to original video creators
- [ ] Review platform ToS (TikTok, Instagram) for scraping/embedding policies

### 9.4 — Analytics
- [ ] Track key events: video submitted, recipe extracted, substitution viewed, recipe saved, recipe shared
- [ ] Funnel analysis: submission → successful extraction → recipe saved
- [ ] Crash and ANR reporting

### 9.5 — Beta Launch
- [ ] Invite 50–100 beta testers (friends, cooking communities, Reddit)
- [ ] Collect feedback via in-app form or survey
- [ ] Prioritize and fix top issues
- [ ] Iterate on AI prompt quality based on real-world video diversity

**Deliverable:** App ready for public launch with analytics, legal compliance, and beta feedback incorporated.

---

## Phase 10: Post-Launch & Future Features

### 10.1 — Iteration Based on User Feedback
- Monitor error rates and common failure modes (unsupported video formats, AI hallucinations)
- A/B test prompt variations for recipe quality
- Improve substitution suggestions based on user ratings

### 10.2 — Feature Roadmap (Future)
- **Meal planning:** save multiple recipes into weekly meal plans
- **Smart grocery list:** aggregate ingredients across multiple recipes, de-duplicate
- **Social features:** share recipes with friends, public recipe feed
- **Cooking timer integration:** embedded timers in step-by-step mode
- **Nutrition estimation:** approximate calories and macros per serving
- **Multi-language support:** UI localization + multilingual video transcription
- **Browser extension:** extract recipes directly from TikTok/IG in-browser
- **YouTube support:** extend to long-form cooking videos

### 10.3 — Platform Expansion
- Launch on both iOS and Android (if started with one)
- Progressive Web App for desktop access
- API for third-party integrations

---

## Summary Timeline (Suggested)

| Phase | Focus | Est. Duration |
|-------|-------|---------------|
| 1 | Project Setup & Foundation | 1 week |
| 2 | Metadata & Transcript Extraction | 1 week |
| 3 | AI Recipe Extraction | 1 week |
| 4 | Ingredient Substitutions | 1 week |
| 5 | Backend API | 1.5 weeks |
| 6 | Frontend Mobile UI | 2.5 weeks |
| 7 | Testing & QA | 1.5 weeks |
| 8 | Deployment & Infra | 1 week |
| 9 | Polish & Launch Prep | 1.5 weeks |
| 10 | Post-Launch Iteration | Ongoing |

**Total to MVP launch: ~12 weeks**

---

*This plan is a living document. Update it as decisions are made and priorities shift.*
