import { ImageResponse } from 'next/og';
import { NextRequest } from 'next/server';

import fs from 'fs';
import path from 'path';

const regularFontPath = path.join(process.cwd(), 'public', 'Roboto-Regular.ttf');
const boldFontPath = path.join(process.cwd(), 'public', 'Roboto-Bold.ttf');

// ──────────────────────────────────────────────
// Verdict colour palette
// ──────────────────────────────────────────────
type VerdictTheme = {
  accent: string;
  accentDim: string;
  bg: string;
  label: string;
  emoji: string;
};

function getTheme(classification: string): VerdictTheme {
  const c = (classification ?? '').toLowerCase();
  if (c.includes('ai-generated') || c.includes('ai generated')) {
    return { accent: '#A855F7', accentDim: '#A855F722', bg: '#1A0A2E', label: 'AI GENERATED', emoji: '🤖' };
  }
  if (c.includes('verified camera') || c.includes('camera original')) {
    return { accent: '#2DD4BF', accentDim: '#2DD4BF22', bg: '#021A18', label: 'VERIFIED', emoji: '✅' };
  }
  if (c.includes('recirculated') || c.includes('out of context')) {
    return { accent: '#F59E0B', accentDim: '#F59E0B22', bg: '#1A1200', label: 'RECIRCULATED', emoji: '🔄' };
  }
  if (c.includes('post-processed') || c.includes('post processed')) {
    return { accent: '#F97316', accentDim: '#F9731622', bg: '#1A0A00', label: 'MODIFIED', emoji: '✏️' };
  }
  return { accent: '#71717A', accentDim: '#71717A22', bg: '#111111', label: 'UNVERIFIED', emoji: '❓' };
}

function getStrengthColor(strength: string): string {
  switch (strength?.toLowerCase()) {
    case 'strong':   return '#2DD4BF';
    case 'moderate': return '#F59E0B';
    default:         return '#71717A';
  }
}

// Truncate long strings gracefully
function trunc(s: string, n: number) {
  return s && s.length > n ? s.slice(0, n - 1) + '…' : (s ?? '');
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    const backendUrl = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || 'https://receipts-backend.onrender.com';

    let receipt: any = null;

    // 1. Try Supabase REST with a 4s timeout
    if (supabaseUrl && supabaseKey) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);
        const res = await fetch(
          `${supabaseUrl}/rest/v1/receipts?id=eq.${id}&select=*`,
          {
            headers: {
              apikey: supabaseKey,
              Authorization: `Bearer ${supabaseKey}`,
            },
            signal: controller.signal,
            next: { revalidate: 60 },
          }
        );
        clearTimeout(timeoutId);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            receipt = data[0];
          }
        }
      } catch (err) {
        console.warn(`Supabase REST fetch timed out or failed for ${id}, falling back to backend:`, err);
      }
    }

    // 2. Fallback: Query backend /receipt/{id} endpoint
    if (!receipt && backendUrl) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        const res = await fetch(`${backendUrl}/receipt/${id}`, {
          signal: controller.signal,
          next: { revalidate: 60 },
        });
        clearTimeout(timeoutId);
        if (res.ok) {
          const data = await res.json();
          if (data && data.id) {
            receipt = data;
          }
        }
      } catch (err) {
        console.warn(`Backend fetch failed for ${id}:`, err);
      }
    }

    // 3. Resilient fallback card if database connections are temporarily down
    if (!receipt) {
      receipt = {
        id,
        classification: 'Unverified — No Provenance Found',
        evidence_strength: 'Limited',
        evidence: ['Verification record generated'],
        interpretation: 'Receipt generated for verification session.',
        created_at: new Date().toISOString(),
        processing_time_ms: 0,
      };
    }
    const theme = getTheme(receipt.classification ?? '');
    const strengthColor = getStrengthColor(receipt.evidence_strength ?? '');
    const evidenceItems: string[] = Array.isArray(receipt.evidence) ? receipt.evidence : [];
    const shortId = (receipt.id ?? '').slice(0, 8).toUpperCase();
    const createdAt = receipt.created_at
      ? new Date(receipt.created_at).toUTCString().replace(' GMT', ' UTC')
      : '—';
    const processingMs = receipt.processing_time_ms ?? 0;

    const regularFont = fs.readFileSync(regularFontPath);
    const boldFont    = fs.readFileSync(boldFontPath);

    // ─── Canvas: 1080 × 1920 ───────────────────────────────────────────
    return new ImageResponse(
      (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            width: '1080px',
            height: '1920px',
            backgroundColor: '#080808',
            color: '#FFFFFF',
            fontFamily: 'Roboto',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {/* ── Background glow blobs ── */}
          <div style={{
            position: 'absolute', top: '-200px', left: '-200px',
            width: '700px', height: '700px', borderRadius: '50%',
            background: `radial-gradient(circle, ${theme.accent}18 0%, transparent 70%)`,
            display: 'flex',
          }} />
          <div style={{
            position: 'absolute', bottom: '-100px', right: '-100px',
            width: '600px', height: '600px', borderRadius: '50%',
            background: `radial-gradient(circle, ${theme.accent}10 0%, transparent 70%)`,
            display: 'flex',
          }} />

          {/* ── Top accent bar ── */}
          <div style={{
            width: '100%', height: '6px',
            background: `linear-gradient(90deg, ${theme.accent}, #7C3AED, ${theme.accent})`,
            display: 'flex',
          }} />

          {/* ── Main content wrapper ── */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            padding: '72px 80px',
          }}>

            {/* ── Header row: brand + verdict label ── */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '64px' }}>
              {/* Logo / brand */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{
                  width: '52px', height: '52px', borderRadius: '14px',
                  background: `linear-gradient(135deg, ${theme.accent}40, ${theme.accent}10)`,
                  border: `2px solid ${theme.accent}50`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '28px',
                }}>
                  🔍
                </div>
                <span style={{
                  fontSize: '28px', fontWeight: 700, letterSpacing: '8px',
                  color: 'rgba(255,255,255,0.55)', textTransform: 'uppercase',
                }}>RECEIPTS</span>
              </div>

              {/* Verdict label pill */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '14px 28px', borderRadius: '9999px',
                background: theme.accentDim,
                border: `2px solid ${theme.accent}60`,
              }}>
                <span style={{ fontSize: '22px' }}>{theme.emoji}</span>
                <span style={{
                  fontSize: '22px', fontWeight: 700, letterSpacing: '3px',
                  color: theme.accent, textTransform: 'uppercase',
                }}>{theme.label}</span>
              </div>
            </div>

            {/* ── Classification ── */}
            <div style={{ display: 'flex', flexDirection: 'column', marginBottom: '48px' }}>
              <span style={{
                fontSize: '20px', fontWeight: 400, letterSpacing: '4px',
                color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', marginBottom: '20px',
              }}>
                VERIFICATION RESULT
              </span>
              <span style={{
                fontSize: '76px', fontWeight: 700, lineHeight: 1.1,
                color: '#FFFFFF', letterSpacing: '-1px',
              }}>
                {receipt.classification ?? 'Unknown'}
              </span>
            </div>

            {/* ── Evidence strength badge ── */}
            <div style={{ display: 'flex', marginBottom: '56px' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '12px 28px', borderRadius: '12px',
                background: `${strengthColor}18`,
                border: `1.5px solid ${strengthColor}50`,
              }}>
                <div style={{
                  width: '10px', height: '10px', borderRadius: '50%',
                  background: strengthColor, display: 'flex',
                }} />
                <span style={{
                  fontSize: '24px', fontWeight: 700, letterSpacing: '3px',
                  color: strengthColor, textTransform: 'uppercase',
                }}>
                  {(receipt.evidence_strength ?? 'Unknown').toUpperCase()} EVIDENCE
                </span>
              </div>
            </div>

            {/* ── Divider ── */}
            <div style={{
              width: '100%', height: '1px',
              background: 'rgba(255,255,255,0.08)', marginBottom: '56px', display: 'flex',
            }} />

            {/* ── Evidence findings ── */}
            <div style={{
              display: 'flex', flexDirection: 'column',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '24px', padding: '48px',
              marginBottom: '40px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '36px' }}>
                <div style={{
                  width: '4px', height: '28px', borderRadius: '2px',
                  background: theme.accent, display: 'flex',
                }} />
                <span style={{
                  fontSize: '22px', fontWeight: 700, letterSpacing: '4px',
                  color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase',
                }}>EVIDENCE FINDINGS</span>
                <span style={{
                  marginLeft: 'auto', fontSize: '20px', fontWeight: 700,
                  color: theme.accent,
                  background: `${theme.accent}18`,
                  padding: '6px 16px', borderRadius: '8px',
                  border: `1px solid ${theme.accent}30`,
                }}>
                  {evidenceItems.length} ITEM{evidenceItems.length !== 1 ? 'S' : ''}
                </span>
              </div>

              {evidenceItems.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
                  {evidenceItems.slice(0, 5).map((item: string, i: number) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '20px' }}>
                      <div style={{
                        width: '28px', height: '28px', borderRadius: '50%',
                        background: `${theme.accent}20`, border: `1.5px solid ${theme.accent}50`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0, marginTop: '6px',
                      }}>
                        <div style={{
                          width: '8px', height: '8px', borderRadius: '50%',
                          background: theme.accent, display: 'flex',
                        }} />
                      </div>
                      <span style={{
                        fontSize: '30px', lineHeight: 1.5, color: 'rgba(255,255,255,0.80)',
                      }}>
                        {trunc(item, 90)}
                      </span>
                    </div>
                  ))}
                  {evidenceItems.length > 5 && (
                    <span style={{ fontSize: '24px', color: 'rgba(255,255,255,0.3)', marginLeft: '48px' }}>
                      +{evidenceItems.length - 5} more finding{evidenceItems.length - 5 !== 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              ) : (
                <span style={{ fontSize: '30px', color: 'rgba(255,255,255,0.3)' }}>
                  No specific evidence items recorded.
                </span>
              )}
            </div>

            {/* ── Interpretation ── */}
            {receipt.interpretation && (
              <div style={{
                display: 'flex', flexDirection: 'column',
                background: `${theme.accent}08`,
                border: `1px solid ${theme.accent}25`,
                borderRadius: '20px', padding: '40px',
                marginBottom: '40px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
                  <div style={{
                    width: '4px', height: '28px', borderRadius: '2px',
                    background: theme.accent, display: 'flex',
                  }} />
                  <span style={{
                    fontSize: '22px', fontWeight: 700, letterSpacing: '4px',
                    color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase',
                  }}>INTERPRETATION</span>
                </div>
                <span style={{
                  fontSize: '28px', lineHeight: 1.6,
                  color: 'rgba(255,255,255,0.65)',
                }}>
                  {trunc(receipt.interpretation, 220)}
                </span>
              </div>
            )}

            {/* ── Spacer ── */}
            <div style={{ flex: 1, display: 'flex' }} />

            {/* ── Footer divider ── */}
            <div style={{
              width: '100%', height: '1px',
              background: `linear-gradient(90deg, transparent, ${theme.accent}40, transparent)`,
              marginBottom: '48px', display: 'flex',
            }} />

            {/* ── Footer ── */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>

              {/* Left: ID block */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <span style={{
                  fontSize: '18px', letterSpacing: '4px',
                  color: 'rgba(255,255,255,0.25)', textTransform: 'uppercase',
                }}>RECEIPT ID</span>
                <span style={{
                  fontFamily: 'monospace', fontSize: '30px', fontWeight: 700,
                  color: theme.accent, letterSpacing: '3px',
                }}>
                  {shortId}
                </span>
                <span style={{
                  fontFamily: 'monospace', fontSize: '18px',
                  color: 'rgba(255,255,255,0.2)',
                }}>
                  {trunc(receipt.id ?? '', 36)}
                </span>
              </div>

              {/* Right: time metadata */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '10px' }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '10px 20px', borderRadius: '10px',
                  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
                }}>
                  <span style={{ fontSize: '20px', color: theme.accent }}>⚡</span>
                  <span style={{ fontSize: '22px', color: 'rgba(255,255,255,0.5)' }}>
                    {processingMs}ms
                  </span>
                </div>
                <span style={{ fontSize: '20px', color: 'rgba(255,255,255,0.25)' }}>{createdAt}</span>
                <span style={{
                  fontSize: '18px', letterSpacing: '3px',
                  color: 'rgba(255,255,255,0.15)', textTransform: 'uppercase',
                }}>receipts.app · verified</span>
              </div>
            </div>
          </div>

          {/* ── Bottom accent bar ── */}
          <div style={{
            width: '100%', height: '4px',
            background: `linear-gradient(90deg, transparent, ${theme.accent}60, transparent)`,
            display: 'flex',
          }} />
        </div>
      ),
      {
        width: 1080,
        height: 1920,
        fonts: [
          { name: 'Roboto', data: regularFont, style: 'normal', weight: 400 },
          { name: 'Roboto', data: boldFont,    style: 'normal', weight: 700 },
        ],
        headers: {
          'Cache-Control': 'public, max-age=31536000, immutable',
        },
      }
    );
  } catch (error: unknown) {
    console.error('Error generating receipt image:', error);
    return new Response('Error generating image', { status: 500 });
  }
}
