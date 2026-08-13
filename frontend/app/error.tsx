'use client';

import { useEffect } from 'react';
import { AlertCircle, RefreshCcw } from 'lucide-react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Unhandled error:', error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A] text-white px-4">
      <div className="flex flex-col items-center gap-6 bg-red-950/20 border border-red-500/20 backdrop-blur-md rounded-3xl p-10 max-w-sm shadow-[0_0_40px_rgba(239,68,68,0.1)] text-center">
        <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center border border-red-500/40 shadow-[0_0_20px_rgba(239,68,68,0.3)]">
          <AlertCircle className="w-8 h-8 text-red-400" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-bold">Something went wrong</h2>
          <p className="text-sm text-red-200/70">
            An unexpected error occurred. Please try again.
          </p>
        </div>
        <button
          onClick={reset}
          className="flex items-center gap-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 px-6 py-3 rounded-2xl text-sm font-bold transition-all"
        >
          <RefreshCcw className="w-4 h-4" /> Try Again
        </button>
      </div>
    </div>
  );
}
