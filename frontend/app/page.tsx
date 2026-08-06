'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type AppState = 'DROPZONE' | 'ANALYZING' | 'RESULT' | 'ERROR';

interface VerifyResult {
  id: string;
  classification: string;
  evidence_strength: string;
  evidence: string[];
  interpretation: string;
  processing_time_ms: number;
  receipt_image_url: string;
  cached: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const LOADING_MESSAGES = [
  'Extracting metadata…',
  'Checking provenance…',
  'Tracing origin…',
  'Applying rules engine…',
];

const STRENGTH_COLORS: Record<string, string> = {
  Strong: 'text-teal-400 border-teal-400/40 bg-teal-400/10',
  Moderate: 'text-amber-400 border-amber-400/40 bg-amber-400/10',
  Limited: 'text-zinc-400 border-zinc-400/40 bg-zinc-400/10',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ReceiptsPage() {
  // ---- state ----
  const [appState, setAppState] = useState<AppState>('DROPZONE');
  const [dragActive, setDragActive] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState('');
  const [loadingIdx, setLoadingIdx] = useState(0);
  const [thumbnail, setThumbnail] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResult | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ---- loading text rotation ----
  useEffect(() => {
    if (appState !== 'ANALYZING') return;
    const id = setInterval(() => {
      setLoadingIdx((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 1500);
    return () => clearInterval(id);
  }, [appState]);

  // ---- drag handlers ----
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) await processFile(e.dataTransfer.files[0]);
  }, []);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) await processFile(e.target.files[0]);
  };

  // ---- file validation ----
  const processFile = async (file: File) => {
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setErrorMsg('Please upload a valid image (JPG, PNG, or WebP).');
      setAppState('ERROR');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setErrorMsg('File size must be under 15 MB.');
      setAppState('ERROR');
      return;
    }
    setThumbnail(URL.createObjectURL(file));
    setAppState('ANALYZING');
    setLoadingIdx(0);
    await sendToApi(file);
  };

  // ---- URL submission ----
  const onUrlSubmit = async () => {
    if (!imageUrl.trim()) return;
    setThumbnail(imageUrl);
    setAppState('ANALYZING');
    setLoadingIdx(0);
    await sendToApi(null, imageUrl);
  };

  // ---- API call ----
  const sendToApi = async (file: File | null, url?: string) => {
    try {
      const formData = new FormData();

      if (file) {
        // Backend expects: input_type="file" + file=<UploadFile>
        formData.append('input_type', 'file');
        formData.append('file', file);
      } else if (url) {
        // Backend expects: input_type="url" + image_url=<string>
        formData.append('input_type', 'url');
        formData.append('image_url', url);
      }

      const res = await fetch(`${API_URL}/verify`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(errBody?.detail || `Server error (${res.status})`);
      }

      const data: VerifyResult = await res.json();
      setResult(data);
      setAppState('RESULT');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Network error';
      setErrorMsg(msg);
      setAppState('ERROR');
    }
  };

  // ---- reset ----
  const resetState = () => {
    setAppState('DROPZONE');
    setErrorMsg(null);
    setThumbnail(null);
    setImageUrl('');
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ---- share / download ----
  const handleShare = async () => {
    if (!result) return;

    const receiptUrl = `/api/receipt/${result.id}`;

    // Fetch the receipt image as a blob for sharing
    try {
      const imgRes = await fetch(receiptUrl);
      const blob = await imgRes.blob();
      const file = new File([blob], `receipt-${result.id}.png`, {
        type: 'image/png',
      });

      // Web Share API with file
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({
          title: 'Receipts — Verification Result',
          files: [file],
        });
        return;
      }
    } catch {
      // Fall through to download fallback
    }

    // Fallback: direct download via anchor tag
    const a = document.createElement('a');
    a.href = receiptUrl;
    a.download = `receipt-${result.id}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  // ---- key handler for URL input ----
  const handleUrlKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') onUrlSubmit();
  };

  // ====================================================================
  // RENDER
  // ====================================================================
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 py-12 relative overflow-hidden">
      {/* Ambient glow */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-[-30%] left-[20%] w-[500px] h-[500px] rounded-full bg-teal-500/5 blur-[120px]" />
        <div className="absolute bottom-[-20%] right-[15%] w-[400px] h-[400px] rounded-full bg-purple-500/5 blur-[100px]" />
      </div>

      {/* Header */}
      <div className="fixed top-0 left-0 right-0 z-50 flex items-center justify-center py-6">
        <h1 className="tracking-[0.35em] text-xs font-semibold uppercase text-white/40">
          Receipts
        </h1>
      </div>

      {/* Content */}
      <div className="w-full max-w-md mx-auto flex flex-col items-center z-10">

        {/* ============================================================ */}
        {/* STATE: DROPZONE                                              */}
        {/* ============================================================ */}
        {appState === 'DROPZONE' && (
          <div className="w-full flex flex-col items-center gap-8 fade-in">
            {/* Tagline */}
            <div className="text-center space-y-3 mb-2">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-gradient leading-tight">
                Don&apos;t share it.
                <br />
                Prove it.
              </h2>
              <p className="text-sm text-white/40 max-w-xs mx-auto">
                Upload an image to verify its provenance, detect AI generation,
                and trace its origin across the web.
              </p>
            </div>

            {/* Dropzone */}
            <div
              id="dropzone"
              className={`glass-panel w-full rounded-2xl flex flex-col items-center justify-center cursor-pointer py-16 px-6 ${
                dragActive ? 'drag-active' : ''
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                id="file-input"
                type="file"
                className="hidden"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileChange}
              />
              {/* Upload icon */}
              <svg
                className="w-10 h-10 text-white/30 mb-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M12 16V4m0 0l-4 4m4-4l4 4M4 14v4a2 2 0 002 2h12a2 2 0 002-2v-4"
                />
              </svg>
              <p className="text-base font-medium text-white/80">
                Drop an image or click to upload
              </p>
              <p className="text-xs text-white/30 mt-2">
                Supports JPG, PNG, WebP&ensp;·&ensp;Max 15 MB
              </p>
            </div>

            {/* OR divider */}
            <div className="flex items-center w-full gap-4 text-white/20 text-xs font-medium uppercase tracking-wider">
              <div className="h-px bg-white/10 flex-1" />
              or
              <div className="h-px bg-white/10 flex-1" />
            </div>

            {/* URL input */}
            <div className="flex w-full gap-2">
              <input
                id="url-input"
                type="url"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                onKeyDown={handleUrlKeyDown}
                placeholder="Paste image URL"
                className="flex-1 bg-white/[0.04] border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/25 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 transition-all"
              />
              <button
                id="verify-url-btn"
                onClick={onUrlSubmit}
                disabled={!imageUrl.trim()}
                className="bg-teal-500/15 hover:bg-teal-500/25 disabled:opacity-30 disabled:cursor-not-allowed text-teal-300 border border-teal-500/20 px-5 py-3 rounded-xl text-sm font-medium transition-all"
              >
                Verify
              </button>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* STATE: ANALYZING                                             */}
        {/* ============================================================ */}
        {appState === 'ANALYZING' && (
          <div className="w-full flex flex-col items-center gap-8 fade-in">
            {/* Thumbnail with scan effect */}
            <div className="relative w-44 h-44 rounded-2xl overflow-hidden bg-white/[0.03] border border-white/10">
              {thumbnail && (
                <img
                  src={thumbnail}
                  alt="Analyzing"
                  className="w-full h-full object-cover opacity-40"
                />
              )}
              <div className="scan-line" />
              {/* Corner accents */}
              <div className="absolute top-0 left-0 w-5 h-5 border-t-2 border-l-2 border-teal-400/60 rounded-tl-lg" />
              <div className="absolute top-0 right-0 w-5 h-5 border-t-2 border-r-2 border-teal-400/60 rounded-tr-lg" />
              <div className="absolute bottom-0 left-0 w-5 h-5 border-b-2 border-l-2 border-teal-400/60 rounded-bl-lg" />
              <div className="absolute bottom-0 right-0 w-5 h-5 border-b-2 border-r-2 border-teal-400/60 rounded-br-lg" />
            </div>

            {/* Loading text */}
            <div className="text-center space-y-5">
              <p className="text-lg font-medium text-white/80 animate-pulse-glow h-7">
                {LOADING_MESSAGES[loadingIdx]}
              </p>
              {/* Progress bar */}
              <div className="w-64 h-1 bg-white/[0.06] rounded-full overflow-hidden mx-auto">
                <div className="h-full bg-gradient-to-r from-teal-400 via-purple-400 to-teal-400 rounded-full progress-slide" />
              </div>
              <p className="text-xs text-white/25">
                This may take a few seconds…
              </p>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* STATE: RESULT                                                */}
        {/* ============================================================ */}
        {appState === 'RESULT' && result && (
          <div className="w-full flex flex-col items-center gap-6 slide-up">
            {/* Summary */}
            <div className="text-center space-y-2">
              <p className="text-xs uppercase tracking-widest text-teal-400/80 font-semibold">
                Verification Complete
              </p>
              <h3 className="text-2xl font-bold text-white">
                {result.classification}
              </h3>
              <span
                className={`inline-block text-xs font-semibold uppercase tracking-wider px-3 py-1 rounded-full border ${
                  STRENGTH_COLORS[result.evidence_strength] ||
                  STRENGTH_COLORS.Limited
                }`}
              >
                {result.evidence_strength} Evidence
              </span>
              {result.cached && (
                <p className="text-[10px] text-white/20 mt-1">
                  ⚡ Cached result
                </p>
              )}
            </div>

            {/* Receipt image */}
            <div className="relative w-full max-w-xs aspect-[9/16] rounded-2xl overflow-hidden border border-white/10 shadow-[0_0_60px_rgba(0,212,170,0.08)]">
              <img
                id="receipt-image"
                src={`/api/receipt/${result.id}`}
                alt="Verification Receipt"
                className="w-full h-full object-cover"
              />
            </div>

            {/* Action buttons */}
            <div className="flex gap-3 w-full max-w-xs">
              <button
                id="share-btn"
                onClick={handleShare}
                className="flex-1 flex items-center justify-center gap-2 bg-teal-500/15 hover:bg-teal-500/25 text-teal-300 border border-teal-500/25 px-4 py-3 rounded-xl text-sm font-medium transition-all"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
                Share
              </button>
              <button
                id="verify-another-btn"
                onClick={resetState}
                className="flex-1 bg-white/[0.06] hover:bg-white/[0.1] text-white/80 border border-white/10 px-4 py-3 rounded-xl text-sm font-medium transition-all"
              >
                Verify Another
              </button>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* STATE: ERROR                                                 */}
        {/* ============================================================ */}
        {appState === 'ERROR' && (
          <div className="w-full flex flex-col items-center gap-6 fade-in">
            <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center border border-red-500/20">
              <svg
                className="w-8 h-8 text-red-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-lg font-semibold text-white">
                Verification Failed
              </h3>
              <p className="text-sm text-white/50 max-w-xs">
                {errorMsg || 'An unexpected error occurred.'}
              </p>
            </div>
            <button
              id="retry-btn"
              onClick={resetState}
              className="bg-white/[0.06] hover:bg-white/[0.1] text-white/80 border border-white/10 px-6 py-3 rounded-xl text-sm font-medium transition-all"
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
