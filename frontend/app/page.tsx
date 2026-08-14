'use client';

import Link from 'next/link';
import { useState, useEffect, useRef } from 'react';
import { motion, useInView, useMotionValue, useSpring, AnimatePresence } from 'framer-motion';
import {
  ShieldCheck,
  FileSearch,
  Fingerprint,
  Brain,
  Layers,
  ArrowRight,
  CheckCircle2,
  XCircle,
  ChevronDown,
  Upload,
  ScanSearch,
  BadgeCheck,
  FileText,
  AlertTriangle,
  Eye,
  Globe,
  Newspaper,
  Users,
  HelpCircle,
  Cpu,
  Zap,
} from 'lucide-react';

// ─── FAQ DATA ────────────────────────────────────────────────────────────────
const FAQ_ITEMS = [
  {
    q: 'What image formats are supported?',
    a: 'JPEG, PNG, and WebP are fully supported. JPEG images yield the richest analysis because they carry quantization tables and compression artifacts that our forensics engine reads. PNG is lossless and skips ELA analysis. All formats support EXIF extraction and C2PA manifest detection.',
  },
  {
    q: 'Does Receipts store my images permanently?',
    a: 'Images are uploaded to a private Supabase Storage bucket solely to run the analysis pipeline. The image is referenced by its SHA-256 hash for caching (so repeat submissions are instant), but images are not shared publicly or used for training. The verification receipt is stored so the result can be retrieved by ID.',
  },
  {
    q: 'What does "Unverified — No Provenance Found" actually mean?',
    a: 'It means the tool found no positive signals — no C2PA credentials, no editing software traces, no prior online appearances, and no compression anomalies. It does NOT mean the image is authentic. Absence of evidence is not evidence of absence. Use this result as a prompt for further manual investigation.',
  },
  {
    q: 'Why does a photo from a news site show "Post-Processed Image"?',
    a: 'Professional photographers routinely process images in Lightroom or Photoshop before submission — this is normal editorial workflow and does not mean the content is fabricated. A "Post-Processed" verdict is Moderate evidence, not a verdict of deception. Read the interpretation text carefully.',
  },
  {
    q: 'Can Receipts detect deepfakes or AI-generated images?',
    a: 'Receipts detects the AI-Generated classification only when the image carries a C2PA manifest that explicitly declares AI generation — a standard being adopted by tools like Adobe Firefly, OpenAI DALL-E, and Midjourney. It cannot currently detect AI-generated images that were created without embedding C2PA credentials. This is a known and documented limitation.',
  },
  {
    q: 'How accurate is the Error Level Analysis (ELA)?',
    a: 'ELA is a useful forensic signal, not a verdict. It works by re-compressing the JPEG and measuring which regions compress differently, which can reveal edits. However, images that have been resaved many times may show high ELA error uniformly (false positive), and very high-quality originals may show minimal ELA error (false negative). Always read ELA results alongside the other evidence items.',
  },
];

// ─── VERDICT DATA ─────────────────────────────────────────────────────────────
const VERDICTS = [
  {
    label: 'AI-Generated Content',
    strength: 'Strong',
    color: 'from-purple-500/20 to-purple-600/5 border-purple-500/30',
    dot: 'bg-purple-400',
    glowColor: 'rgba(168,85,247,0.15)',
    text: 'text-purple-300',
    desc: 'A C2PA manifest is embedded that explicitly declares AI generation. The image carries a cryptographic attestation from the software that created it.',
    when: 'Adobe Firefly, DALL-E, Midjourney with credentials enabled.',
  },
  {
    label: 'Verified Camera Original',
    strength: 'Strong',
    color: 'from-teal-500/20 to-teal-600/5 border-teal-500/30',
    dot: 'bg-teal-400',
    glowColor: 'rgba(45,212,191,0.15)',
    text: 'text-teal-300',
    desc: 'A tamper-evident C2PA signature from a physical camera was verified. The image has not been undisclosed-edited since capture.',
    when: 'Sony, Nikon, Leica cameras with Content Credentials hardware.',
  },
  {
    label: 'Recirculated / Out of Context',
    strength: 'Moderate–Strong',
    color: 'from-amber-500/20 to-amber-600/5 border-amber-500/30',
    dot: 'bg-amber-400',
    glowColor: 'rgba(251,191,36,0.12)',
    text: 'text-amber-300',
    desc: 'The same image was found circulating online before the current claim. The image may be real, but the context it is being used in is likely misleading.',
    when: 'Old news photos reused in new stories, stock images misrepresented.',
  },
  {
    label: 'Post-Processed Image',
    strength: 'Moderate',
    color: 'from-orange-500/20 to-orange-600/5 border-orange-500/30',
    dot: 'bg-orange-400',
    glowColor: 'rgba(251,146,60,0.12)',
    text: 'text-orange-300',
    desc: 'Editing software was detected via EXIF metadata, JPEG quantization table fingerprinting, or Error Level Analysis. Most published photos are edited — treat this as a flag for closer scrutiny.',
    when: 'Photos edited in Photoshop, Lightroom, GIMP, or re-uploaded via Instagram.',
  },
  {
    label: 'Unverified — No Provenance Found',
    strength: 'Limited',
    color: 'from-zinc-500/20 to-zinc-600/5 border-zinc-500/30',
    dot: 'bg-zinc-400',
    glowColor: 'rgba(113,113,122,0.08)',
    text: 'text-zinc-300',
    desc: 'No positive signals were found. This is not a certificate of authenticity — it means the available evidence is limited, not that the image is confirmed true.',
    when: 'New images, metadata-stripped images, or images not indexed online.',
  },
];

// ─── USE CASES ────────────────────────────────────────────────────────────────
const USE_CASES = [
  {
    icon: Newspaper,
    title: 'Journalists & Editors',
    color: 'text-teal-400',
    bg: 'bg-teal-500/10 border-teal-500/20',
    items: [
      'Verify images before publication',
      'Detect out-of-context photo reuse',
      'Establish provenance chains for archival',
      'Flag potential AI-generated sources',
    ],
  },
  {
    icon: Eye,
    title: 'Fact-Checkers',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10 border-purple-500/20',
    items: [
      'Trace viral images to their earliest known origin',
      'Surface editing software evidence without tools',
      'Generate verifiable receipts as evidence',
      'Cross-reference images against web archives',
    ],
  },
  {
    icon: Users,
    title: 'Everyone Else',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10 border-amber-500/20',
    items: [
      'Double-check suspicious social media images',
      'Verify images before sharing them',
      'Understand what metadata your own photos expose',
      'Detect AI-generated images in your feed',
    ],
  },
];

// ─── WHAT WE CHECK ────────────────────────────────────────────────────────────
const CHECKS = [
  {
    icon: ShieldCheck,
    title: 'C2PA Manifest',
    color: 'text-teal-400',
    bg: 'bg-teal-500/10 border-teal-500/20',
    what: 'Cryptographic proof of origin',
    how: 'We parse the Content Credentials standard (C2PA). If the image carries a signed manifest from a camera or AI tool, we verify the signature and extract the assertion.',
    catches: 'AI-generated content, tamper-evident camera originals',
  },
  {
    icon: FileSearch,
    title: 'EXIF Metadata',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10 border-purple-500/20',
    what: 'Hidden camera and software data',
    how: 'Using Pillow we extract all EXIF tags including GPS coordinates, camera make/model, date taken, and software fields. We check 14+ known editing tools by name.',
    catches: 'Editing software (Photoshop, Lightroom, GIMP, Canva, Snapseed…)',
  },
  {
    icon: Cpu,
    title: 'Error Level Analysis',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10 border-amber-500/20',
    what: 'Compression forensics without metadata',
    how: 'We re-compress the JPEG at a known quality level and compare it pixel-by-pixel against the original. Edited regions compress differently, creating measurable error level anomalies.',
    catches: 'Post-capture editing even after EXIF stripping',
  },
  {
    icon: Fingerprint,
    title: 'Quantization Fingerprint',
    color: 'text-rose-400',
    bg: 'bg-rose-500/10 border-rose-500/20',
    what: 'Software ID via JPEG tables',
    how: 'Every JPEG encoder embeds characteristic quantization tables in the data stream. We match these against known signatures for Photoshop, GIMP, Instagram, Twitter, WhatsApp and more.',
    catches: 'Software identity even when EXIF is completely stripped',
  },
  {
    icon: Globe,
    title: 'Origin Trace',
    color: 'text-sky-400',
    bg: 'bg-sky-500/10 border-sky-500/20',
    what: 'Reverse image search + web archive',
    how: 'We submit the image to Google Lens via SerpApi for visual matching, then cross-reference matches against the Wayback Machine and URL-embedded date patterns to establish first appearance.',
    catches: 'Recirculated images, out-of-context photos, misattributed archival images',
  },
];

// ─── LIMITATIONS ─────────────────────────────────────────────────────────────
const CAN_DO = [
  'Detect AI generation when C2PA credentials are embedded',
  'Verify tamper-evident camera signatures (C2PA hardware)',
  'Find editing software via EXIF, ELA, and quantization tables',
  'Trace images to earlier web appearances via archive cross-referencing',
  'Produce a verifiable, shareable receipt of the verification result',
];

const CANNOT_DO = [
  'Detect AI generation without embedded C2PA credentials',
  'Recover metadata that has been stripped by platforms (Twitter, Instagram)',
  'Determine the intent behind an edit (malicious vs. routine)',
  'Verify the truthfulness of the depicted content (only the image\'s history)',
  'Access private, restricted, or password-protected image sources',
];

// ─── ANIMATION HELPERS ────────────────────────────────────────────────────────
const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

function useReveal(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: threshold });
  return { ref, inView };
}

// ─── ANIMATED COUNTER ─────────────────────────────────────────────────────────
function Counter({ to, suffix = '' }: { to: number; suffix?: string }) {
  const { ref, inView } = useReveal(0.5);
  const motionVal = useMotionValue(0);
  const spring = useSpring(motionVal, { stiffness: 80, damping: 20 });
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (inView) motionVal.set(to);
  }, [inView, motionVal, to]);

  useEffect(() => {
    return spring.on('change', (v) => setDisplay(Math.round(v)));
  }, [spring]);

  return <span ref={ref}>{display}{suffix}</span>;
}

// ─── FAQ COMPONENT ────────────────────────────────────────────────────────────
function FAQItem({ q, a, idx }: { q: string; a: string; idx: number }) {
  const [open, setOpen] = useState(false);
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay: idx * 0.06, ease: EASE }}
      className={`border rounded-2xl overflow-hidden transition-all duration-300 ${open ? 'border-teal-500/30 bg-teal-500/5' : 'border-white/10 bg-white/[0.03] hover:border-white/20'}`}
    >
      <button
        className="w-full text-left px-6 py-5 flex items-start justify-between gap-4"
        onClick={() => setOpen(!open)}
      >
        <span className="font-semibold text-white/90 text-sm leading-relaxed">{q}</span>
        <ChevronDown className={`w-5 h-5 text-white/40 shrink-0 mt-0.5 transition-transform duration-300 ${open ? 'rotate-180 text-teal-400' : ''}`} />
      </button>
      <div className={`px-6 transition-all duration-300 overflow-hidden ${open ? 'max-h-64 pb-5' : 'max-h-0'}`}>
        <p className="text-sm text-white/60 leading-relaxed">{a}</p>
      </div>
    </motion.div>
  );
}

// ─── FLOATING PARTICLES ───────────────────────────────────────────────────────
const PARTICLE_LABELS = ['SHA-256', 'C2PA', 'EXIF', 'ELA', '0xFF', 'QNT', 'ORIG', '0xA3', 'C2', 'META'];

function HeroParticles() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {PARTICLE_LABELS.map((label, i) => {
        const left = 5 + (i * 9.3) % 90;
        const startY = 20 + (i * 13.7) % 60;
        const duration = 8 + (i * 1.3) % 8;
        const delay = i * 0.7;
        return (
          <motion.span
            key={label}
            className="absolute font-mono text-[10px] text-teal-400/20 select-none"
            style={{ left: `${left}%`, top: `${startY}%` }}
            animate={{ y: [-20, -80], opacity: [0, 0.5, 0] }}
            transition={{ duration, delay, repeat: Infinity, ease: 'easeInOut' }}
          >
            {label}
          </motion.span>
        );
      })}
    </div>
  );
}

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center bg-[#0A0A0A] text-white overflow-x-hidden">

      {/* ── Animated ambient background glows ── */}
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden="true">
        <motion.div
          animate={{ scale: [1, 1.15, 1], opacity: [0.06, 0.12, 0.06] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute top-[-10%] left-[5%] w-[700px] h-[700px] rounded-full bg-teal-500 blur-[140px]"
        />
        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.05, 0.1, 0.05] }}
          transition={{ duration: 13, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
          className="absolute top-[40%] right-[-5%] w-[500px] h-[500px] rounded-full bg-purple-600 blur-[120px]"
        />
        <motion.div
          animate={{ scale: [1, 1.1, 1], opacity: [0.03, 0.08, 0.03] }}
          transition={{ duration: 9, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
          className="absolute bottom-[10%] left-[20%] w-[400px] h-[400px] rounded-full bg-sky-600 blur-[100px]"
        />
      </div>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ HERO ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <section className="relative z-10 w-full max-w-6xl mx-auto px-6 pt-24 pb-20 flex flex-col items-center text-center">
        <HeroParticles />

        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mb-8 inline-flex items-center gap-2 px-4 py-2 rounded-full border border-teal-500/30 bg-teal-500/10 text-teal-300 text-xs font-semibold tracking-widest uppercase"
        >
          <motion.div animate={{ rotate: [0, 20, 0] }} transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}>
            <Zap className="w-3 h-3" />
          </motion.div>
          Image Provenance &amp; Verification
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2, ease: EASE }}
          className="text-6xl sm:text-7xl lg:text-8xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-teal-400 via-white/90 to-purple-500 leading-[1.05] pb-2"
        >
          Don&apos;t share it.<br />Prove it.
        </motion.h1>

        {/* Sub */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.4 }}
          className="mt-8 text-lg sm:text-xl text-white/60 max-w-2xl mx-auto leading-relaxed"
        >
          Receipts is a forensic image analysis tool that traces provenance, detects AI generation, surfaces editing signatures, and finds earlier online appearances — generating a verifiable, shareable receipt of every analysis.
        </motion.p>

        {/* Stats bar — animated counters */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.55 }}
          className="mt-12 flex flex-wrap justify-center gap-10"
        >
          {[
            { value: 5, suffix: ' layers', label: 'Analysis pipeline' },
            { value: 30, suffix: 's', label: 'Typical result time' },
            { value: 14, suffix: '+', label: 'Software fingerprints' },
          ].map(({ value, suffix, label }) => (
            <div key={label} className="flex flex-col items-center gap-1">
              <span className="text-3xl font-extrabold text-white/90 tabular-nums">
                <Counter to={value} suffix={suffix} />
              </span>
              <span className="text-xs text-white/35 font-medium tracking-wide">{label}</span>
            </div>
          ))}
        </motion.div>

        {/* Mini checklist */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.65 }}
          className="mt-6 flex flex-wrap justify-center gap-5 text-sm text-white/50"
        >
          {['5-layer analysis pipeline', 'Results in under 30 seconds', 'No account required'].map((t) => (
            <div key={t} className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
              <span>{t}</span>
            </div>
          ))}
        </motion.div>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.75 }}
          className="mt-10 flex flex-col sm:flex-row gap-4 items-center"
        >
          <Link
            href="/verify"
            id="hero-cta-primary"
            className="group inline-flex items-center gap-2 bg-teal-500 hover:bg-teal-400 text-black font-bold px-8 py-4 rounded-2xl text-base transition-all shadow-[0_0_30px_rgba(45,212,191,0.3)] hover:shadow-[0_0_60px_rgba(45,212,191,0.5)] hover:scale-105"
          >
            Verify an Image
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Link>
          <a
            href="#how-it-works"
            id="hero-cta-secondary"
            className="inline-flex items-center gap-2 text-white/60 hover:text-white/90 font-medium px-6 py-4 rounded-2xl border border-white/10 hover:border-white/20 transition-all text-sm"
          >
            See how it works
            <motion.div animate={{ y: [0, 4, 0] }} transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}>
              <ChevronDown className="w-4 h-4" />
            </motion.div>
          </a>
        </motion.div>
      </section>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━ HOW IT WORKS ━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionWrapper id="how-it-works">
        <RevealBlock>
          <SectionLabel>Walkthrough</SectionLabel>
          <SectionTitle>How it works</SectionTitle>
          <SectionSub>Four steps from submission to receipt. The entire pipeline runs automatically — no manual steps required.</SectionSub>
        </RevealBlock>

        <div className="mt-16 grid grid-cols-1 md:grid-cols-4 gap-6 relative">
          {/* Animated connector line */}
          <div className="hidden md:block absolute top-10 left-[12.5%] right-[12.5%] h-px overflow-hidden">
            <motion.div
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 1.2, ease: EASE }}
              style={{ originX: 0 }}
              className="h-full bg-gradient-to-r from-teal-500/30 via-purple-500/40 to-teal-500/30"
            />
          </div>

          {[
            { step: 1, icon: Upload, color: 'text-teal-400', bg: 'bg-teal-500/10 border-teal-500/20', title: 'Submit', desc: 'Paste an image URL or drag-and-drop a local file. JPEGs, PNGs, and WebPs up to 15 MB are supported.' },
            { step: 2, icon: ScanSearch, color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/20', title: 'Analyze', desc: '5 forensic checks run in parallel: C2PA parsing, EXIF extraction, ELA, quantization fingerprinting, and origin trace.' },
            { step: 3, icon: Layers, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20', title: 'Classify', desc: 'The rules engine evaluates all evidence and assigns a classification with one of three evidence strengths: Strong, Moderate, or Limited.' },
            { step: 4, icon: FileText, color: 'text-sky-400', bg: 'bg-sky-500/10 border-sky-500/20', title: 'Receipt', desc: 'A verifiable image receipt is generated with all findings. Share the URL or download it as evidence.' },
          ].map(({ step, icon: Icon, color, bg, title, desc }, i) => (
            <motion.div
              key={step}
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.12, ease: EASE }}
              className="flex flex-col items-center text-center gap-4 group"
            >
              <motion.div
                whileHover={{ scale: 1.1, rotate: 3 }}
                transition={{ type: 'spring', stiffness: 300 }}
                className={`relative w-20 h-20 rounded-2xl ${bg} border flex items-center justify-center shadow-lg z-10 cursor-default`}
              >
                <Icon className={`w-9 h-9 ${color}`} />
                <span className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-[#0A0A0A] border border-white/10 text-xs font-bold text-white/60 flex items-center justify-center">{step}</span>
              </motion.div>
              <h3 className="text-lg font-bold text-white">{title}</h3>
              <p className="text-sm text-white/55 leading-relaxed max-w-[200px]">{desc}</p>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━ WHAT WE CHECK ━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionWrapper>
        <RevealBlock>
          <SectionLabel>Capabilities</SectionLabel>
          <SectionTitle>What we check</SectionTitle>
          <SectionSub>A 5-layer pipeline runs on every image. Each layer adds independent evidence that feeds into the classification engine.</SectionSub>
        </RevealBlock>

        <div className="mt-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {CHECKS.map(({ icon: Icon, title, color, bg, what, how, catches }, i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.55, delay: i * 0.08, ease: EASE }}
              whileHover={{ y: -4, transition: { duration: 0.2 } }}
              className="group bg-white/[0.03] border border-white/10 rounded-3xl p-7 flex flex-col gap-4 hover:border-white/20 hover:bg-white/[0.05] transition-colors duration-300 cursor-default"
            >
              <motion.div
                whileHover={{ rotate: [0, -8, 8, 0] }}
                transition={{ duration: 0.4 }}
                className={`w-12 h-12 rounded-xl ${bg} border flex items-center justify-center shrink-0`}
              >
                <Icon className={`w-6 h-6 ${color}`} />
              </motion.div>
              <div>
                <h3 className="text-base font-bold text-white mb-1">{title}</h3>
                <p className={`text-xs font-semibold uppercase tracking-wider ${color} mb-3`}>{what}</p>
                <p className="text-sm text-white/55 leading-relaxed mb-3">{how}</p>
                <div className="flex items-start gap-2 mt-auto">
                  <BadgeCheck className={`w-4 h-4 ${color} shrink-0 mt-0.5`} />
                  <p className="text-xs text-white/40 leading-relaxed">Catches: {catches}</p>
                </div>
              </div>
            </motion.div>
          ))}

          {/* Rules Engine card */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.55, delay: 0.5, ease: EASE }}
            whileHover={{ y: -4, transition: { duration: 0.2 } }}
            className="bg-gradient-to-br from-teal-500/10 to-purple-500/10 border border-teal-500/20 rounded-3xl p-7 flex flex-col justify-between gap-4 cursor-default"
          >
            <div className="flex items-center gap-3">
              <motion.div animate={{ rotate: [0, 360] }} transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}>
                <Brain className="w-8 h-8 text-teal-400" />
              </motion.div>
              <h3 className="text-base font-bold text-white">Rules Engine</h3>
            </div>
            <p className="text-sm text-white/60 leading-relaxed">All five evidence sources feed into a weighted rules engine. First-match-wins determines the headline classification; all matching evidence accumulates in the itemized findings.</p>
            <div className="grid grid-cols-3 gap-2 mt-2">
              {['Strong', 'Moderate', 'Limited'].map((s, i) => (
                <motion.div
                  key={s}
                  whileHover={{ scale: 1.05 }}
                  className={`text-center rounded-xl py-2 text-xs font-bold border ${['bg-teal-500/10 border-teal-500/20 text-teal-300', 'bg-amber-500/10 border-amber-500/20 text-amber-300', 'bg-zinc-500/10 border-zinc-500/20 text-zinc-400'][i]}`}
                >
                  {s}
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━ VERDICTS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionWrapper>
        <RevealBlock>
          <SectionLabel>Classifications</SectionLabel>
          <SectionTitle>Understanding your result</SectionTitle>
          <SectionSub>Every analysis produces exactly one of five verdicts. Here is what each one means and when to expect it.</SectionSub>
        </RevealBlock>

        <div className="mt-16 flex flex-col gap-4">
          {VERDICTS.map(({ label, strength, color, dot, glowColor, text, desc, when }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, x: -40 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.55, delay: i * 0.08, ease: EASE }}
              whileHover={{ x: 4, boxShadow: `0 0 40px ${glowColor}`, transition: { duration: 0.2 } }}
              className={`bg-gradient-to-r ${color} border rounded-2xl p-6 flex flex-col sm:flex-row gap-4 sm:gap-6 items-start cursor-default transition-shadow duration-300`}
            >
              <div className="shrink-0 flex items-center gap-3 sm:w-64">
                <motion.div
                  animate={{ scale: [1, 1.3, 1], opacity: [0.7, 1, 0.7] }}
                  transition={{ duration: 2 + i * 0.3, repeat: Infinity, ease: 'easeInOut' }}
                  className={`w-3 h-3 rounded-full shrink-0 ${dot}`}
                />
                <div>
                  <p className={`font-bold text-sm ${text}`}>{label}</p>
                  <p className="text-xs text-white/40 mt-0.5">Evidence: {strength}</p>
                </div>
              </div>
              <div className="flex-1 flex flex-col gap-2">
                <p className="text-sm text-white/70 leading-relaxed">{desc}</p>
                <p className="text-xs text-white/40"><span className="text-white/60 font-semibold">Typical trigger: </span>{when}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━ USE CASES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionWrapper>
        <RevealBlock>
          <SectionLabel>Who is this for</SectionLabel>
          <SectionTitle>Built for people who need answers</SectionTitle>
          <SectionSub>Whether you are a professional fact-checker or just saw something suspicious in your feed — Receipts is designed for you.</SectionSub>
        </RevealBlock>

        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8">
          {USE_CASES.map(({ icon: Icon, title, color, bg, items }, i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0, y: 50 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.12, ease: EASE }}
              whileHover={{ y: -6, transition: { duration: 0.25 } }}
              className="bg-white/[0.03] border border-white/10 rounded-3xl p-8 flex flex-col gap-6 hover:border-white/20 hover:bg-white/[0.05] transition-colors duration-300 cursor-default"
            >
              <motion.div
                whileHover={{ scale: 1.1, rotate: -5 }}
                transition={{ type: 'spring', stiffness: 300 }}
                className={`w-14 h-14 rounded-2xl ${bg} border flex items-center justify-center`}
              >
                <Icon className={`w-7 h-7 ${color}`} />
              </motion.div>
              <h3 className="text-xl font-bold text-white">{title}</h3>
              <ul className="flex flex-col gap-3">
                {items.map((item, j) => (
                  <motion.li
                    key={item}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.12 + j * 0.06 }}
                    className="flex items-start gap-3 text-sm text-white/60 leading-relaxed"
                  >
                    <CheckCircle2 className={`w-4 h-4 ${color} shrink-0 mt-0.5`} />
                    {item}
                  </motion.li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━ LIMITATIONS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionWrapper>
        <RevealBlock>
          <SectionLabel>Transparency</SectionLabel>
          <SectionTitle>What Receipts can and cannot do</SectionTitle>
          <SectionSub>We believe in being honest about what this tool detects — and what it does not. No forensic tool is infallible.</SectionSub>
        </RevealBlock>

        <div className="mt-16 grid grid-cols-1 md:grid-cols-2 gap-6">
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: EASE }}
            className="bg-teal-500/5 border border-teal-500/20 rounded-3xl p-8"
          >
            <div className="flex items-center gap-3 mb-6">
              <CheckCircle2 className="w-6 h-6 text-teal-400" />
              <h3 className="text-lg font-bold text-teal-300">What it can detect</h3>
            </div>
            <ul className="flex flex-col gap-4">
              {CAN_DO.map((item, i) => (
                <motion.li
                  key={item}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.07 }}
                  className="flex items-start gap-3 text-sm text-white/70 leading-relaxed"
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-teal-400 shrink-0 mt-2" />
                  {item}
                </motion.li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: EASE }}
            className="bg-rose-500/5 border border-rose-500/20 rounded-3xl p-8"
          >
            <div className="flex items-center gap-3 mb-6">
              <XCircle className="w-6 h-6 text-rose-400" />
              <h3 className="text-lg font-bold text-rose-300">What it cannot detect</h3>
            </div>
            <ul className="flex flex-col gap-4">
              {CANNOT_DO.map((item, i) => (
                <motion.li
                  key={item}
                  initial={{ opacity: 0, x: 10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.07 }}
                  className="flex items-start gap-3 text-sm text-white/70 leading-relaxed"
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-rose-400 shrink-0 mt-2" />
                  {item}
                </motion.li>
              ))}
            </ul>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-6 flex items-start gap-4 bg-amber-500/5 border border-amber-500/20 rounded-2xl p-6"
        >
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <p className="text-sm text-white/60 leading-relaxed">
            <span className="text-amber-300 font-semibold">Important: </span>
            Receipts provides technical evidence, not legal verdicts. Results should be treated as one input in a broader editorial or investigative process — never as sole proof of authenticity or fabrication. Always apply human judgment.
          </p>
        </motion.div>
      </SectionWrapper>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━ HOW TO USE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionWrapper>
        <RevealBlock>
          <SectionLabel>Guide</SectionLabel>
          <SectionTitle>How to use Receipts</SectionTitle>
          <SectionSub>Follow this short guide to get the most accurate results from your analysis.</SectionSub>
        </RevealBlock>

        <div className="mt-16 grid grid-cols-1 lg:grid-cols-2 gap-10">
          <div className="flex flex-col gap-6">
            {[
              { n: '01', title: 'Use the original source URL when possible', body: "If you find an image on social media, try to find the earliest known source. A URL from the original news article or photographer's site carries more metadata than a Twitter CDN link." },
              { n: '02', title: 'Upload the file directly for deeper ELA analysis', body: 'When you upload a file from disk, the full JPEG data (including quantization tables) is preserved. URL-fetched images that passed through CDNs may have metadata partially stripped.' },
              { n: '03', title: 'Read the interpretation text, not just the verdict label', body: 'Each result includes a plain-language interpretation that explains what the findings mean in context. A "Post-Processed" verdict on a professional photo is very different from one on a claimed raw document.' },
              { n: '04', title: 'Use the receipt link as shareable evidence', body: 'Every verification generates a permanent receipt URL. Share this link so others can independently view the same findings without re-running the analysis.' },
            ].map(({ n, title, body }, i) => (
              <motion.div
                key={n}
                initial={{ opacity: 0, x: -30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: EASE }}
                className="flex gap-5 group"
              >
                <motion.div
                  whileHover={{ scale: 1.1, backgroundColor: 'rgba(45,212,191,0.15)' }}
                  className="shrink-0 w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-xs font-bold text-white/40 font-mono transition-colors"
                >
                  {n}
                </motion.div>
                <div>
                  <h4 className="font-semibold text-white mb-1.5 group-hover:text-teal-300 transition-colors">{title}</h4>
                  <p className="text-sm text-white/55 leading-relaxed">{body}</p>
                </div>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: EASE }}
            className="bg-white/[0.03] border border-white/10 rounded-3xl p-8 flex flex-col gap-6 h-fit"
          >
            <h3 className="font-bold text-white flex items-center gap-2">
              <HelpCircle className="w-5 h-5 text-teal-400" />
              Quick Reference
            </h3>
            <div className="flex flex-col gap-3">
              {[
                { q: 'Supported formats', a: 'JPEG, PNG, WebP' },
                { q: 'Max file size', a: '15 MB' },
                { q: 'Rate limit', a: '10 verifications / minute' },
                { q: 'Result cache', a: 'Same image returns instantly (SHA-256 cache)' },
                { q: 'C2PA detection', a: 'Requires embedded credentials in image' },
                { q: 'ELA analysis', a: 'JPEG only (PNG is lossless)' },
                { q: 'Origin trace', a: 'Requires SerpApi key (configured server-side)' },
              ].map(({ q, a }, i) => (
                <motion.div
                  key={q}
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-start justify-between gap-4 py-2.5 border-b border-white/5 last:border-0 hover:border-white/10 transition-colors"
                >
                  <span className="text-xs text-white/50">{q}</span>
                  <span className="text-xs text-white/80 font-medium text-right">{a}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━ FAQ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <section className="relative z-10 w-full max-w-4xl mx-auto px-6 py-24">
        <RevealBlock>
          <SectionLabel>FAQ</SectionLabel>
          <SectionTitle>Frequently asked questions</SectionTitle>
          <SectionSub>Answers to the most common questions about how Receipts works and what it detects.</SectionSub>
        </RevealBlock>

        <div className="mt-16 flex flex-col gap-3">
          {FAQ_ITEMS.map(({ q, a }, i) => (
            <FAQItem key={q} q={q} a={a} idx={i} />
          ))}
        </div>
      </section>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━ FINAL CTA ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, ease: EASE }}
          className="relative bg-gradient-to-br from-teal-500/10 via-white/[0.02] to-purple-500/10 border border-white/10 rounded-3xl p-12 text-center flex flex-col items-center gap-6 overflow-hidden"
        >
          {/* Subtle animated inner glow */}
          <motion.div
            animate={{ scale: [1, 1.3, 1], opacity: [0.05, 0.12, 0.05] }}
            transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute inset-0 bg-gradient-radial from-teal-400/20 to-transparent pointer-events-none"
          />
          <motion.div
            whileHover={{ scale: 1.1, rotate: 5 }}
            className="w-16 h-16 rounded-2xl bg-teal-500/20 border border-teal-500/30 flex items-center justify-center z-10"
          >
            <ShieldCheck className="w-8 h-8 text-teal-400" />
          </motion.div>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-teal-400 to-purple-500 z-10">
            Ready to verify?
          </h2>
          <p className="text-white/60 max-w-lg text-base leading-relaxed z-10">
            Paste a URL or upload a file. The full analysis pipeline runs in seconds — no account, no setup.
          </p>
          <Link
            href="/verify"
            id="final-cta"
            className="group inline-flex items-center gap-2 bg-teal-500 hover:bg-teal-400 text-black font-bold px-10 py-4 rounded-2xl text-base transition-all shadow-[0_0_30px_rgba(45,212,191,0.3)] hover:shadow-[0_0_60px_rgba(45,212,191,0.6)] hover:scale-105 z-10"
          >
            Launch Receipts
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Link>
        </motion.div>
      </SectionWrapper>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━ FOOTER ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <footer className="relative z-10 w-full border-t border-white/5 mt-8">
        <div className="max-w-6xl mx-auto px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="flex items-center gap-2 text-sm text-white/40"
          >
            <ShieldCheck className="w-4 h-4 text-teal-500/60" />
            <span>Receipts — Image Provenance Verification</span>
          </motion.div>
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="flex items-center gap-4 sm:gap-6 text-xs text-white/30"
          >
            <span>Created by <span className="text-white/50 font-semibold">Beneyas Tadu</span></span>
            <a
              href="mailto:beneyas.work@gmail.com"
              className="flex items-center gap-1.5 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white/50 hover:text-white/70 px-3 py-1.5 rounded-lg transition-all font-medium"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
              Contact Us
            </a>
            <Link href="/verify" className="hover:text-white/60 transition-colors">Verify →</Link>
          </motion.div>
        </div>
      </footer>
    </main>
  );
}

// ─── LAYOUT HELPERS ───────────────────────────────────────────────────────────
function SectionWrapper({ children, id }: { children: React.ReactNode; id?: string }) {
  return (
    <section id={id} className="relative z-10 w-full max-w-6xl mx-auto px-6 py-24">
      {children}
    </section>
  );
}

function RevealBlock({ children }: { children: React.ReactNode }) {
  const { ref, inView } = useReveal(0.2);
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-white/40 text-xs font-semibold tracking-widest uppercase mb-4">
      {children}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">{children}</h2>
  );
}

function SectionSub({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-4 text-base text-white/50 max-w-2xl leading-relaxed">{children}</p>
  );
}
