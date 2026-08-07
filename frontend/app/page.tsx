import Link from 'next/link';
import { ShieldCheck, FileSearch, Fingerprint } from 'lucide-react';

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-between px-4 py-16 relative overflow-hidden bg-[#0A0A0A] text-white">
      {/* Ambient Cyber Glows */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-[-20%] left-[10%] w-[600px] h-[600px] rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[5%] w-[500px] h-[500px] rounded-full bg-purple-600/10 blur-[100px]" />
      </div>

      <div className="w-full max-w-4xl mx-auto flex flex-col items-center z-10 space-y-24">
        {/* Hero Section */}
        <div className="text-center space-y-8 mt-12">
          <h1 className="text-6xl sm:text-7xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-teal-400 to-purple-500 leading-tight">
            Don't share it.<br/>Prove it.
          </h1>
          <p className="text-xl text-white/70 max-w-2xl mx-auto font-medium">
            Verify provenance, detect AI, and trace origins instantly. 
            Protect your content with cryptographically secure metadata and automated verification pipelines.
          </p>
          <div className="pt-4">
            <Link 
              href="/verify" 
              className="inline-block bg-teal-500/20 hover:bg-teal-500/30 text-teal-300 border border-teal-500/30 px-10 py-5 rounded-2xl text-lg font-bold tracking-wide transition-all shadow-[0_0_15px_rgba(45,212,191,0.1)] hover:shadow-[0_0_30px_rgba(45,212,191,0.3)] hover:scale-105"
            >
              Launch Tool
            </Link>
          </div>
        </div>

        {/* Pipeline Explanation Section */}
        <div className="w-full grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Card 1 */}
          <div className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-sm shadow-xl flex flex-col items-center text-center space-y-4 hover:border-teal-400/30 transition-colors">
            <div className="w-16 h-16 rounded-2xl bg-teal-500/10 flex items-center justify-center border border-teal-500/20 mb-2">
              <ShieldCheck className="w-8 h-8 text-teal-400" />
            </div>
            <h3 className="text-xl font-bold text-white">C2PA Verification</h3>
            <p className="text-sm text-white/60 leading-relaxed">
              Cryptographic signatures confirm the exact software and hardware used to create an image, establishing tamper-proof authenticity.
            </p>
          </div>

          {/* Card 2 */}
          <div className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-sm shadow-xl flex flex-col items-center text-center space-y-4 hover:border-purple-500/30 transition-colors">
            <div className="w-16 h-16 rounded-2xl bg-purple-500/10 flex items-center justify-center border border-purple-500/20 mb-2">
              <FileSearch className="w-8 h-8 text-purple-400" />
            </div>
            <h3 className="text-xl font-bold text-white">EXIF Deep Scan</h3>
            <p className="text-sm text-white/60 leading-relaxed">
              We extract hidden structural metadata and detect anomalies that indicate manipulation, even when signatures are stripped.
            </p>
          </div>

          {/* Card 3 */}
          <div className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-sm shadow-xl flex flex-col items-center text-center space-y-4 hover:border-teal-400/30 transition-colors">
            <div className="w-16 h-16 rounded-2xl bg-teal-500/10 flex items-center justify-center border border-teal-500/20 mb-2">
              <Fingerprint className="w-8 h-8 text-teal-400" />
            </div>
            <h3 className="text-xl font-bold text-white">Origin Trace</h3>
            <p className="text-sm text-white/60 leading-relaxed">
              Cross-referencing global databases to trace the image back to its original source on the open web, preventing malicious reuse.
            </p>
          </div>
        </div>
      </div>

      <footer className="mt-24 z-10 text-white/40 text-sm tracking-wider">
        <p>Created by <span className="text-white/60 font-semibold">Beneyas Tadu</span></p>
      </footer>
    </main>
  );
}
