-- ==========================================
-- Receipts: Supabase Setup (M2)
-- ==========================================

-- 1. Create receipts table
CREATE TABLE IF NOT EXISTS public.receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sha256 TEXT UNIQUE,
    phash TEXT,
    input_type TEXT,
    source_url TEXT,
    original_image_url TEXT,
    classification TEXT,
    evidence_strength TEXT,
    evidence JSONB,
    interpretation TEXT,
    status TEXT,
    error_message TEXT,
    processing_time_ms INTEGER,
    receipt_schema_version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS receipts_sha256_idx ON public.receipts(sha256);
CREATE INDEX IF NOT EXISTS receipts_phash_idx ON public.receipts(phash);

-- 2. Enable RLS on receipts table
ALTER TABLE public.receipts ENABLE ROW LEVEL SECURITY;

-- Policy: INSERT restricted to Service Role
CREATE POLICY "Enable insert for service role only" ON public.receipts
    FOR INSERT
    TO service_role
    WITH CHECK (true);

-- Policy: SELECT is public
CREATE POLICY "Enable read access for all users" ON public.receipts
    FOR SELECT
    USING (true);

-- ==========================================
-- 3. Set up Storage Bucket (images)
-- ==========================================

-- Create the bucket if it doesn't exist (publicly accessible reads)
INSERT INTO storage.buckets (id, name, public) 
VALUES ('images', 'images', true)
ON CONFLICT (id) DO NOTHING;

-- Policy: INSERT into images bucket restricted to Service Role
CREATE POLICY "Enable insert for service role only (storage)" ON storage.objects
    FOR INSERT
    TO service_role
    WITH CHECK (bucket_id = 'images');

-- Policy: SELECT from images bucket is public
CREATE POLICY "Enable read access for all users (storage)" ON storage.objects
    FOR SELECT
    USING (bucket_id = 'images');
