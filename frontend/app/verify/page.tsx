'use client';

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  UploadCloud, CheckCircle, AlertCircle, Share2, RefreshCcw, Scan,
  FileSearch, Code, ZoomIn, ZoomOut, Info, Clock, Database, ChevronDown,
  ArrowLeft, ShieldCheck, Brain, Globe, Cpu, CheckCircle2,
  HelpCircle, ExternalLink, Plus, Minus, Maximize2,
  Download, Link2, Copy, Check, X, Send, MessageCircle,
} from 'lucide-react';
import Link from 'next/link';
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

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
const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

const LOADING_MESSAGES = [
  'Initializing forensic pipeline…',
  'Extracting metadata…',
  'Checking C2PA signatures…',
  'Running Error Level Analysis…',
  'Querying origin trace…',
  'Analyzing Wayback Machine data…',
  'Applying rules engine…',
];

const PHASE_DURATION = 2500;

/** Map raw backend errors to user-friendly messages */
function friendlyError(raw: string): { title: string; message: string; hint?: string } {
  if (!raw) return { title: 'Unexpected Error', message: 'Something went wrong.', hint: 'Please try again.' };
  const lower = raw.toLowerCase();
  if (lower.includes('could not fetch html') || lower.includes('no social image metadata'))
    return { title: 'Not a Direct Image', message: 'This URL points to a webpage, not an image file.', hint: 'Right-click the image → "Copy image address" and paste that URL instead.' };
  if (lower.includes('content type') || lower.includes('not a valid image') || lower.includes('url must point directly'))
    return { title: 'Invalid Image URL', message: "The URL doesn't point to a supported image format.", hint: 'Make sure the URL ends in .jpg, .png, or .webp — not a webpage URL.' };
  if (lower.includes('too large') || lower.includes('exceeds'))
    return { title: 'File Too Large', message: 'The image exceeds the 15 MB size limit.', hint: 'Try compressing the image or using a smaller version.' };
  if (lower.includes('rate limit'))
    return { title: 'Rate Limited', message: 'Too many requests. Please wait a moment.', hint: 'The limit is 10 verifications per minute.' };
  if (lower.includes('blocked ip') || lower.includes('resolve') || lower.includes('dns'))
    return { title: 'URL Blocked', message: 'This URL could not be safely accessed.', hint: 'The URL may point to an internal network. Try a public image URL.' };
  if (lower.includes('timed out') || lower.includes('aborterror'))
    return { title: 'Request Timed Out', message: 'The analysis took too long to complete.', hint: 'The server may be starting up from sleep — wait 10 seconds and try again.' };
  if (lower.includes('internal server error') || lower.includes('500'))
    return { title: 'Server Error', message: 'Something went wrong on our end.', hint: 'This is usually temporary. Please try again in a moment.' };
  if (lower.includes('422') || lower.includes('unprocessable'))
    return { title: 'Invalid Input', message: 'The server couldn\'t process this image.', hint: 'Make sure the URL points directly to an image file.' };
  if (lower.includes('cors') || lower.includes('origin'))
    return { title: 'Connection Blocked', message: 'Cross-origin request was blocked.', hint: 'This is usually temporary — please try again.' };
  if (lower.includes('ssl') || lower.includes('certificate'))
    return { title: 'Secure Connection Failed', message: 'Could not establish a secure connection to the image source.', hint: 'Try a different image URL from a trusted source.' };
  if (lower.includes('network') || lower.includes('fetch') || lower.includes('failed to fetch'))
    return { title: 'Connection Error', message: 'Could not reach the verification server.', hint: 'The server may be waking up — wait 10 seconds and try again.' };
  if (lower.includes('server error'))
    return { title: 'Server Error', message: raw, hint: 'Please try again in a moment.' };
  return { title: 'Verification Failed', message: raw.length > 120 ? raw.slice(0, 120) + '…' : raw, hint: 'Please try again or use a different image.' };
}

// Classification → visual config
const CLASSIFICATION_CONFIG: Record<string, {
  color: string; border: string; bg: string; glow: string; icon: React.ReactNode; strengthColor: string;
}> = {
  'AI-Generated Content': {
    color: 'text-purple-300', border: 'border-purple-500/40', bg: 'bg-purple-500/10',
    glow: 'shadow-[0_0_40px_rgba(168,85,247,0.15)]',
    icon: <Brain className="w-5 h-5 text-purple-400" />,
    strengthColor: 'text-purple-400 border-purple-400/40 bg-purple-400/10',
  },
  'Verified Camera Original': {
    color: 'text-teal-300', border: 'border-teal-500/40', bg: 'bg-teal-500/10',
    glow: 'shadow-[0_0_40px_rgba(45,212,191,0.15)]',
    icon: <ShieldCheck className="w-5 h-5 text-teal-400" />,
    strengthColor: 'text-teal-400 border-teal-400/40 bg-teal-400/10',
  },
  'Recirculated / Out of Context': {
    color: 'text-amber-300', border: 'border-amber-500/40', bg: 'bg-amber-500/10',
    glow: 'shadow-[0_0_40px_rgba(251,191,36,0.15)]',
    icon: <Globe className="w-5 h-5 text-amber-400" />,
    strengthColor: 'text-amber-400 border-amber-400/40 bg-amber-400/10',
  },
  'Post-Processed Image': {
    color: 'text-orange-300', border: 'border-orange-500/40', bg: 'bg-orange-500/10',
    glow: 'shadow-[0_0_40px_rgba(251,146,60,0.15)]',
    icon: <Cpu className="w-5 h-5 text-orange-400" />,
    strengthColor: 'text-orange-400 border-orange-400/40 bg-orange-400/10',
  },
  'Unverified — No Provenance Found': {
    color: 'text-zinc-300', border: 'border-zinc-500/40', bg: 'bg-zinc-500/10',
    glow: 'shadow-[0_0_20px_rgba(113,113,122,0.1)]',
    icon: <HelpCircle className="w-5 h-5 text-zinc-400" />,
    strengthColor: 'text-zinc-400 border-zinc-400/40 bg-zinc-400/10',
  },
};

const DEFAULT_CONFIG = {
  color: 'text-white', border: 'border-white/20', bg: 'bg-white/5', glow: '',
  icon: <CheckCircle className="w-5 h-5 text-teal-400" />,
  strengthColor: 'text-teal-400 border-teal-400/40 bg-teal-400/10',
};

// ---------------------------------------------------------------------------
// ZoomableReceipt — wheel zoom + drag to pan
// ---------------------------------------------------------------------------
function ZoomableReceipt({ src }: { src: string }) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef<{ x: number; y: number; px: number; py: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Wheel zoom
  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setScale(s => Math.min(5, Math.max(1, s - e.deltaY * 0.002)));
  }, []);

  // Drag to pan
  const onPointerDown = (e: React.PointerEvent) => {
    if (scale <= 1) return;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY, px: pos.x, py: pos.y };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging || !dragStart.current) return;
    setPos({ x: dragStart.current.px + e.clientX - dragStart.current.x, y: dragStart.current.py + e.clientY - dragStart.current.y });
  };
  const onPointerUp = () => { setDragging(false); dragStart.current = null; };

  // Reset when scale goes back to 1
  useEffect(() => { if (scale <= 1) setPos({ x: 0, y: 0 }); }, [scale]);

  const zoom = (delta: number) => setScale(s => Math.min(5, Math.max(1, +(s + delta).toFixed(1))));
  const reset = () => { setScale(1); setPos({ x: 0, y: 0 }); };

  return (
    <div ref={containerRef} className="relative w-full h-full rounded-xl bg-black/90 overflow-hidden select-none"
      onWheel={onWheel} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
      onPointerUp={onPointerUp} onPointerLeave={onPointerUp}
      style={{ cursor: scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'default' }}
    >
      <img
        src={src} alt="Full Receipt" draggable={false}
        style={{ transform: `scale(${scale}) translate(${pos.x / scale}px, ${pos.y / scale}px)`, transformOrigin: 'center center', transition: dragging ? 'none' : 'transform 0.15s ease' }}
        className="w-full h-full object-contain"
      />
      {/* Zoom controls */}
      <div className="absolute bottom-4 right-4 z-40 flex items-center gap-1.5 bg-black/70 backdrop-blur-md border border-white/10 rounded-xl p-1.5">
        <button onClick={() => zoom(-0.5)} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 transition-colors text-white/70 hover:text-white" aria-label="Zoom out">
          <Minus className="w-3.5 h-3.5" />
        </button>
        <span className="text-[11px] font-bold text-white/50 min-w-[38px] text-center">{Math.round(scale * 100)}%</span>
        <button onClick={() => zoom(0.5)} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 transition-colors text-white/70 hover:text-white" aria-label="Zoom in">
          <Plus className="w-3.5 h-3.5" />
        </button>
        {scale > 1 && (
          <button onClick={reset} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 transition-colors text-teal-400 hover:text-teal-300 border-l border-white/10 ml-0.5" aria-label="Reset zoom">
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {scale <= 1 && (
        <div className="absolute bottom-4 left-4 z-40 text-[11px] text-white/30 bg-black/50 px-2.5 py-1 rounded-lg border border-white/5 backdrop-blur-md">
          Scroll or use controls to zoom
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Interface
// ---------------------------------------------------------------------------
interface ImageDetails {
  name: string;
  size: string;
  dimensions: string;
  source: string;
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------
export default function ReceiptsPage() {
  const [imageDetails, setImageDetails] = useState<ImageDetails | null>(null);
  const [appState, setAppState] = useState<AppState>('DROPZONE');
  const [dragActive, setDragActive] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState('');
  const [loadingIdx, setLoadingIdx] = useState(0);
  const [thumbnail, setThumbnail] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResult | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Share menu state
  const [shareOpen, setShareOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const shareRef = useRef<HTMLDivElement>(null);
  const [retrying, setRetrying] = useState(false);

  // Close share menu on outside click
  useEffect(() => {
    if (!shareOpen) return;
    const handler = (e: MouseEvent) => {
      if (shareRef.current && !shareRef.current.contains(e.target as Node)) setShareOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [shareOpen]);

  // loading text rotation
  useEffect(() => {
    if (appState !== 'ANALYZING') return;
    const id = setInterval(() => {
      setLoadingIdx((i) => (i + 1) % LOADING_MESSAGES.length);
    }, PHASE_DURATION);
    return () => clearInterval(id);
  }, [appState]);

  // Phase progress for the scanner
  const scanProgress = useMemo(() => (loadingIdx + 1) / LOADING_MESSAGES.length, [loadingIdx]);

  // drag handlers
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    const uriList = e.dataTransfer.getData('text/uri-list');
    const plainText = e.dataTransfer.getData('text/plain');
    const url = uriList || plainText;
    if (url && url.startsWith('http')) {
      setImageUrl(url); setThumbnail(url);
      setAppState('ANALYZING'); setLoadingIdx(0);
      await sendToApi(null, url); return;
    }
    if (e.dataTransfer.files?.[0]) await processFile(e.dataTransfer.files[0]);
  }, []);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) await processFile(e.target.files[0]);
  };

  const processFile = async (file: File) => {
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) { setErrorMsg('Please upload a valid image (JPG, PNG, or WebP).'); setAppState('ERROR'); return; }
    if (file.size > 15 * 1024 * 1024) { setErrorMsg('File size must be under 15 MB.'); setAppState('ERROR'); return; }
    if (thumbnail) URL.revokeObjectURL(thumbnail);
    const objectUrl = URL.createObjectURL(file);
    setThumbnail(objectUrl);
    const img = new window.Image();
    img.onload = () => setImageDetails({ name: file.name, size: (file.size / 1024 / 1024).toFixed(2) + ' MB', dimensions: `${img.width} × ${img.height} px`, source: 'Local Upload' });
    img.src = objectUrl;
    setAppState('ANALYZING'); setLoadingIdx(0);
    await sendToApi(file);
  };

  const onUrlSubmit = async () => {
    if (!imageUrl.trim()) return;
    setThumbnail(imageUrl);
    const img = new window.Image();
    img.onload = () => {
      let name = 'Image from URL';
      try { name = new URL(imageUrl).pathname.split('/').pop() || name; } catch {}
      setImageDetails({ name, size: 'Unknown', dimensions: `${img.width} × ${img.height} px`, source: 'URL Input' });
    };
    img.src = imageUrl;
    setAppState('ANALYZING'); setLoadingIdx(0);
    await sendToApi(null, imageUrl);
  };

  const doFetch = async (file: File | null, url?: string, signal?: AbortSignal): Promise<Response> => {
    const formData = new FormData();
    if (file) { formData.append('input_type', 'file'); formData.append('file', file); }
    else if (url) { formData.append('input_type', 'url'); formData.append('image_url', url); }
    return fetch(`${API_URL}/verify`, { method: 'POST', body: formData, signal });
  };

  const sendToApi = async (file: File | null, url?: string) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minutes
    try {
      let res: Response;
      try {
        res = await doFetch(file, url, controller.signal);
      } catch (firstErr: unknown) {
        // Auto-retry once on network/timeout errors (cold start)
        const isRetryable = firstErr instanceof Error &&
          (firstErr.name === 'AbortError' || firstErr.message.toLowerCase().includes('fetch') || firstErr.message.toLowerCase().includes('network'));
        if (!isRetryable) throw firstErr;
        setRetrying(true);
        await new Promise(r => setTimeout(r, 3000));
        setRetrying(false);
        res = await doFetch(file, url, controller.signal);
      }
      clearTimeout(timeoutId);
      if (!res.ok) { const errBody = await res.json().catch(() => null); throw new Error(errBody?.detail || `Server error (${res.status})`); }
      const data: VerifyResult = await res.json();
      if (data.classification === 'Unverified — No Provenance Found') {
        data.interpretation = 'No cryptographic signatures or structural metadata were found. Social media platforms (like Twitter/Instagram) typically strip this metadata to protect user privacy and save space. We can confirm there is no data, rather than a failure to find it.';
      }
      setResult(data); setAppState('RESULT');
    } catch (err: unknown) {
      clearTimeout(timeoutId);
      setRetrying(false);
      let msg = 'Network error';
      if (err instanceof Error) msg = err.name === 'AbortError' ? 'Verification timed out. The server might be warming up, please try again.' : err.message;
      setErrorMsg(msg); setAppState('ERROR');
    }
  };

  const resetState = () => {
    if (thumbnail) URL.revokeObjectURL(thumbnail);
    setAppState('DROPZONE'); setErrorMsg(null); setThumbnail(null);
    setImageUrl(''); setResult(null); setImageDetails(null); setShareOpen(false); setCopied(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const getReceiptFullUrl = () => {
    if (!result) return '';
    return `${window.location.origin}/api/receipt/${result.id}`;
  };

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(getReceiptFullUrl());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard not available */ }
  };

  const handleDownload = async () => {
    if (!result) return;
    const a = document.createElement('a');
    a.href = `/api/receipt/${result.id}`; a.download = `receipt-${result.id}.png`;
    document.body.appendChild(a); a.click(); a.remove();
    setShareOpen(false);
  };

  const handleShareSocial = (platform: 'x' | 'telegram' | 'whatsapp') => {
    const url = getReceiptFullUrl();
    const text = `Image verified with Receipts — forensic analysis complete.`;
    const encodedUrl = encodeURIComponent(url);
    const encodedText = encodeURIComponent(text);
    const links: Record<string, string> = {
      x: `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`,
      telegram: `https://t.me/share/url?url=${encodedUrl}&text=${encodedText}`,
      whatsapp: `https://wa.me/?text=${encodedText}%20${encodedUrl}`,
    };
    window.open(links[platform], '_blank', 'noopener,noreferrer');
    setShareOpen(false);
  };

  const handleNativeShare = async () => {
    if (!result) return;
    try {
      const imgRes = await fetch(`/api/receipt/${result.id}`);
      const blob = await imgRes.blob();
      const file = new File([blob], `receipt-${result.id}.png`, { type: 'image/png' });
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({ title: 'Receipts — Verification Result', files: [file] });
      }
    } catch { /* fall through */ }
    setShareOpen(false);
  };

  const handleUrlKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') onUrlSubmit(); };

  const cfg = result ? (CLASSIFICATION_CONFIG[result.classification] ?? DEFAULT_CONFIG) : DEFAULT_CONFIG;

  // ====================================================================
  // RENDER
  // ====================================================================
  return (
    <main className="min-h-screen flex flex-col bg-[#0A0A0A] text-white relative overflow-x-hidden">

      {/* Ambient glows */}
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden="true">
        <motion.div animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0.5, 0.3] }} transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute top-[-20%] left-[10%] w-[600px] h-[600px] rounded-full bg-teal-500/10 blur-[120px]" />
        <motion.div animate={{ scale: [1, 1.2, 1], opacity: [0.2, 0.4, 0.2] }} transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
          className="absolute bottom-[-10%] right-[5%] w-[500px] h-[500px] rounded-full bg-purple-600/10 blur-[100px]" />
      </div>

      {/* ── Nav Header ── */}
      <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-[#0A0A0A]/60 border-b border-white/5">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-1.5 text-white/50 hover:text-white/80 transition-colors text-sm font-medium">
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">Back</span>
          </Link>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-teal-500" />
            <span className="tracking-[0.3em] text-xs font-bold uppercase text-white/60">Receipts</span>
          </div>
          <div className="w-10 sm:w-16" />
        </div>
      </header>

      {/* ── Main content ── */}
      <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-3 sm:px-6 py-20 sm:py-24">
        <AnimatePresence mode="wait">

          {/* ══════════════ DROPZONE ══════════════ */}
          {appState === 'DROPZONE' && (
            <motion.div
              key="dropzone"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.4 }}
              className="w-full max-w-2xl flex flex-col items-center gap-6 sm:gap-8"
            >
              {/* Hero text */}
              <div className="text-center space-y-3">
                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-teal-400 via-white/90 to-purple-500 leading-tight pb-1">
                  Don&apos;t share it.<br />Prove it.
                </h1>
                <p className="text-sm text-white/50 max-w-sm sm:max-w-md mx-auto leading-relaxed">
                  Paste a URL or drop an image file — our 5-layer forensic pipeline runs in seconds.
                </p>
              </div>

              {/* Dropzone */}
              <motion.div
                id="dropzone"
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                className={`group relative w-full rounded-3xl flex flex-col items-center justify-center cursor-pointer py-12 sm:py-16 px-6 sm:px-8 overflow-hidden backdrop-blur-xl transition-all duration-300 ${
                  dragActive
                    ? 'border-2 border-teal-400 bg-teal-400/10 shadow-[0_0_40px_rgba(45,212,191,0.2)]'
                    : 'border border-white/10 bg-white/[0.03] hover:border-teal-400/40 hover:bg-white/[0.05] hover:shadow-[0_0_30px_rgba(45,212,191,0.1)]'
                }`}
                onDragEnter={handleDrag} onDragLeave={handleDrag}
                onDragOver={handleDrag} onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <motion.div animate={{ opacity: [0.05, 0.15, 0.05] }} transition={{ duration: 4, repeat: Infinity }}
                  className="absolute inset-0 bg-gradient-to-b from-teal-500/10 to-transparent pointer-events-none" />
                <div className="absolute top-3 left-3 w-5 h-5 border-t-2 border-l-2 border-teal-400/40" />
                <div className="absolute top-3 right-3 w-5 h-5 border-t-2 border-r-2 border-teal-400/40" />
                <div className="absolute bottom-3 left-3 w-5 h-5 border-b-2 border-l-2 border-teal-400/40" />
                <div className="absolute bottom-3 right-3 w-5 h-5 border-b-2 border-r-2 border-teal-400/40" />

                <input ref={fileInputRef} id="file-input" type="file" className="hidden"
                  accept="image/jpeg,image/png,image/webp" onChange={handleFileChange} aria-label="Upload image file" />

                <div className={`w-14 h-14 sm:w-16 sm:h-16 rounded-2xl mb-4 flex items-center justify-center transition-colors ${dragActive ? 'bg-teal-400/20 border border-teal-400/40' : 'bg-white/5 border border-white/10'}`}>
                  <UploadCloud className={`w-7 h-7 sm:w-8 sm:h-8 transition-colors ${dragActive ? 'text-teal-400' : 'text-white/40 group-hover:text-white/60'}`} />
                </div>
                <p className="text-base sm:text-lg font-semibold text-white/90">
                  {dragActive ? 'Drop it here!' : 'Drop image or click to upload'}
                </p>
                <p className="text-xs text-white/35 mt-1.5 font-medium tracking-wide">JPEG · PNG · WebP · Max 15 MB</p>
              </motion.div>

              {/* Divider */}
              <div className="flex items-center w-full gap-3 text-white/20 text-xs font-bold uppercase tracking-widest">
                <div className="h-px bg-white/10 flex-1" />or<div className="h-px bg-white/10 flex-1" />
              </div>

              {/* URL input */}
              <div className="flex w-full gap-2 sm:gap-3">
                <div className="relative flex-1 min-w-0">
                  <ExternalLink className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25" />
                  <input
                    id="url-input" type="url" value={imageUrl}
                    onChange={(e) => setImageUrl(e.target.value)}
                    onKeyDown={handleUrlKeyDown}
                    placeholder="https://example.com/image.jpg"
                    aria-label="Image URL"
                    className="w-full pl-10 sm:pl-11 pr-3 bg-white/5 border border-white/10 rounded-2xl py-3.5 sm:py-4 text-sm text-white placeholder-white/25 focus:outline-none focus:border-teal-400/60 focus:ring-1 focus:ring-teal-400/30 transition-all"
                  />
                </div>
                <button
                  id="verify-url-btn" onClick={onUrlSubmit}
                  disabled={!imageUrl.trim()}
                  className="bg-teal-500 hover:bg-teal-400 disabled:opacity-30 disabled:cursor-not-allowed text-black font-bold px-5 sm:px-7 py-3.5 sm:py-4 rounded-2xl text-sm tracking-wide transition-all shadow-[0_0_20px_rgba(45,212,191,0.2)] hover:shadow-[0_0_30px_rgba(45,212,191,0.4)] shrink-0"
                >
                  Verify
                </button>
              </div>

              {/* Capability pills */}
              <div className="flex flex-wrap justify-center gap-1.5 sm:gap-2">
                {['C2PA', 'EXIF', 'ELA', 'Quantization', 'Origin Trace'].map((c) => (
                  <span key={c} className="text-[10px] sm:text-[11px] text-white/35 bg-white/5 border border-white/10 px-2.5 sm:px-3 py-1 rounded-full font-medium">{c}</span>
                ))}
              </div>
            </motion.div>
          )}

          {/* ══════════════ ANALYZING ══════════════ */}
          {appState === 'ANALYZING' && (
            <motion.div
              key="analyzing"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.05 }}
              transition={{ duration: 0.5 }}
              className="w-full max-w-md flex flex-col items-center gap-10"
            >
              {/* ── Premium Forensic Scanner ── */}
              <div className="relative w-72 h-72 sm:w-80 sm:h-80">

                {/* Rotating outer ring — slow spin */}
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
                  className="absolute -inset-4 rounded-[2rem] pointer-events-none"
                  style={{ border: '1px dashed rgba(45,212,191,0.12)' }}
                />
                {/* Counter-rotating ring */}
                <motion.div
                  animate={{ rotate: -360 }}
                  transition={{ duration: 14, repeat: Infinity, ease: 'linear' }}
                  className="absolute -inset-2 rounded-[1.6rem] pointer-events-none"
                  style={{ border: '1px solid rgba(168,85,247,0.08)' }}
                />

                {/* Pulsing outer glow */}
                <motion.div
                  animate={{ opacity: [0.2, 0.5, 0.2], scale: [1, 1.03, 1] }}
                  transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                  className="absolute inset-0 rounded-3xl shadow-[0_0_50px_rgba(45,212,191,0.2),0_0_100px_rgba(168,85,247,0.08)] border border-teal-400/20"
                />

                {/* Scanner box */}
                <div className="absolute inset-0 rounded-3xl overflow-hidden bg-[#040a0a] border border-teal-500/25">

                  {/* Thumbnail — fades in as scan progresses */}
                  {thumbnail && (
                    <motion.img
                      src={thumbnail} alt="Analyzing" draggable={false}
                      animate={{ opacity: 0.08 + scanProgress * 0.32 }}
                      transition={{ duration: 0.8 }}
                      className="absolute inset-0 w-full h-full object-cover grayscale"
                    />
                  )}

                  {/* Cyber grid overlay */}
                  <div className="absolute inset-0 bg-[linear-gradient(rgba(45,212,191,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(45,212,191,0.03)_1px,transparent_1px)] bg-[size:20px_20px]" />

                  {/* CRT scanlines */}
                  <div className="absolute inset-0 bg-[repeating-linear-gradient(0deg,transparent,transparent_2px,rgba(0,0,0,0.12)_2px,rgba(0,0,0,0.12)_4px)] pointer-events-none" />

                  {/* Crosshair lines */}
                  <div className="absolute top-1/2 left-[10%] right-[10%] h-[1px] bg-teal-400/10 z-10" />
                  <div className="absolute left-1/2 top-[10%] bottom-[10%] w-[1px] bg-teal-400/10 z-10" />
                  {/* Center dot */}
                  <motion.div
                    animate={{ scale: [1, 1.5, 1], opacity: [0.4, 0.8, 0.4] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-teal-400/60 z-10"
                  />

                  {/* Horizontal scan beam (teal) */}
                  <motion.div
                    animate={{ top: ['0%', '100%'] }}
                    transition={{ duration: 2.2, repeat: Infinity, repeatType: 'reverse', ease: 'easeInOut' }}
                    className="absolute left-0 right-0 h-0 z-10" style={{ pointerEvents: 'none' }}
                  >
                    <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-b from-transparent via-teal-400/5 to-teal-400/25" />
                    <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-teal-400 shadow-[0_0_15px_4px_rgba(45,212,191,0.7),0_0_40px_10px_rgba(45,212,191,0.3)]" />
                    <div className="absolute bottom-[2px] left-[8%] right-[8%] h-[1px] bg-white/30" />
                  </motion.div>

                  {/* Vertical scan beam (purple) */}
                  <motion.div
                    animate={{ left: ['0%', '100%'] }}
                    transition={{ duration: 2.8, repeat: Infinity, repeatType: 'reverse', ease: 'easeInOut', delay: 0.5 }}
                    className="absolute top-0 bottom-0 w-0 z-10" style={{ pointerEvents: 'none' }}
                  >
                    <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-purple-500/20 to-transparent" />
                    <div className="absolute right-0 top-0 bottom-0 w-[2px] bg-purple-400/80 shadow-[0_0_12px_3px_rgba(168,85,247,0.5),0_0_30px_6px_rgba(168,85,247,0.2)]" />
                  </motion.div>

                  {/* Expanding pulse rings */}
                  {[0, 0.8, 1.6].map((delay, i) => (
                    <motion.div key={i}
                      animate={{ scale: [0.2, 1.6], opacity: [0.5, 0] }}
                      transition={{ duration: 2.5, repeat: Infinity, delay, ease: 'easeOut' }}
                      className="absolute inset-0 m-auto w-12 h-12 rounded-full border border-teal-400/30"
                    />
                  ))}

                  {/* Floating hex data particles */}
                  {['A3', 'F7', '0x', 'C2', 'FF', '9B', 'D4', 'E1'].map((hex, i) => (
                    <motion.span
                      key={hex}
                      animate={{
                        y: [0, -120 - i * 15],
                        x: [0, (i % 2 === 0 ? 1 : -1) * (8 + i * 3)],
                        opacity: [0, 0.7, 0],
                      }}
                      transition={{ duration: 3 + i * 0.3, repeat: Infinity, delay: i * 0.4, ease: 'easeOut' }}
                      className="absolute font-mono text-[8px] text-teal-400/40 z-10 pointer-events-none"
                      style={{ left: `${15 + i * 10}%`, top: '75%' }}
                    >
                      {hex}
                    </motion.span>
                  ))}

                  {/* Data readout — left */}
                  <div className="absolute top-3 left-3 flex flex-col gap-1.5 font-mono text-[9px] text-teal-400/50 z-20">
                    {['SHA-256', 'C2PA', 'EXIF', 'ELA'].map((label, i) => (
                      <motion.div key={label}
                        animate={{ opacity: loadingIdx >= i ? [0.5, 1, 0.5] : 0.2 }}
                        transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.3 }}
                        className="flex items-center gap-1.5">
                        <motion.div
                          animate={{ backgroundColor: loadingIdx >= i ? 'rgba(45,212,191,1)' : 'rgba(45,212,191,0.3)' }}
                          className="w-1.5 h-1.5 rounded-full"
                        />
                        {label}
                        {loadingIdx === i && <motion.span animate={{ opacity: [1, 0] }} transition={{ duration: 0.5, repeat: Infinity }}>_</motion.span>}
                      </motion.div>
                    ))}
                  </div>

                  {/* Data readout — right */}
                  <div className="absolute top-3 right-3 flex flex-col items-end gap-1.5 font-mono text-[9px] text-purple-400/40 z-20">
                    {['QNT', 'SERPAPI', 'WAYBACK'].map((label, i) => (
                      <motion.div key={label}
                        animate={{ opacity: loadingIdx >= i + 4 ? [0.5, 1, 0.5] : 0.2 }}
                        transition={{ duration: 2, repeat: Infinity, delay: i * 0.4 }}
                        className="flex items-center gap-1.5">
                        {label}
                        <motion.div
                          animate={{ backgroundColor: loadingIdx >= i + 4 ? 'rgba(168,85,247,1)' : 'rgba(168,85,247,0.3)' }}
                          className="w-1.5 h-1.5 rounded-full"
                        />
                      </motion.div>
                    ))}
                  </div>

                  {/* Bottom status bar */}
                  <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between font-mono text-[9px] text-teal-400/50 z-20">
                    <div className="flex items-center gap-1.5">
                      <motion.div animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 0.6, repeat: Infinity }}
                        className="w-1.5 h-1.5 rounded-full bg-teal-400" />
                      <span>SCANNING</span>
                    </div>
                    <span className="text-white/20">{Math.round(scanProgress * 100)}%</span>
                  </div>

                  {/* Rotating corner brackets */}
                  {[
                    { pos: 'top-2 left-2', border: 'border-t-2 border-l-2', rotate: [0, 2, 0] },
                    { pos: 'top-2 right-2', border: 'border-t-2 border-r-2', rotate: [0, -2, 0] },
                    { pos: 'bottom-2 left-2', border: 'border-b-2 border-l-2', rotate: [0, -2, 0] },
                    { pos: 'bottom-2 right-2', border: 'border-b-2 border-r-2', rotate: [0, 2, 0] },
                  ].map(({ pos, border, rotate }, i) => (
                    <motion.div key={i}
                      animate={{ rotate }}
                      transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                      className={`absolute ${pos} w-5 h-5 ${border} border-teal-400 z-20`}
                    />
                  ))}
                </div>
              </div>

              {/* Loading text + progress */}
              <div className="text-center space-y-4 w-full">
                {/* Retry message */}
                {retrying && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    className="text-xs text-amber-400/80 bg-amber-500/10 border border-amber-500/20 px-4 py-2 rounded-xl">
                    Server waking up, retrying…
                  </motion.p>
                )}
                <div className="min-h-[36px] flex items-center justify-center">
                  <AnimatePresence mode="wait">
                    <motion.div key={loadingIdx} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.3 }}
                      className="flex items-center gap-2.5 text-base font-semibold text-teal-300 drop-shadow-[0_0_12px_rgba(45,212,191,0.6)]">
                      <FileSearch className="w-5 h-5 shrink-0" />
                      {LOADING_MESSAGES[loadingIdx]}
                    </motion.div>
                  </AnimatePresence>
                </div>
                {/* Segmented progress bar */}
                <div className="flex items-center justify-center gap-1 w-64 mx-auto">
                  {LOADING_MESSAGES.map((_, i) => (
                    <motion.div key={i}
                      animate={{ opacity: i <= loadingIdx ? 1 : 0.15 }}
                      className={`h-1 flex-1 rounded-full transition-all duration-500 ${
                        i < loadingIdx ? 'bg-teal-400' : i === loadingIdx ? 'bg-gradient-to-r from-teal-400 to-purple-400' : 'bg-white/10'
                      }`}
                    />
                  ))}
                </div>
                {/* Progress dots */}
                <div className="flex items-center justify-center gap-2">
                  {LOADING_MESSAGES.map((_, i) => (
                    <motion.div key={i}
                      animate={{ scale: i === loadingIdx ? 1.5 : 1, opacity: i === loadingIdx ? 1 : i < loadingIdx ? 0.6 : 0.15 }}
                      transition={{ duration: 0.3 }}
                      className={`w-1.5 h-1.5 rounded-full ${
                        i < loadingIdx ? 'bg-teal-400' : i === loadingIdx ? 'bg-teal-400' : 'bg-white/20'
                      }`}
                    />
                  ))}
                </div>
                <p className="text-xs text-white/20 font-mono tracking-wider">FORENSIC PIPELINE ACTIVE — STAGE {loadingIdx + 1}/{LOADING_MESSAGES.length}</p>
              </div>
            </motion.div>
          )}

          {/* ══════════════ RESULT ══════════════ */}
          {appState === 'RESULT' && result && (
            <motion.div
              key="result"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ type: 'spring', damping: 25, stiffness: 180 }}
              className="w-full max-w-5xl flex flex-col gap-4 sm:gap-6"
            >
              {/* ── Classification Header ── */}
              <div className={`flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4 p-4 sm:p-5 rounded-2xl border ${cfg.border} ${cfg.bg} ${cfg.glow}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-9 h-9 sm:w-10 sm:h-10 rounded-xl ${cfg.bg} border ${cfg.border} flex items-center justify-center shrink-0`}>
                    {cfg.icon}
                  </div>
                  <div>
                    <p className="text-[10px] text-white/40 uppercase tracking-widest font-bold mb-0.5">Verification Result</p>
                    <h2 className={`text-lg sm:text-xl font-extrabold ${cfg.color} leading-tight`}>{result.classification}</h2>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:gap-3 shrink-0">
                  <span className={`text-xs font-bold uppercase tracking-wider px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg border ${cfg.strengthColor}`}>
                    {result.evidence_strength} Evidence
                  </span>
                  {result.cached && (
                    <span className="text-xs text-teal-400 bg-teal-400/10 border border-teal-400/20 px-2 sm:px-2.5 py-1 sm:py-1.5 rounded-lg font-bold uppercase tracking-wide">
                      Cached
                    </span>
                  )}
                </div>
              </div>

              {/* ── Scanned image preview ── */}
              {thumbnail && (
                <div className="flex items-center gap-4 p-3 sm:p-4 rounded-2xl bg-white/[0.03] border border-white/8">
                  <div className="relative w-14 h-14 sm:w-16 sm:h-16 rounded-xl overflow-hidden shrink-0 border border-white/10">
                    <img src={thumbnail} alt="Scanned image" className="w-full h-full object-cover" />
                    <div className="absolute inset-0 bg-gradient-to-br from-transparent to-black/20" />
                  </div>
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <span className="text-[10px] text-white/35 uppercase tracking-widest font-bold">Scanned Image</span>
                    <span className="text-sm text-white/70 font-medium truncate">
                      {imageDetails?.name ?? (imageUrl ? (() => { try { return new URL(imageUrl).hostname; } catch { return 'URL Image'; } })() : 'Uploaded Image')}
                    </span>
                    <div className="flex items-center gap-3 mt-0.5">
                      {imageDetails?.dimensions && (
                        <span className="text-[11px] text-white/35">{imageDetails.dimensions}</span>
                      )}
                      {imageDetails?.size && imageDetails.size !== 'Unknown' && (
                        <span className="text-[11px] text-white/35">{imageDetails.size}</span>
                      )}
                      <span className="text-[11px] text-white/25">{imageDetails?.source ?? 'Remote'}</span>
                    </div>
                  </div>
                  <div className="ml-auto shrink-0">
                    <CheckCircle className="w-5 h-5 text-teal-400/60" />
                  </div>
                </div>
              )}

              {/* ── Two-column layout ── */}
              <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] xl:grid-cols-[340px_1fr] gap-4 sm:gap-6">

                {/* LEFT: Receipt image */}
                <div className="flex flex-col gap-4">
                  {/* Receipt card */}
                  <Dialog>
                    <DialogTrigger asChild>
                      <motion.div whileHover={{ scale: 1.02 }}
                        className="relative w-full aspect-[9/16] rounded-[2rem] overflow-hidden border-2 border-white/10 shadow-[0_20px_60px_-15px_rgba(45,212,191,0.2)] cursor-zoom-in group">
                        <img id="receipt-image" src={`/api/receipt/${result.id}`} alt="Verification Receipt" className="w-full h-full object-cover" />
                        <div className="absolute inset-0 bg-[#0A0A0A]/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                          <ZoomIn className="w-10 h-10 text-white drop-shadow-2xl" />
                        </div>
                        {/* Tap hint */}
                        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <span className="bg-black/70 text-white/80 text-xs px-3 py-1.5 rounded-full backdrop-blur-md border border-white/10 font-medium">
                            Click to expand
                          </span>
                        </div>
                      </motion.div>
                    </DialogTrigger>
                    <DialogContent className="max-w-7xl w-[95vw] h-[95vh] bg-[#0A0A0A]/95 backdrop-blur-xl border-white/10 flex flex-col p-2 sm:p-6 !pt-12">
                      <DialogHeader className="sr-only"><DialogTitle>Full Receipt View</DialogTitle><DialogDescription>Click the image to zoom in or out</DialogDescription></DialogHeader>
                      <ZoomableReceipt src={`/api/receipt/${result.id}`} />
                    </DialogContent>
                  </Dialog>

                  {/* Action buttons */}
                  <div className="flex gap-3">
                    {/* Share dropdown */}
                    <div className="relative flex-1" ref={shareRef}>
                      <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                        id="share-btn" onClick={() => setShareOpen(!shareOpen)}
                        className="w-full flex items-center justify-center gap-2 bg-teal-500/20 hover:bg-teal-500/30 text-teal-300 border border-teal-500/30 px-4 py-3.5 rounded-2xl text-sm font-bold transition-all shadow-[0_0_20px_rgba(45,212,191,0.1)] hover:shadow-[0_0_25px_rgba(45,212,191,0.25)]">
                        <Share2 className="w-4 h-4" /> Share
                        <ChevronDown className={`w-3 h-3 transition-transform ${shareOpen ? 'rotate-180' : ''}`} />
                      </motion.button>
                      <AnimatePresence>
                        {shareOpen && (
                          <motion.div
                            initial={{ opacity: 0, y: 8, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: 8, scale: 0.95 }}
                            transition={{ duration: 0.15 }}
                            className="absolute bottom-full left-0 right-0 mb-2 bg-[#111]/95 backdrop-blur-xl border border-white/10 rounded-2xl p-2 shadow-2xl z-50 flex flex-col gap-0.5"
                          >
                            <button onClick={handleCopyLink}
                              className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/8 transition-colors text-left w-full">
                              {copied ? <Check className="w-4 h-4 text-teal-400 shrink-0" /> : <Copy className="w-4 h-4 text-white/50 shrink-0" />}
                              <span className="text-sm text-white/80 font-medium">{copied ? 'Copied!' : 'Copy Link'}</span>
                            </button>
                            <button onClick={handleDownload}
                              className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/8 transition-colors text-left w-full">
                              <Download className="w-4 h-4 text-white/50 shrink-0" />
                              <span className="text-sm text-white/80 font-medium">Download PNG</span>
                            </button>
                            <div className="h-px bg-white/8 mx-2 my-1" />
                            <button onClick={() => handleShareSocial('x')}
                              className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/8 transition-colors text-left w-full">
                              <X className="w-4 h-4 text-white/50 shrink-0" />
                              <span className="text-sm text-white/80 font-medium">Share on X</span>
                            </button>
                            <button onClick={() => handleShareSocial('telegram')}
                              className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/8 transition-colors text-left w-full">
                              <Send className="w-4 h-4 text-white/50 shrink-0" />
                              <span className="text-sm text-white/80 font-medium">Share on Telegram</span>
                            </button>
                            <button onClick={() => handleShareSocial('whatsapp')}
                              className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/8 transition-colors text-left w-full">
                              <MessageCircle className="w-4 h-4 text-white/50 shrink-0" />
                              <span className="text-sm text-white/80 font-medium">Share on WhatsApp</span>
                            </button>
                            {typeof navigator !== 'undefined' && 'share' in navigator && (
                              <>
                                <div className="h-px bg-white/8 mx-2 my-1" />
                                <button onClick={handleNativeShare}
                                  className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/8 transition-colors text-left w-full">
                                  <Share2 className="w-4 h-4 text-teal-400 shrink-0" />
                                  <span className="text-sm text-teal-300 font-medium">More Options…</span>
                                </button>
                              </>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                    <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                      id="verify-another-btn" onClick={resetState}
                      className="flex-1 flex items-center justify-center gap-2 bg-white/10 hover:bg-white/15 text-white/80 border border-white/20 px-4 py-3.5 rounded-2xl text-sm font-bold transition-all">
                      <RefreshCcw className="w-4 h-4" /> New
                    </motion.button>
                  </div>
                </div>

                {/* RIGHT: Evidence + Details */}
                <div className="flex flex-col gap-5">

                  {/* Interpretation */}
                  {result.interpretation && (
                    <div className={`flex items-start gap-3 p-4 rounded-2xl border ${cfg.border} ${cfg.bg}`}>
                      <Info className={`w-4 h-4 shrink-0 mt-0.5 ${cfg.color}`} />
                      <p className="text-sm text-white/70 leading-relaxed">{result.interpretation}</p>
                    </div>
                  )}

                  {/* Evidence list */}
                  {result.evidence && result.evidence.length > 0 && (
                    <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5">
                      <h3 className="text-xs uppercase tracking-widest font-bold text-white/40 mb-4 flex items-center gap-2">
                        <FileSearch className="w-3.5 h-3.5" />
                        Evidence Findings
                        <span className="ml-auto text-white/25">{result.evidence.length} item{result.evidence.length !== 1 ? 's' : ''}</span>
                      </h3>
                      <ul className="flex flex-col gap-3">
                        {result.evidence.map((item, i) => (
                          <motion.li key={i}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.07 }}
                            className="flex items-start gap-3 text-sm text-white/70 leading-relaxed">
                            <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${cfg.color} opacity-80`} />
                            {item}
                          </motion.li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Scan details */}
                  <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5">
                    <h3 className="text-xs uppercase tracking-widest font-bold text-white/40 mb-4 flex items-center gap-2">
                      <Info className="w-3.5 h-3.5" />
                      Scan Details
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { label: 'Source', value: imageDetails?.source || 'Unknown', icon: <UploadCloud className="w-3.5 h-3.5" /> },
                        { label: 'File Name', value: imageDetails?.name || '—', icon: <FileSearch className="w-3.5 h-3.5" /> },
                        { label: 'File Size', value: imageDetails?.size || 'Unknown', icon: <Database className="w-3.5 h-3.5" /> },
                        { label: 'Dimensions', value: imageDetails?.dimensions || 'Unknown', icon: <Scan className="w-3.5 h-3.5" /> },
                        { label: 'Processing', value: `${result.processing_time_ms} ms`, icon: <Clock className="w-3.5 h-3.5" /> },
                        { label: 'Cache', value: result.cached ? 'Hit (instant)' : 'Miss (fresh run)', icon: <Database className="w-3.5 h-3.5" /> },
                      ].map(({ label, value, icon }) => (
                        <div key={label} className="flex flex-col gap-1 bg-white/5 rounded-xl p-3 border border-white/5">
                          <span className="text-[10px] text-white/35 uppercase tracking-wider font-bold flex items-center gap-1.5">{icon}{label}</span>
                          <span className="text-xs text-white/80 font-medium truncate" title={value}>{value}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Raw data */}
                  <Dialog>
                    <DialogTrigger asChild>
                      <button className="flex items-center justify-center gap-2 bg-white/5 hover:bg-white/8 text-white/50 hover:text-white/70 border border-white/10 hover:border-white/20 px-4 py-3 rounded-2xl text-xs font-bold transition-all">
                        <Code className="w-3.5 h-3.5" /> View Raw JSON
                      </button>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto bg-[#0a0a0a] border-white/10 text-white">
                      <DialogHeader>
                        <DialogTitle className="text-teal-400">Raw Verification Data</DialogTitle>
                        <DialogDescription>Complete JSON response from the API.</DialogDescription>
                      </DialogHeader>
                      <pre className="p-4 rounded-xl bg-white/5 border border-white/10 overflow-x-auto text-xs text-white/80 font-mono mt-4">
                        {JSON.stringify(result, null, 2)}
                      </pre>
                    </DialogContent>
                  </Dialog>
                </div>
              </div>
            </motion.div>
          )}

          {/* ══════════════ ERROR ══════════════ */}
          {appState === 'ERROR' && (() => {
            const err = friendlyError(errorMsg || 'An unexpected error occurred.');
            return (
              <motion.div key="error" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                className="w-full max-w-md flex flex-col items-center gap-5 bg-red-950/20 border border-red-500/20 backdrop-blur-md rounded-3xl p-8 shadow-[0_0_40px_rgba(239,68,68,0.1)]">
                <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center border border-red-500/40 shadow-[0_0_20px_rgba(239,68,68,0.3)]">
                  <AlertCircle className="w-8 h-8 text-red-400" />
                </div>
                <div className="text-center space-y-2">
                  <h3 className="text-lg font-bold text-white">{err.title}</h3>
                  <p className="text-sm text-red-200/80 leading-relaxed">{err.message}</p>
                  {err.hint && (
                    <p className="text-xs text-white/40 mt-2 bg-white/5 rounded-xl px-4 py-2.5 border border-white/5">💡 {err.hint}</p>
                  )}
                </div>
                {errorMsg && errorMsg !== err.message && (
                  <details className="w-full text-left">
                    <summary className="text-[10px] text-white/30 cursor-pointer hover:text-white/50 flex items-center gap-1 justify-center uppercase tracking-widest font-bold">
                      <ChevronDown className="w-3 h-3" /> Technical Details
                    </summary>
                    <pre className="mt-2 text-[10px] text-white/25 bg-white/5 rounded-xl p-3 overflow-x-auto border border-white/5 break-all whitespace-pre-wrap">{errorMsg}</pre>
                  </details>
                )}
                <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                  id="retry-btn" onClick={resetState}
                  className="w-full bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 px-6 py-4 rounded-2xl text-sm font-bold transition-all mt-1">
                  Try Again
                </motion.button>
              </motion.div>
            );
          })()}
        </AnimatePresence>
      </div>
    </main>
  );
}
