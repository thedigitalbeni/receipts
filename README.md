<div align="center">

<br/>

```
██████╗ ███████╗ ██████╗███████╗██╗██████╗ ████████╗███████╗
██╔══██╗██╔════╝██╔════╝██╔════╝██║██╔══██╗╚══██╔══╝██╔════╝
██████╔╝█████╗  ██║     █████╗  ██║██████╔╝   ██║   ███████╗
██╔══██╗██╔══╝  ██║     ██╔══╝  ██║██╔═══╝    ██║   ╚════██║
██║  ██║███████╗╚██████╗███████╗██║██║        ██║   ███████║
╚═╝  ╚═╝╚══════╝ ╚═════╝╚══════╝╚═╝╚═╝        ╚═╝   ╚══════╝
```

### **Don't share it. Prove it.**

*A forensic image verification engine that exposes AI generation, manipulation, and misinformation — and generates a shareable proof receipt.*

<br/>

[![FastAPI](https://img.shields.io/badge/FastAPI-0.140-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)

<br/>

</div>

---

## What is Receipts?

In an era of viral misinformation, AI-generated fakes, and recycled imagery stripped of context — **knowing whether an image is real matters**.

Receipts is a **forensic image verification engine**. Drop any image or paste any URL and it runs a multi-layer analysis pipeline — cryptographic provenance, EXIF forensics, perceptual hashing, historical reverse-image search, AI fingerprinting, and Error Level Analysis — then distills it all into a single, shareable **1080×1920 "Receipt"** card you can post as proof.

> Think of it as a receipt for reality.

---

## Pipeline Overview

Every image submitted is processed sequentially through a 5-rule evidence engine. Rules are evaluated in priority order — the first match wins.

```
┌────────────────────────────────────────────────────────────┐
│                      INPUT IMAGE                           │
│           (Upload · URL · Social media embed)              │
└─────────────────────────┬──────────────────────────────────┘
                          │
          ┌───────────────▼────────────────┐
          │   Security Gate                │
          │   • 15 MB size limit           │
          │   • Pillow format validation   │
          │   • SSRF IP-range blocking     │
          │   • Rate limit (10 req/min)    │
          └───────────────┬────────────────┘
                          │
          ┌───────────────▼────────────────┐
          │   SHA-256 Cache Check          │──── HIT ────► Return cached result instantly
          └───────────────┬────────────────┘
                          │ MISS
                          ▼
          ┌──────────────────────────────────────────────────┐
          │             5-RULE ENGINE                        │
          │                                                  │
          │  Rule 1 ── C2PA Cryptographic Manifest           │
          │            Signed camera / AI tool proof         │
          │                                                  │
          │  Rule 2 ── EXIF & Software Fingerprinting        │
          │            AI tags, Photoshop, Stable Diffusion  │
          │                                                  │
          │  Rule 3 ── Reverse Image Search (SerpApi)        │
          │            pHash vs. Google Lens results         │
          │                                                  │
          │  Rule 4 ── Wayback Machine Historical Trace      │
          │            When did this image first appear?     │
          │                                                  │
          │  Rule 5 ── Unverified Fallback                   │
          │            Stripped metadata, no footprint       │
          └───────────────┬──────────────────────────────────┘
                          │
          ┌───────────────▼────────────────┐
          │   ELA (Error Level Analysis)   │
          │   Detects JPEG re-compression  │
          │   artifacts from editing       │
          └───────────────┬────────────────┘
                          │
          ┌───────────────▼────────────────┐
          │   Supabase Persist             │
          │   INSERT receipt row           │
          │   Upload image to Storage      │
          └───────────────┬────────────────┘
                          │
                          ▼
          ┌──────────────────────────────────────────────────┐
          │             VERDICT + RECEIPT                    │
          │                                                  │
          │  ✅  Verified Camera Original                    │
          │  🤖  AI-Generated                                │
          │  🔄  Recirculated / Out of Context               │
          │  ✏️  Post-Processed / Edited                     │
          │  ❓  Unverified (metadata stripped)              │
          └──────────────────────────────────────────────────┘
```

---

## The 5 Rules — In Detail

### Rule 1 — C2PA Cryptographic Provenance
The gold standard. Scans for an embedded **Coalition for Content Provenance and Authenticity (C2PA)** manifest — a cryptographic signature baked into the image file by the camera or AI tool at the moment of creation.

- A **valid camera manifest** (Leica, Sony, Nikon) → `Verified Camera Original`
- A **valid AI-tool manifest** (Adobe Firefly, Midjourney, DALL·E) → `AI-Generated`
- A manifest that has been **tampered with or broken** → flagged immediately

### Rule 2 — EXIF & Software Fingerprinting
Extracts and cross-references EXIF/XMP metadata:
- **Software tag** compared against a database of known AI generators (Stable Diffusion, Midjourney, ComfyUI, NovelAI, etc.) and editing tools (Photoshop, Lightroom, GIMP)
- **Do-Not-Train (`c-dnt`) flag** detection — signals the creator asserted opt-out rights
- **Quantization table fingerprinting** — identifies the specific JPEG encoder (Canon, Nikon, iPhone, WhatsApp, Twitter/X compression)

### Rule 3 — Reverse Image Search
Computes a **perceptual hash (pHash)** of the image and submits it to **Google Lens via SerpApi**. Each result's visual similarity (Hamming distance ≤ 10) is checked to identify known copies or near-duplicates already on the web.

### Rule 4 — Wayback Machine Historical Trace
If reverse image search returns matches, the URLs are checked against the **Internet Archive**. If the earliest archived snapshot pre-dates the image's claimed context by a significant margin, it is classified as `Recirculated / Out of Context`.

### Rule 5 — Unverified Fallback
Images that have been completely stripped of metadata (common on social media platforms) and have no traceable web history are classified as `Unverified`. This is an honest, ethical classification — absence of proof is not proof of absence.

---

## Tech Stack

<table>
<tr>
<td valign="top" width="50%">

### Frontend
| | |
|---|---|
| **Framework** | Next.js 16.2 (App Router) |
| **Styling** | Tailwind CSS v4 |
| **Components** | shadcn/ui |
| **Animations** | Framer Motion |
| **Receipt Images** | `next/og` (Satori, edge-rendered) |
| **State** | React `useState` / `useRef` |

</td>
<td valign="top" width="50%">

### Backend
| | |
|---|---|
| **Framework** | FastAPI 0.140 + Uvicorn |
| **Forensics** | Pillow, ImageHash, c2pa-python |
| **Rate Limiting** | SlowAPI (10 req/min/IP) |
| **HTTP** | httpx (async, SSRF-safe) |
| **Origin Trace** | SerpApi + Internet Archive |
| **Database** | Supabase (PostgreSQL + Storage) |

</td>
</tr>
</table>

---

## What It Can & Can't Do

### ✅ What Receipts CAN detect

| Signal | Method |
|---|---|
| Images signed by C2PA-compliant cameras (Leica, Sony α7, etc.) | Cryptographic manifest |
| Images generated by C2PA-compliant AI tools (Adobe Firefly, DALL·E) | Cryptographic manifest |
| Images edited in Photoshop, Lightroom, or GIMP | EXIF software tag |
| Images generated by Stable Diffusion, Midjourney, NovelAI, ComfyUI | EXIF / XMP AI tags |
| Old images recirculated in new, misleading contexts | pHash + Wayback Machine |
| Images whose metadata has been deliberately stripped | Fallback classification |
| JPEG re-compression artifacts from editing | Error Level Analysis |

### ❌ What Receipts CANNOT guarantee

| Limitation | Reason |
|---|---|
| 100% certainty on "Unverified" images | Absence of metadata ≠ proof of editing |
| Detection of images that were screenshotted | Screenshots strip all original metadata |
| Detection of deepfakes with no AI metadata | No embedded signature = invisible to Rule 2 |
| Analysis of images behind login walls or paywalls | SSRF protection and access restrictions |
| Real-time Wayback Machine accuracy | Crawl lag — recent images may not be indexed yet |

---

## Features

- **🔍 Cinematic Scanner** — Multi-layer animated forensics display with radar rings, data readouts (SHA-256 · C2PA · EXIF · ELA), and a smooth laser-sweep beam
- **🖨️ Dynamic Receipts** — Color-coded 1080×1920 PNG receipts generated at the edge via `next/og` — purple for AI, teal for camera, amber for recirculated
- **🔎 Zoom & Pan** — Full-screen receipt viewer with mouse-wheel zoom (1×–5×) and click-drag panning
- **🛡️ Security-first Backend** — SSRF redirect validation, 15 MB upload cap, Pillow format gating, per-IP rate limiting, SHA-256 deduplication cache
- **🌐 URL Verification** — Paste any public image URL or social page and Receipts fetches the canonical image (including OpenGraph extraction from article pages)
- **📱 Fully Responsive** — Polished on mobile, tablet, and desktop
- **⚡ Cache Layer** — SHA-256 hash checked against Supabase before any analysis — repeat submissions return instantly

---

## Local Development

### Prerequisites

```
Node.js  ≥ 18
Python   ≥ 3.11
Supabase project (URL + Anon Key + Service Role Key)
SerpApi account (free tier: 100 searches/month)
```

### 1. Clone

```bash
git clone https://github.com/thedigitalbeni/receipts.git
cd receipts
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SERPAPI_API_KEY=your_serpapi_key
CORS_ORIGINS=http://localhost:3000
```

```bash
uvicorn app.main:app --reload --port 8000
```

Backend is live at `http://localhost:8000` · API docs at `http://localhost:8000/docs`

### 3. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

```bash
npm run dev
```

Frontend is live at `http://localhost:3000`

---

## Deployment

| Service | Platform | Free Tier |
|---|---|---|
| **Frontend** | [Vercel](https://vercel.com) | Unlimited · 100 GB bandwidth/mo |
| **Backend** | [Render](https://render.com) | 750 hrs/mo · auto-deploy from GitHub |
| **Database** | [Supabase](https://supabase.com) | 500 MB DB · 1 GB Storage |

**Key deployment settings:**

- Vercel → Root Directory: `frontend`
- Render → Root Directory: `backend` · Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- After deploying, update `CORS_ORIGINS` on Render to your Vercel URL

---

## Project Structure

```
receipts/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, /verify endpoint, rate limiting
│   │   ├── rules.py         # 5-rule evidence engine
│   │   ├── forensics.py     # pHash, EXIF extraction, quantization fingerprinting
│   │   ├── provenance.py    # C2PA manifest parsing
│   │   ├── origin_trace.py  # SerpApi + Wayback Machine integration
│   │   ├── ela.py           # Error Level Analysis
│   │   ├── security.py      # SSRF protection, input validation
│   │   ├── db.py            # Supabase persistence
│   │   └── schemas.py       # Pydantic models (VerifyResponse, etc.)
│   ├── tests/               # pytest test suite
│   ├── requirements.txt
│   └── render.yaml          # Render deployment config
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx         # Landing page (8-section, animated)
│   │   ├── verify/
│   │   │   └── page.tsx     # Verification UI (scanner, zoom, results)
│   │   └── api/
│   │       └── receipt/
│   │           └── [id]/
│   │               └── route.tsx  # next/og receipt image generator
│   └── public/
│       ├── Roboto-Regular.ttf
│       └── Roboto-Bold.ttf
│
└── README.md
```

---

## Security Model

| Layer | Protection |
|---|---|
| **Upload size** | 15 MB hard cap — rejected before Pillow |
| **Format validation** | `Pillow.verify()` — rejects non-image files |
| **SSRF** | DNS resolution → IP range blocklist (RFC 1918, loopback, link-local) |
| **Redirect SSRF** | `follow_redirects=False` + re-validate each redirect hop |
| **Rate limiting** | 10 requests/min per IP via SlowAPI |
| **SHA-256 cache** | Prevents redundant processing + replay attacks |
| **CORS** | Strict allowlist — no wildcard |
| **RLS** | Supabase Row Level Security enabled on all tables |

---

<div align="center">

<br/>

**Built by [Beneyas Tadu](mailto:beneyas.work@gmail.com)**

*Precision forensics. Zero compromise.*

<br/>

</div>
