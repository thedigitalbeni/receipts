# Test Assets — Candidate Demo Images (M0)

These images are CANDIDATES selected during M0: Contract Freeze.
Actual verification against their intended rules happens in M4 (C2PA)
and M5 (Origin Trace). Either may be swapped if verification fails.

## 1. C2PA-signed image — Rule 1 (AI-Generated) candidate

**File:** `c2pa_ai_candidate.jpg`
**Source:** contentauth/example-assets — `Firefly_tabby_cat.jpg`
**URL:** https://raw.githubusercontent.com/contentauth/example-assets/main/images/Firefly_tabby_cat.jpg
**License:** Apache 2.0 (contentauth)
**Intended rule mapping:** Rule 1 (AI-Generated Content) — filename
indicates Adobe Firefly generation, which should embed an
`ai_generated` assertion in the C2PA manifest.
**Verification status:** NOT YET VERIFIED — M4 will confirm whether
`c2pa-python` parses this and whether the manifest maps to Rule 1.

## 2. C2PA-signed image — Rule 2 (Camera) / general C2PA candidate

**File:** `c2pa_candidate.jpg`
**Source:** contentauth/c2pa-rs test fixtures — `CA.jpg`
**URL:** https://raw.githubusercontent.com/contentauth/c2pa-rs/main/sdk/tests/fixtures/CA.jpg
**License:** Apache 2.0 / MIT dual (c2pa-rs)
**Intended rule mapping:** Rule 2 (Verified Camera Original), pending
manifest inspection. May carry a camera signature or generic assertions.
**Verification status:** NOT YET VERIFIED — M4 will inspect the
manifest claims and determine exact rule mapping.

**File:** `rule2_camera_candidate.jpg`
**Source:** contentauth/c2pa-rs test fixtures — `CACA.jpg` (two-deep manifest chain)
**URL:** https://raw.githubusercontent.com/contentauth/c2pa-rs/main/sdk/tests/fixtures/CACA.jpg
**License:** Apache 2.0 / MIT dual (c2pa-rs)
**Intended rule mapping:** Backup candidate for camera-verified C2PA.
**Verification status:** NOT YET VERIFIED.

## 3. Rule 2+3 combination candidate (Camera-verified AND Recirculated)

**Status:** NO NATURAL CANDIDATE EXISTS.

Social media platforms strip C2PA metadata during upload/compression.
Camera manufacturers (Leica, Sony, Nikon, Canon) supporting C2PA do
not publish sample images with camera credentials that are also
widely recirculated online. A camera-signed original and a recirculated
copy are by nature separate files — the recirculated copy has lost
its C2PA data.

This means the M5 verification step for this combination will need
to either: (a) find a creative workaround, or (b) flag this to the
human for a plan revision. The plan allows swapping candidates if
verification fails.

## 4. Clean image — Rule 5 (No Provenance) candidate

**File:** `clean_no_provenance.jpg`
**Source:** Programmatically generated solid-color JPEG (800x600, RGB)
**License:** N/A (generated locally, no third-party content)
**Intended rule mapping:** Rule 5 (Unverified — No Provenance Found)
**Verification status:** High confidence — generated with zero EXIF,
zero C2PA, zero online history by construction.
