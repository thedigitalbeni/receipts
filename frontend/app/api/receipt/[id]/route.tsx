import { ImageResponse } from 'next/og';
import { NextRequest } from 'next/server';

import fs from 'fs';
import path from 'path';

// Load fonts from the public directory
const regularFontPath = path.join(process.cwd(), 'public', 'Roboto-Regular.ttf');
const boldFontPath = path.join(process.cwd(), 'public', 'Roboto-Bold.ttf');
const getInterRegular = fs.readFileSync(regularFontPath);
const getInterBold = fs.readFileSync(boldFontPath);

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseKey) {
      return new Response('Missing Supabase credentials', { status: 500 });
    }

    const res = await fetch(
      `${supabaseUrl}/rest/v1/receipts?id=eq.${id}&select=*`,
      {
        headers: {
          apikey: supabaseKey,
          Authorization: `Bearer ${supabaseKey}`,
        },
      }
    );

    if (!res.ok) {
      return new Response('Failed to fetch receipt', { status: res.status });
    }

    const data = await res.json();
    if (!data || data.length === 0) {
      return new Response('Receipt not found', { status: 404 });
    }

    const receipt = data[0];

    const interRegularFont = getInterRegular;
    const interBoldFont = getInterBold;

    const getStrengthColor = (strength: string) => {
      switch (strength?.toLowerCase()) {
        case 'strong':
          return '#00D4AA';
        case 'moderate':
          return '#F59E0B';
        case 'limited':
          return '#6B7280';
        default:
          return '#6B7280';
      }
    };

    const strengthColor = getStrengthColor(receipt.evidence_strength);
    const evidenceItems = Array.isArray(receipt.evidence) ? receipt.evidence : [];

    return new ImageResponse(
      (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            width: '1080px',
            height: '1920px',
            backgroundColor: '#0A0A0A',
            color: '#FFFFFF',
            fontFamily: 'Inter',
            padding: '80px',
            boxSizing: 'border-box',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              marginBottom: '60px',
            }}
          >
            <span
              style={{
                fontSize: '32px',
                letterSpacing: '12px',
                fontWeight: 700,
                color: 'rgba(255, 255, 255, 0.6)',
                textTransform: 'uppercase',
              }}
            >
              Receipts
            </span>
          </div>

          {/* Classification */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              marginBottom: '40px',
            }}
          >
            <span
              style={{
                fontSize: '84px',
                fontWeight: 700,
                lineHeight: 1.1,
                marginBottom: '40px',
              }}
            >
              {receipt.classification || 'Unknown Classification'}
            </span>
            <div style={{ display: 'flex' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '12px 24px',
                  borderRadius: '9999px',
                  backgroundColor: `${strengthColor}22`,
                  border: `2px solid ${strengthColor}`,
                }}
              >
                <span
                  style={{
                    fontSize: '28px',
                    fontWeight: 700,
                    color: strengthColor,
                    textTransform: 'uppercase',
                    letterSpacing: '2px',
                  }}
                >
                  {receipt.evidence_strength || 'Unknown'} Evidence
                </span>
              </div>
            </div>
          </div>

          {/* Evidence Panel */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '24px',
              padding: '40px',
              marginBottom: '40px',
            }}
          >
            <span
              style={{
                fontSize: '24px',
                color: 'rgba(255, 255, 255, 0.6)',
                textTransform: 'uppercase',
                letterSpacing: '2px',
                marginBottom: '24px',
              }}
            >
              Evidence Found
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {evidenceItems.length > 0 ? (
                evidenceItems.map((item: string, i: number) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '32px', marginRight: '16px', color: strengthColor }}>•</span>
                    <span style={{ fontSize: '32px', lineHeight: 1.4 }}>{item}</span>
                  </div>
                ))
              ) : (
                <span style={{ fontSize: '32px', color: 'rgba(255,255,255,0.4)' }}>
                  No evidence provided.
                </span>
              )}
            </div>
          </div>

          {/* Interpretation Panel */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '24px',
              padding: '40px',
              flex: 1,
            }}
          >
            <span
              style={{
                fontSize: '24px',
                color: 'rgba(255, 255, 255, 0.6)',
                textTransform: 'uppercase',
                letterSpacing: '2px',
                marginBottom: '24px',
              }}
            >
              Interpretation
            </span>
            <span style={{ fontSize: '32px', lineHeight: 1.5 }}>
              {receipt.interpretation || 'No interpretation available.'}
            </span>
          </div>

          {/* Footer */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginTop: '40px',
              borderTop: '1px solid rgba(255, 255, 255, 0.1)',
              paddingTop: '40px',
            }}
          >
            <span
              style={{
                fontFamily: 'monospace',
                fontSize: '24px',
                color: 'rgba(255, 255, 255, 0.4)',
              }}
            >
              ID: {receipt.id}
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
              <span style={{ fontSize: '24px', color: 'rgba(255, 255, 255, 0.4)' }}>
                Processed in {receipt.processing_time_ms || 0}ms
              </span>
              <span style={{ fontSize: '20px', color: 'rgba(255, 255, 255, 0.3)' }}>
                {receipt.created_at ? new Date(receipt.created_at).toLocaleString() : ''}
              </span>
            </div>
          </div>
        </div>
      ),
      {
        width: 1080,
        height: 1920,
        fonts: [
          {
            name: 'Inter',
            data: interRegularFont,
            style: 'normal',
            weight: 400,
          },
          {
            name: 'Inter',
            data: interBoldFont,
            style: 'normal',
            weight: 700,
          },
        ],
      }
    );
  } catch (error: any) {
    console.error('Error generating image:', error);
    return new Response('Error generating image', { status: 500 });
  }
}
