<div align="center">
  <img src="./frontend/public/favicon.ico" alt="Logo" width="80" height="80">
  <h1 align="center">RECEIPTS</h1>
  <p align="center">
    <strong>Don't share it. Prove it.</strong><br>
    A rigorous, cryptographically-inspired image provenance verification engine.
  </p>
  
  <p align="center">
    <a href="#features">Features</a> •
    <a href="#how-it-works">How It Works</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#getting-started">Getting Started</a>
  </p>
</div>

---

## 👁️ Overview

**Receipts** is an automated verification engine designed to combat misinformation, deepfakes, and recirculated imagery. By dragging and dropping an image (or pasting a URL), Receipts runs a rigorous 5-rule analysis pipeline to extract metadata, detect AI manipulation, trace historical circulation via the Wayback Machine, and determine if an image is genuinely what it claims to be.

If the image is analyzed successfully, the system generates a verifiable, 1080x1920 "Receipt" card that clearly communicates the image's classification and the strength of the evidence found, ready to be shared as proof.

## ✨ Features

- 🕵️ **Deep Provenance Pipeline**: Analyzes C2PA manifests, EXIF data, Do Not Train (Opt-Out) metadata, and visual fingerprints (pHash).
- 🧠 **AI & Recirculation Detection**: Identifies state-of-the-art AI-generated content and detects old images being recirculated in new, misleading contexts.
- ⚡ **URL Pre-fetching & Validation**: Automatically extracts embedded social media imagery (X/Twitter, OpenGraph) with strict SSRF protection and timeouts.
- 🎨 **Beautiful UI**: A highly polished, glassmorphism-heavy neon UI built with Next.js and Framer Motion, featuring buttery smooth scanning animations and interactive full-screen receipt exploration.
- 🖨️ **Dynamic Receipt Generation**: Serverlessly generates custom, dynamic PNG "Receipts" using `next/og` (Satori).

---

## ⚙️ How It Works (The 5-Rule Engine)

When an image is submitted, the Python FastAPI backend processes it sequentially against a strict ruleset:

1. **Rule 1: C2PA Cryptographic Provenance**
   Scans for deeply embedded Coalition for Content Provenance and Authenticity (C2PA) cryptographic manifests to definitively prove origin (e.g., Leica Camera Original, Midjourney AI).
2. **Rule 2: AI & Manipulation Metadata**
   Inspects standard EXIF and XMP tags for common AI software signatures or extensive post-processing footprints (e.g., Adobe Photoshop, Stable Diffusion).
3. **Rule 3: Historical Recirculation**
   Generates a perceptual hash (pHash) of the image and cross-references it with SerpApi (Google Reverse Image Search) and the Internet Archive's Wayback Machine. If a highly similar visual match is found from years prior, the image is flagged as "Recirculated".
4. **Rule 4: Do Not Train (Opt-Out)**
   Checks for embedded `c-dnt` (Do Not Train) metadata, asserting the creator's legal restriction against the image being used for AI training.
5. **Rule 5: Unverified (Fallback)**
   If an image has been completely stripped of metadata (common on social media) and lacks historical footprint, it is ethically classified as "Unverified".

---

## 🏗️ Architecture

- **Frontend**: 
  - Framework: Next.js 16.2 (App Router, Turbopack)
  - Styling: Tailwind CSS v4, `shadcn/ui`, Framer Motion
  - Dynamic Rendering: `next/og` for edge-generated PNG Receipts
- **Backend**:
  - Framework: Python 3.11+ with FastAPI
  - Analysis: `ImageHash`, `Pillow`, C2PA verification utilities
  - Integrations: SerpApi, Internet Archive API
- **Database**:
  - Supabase (PostgreSQL)
  - Caches pHash API results to prevent rate-limiting and drastically speed up future scans for known images.

---

## 🚀 Getting Started

### Prerequisites
- Node.js (v18+)
- Python 3.11+
- Supabase Project (URL & Anon Key)
- SerpApi Key

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt

# Create a .env file
echo "SERPAPI_KEY=your_key_here" > .env
echo "SUPABASE_URL=your_supabase_url" >> .env
echo "SUPABASE_SERVICE_KEY=your_service_key" >> .env

# Run the backend
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install

# Create a .env.local file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_SUPABASE_URL=your_supabase_url" >> .env.local
echo "NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key" >> .env.local

# Run the frontend
npm run dev
```

Navigate to `http://localhost:3000` to begin verifying images.

---

<div align="center">
  <p>Built with precision.</p>
</div>
