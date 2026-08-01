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

## 2. C2PA-signed image — Rule 2 (Camera/Non-AI Signature) ✅ VERIFIED

**File:** `c2pa_candidate.jpg`
**Source:** contentauth/c2pa-rs test fixtures — `CA.jpg`
**URL:** https://raw.githubusercontent.com/contentauth/c2pa-rs/main/sdk/tests/fixtures/CA.jpg
**License:** Apache 2.0 / MIT dual (c2pa-rs)
**Rule mapping:** Rule 2 (Verified Camera Original) — **VERIFIED in M4**

**Manifest evidence (c2pa-python 0.37.2):**
- `claim_generator`: `"make_test_images/0.33.1 c2pa-rs/0.33.1"`
- `actions`: `"c2pa.opened"`, `"c2pa.color_adjustments"` (brightness/contrast)
- No `digitalSourceType` field — NOT AI-generated
- `signature_issuer`: `"C2PA Test Signing Cert"`
- Has `stds.schema-org.CreativeWork` assertion with `author: "John Doe"`

This asset has a valid C2PA manifest but no AI-generation markers.
It unambiguously triggers Rule 2 (non-AI C2PA signature present).

**Backup file:** `rule2_camera_candidate.jpg`
**Source:** contentauth/c2pa-rs test fixtures — `CACA.jpg` (two-deep chain)
**Manifest:** Same pattern as `c2pa_candidate.jpg` — c2pa.opened +
c2pa.color_adjustments, no AI markers. Contains an ingredient chain
(CACA → CA). Also verified to trigger Rule 2.

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

## 4. Clean image — Rule 5 (No Provenance) ✅ VERIFIED

**File:** `clean_no_provenance.jpg`
**Source:** Programmatically generated solid-color JPEG (800x600, RGB)
**License:** N/A (generated locally, no third-party content)
**Rule mapping:** Rule 5 (Unverified — No Provenance Found) — **VERIFIED in M4**

**Verification evidence (c2pa-python 0.37.2):**
- `Reader.try_create()` returns `None` — no C2PA manifest found
- Zero EXIF metadata (confirmed in M3)
- Zero online history by construction
