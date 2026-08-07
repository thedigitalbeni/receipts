'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, CheckCircle, AlertCircle, Share2, RefreshCcw, Scan, FileSearch, Code, ZoomIn, ZoomOut, Info, Clock, Database } from 'lucide-react';
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
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const LOADING_MESSAGES = [
  'Extracting metadata...',
  'Checking C2PA signatures...',
  'Querying origin trace...',
  'Applying rules engine...',
];

const STRENGTH_COLORS: Record<string, string> = {
  Strong: 'text-teal-400 border-teal-400/40 bg-teal-400/10 shadow-[0_0_15px_rgba(45,212,191,0.2)]',
  Moderate: 'text-amber-400 border-amber-400/40 bg-amber-400/10 shadow-[0_0_15px_rgba(251,191,36,0.2)]',
  Limited: 'text-zinc-400 border-zinc-400/40 bg-zinc-400/10',
};


function ZoomableReceipt({ src }: { src: string }) {
  const [zoomed, setZoomed] = useState(false);
  return (
    <div 
      className={`relative w-full h-full rounded-xl bg-black/50 border border-white/5 ${zoomed ? 'overflow-auto flex items-start justify-center' : 'flex items-center justify-center overflow-hidden'}`}
      onClick={() => setZoomed(!zoomed)}
    >
      <div className="absolute top-4 right-4 z-50 pointer-events-none bg-black/50 text-white/70 px-3 py-1.5 rounded-full text-xs font-bold backdrop-blur-md flex items-center gap-2 border border-white/10">
        {zoomed ? <ZoomOut className="w-4 h-4"/> : <ZoomIn className="w-4 h-4"/>}
        {zoomed ? 'Click to zoom out' : 'Click to zoom in'}
      </div>
      <img
        src={src}
        alt="Full Receipt"
        className={`transition-all duration-300 ${zoomed ? 'w-full h-auto max-w-none cursor-zoom-out' : 'max-w-full max-h-full object-contain cursor-zoom-in'}`}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------


interface ImageDetails {
  name: string;
  size: string;
  dimensions: string;
  source: string;
}

export default function ReceiptsPage() {
  const [imageDetails, setImageDetails] = useState<ImageDetails | null>(null);

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
    }, 2000);
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

    const uriList = e.dataTransfer.getData('text/uri-list');
    const plainText = e.dataTransfer.getData('text/plain');
    const url = uriList || plainText;
    
    if (url && url.startsWith('http')) {
      setImageUrl(url);
      setThumbnail(url);
      setAppState('ANALYZING');
      setLoadingIdx(0);
      await sendToApi(null, url);
      return;
    }

    if (e.dataTransfer.files?.[0]) {
      await processFile(e.dataTransfer.files[0]);
    }
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
    const objectUrl = URL.createObjectURL(file);
    setThumbnail(objectUrl);
    
    const img = new window.Image();
    img.onload = () => {
      setImageDetails({
        name: file.name,
        size: (file.size / 1024 / 1024).toFixed(2) + ' MB',
        dimensions: `${img.width} × ${img.height} px`,
        source: 'Local Upload',
      });
    };
    img.src = objectUrl;

    setAppState('ANALYZING');
    setLoadingIdx(0);
    await sendToApi(file);
  };

  // ---- URL submission ----
  const onUrlSubmit = async () => {
    if (!imageUrl.trim()) return;
    setThumbnail(imageUrl);
    
    const img = new window.Image();
    img.onload = () => {
      let name = 'Image from URL';
      try { name = new URL(imageUrl).pathname.split('/').pop() || name; } catch {}
      setImageDetails({
        name,
        size: 'Unknown',
        dimensions: `${img.width} × ${img.height} px`,
        source: 'URL Input',
      });
    };
    img.src = imageUrl;

    setAppState('ANALYZING');
    setLoadingIdx(0);
    await sendToApi(null, imageUrl);
  };

  // ---- API call ----
  const sendToApi = async (file: File | null, url?: string) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    try {
      const formData = new FormData();
      if (file) {
        formData.append('input_type', 'file');
        formData.append('file', file);
      } else if (url) {
        formData.append('input_type', 'url');
        formData.append('image_url', url);
      }

      const res = await fetch(`${API_URL}/verify`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(errBody?.detail || `Server error (${res.status})`);
      }

      const data: VerifyResult = await res.json();
      
      // Override interpretation for Rule 5 missing provenance
      if (data.classification === 'Unverified — No Provenance Found') {
        data.interpretation = 'No cryptographic signatures or structural metadata were found. Social media platforms (like Twitter/Instagram) typically strip this metadata to protect user privacy and save space. We can confirm there is no data, rather than a failure to find it.';
      }
      
      setResult(data);
      setAppState('RESULT');
    } catch (err: unknown) {
      clearTimeout(timeoutId);
      let msg = 'Network error';
      if (err instanceof Error) {
        if (err.name === 'AbortError') {
          msg = 'Verification timed out. The server might be warming up, please try again.';
        } else {
          msg = err.message;
        }
      }
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
    setImageDetails(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ---- share / download ----
  const handleShare = async () => {
    if (!result) return;
    const receiptUrl = `/api/receipt/${result.id}`;

    try {
      const imgRes = await fetch(receiptUrl);
      const blob = await imgRes.blob();
      const file = new File([blob], `receipt-${result.id}.png`, { type: 'image/png' });

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

    const a = document.createElement('a');
    a.href = receiptUrl;
    a.download = `receipt-${result.id}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const handleUrlKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') onUrlSubmit();
  };

  // ====================================================================
  // RENDER
  // ====================================================================
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 py-12 relative overflow-hidden bg-[#0A0A0A] text-white">
      {/* Ambient Cyber Glows */}
      <div className="pointer-events-none fixed inset-0">
        <motion.div 
          animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-[-20%] left-[10%] w-[600px] h-[600px] rounded-full bg-teal-500/10 blur-[120px]" 
        />
        <motion.div 
          animate={{ scale: [1, 1.2, 1], opacity: [0.2, 0.4, 0.2] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          className="absolute bottom-[-10%] right-[5%] w-[500px] h-[500px] rounded-full bg-purple-600/10 blur-[100px]" 
        />
      </div>

      {/* Header */}
      <div className="fixed top-0 left-0 right-0 z-50 flex items-center justify-center py-6 backdrop-blur-md bg-[#0A0A0A]/50 border-b border-white/5">
        <h1 className="tracking-[0.4em] text-xs font-bold uppercase text-white/60">
          Receipts
        </h1>
      </div>

      {/* Content Container */}
      <div className="w-full max-w-md mx-auto flex flex-col items-center z-10 mt-12">
        <AnimatePresence mode="wait">
          
          {/* ==================== DROPZONE ==================== */}
          {appState === 'DROPZONE' && (
            <motion.div 
              key="dropzone"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.4 }}
              className="w-full flex flex-col items-center gap-8"
            >
              <div className="text-center space-y-4 mb-4">
                <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-teal-400 to-purple-500 leading-tight">
                  Don&apos;t share it.<br/>Prove it.
                </h2>
                <p className="text-sm text-white/50 max-w-sm mx-auto font-medium">
                  Verify provenance, detect AI, and trace origins instantly.
                </p>
              </div>

              <motion.div
                id="dropzone"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`group relative w-full rounded-3xl flex flex-col items-center justify-center cursor-pointer py-16 px-6 overflow-hidden backdrop-blur-xl transition-all duration-300 ${
                  dragActive 
                    ? 'border-2 border-teal-400 bg-teal-400/10 shadow-[0_0_30px_rgba(45,212,191,0.2)]' 
                    : 'border border-white/10 bg-white/5 hover:border-transparent hover:bg-white/10 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.1)] hover:shadow-[0_0_20px_rgba(45,212,191,0.3),inset_0_0_0_2px_rgba(45,212,191,0.5)]'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                {/* Magic glow border */}
                <div className="absolute inset-[-2px] rounded-3xl bg-gradient-to-r from-teal-400 to-purple-500 opacity-0 transition-opacity duration-500 group-hover:opacity-100 pointer-events-none -z-10" />
                <div className="absolute inset-[1px] rounded-[23px] bg-[#0A0A0A] pointer-events-none -z-10 group-hover:opacity-100 opacity-0 transition-opacity duration-500" />
                
                {/* Subtle pulsing background for the empty state */}
                <motion.div 
                  animate={{ opacity: [0.1, 0.3, 0.1] }}
                  transition={{ duration: 3, repeat: Infinity }}
                  className="absolute inset-0 bg-gradient-to-b from-teal-500/5 to-transparent pointer-events-none"
                />
                
                <input
                  ref={fileInputRef}
                  id="file-input"
                  type="file"
                  className="hidden"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleFileChange}
                />
                
                <UploadCloud className={`w-12 h-12 mb-5 transition-colors ${dragActive ? 'text-teal-400' : 'text-white/40'}`} />
                <p className="text-lg font-semibold text-white/90">
                  {dragActive ? 'Drop it here!' : 'Drop image or click'}
                </p>
                <p className="text-xs text-white/40 mt-2 font-medium tracking-wide">
                  JPG, PNG, WebP • Max 15MB
                </p>
              </motion.div>

              <div className="flex items-center w-full gap-4 text-white/20 text-xs font-bold uppercase tracking-widest">
                <div className="h-px bg-white/10 flex-1" />
                or
                <div className="h-px bg-white/10 flex-1" />
              </div>

              <div className="flex w-full gap-2 relative">
                <input
                  id="url-input"
                  type="url"
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  onKeyDown={handleUrlKeyDown}
                  placeholder="Paste image URL"
                  className="flex-1 bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm text-white placeholder-white/30 focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-400 focus:bg-white/10 transition-all shadow-inner"
                />
                <button
                  id="verify-url-btn"
                  onClick={onUrlSubmit}
                  disabled={!imageUrl.trim()}
                  className="bg-teal-500/20 hover:bg-teal-500/30 disabled:opacity-30 disabled:cursor-not-allowed text-teal-300 border border-teal-500/30 px-6 py-4 rounded-2xl text-sm font-bold tracking-wide transition-all shadow-[0_0_15px_rgba(45,212,191,0.1)] hover:shadow-[0_0_25px_rgba(45,212,191,0.25)]"
                >
                  Verify
                </button>
              </div>
            </motion.div>
          )}

          {/* ==================== ANALYZING ==================== */}
          {appState === 'ANALYZING' && (
            <motion.div 
              key="analyzing"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.05 }}
              transition={{ duration: 0.5 }}
              className="w-full flex flex-col items-center gap-10"
            >
              <div className="relative w-56 h-56 rounded-3xl overflow-hidden bg-white/5 border border-white/10 shadow-[0_0_40px_rgba(45,212,191,0.15)]">
                {thumbnail && (
                  <img
                    src={thumbnail}
                    alt="Analyzing"
                    className="w-full h-full object-cover opacity-30 grayscale blur-[2px]"
                  />
                )}
                
                {/* Cyber grid overlay */}
                <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:20px_20px]" />
                
                <motion.div 
                  animate={{ 
                    y: [0, 224, 224, 0, 0],
                    scaleY: [1, 1, -1, -1, 1]
                  }}
                  transition={{ 
                    duration: 3, 
                    repeat: Infinity, 
                    ease: "linear",
                    times: [0, 0.499, 0.5, 0.999, 1]
                  }}
                  className="absolute left-0 right-0 h-32 -top-32 bg-gradient-to-b from-transparent to-teal-400/40 z-10 border-b-[3px] border-teal-400 shadow-[0_20px_30px_rgba(45,212,191,0.4)] origin-bottom" 
                />
                
                {/* UI Corner Accents */}
                <div className="absolute top-3 left-3 w-4 h-4 border-t-2 border-l-2 border-teal-400" />
                <div className="absolute top-3 right-3 w-4 h-4 border-t-2 border-r-2 border-teal-400" />
                <div className="absolute bottom-3 left-3 w-4 h-4 border-b-2 border-l-2 border-teal-400" />
                <div className="absolute bottom-3 right-3 w-4 h-4 border-b-2 border-r-2 border-teal-400" />
                
                {/* Center radar icon */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <Scan className="w-12 h-12 text-teal-400/50 animate-pulse" />
                </div>
              </div>

              <div className="text-center space-y-6 w-full">
                <div className="min-h-[40px] flex items-center justify-center">
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={loadingIdx}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.3 }}
                      className="h-8 flex items-center justify-center gap-3 text-lg font-semibold text-teal-300 drop-shadow-[0_0_8px_rgba(45,212,191,0.5)]"
                    >
                      <FileSearch className="w-5 h-5 flex-shrink-0" />
                      {LOADING_MESSAGES[loadingIdx]}
                    </motion.div>
                  </AnimatePresence>
                </div>
                
                <div className="w-64 h-1.5 bg-white/10 rounded-full overflow-hidden mx-auto relative">
                  <motion.div 
                    className="absolute top-0 bottom-0 left-0 bg-gradient-to-r from-teal-400 via-purple-500 to-teal-400 rounded-full"
                    animate={{ width: '100%', x: ['-100%', '100%'] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                  />
                </div>
              </div>
            </motion.div>
          )}

          {/* ==================== RESULT ==================== */}
          {appState === 'RESULT' && result && (
            <motion.div 
              key="result"
              initial={{ opacity: 0, y: 40, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="w-full flex flex-col items-center gap-6"
            >
              <div className="text-center space-y-3 bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-5 w-full max-w-xs shadow-xl relative overflow-hidden">
                {/* Result header glow */}
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-1 bg-teal-400 shadow-[0_0_20px_rgba(45,212,191,1)]" />
                
                <p className="text-[10px] uppercase tracking-[0.2em] text-white/50 font-bold flex items-center justify-center gap-2">
                  <CheckCircle className="w-3 h-3 text-teal-400" /> Analysis Complete
                </p>
                <h3 className="text-xl font-bold text-white leading-tight">
                  {result.classification}
                </h3>
                <div className="flex justify-center pt-1">
                  <span className={`inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider px-3 py-1.5 rounded-lg border ${STRENGTH_COLORS[result.evidence_strength] || STRENGTH_COLORS.Limited}`}>
                    {result.evidence_strength} Evidence
                  </span>
                </div>
              </div>

              <Dialog>
                <DialogTrigger asChild>
                  <motion.div 
                    whileHover={{ scale: 1.02 }}
                    className="relative w-full max-w-xs aspect-[9/16] rounded-[2rem] overflow-hidden border-2 border-white/10 shadow-[0_20px_60px_-15px_rgba(45,212,191,0.2)] cursor-zoom-in group"
                  >
                    <img
                      id="receipt-image"
                      src={`/api/receipt/${result.id}`}
                      alt="Verification Receipt"
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-[#0A0A0A]/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                      <ZoomIn className="w-10 h-10 text-white drop-shadow-2xl" />
                    </div>
                  </motion.div>
                </DialogTrigger>
                <DialogContent className="max-w-7xl w-[95vw] h-[95vh] bg-[#0A0A0A]/95 backdrop-blur-xl border-white/10 flex flex-col p-2 sm:p-6 !pt-12">
                  <DialogHeader className="hidden"><DialogTitle>Receipt</DialogTitle><DialogDescription>Receipt Modal</DialogDescription></DialogHeader>
                  <ZoomableReceipt src={`/api/receipt/${result.id}`} />
                </DialogContent>
              </Dialog>

              <div className="flex gap-3 w-full max-w-xs mt-2">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  id="share-btn"
                  onClick={handleShare}
                  className="flex-1 flex items-center justify-center gap-2 bg-teal-500/20 hover:bg-teal-500/30 text-teal-300 border border-teal-500/30 px-4 py-4 rounded-2xl text-sm font-bold transition-all shadow-[0_0_20px_rgba(45,212,191,0.15)]"
                >
                  <Share2 className="w-4 h-4" /> Share
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  id="verify-another-btn"
                  onClick={resetState}
                  className="flex-1 flex items-center justify-center gap-2 bg-white/10 hover:bg-white/15 text-white/90 border border-white/20 px-4 py-4 rounded-2xl text-sm font-bold transition-all"
                >
                  <RefreshCcw className="w-4 h-4" /> Again
                </motion.button>
              </div>

              <div className="w-full max-w-xs mt-2">
                <Dialog>
                  <DialogTrigger asChild>
                    <button className="w-full flex items-center justify-center gap-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/30 px-4 py-3 rounded-2xl text-sm font-bold transition-all">
                      <Code className="w-4 h-4" /> View Raw Data
                    </button>
                  </DialogTrigger>
                  <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto bg-[#0a0a0a] border-white/10 text-white">
                    <DialogHeader>
                      <DialogTitle className="text-teal-400">Raw Verification Data</DialogTitle>
                      <DialogDescription>
                        Complete JSON response from the API.
                      </DialogDescription>
                    </DialogHeader>
                    <pre className="p-4 rounded-xl bg-white/5 border border-white/10 overflow-x-auto text-xs text-white/80 font-mono mt-4">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  </DialogContent>
                </Dialog>
              </div>
              <div className="w-full max-w-md mt-6 bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-5 shadow-xl text-sm">
                <div className="flex items-center gap-2 text-teal-400 font-bold mb-4 uppercase tracking-wider text-xs">
                  <Info className="w-4 h-4" /> Scan Details
                </div>
                
                <div className="space-y-3">
                  <div className="flex justify-between items-center border-b border-white/5 pb-2">
                    <span className="text-white/50 flex items-center gap-1.5"><FileSearch className="w-3.5 h-3.5"/> File Size</span>
                    <span className="text-white/90 font-medium">{imageDetails?.size || 'Unknown'}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-white/5 pb-2">
                    <span className="text-white/50 flex items-center gap-1.5"><Scan className="w-3.5 h-3.5"/> Dimensions</span>
                    <span className="text-white/90 font-medium">{imageDetails?.dimensions || 'Unknown'}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-white/5 pb-2">
                    <span className="text-white/50 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5"/> Processing Time</span>
                    <span className="text-white/90 font-medium">{result.processing_time_ms} ms</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-white/50 flex items-center gap-1.5"><Database className="w-3.5 h-3.5"/> Cache Status</span>
                    {result.cached ? (
                      <span className="text-teal-400 bg-teal-400/10 px-2 py-0.5 rounded-md font-bold text-xs uppercase border border-teal-400/20">Hit</span>
                    ) : (
                      <span className="text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-md font-bold text-xs uppercase border border-purple-500/20">Miss (Native Run)</span>
                    )}
                  </div>
                </div>
              </div>

            </motion.div>
          )}

          {/* ==================== ERROR ==================== */}
          {appState === 'ERROR' && (
            <motion.div 
              key="error"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="w-full flex flex-col items-center gap-6 bg-red-950/20 border border-red-500/20 backdrop-blur-md rounded-3xl p-8 max-w-xs shadow-[0_0_40px_rgba(239,68,68,0.1)]"
            >
              <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center border border-red-500/40 shadow-[0_0_20px_rgba(239,68,68,0.3)]">
                <AlertCircle className="w-8 h-8 text-red-400" />
              </div>
              <div className="text-center space-y-2">
                <h3 className="text-lg font-bold text-white">
                  Verification Failed
                </h3>
                <p className="text-sm text-red-200/70">
                  {errorMsg || 'An unexpected error occurred.'}
                </p>
              </div>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                id="retry-btn"
                onClick={resetState}
                className="w-full bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 px-6 py-4 rounded-2xl text-sm font-bold transition-all mt-2"
              >
                Try Again
              </motion.button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
