# Test Assets — Demo Images

These images were selected during M0 (Contract Freeze) and verified
against their intended rules during M4 (C2PA) and M5 (Origin Trace).

## 1. C2PA-signed image — Rule 1 (AI-Generated) ✅ VERIFIED

**File:** `c2pa_ai_candidate.jpg`
**Source:** contentauth/example-assets — `Firefly_tabby_cat.jpg`
**URL:** https://raw.githubusercontent.com/contentauth/example-assets/main/images/Firefly_tabby_cat.jpg
**License:** Apache 2.0 (contentauth)
**Rule mapping:** Rule 1 (AI-Generated Content) — **VERIFIED in M4**

**Manifest evidence (c2pa-python 0.37.2):**
- `claim_generator`: `"Adobe_Firefly"`
- `action`: `"c2pa.created"`
- `digitalSourceType`: `"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"`
- `softwareAgent`: `"Adobe Firefly"`
- `signature_issuer`: `"Adobe Inc."`

The `trainedAlgorithmicMedia` IPTC digital source type is the canonical
C2PA declaration for AI-generated content. This asset unambiguously
triggers Rule 1.

## 2. Rule 2 (Verified Camera Original) — NO LIVE DEMO ASSET

**Status:** No candidate asset demonstrates Rule 2 live. This is expected
and acceptable.

**Investigation (M4):** Both `c2pa_candidate.jpg` and
`rule2_camera_candidate.jpg` (sourced from contentauth/c2pa-rs test
fixtures) were exhaustively inspected. Their full manifests contain:
- `claim_generator`: `"make_test_images/c2pa-rs"` — a test harness tool, not camera hardware
- `actions`: `"c2pa.opened"` + `"c2pa.color_adjustments"` — software editing history
- No `digitalSourceType` field of any kind
- No camera/device/hardware/manufacturer/capture assertions anywhere
  in the complete manifest tree (confirmed via recursive key/value search)

These are software-editing provenance records from a test fixture
generator, not camera hardware signatures. Mapping them to Rule 2
("Verified Camera Original") would be inaccurate.

**Resolution:** Rule 2's classification logic is validated exclusively
through the M6 unit test using mocked/synthetic evidence dictionaries.
This is the same resolution applied to the Rule 2+3 combination
problem — standard, honest unit-testing practice.

**Files retained for reference (not used in live demo):**
- `c2pa_candidate.jpg` — contentauth/c2pa-rs `CA.jpg`
- `rule2_camera_candidate.jpg` — contentauth/c2pa-rs `CACA.jpg`

## 3. Rule 2+3 combination candidate (Camera-verified AND Recirculated)

**Status:** NO NATURAL CANDIDATE EXISTS.

Social media platforms strip C2PA metadata during upload/compression.
Camera manufacturers (Leica, Sony, Nikon, Canon) supporting C2PA do
not publish sample images with camera credentials that are also
widely recirculated online. A camera-signed original and a recirculated
copy are by nature separate files — the recirculated copy has lost
its C2PA data.

The Rule 2 + Rule 3 multi-match logic is validated exclusively through
the M6 unit test using mocked/synthetic evidence dictionaries.

## 5. Rule 3 (Recirculated / Out of Context) ✅ VERIFIED

**File:** `rule3_recirculated_candidate.jpg`
**Source:** Unsplash mountain landscape (photo-1506905925346-21bda4d32df4), CC0-like license
**License:** Unsplash License (free for commercial and non-commercial use)
**Rule mapping:** Rule 3 (Recirculated Content) — **VERIFIED in M5**

**Verification evidence (SerpApi Google Lens + Wayback Machine, 2026-08-05):**
- SerpApi returned **60 visual matches** across different websites
- Image found on 60+ different sites in different contexts:
  wine tours, real estate, religious organizations, wellness clinics, etc.
- Wayback Machine confirmed earliest appearance: **2020-11-01** at sola.network
  (5.8 years old — exceeds 1-year threshold)
- Matches documented at: austinpartyride.com, musecap.com, sola.network,
  luxurydestinationsparkcity.com, abidingwaters.org, and many others
- Full SerpApi result cached in `rule3_serpapi_result.json`

**Why this works for Rule 3:** This CC0 stock photo has been genuinely
reproduced across dozens of websites in entirely different contexts over
multiple years. The pipeline correctly identifies it as having prior
online appearances with independently verifiable Wayback timestamps.

## 6. Clean image — Rule 5 (No Provenance) ✅ VERIFIED

**File:** `clean_no_provenance.jpg`
**Source:** Programmatically generated solid-color JPEG (800x600, RGB)
**License:** N/A (generated locally, no third-party content)
**Rule mapping:** Rule 5 (Unverified — No Provenance Found) — **VERIFIED in M4**

**Verification evidence (c2pa-python 0.37.2):**
- `Reader.try_create()` returns `None` — no C2PA manifest found
- Zero EXIF metadata (confirmed in M3)
- SerpApi returned 59 visual matches (solid-color images match generically),
  but this does not affect Rule 5 classification since it has no C2PA provenance

