import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const maxDuration = 60; // Max allowed execution duration on serverless

const BACKEND_URL = (
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://receipts-backend.onrender.com'
).replace(/\/+$/, '');

export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get('content-type') || '';

    let backendResponse: Response;

    if (contentType.includes('multipart/form-data')) {
      const incomingFormData = await req.formData();
      
      // Construct a clean outgoing FormData to forward to FastAPI
      const outgoingFormData = new FormData();
      for (const [key, value] of incomingFormData.entries()) {
        outgoingFormData.append(key, value);
      }

      backendResponse = await fetch(`${BACKEND_URL}/verify`, {
        method: 'POST',
        body: outgoingFormData,
        // No manual content-type header so fetch sets boundary correctly
      });
    } else {
      // Fallback for raw JSON or other content types
      const rawBody = await req.text();
      backendResponse = await fetch(`${BACKEND_URL}/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': contentType || 'application/json',
        },
        body: rawBody,
      });
    }

    const data = await backendResponse.json().catch(() => null);

    if (!backendResponse.ok) {
      return NextResponse.json(
        { detail: data?.detail || `Backend error (${backendResponse.status})` },
        { status: backendResponse.status }
      );
    }

    return NextResponse.json(data, { status: 200 });
  } catch (error: unknown) {
    console.error('API Proxy error in /api/verify:', error);
    const errMessage = error instanceof Error ? error.message : String(error);
    const isNetwork = errMessage.toLowerCase().includes('fetch') || errMessage.toLowerCase().includes('connect') || errMessage.toLowerCase().includes('network') || errMessage.toLowerCase().includes('timeout');

    return NextResponse.json(
      {
        detail: isNetwork
          ? 'Could not connect to the verification server. The server may be waking up from sleep — please wait a moment and try again.'
          : (errMessage || 'Internal proxy error during verification'),
      },
      { status: 502 }
    );
  }
}
