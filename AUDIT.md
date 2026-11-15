# Repository Audit & Target Architecture Proposal

**Repository:** `https://github.com/iizzii/Medium-Article-Automation/`  
**Audit Date:** 2026-11-15  
**Scope:** Phase 0 audit of all existing files (`main.py`, `news_fetcher.py`, `writer.py`, `publisher.py`, `scraper.py`, `requirements.txt`, `.github/workflows/main.yml`) and proposed target architecture for Phases 1–8.

---

## 1. Current Architecture, Scripts, Dependencies, Workflows & Secrets

### 1.1 Architecture Overview
The current repository is a flat, 6-file Python script pipeline triggered by GitHub Actions once daily. Contrary to the repository name, **it does not publish to Medium at all** — it fetches RSS headlines, asks the user to pick a topic via Telegram polling, generates a short 400–550 word HTML-formatted essay via Gemini/Groq, and delivers the draft as chunked Telegram messages plus an HTML attachment (`Medium_Draft.html`) for manual copy-pasting.

```
[GitHub Actions: cron 07:30 UTC]
       │
       ▼
  main.py
   ├─► news_fetcher.py (RSS: BleepingComputer, TheHackerNews → top 10 titles)
   ├─► publisher.py:wait_for_user_selection() (Telegram sendMessage + 3-min getUpdates poll)
   ├─► writer.py:generate_article() (Gemini 'gemini-3.6-flash' → Groq fallback)
   └─► publisher.py:push_article_to_telegram() (chunked sendMessage + tags + Medium_Draft.html)
```

### 1.2 Scripts Inventory

| File | Bytes | Role & Behavior | Key Issues / Gaps |
| :--- | :--- | :--- | :--- |
| `main.py` | 957 | Orchestrator: calls `get_top_10_topics()`, `wait_for_user_selection()`, `generate_article()`, `push_article_to_telegram()`. Prints `[SYSTEM LOG]` / `[LOG]` banners to stdout. | No state tracking, no idempotency, no error handling/issue creation, blocks for 3 minutes waiting on human Telegram reply. |
| `news_fetcher.py` | 1,287 | Parses 2 InfoSec RSS feeds (`bleepingcomputer.com/feed/`, `feeds.feedburner.com/TheHackersNews`), takes 6 entries each, deduplicates, returns up to 10 titles. Includes 5 hardcoded fallback topics (`* 2`). | News-reactive headlines only; no practitioner depth, no deduplication against past articles, no pillar/format structure. |
| `writer.py` | 4,512 | Defines `VIRAL_SYSTEM_PERSONA`. Calls `genai.Client()` with hardcoded `gemini-3.6-flash` (5 retries, 10s sleep). Falls back to `Groq` iterating all non-whisper/non-guard models. Splits output on `===TAGS===` and strips `<b>`/`#`/`*` from line 1 for title. | Hardcoded model name (`gemini-3.6-flash`), 400–550 word limit ("viral" fluff), instructs HTML `<b>` tags instead of Markdown, no outline/critic/grounding/code-validation stages, no images. |
| `publisher.py` | 5,657 | Handles all Telegram I/O: `get_latest_update_id()`, `wait_for_user_selection()` (sends 10 topics, polls `getUpdates` 18×10s), `push_article_to_telegram()` (converts `**` to `<b>`, chunks at 3,800 chars, sends tags, builds `Medium_Draft.html`, calls `sendDocument`). | Does not call Medium API. Sends 4+ Telegram messages per run. Generates unstyled HTML file on runner disk without committing or cleaning up. |
| `scraper.py` | 450 | **Dead/legacy code** (`get_daily_topic()`). Queries Google News RSS for `AI+jobs+layoffs+corporate+culture+India`, picks 1 random entry from top 5. Not imported anywhere. | Unused remnant from an earlier iteration. |
| `requirements.txt` | 38 | Lists `feedparser`, `google-genai`, `requests`, `groq`. | Unpinned versions; workflow doesn't even use `pip install -r requirements.txt`. |

### 1.3 Workflows & CI/CD
- **`.github/workflows/main.yml`** (`Medium Viral Automator`):
  - **Triggers:** `schedule: cron: '30 7 * * *'` (07:30 UTC / 13:00 IST) and `workflow_dispatch` (no inputs).
  - **Runner:** `ubuntu-latest`, `actions/checkout@v3`, `actions/setup-python@v4` with Python `3.10`.
  - **Install step:** `pip install requests feedparser google-genai groq` (ignores `requirements.txt`, no pip cache).
  - **Execution:** `python -u main.py`.
  - **Missing:** No `permissions`, no `concurrency` group, no `ruff`/`mypy`/`pytest` CI workflow, no Node/Mermaid/Graphviz/fonts, no artifact upload, no state commit, no `$GITHUB_STEP_SUMMARY` output.

### 1.4 Secrets Currently Used
| Secret | Used In | Status in Target Architecture |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | `writer.py` (via `genai.Client()` env var) | **Keep** (primary LLM, Search grounding, embeddings, image generation, multimodal image critic). |
| `TELEGRAM_BOT_TOKEN` | `publisher.py` | **Keep** (moved to `src/notify_telegram.py`, final link + cover photo only). |
| `TELEGRAM_CHAT_ID` | `publisher.py` | **Keep** (moved to `src/notify_telegram.py`). |
| `GROQ_API_KEY` | `writer.py` & `main.yml` | **Remove** (Gemini-only pipeline per Phase 3). |
| `MEDIUM_TOKEN` | *Not present* | **Add** (required for Phase 5 Medium API publishing). |
| `PUBLISH_STATUS` | *Not present* | **Add (optional env/var)** (defaults to `"draft"`). |

---

## 2. Complete Inventory of Current Telegram Usage

All Telegram API calls currently live in `publisher.py`. Every run sends **multiple interactive/preview messages**:

| # | Function & Line | Trigger / Timing | Endpoint & Payload | Exact Message Content |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `wait_for_user_selection()` (`publisher.py:25`) | Start of run, immediately after RSS fetch | `POST /sendMessage` (`parse_mode=HTML`) | `📰 <b>Today's Top 10 Tech Topics:</b>\n\n1. {t1}\n...\n10. {t10}\n\n<i>Reply with a number (1-10) within the next 3 minutes.</i>` |
| 2 | `get_latest_update_id()` / polling (`publisher.py:6-14, 31-48`) | Polls every 10s for up to 3 min | `GET /getUpdates?offset=...` | Reads user's numeric reply (`1`–`10`). |
| 3 | `wait_for_user_selection()` (`publisher.py:44`) | Immediately if user replies `1`–`10` | `POST /sendMessage` (`parse_mode=HTML`) | `✅ Confirmed. Crafting article for:\n<b>{selection}</b>` |
| 4 | `wait_for_user_selection()` (`publisher.py:51`) | If 3-minute timeout expires with no valid reply | `POST /sendMessage` (`parse_mode=HTML`) | `⏱️ <i>Timeout reached. Auto-selecting Topic 1.</i>` |
| 5 | `push_article_to_telegram()` (`publisher.py:86-92`) | After article generation; 1 message per 3,800-char chunk | `POST /sendMessage` (`parse_mode=HTML`, falls back to plain text on non-200) | `<b>{clean_title}</b>\n\n{body}` (full article body in 1+ chunks). |
| 6 | `push_article_to_telegram()` (`publisher.py:95-96`) | After article body chunks | `POST /sendMessage` (`parse_mode=HTML`) | `🏷️ <b>Suggested Medium Tags:</b>\n\n{tags}` |
| 7 | `push_article_to_telegram()` (`publisher.py:129-133`) | End of run | `POST /sendDocument` (`Medium_Draft.html`, `parse_mode=HTML`) | Caption: `📝 <b>MEDIUM DRAFT READY</b>\n\nOpen this file in your browser, press <b>Select All -> Copy</b>, and paste directly into Medium. Your bold formatting will transfer perfectly!` |

*Note:* Errors currently crash the Python process and send nothing to Telegram (nor do they open GitHub Issues).

---

## 3. Existing Topics, Themes, Prompts & Keywords (Seed Material)

### 3.1 Feeds & Fallback Topics (`news_fetcher.py`, `scraper.py`)
- **Active RSS Feeds (`news_fetcher.py:5-8`):**
  - `https://www.bleepingcomputer.com/feed/` (enterprise security, vulnerabilities, malware, patches)
  - `https://feeds.feedburner.com/TheHackersNews` (cybersecurity, exploits, cloud security, threat actors)
- **Hardcoded Fallback Topics (`news_fetcher.py:25-31`):**
  - Critical Zero-Day in major enterprise software infrastructure
  - Reverse engineering kernel-level malware variants
  - Out-of-band security patches breaking production systems
  - Supply chain attacks bypassing standard EDR solutions
  - Threat actors exploiting misconfigured cloud environments
- **Legacy Query (`scraper.py:6`):** `AI jobs layoffs corporate culture India` (not aligned with security engineering; will be retired, while AI-in-security ops is absorbed into Pillar 6).

### 3.2 Existing Persona, Voice & Prompts (`writer.py:7-29`)
- **Persona:** *"14-year veteran in enterprise cybersecurity and systems architecture"* — skeptical, conversational, direct, *"Expose the gap between PR/vendor theater and ground-level reality"*, *"uncomfortable operational truth"*.
- **Banned AI Clichés (`writer.py:15`):** `"delve"`, `"tapestry"`, `"beacon"`, `"game-changer"`, `"testament"`, `"crucial"`, `"vital"`, `"in conclusion"`. (We will carry these forward into our writer/critic rules.)
- **Default Fallback Tags (`writer.py:84`):** `#TechNews #CyberSecurity #Innovation #SoftwareEngineering #TechTrends` (to be replaced by pillar-specific Medium tags, max 5).

### 3.3 How Seed Material Maps to the New Content Strategy
The existing InfoSec/enterprise-architecture skepticism and BleepingComputer/THN practitioner focus merge naturally into the 7 pillars:
- **Pillar 1 (Abuse & Fraud Detection at Scale)** & **Pillar 3 (Detection Engineering)**: Absorbs the EDR-bypass, rule-decay, and operational-reality-vs-vendor-theater themes.
- **Pillar 2 (Security Automation / SOAR)** & **Pillar 4 (Compliance & Audit Automation)**: Grounded in production reliability ("patches breaking production", reconciliation, human-in-the-loop gates).
- **Pillar 5 (Ops Tooling Engineering)**, **Pillar 6 (Applied AI for Security)**, & **Pillar 7 (Leading Security Teams)**: Extends the practitioner voice to internal tooling, LLM triage/evals, and team calibration.

---

## 4. Proposed Target Architecture (Phases 1–8)

### 4.1 High-Level Pipeline Flow
```
[GitHub Actions: daily-article.yml (03:30 UTC / 09:00 IST)]
   │
   ├─ 1. State & Idempotency Check (src/state.py → state/history.json)
   │     └─ Abort cleanly if today's date already published (unless force/dry_run)
   │
   ├─ 2. Topic Selection (src/topics.py)
   │     ├─ Select Pillar (1–7) + Format (7 formats, no back-to-back repeat)
   │     ├─ Generate non-obvious practitioner angle via Gemini
   │     └─ Compute embedding & reject if cosine similarity > 0.80 vs last 90 entries
   │
   ├─ 3. Outline & Heading Gate (src/headings.py)
   │     ├─ Outliner produces title (<=70 chars), subtitle, hook, 5–8 H2s, planned code/tables/visuals
   │     └─ Strict validation: title length, concrete technical H2s, no banned/vague labels/emoji
   │
   ├─ 4. Multi-Stage Article Generation & Validation (src/writer.py, src/validate.py)
   │     ├─ Writer (1,800–3,000 words Markdown, >=2 code blocks, >=1 table, required sections)
   │     ├─ Reference Verifier (Gemini Google Search grounding → drop unverified refs, keep 3–6)
   │     ├─ Text Critic (scores 1–10 on 7 dimensions; any < 8 → rewrite up to 2x, else new topic)
   │     └─ Code Validator (py_compile + sandboxed subprocess execution of self-contained snippets)
   │
   ├─ 5. Visual Pipeline (src/visual_planner.py, images_render.py, images_ai.py, image_critic.py)
   │     ├─ Visual Planner: 1 JSON brief per heading (Cover + each H2; >= 4 visuals total)
   │     ├─ Hybrid Renderers:
   │     │    ├─ diagram    → Mermaid CLI (mmdc) / Graphviz (2x DPI PNG)
   │     │    ├─ chart      → Matplotlib / Plotly with exact article numbers (2x DPI PNG)
   │     │    ├─ code_card  → Pygments + Pillow Carbon-style card (PNG)
   │     │    ├─ table_card → Pillow/HTML-to-PNG styled matrix
   │     │    └─ illustration → Gemini/Imagen (3 candidates, no text/faces/logos, 1400x788 cover)
   │     ├─ Image Critic (multimodal Gemini, 5 dimensions, all >= 8; up to 3 rounds or fallback)
   │     └─ Save manifest.json, optimize (<1 MB), inject alt text & captions under each H2
   │
   ├─ 6. Confidentiality & Safety Scan (src/validate.py + config/blocklist.txt)
   │     └─ Scan article, captions, alt text, and image prompts for blocklist, emails, *.corp.*, go/ links, IDs
   │
   ├─ 7. Publishing & Notifications (src/publisher_medium.py, src/notify_telegram.py)
   │     ├─ If dry_run: save /output/ + /assets/, upload GH artifacts, skip Medium & Telegram
   │     ├─ Else: upload images (Medium /v1/images, fallback raw.githubusercontent) → POST /v1/users/{id}/posts (3x backoff)
   │     ├─ On Medium success → notify_telegram.py (1 sendPhoto with HTML caption, fallback sendMessage; 2 retries, non-fatal)
   │     └─ On Medium failure → commit /output/ + /assets/, open GitHub Issue ("Ready to import: <title>"), NO Telegram
   │
   └─ 8. Persist State & Summary
         ├─ Write title, URL, tags, text & image critic scores to $GITHUB_STEP_SUMMARY
         └─ Commit state/history.json (and assets/output if needed) with [skip ci]
```

### 4.2 Target Directory Structure
```text
.
├── .github/
│   └── workflows/
│       ├── daily-article.yml      # Cron 30 3 * * * + workflow_dispatch, Py 3.12, mmdc, fonts
│       └── ci.yml                 # ruff, mypy, pytest on every push/PR
├── config/
│   ├── pillars.yaml               # 7 content pillars + seed themes & tags
│   ├── formats.yaml               # 7 rotating formats + structural requirements
│   ├── style.yaml                 # Brand palette (#0B1220, #00E5FF, #FFB020), dimensions, DPI
│   ├── models.yaml                # Gemini text, grounding, embedding, vision, image models
│   ├── blocklist.txt              # Confidential terms (user-populated)
│   ├── fonts/                     # Bundled Inter & JetBrains Mono fonts
│   └── prompts/
│       ├── topic.md
│       ├── outline.md
│       ├── writer.md
│       ├── critic.md
│       ├── visual_planner.md
│       ├── image.md
│       └── image_critic.md
├── src/
│   ├── __init__.py
│   ├── pipeline.py                # End-to-end orchestrator & CLI entrypoint
│   ├── state.py                   # state/history.json load/save, idempotency, format rotation
│   ├── topics.py                  # Pillar/format selection, Gemini angle, embedding dedup (>0.8)
│   ├── headings.py                # Outliner + strict title (<=70) & H2 specificity validator
│   ├── writer.py                  # Writer, Search-grounded reference verifier, Text Critic
│   ├── validate.py                # Code validator (py_compile + sandbox), confidentiality scanner
│   ├── visual_planner.py          # Per-heading JSON brief generator
│   ├── images_render.py           # Mermaid, Graphviz, Matplotlib/Plotly, code_card, table_card
│   ├── images_ai.py               # Gemini/Imagen illustration generator + Pillow upscaling/optim
│   ├── image_critic.py            # Multimodal Gemini quality gate + prompt refinement loop
│   ├── publisher_medium.py        # Medium /v1/me, /v1/images, /v1/posts + backoff + GH issue fallback
│   └── notify_telegram.py         # Single sendPhoto (fallback sendMessage), 2 retries, non-fatal
├── state/
│   └── history.json               # Published history (title, slug, pillar, format, tags, URL, scores, embedding)
├── tests/                         # pytest suite (mocked Gemini, Medium, Telegram; Telegram 1-on-success / 0-on-fail)
├── samples/                       # One complete dry-run article + images + manifest.json + critic scores
├── AUDIT.md
├── README.md
├── pyproject.toml                 # ruff, mypy, pytest configuration
└── requirements.txt               # Pinned runtime & dev dependencies
```

### 4.3 Key Design Decisions & Safeguards
1. **Model Configuration (`config/models.yaml`)**: Zero hardcoded model strings in Python; all text, search-grounding, embedding, multimodal critic, and image generation models are loaded from `config/models.yaml`.
2. **Telegram Discipline (`src/notify_telegram.py`)**: Strictly one `sendPhoto` (HTML caption, falling back to `sendMessage`) only after a confirmed Medium publish. Zero messages on failure, dry-run, or intermediate steps. Failures are logged and retried twice without failing the job.
3. **Accuracy-First Visuals**: Diagrams and charts are never generated by AI image models — they are deterministically rendered from section text/data via Mermaid/Graphviz/Matplotlib. AI illustrations are restricted to the cover and conceptual sections, must contain no text/logos/faces, and pass a multimodal critic (`>= 8` across all 5 dimensions) with a code-rendered fallback if 3 rounds fail.
4. **Confidentiality Gate**: Runs after all text, captions, alt text, and image prompts are finalized, blocking any run that matches `config/blocklist.txt`, emails, `*.corp.*`, `go/` links, or internal ID patterns.
5. **Security & Sandboxing**: Code validation runs snippets in an isolated subprocess with stripped environment variables (`GEMINI_API_KEY`, `MEDIUM_TOKEN`, `TELEGRAM_BOT_TOKEN` never exposed to generated code) and strict timeouts. Secrets are never logged.

---

**Next Step:** Awaiting your approval on `AUDIT.md` before implementing Phases 1–8.
