-- ===========================================
-- Blog Images Storage Bucket Policies
-- ===========================================
--
-- PREREQUISITE: Create the bucket manually in Dashboard first:
-- 1. Go to: Storage (left sidebar)
-- 2. Click: "New bucket"
-- 3. Enter:
--    - Name: blog-images
--    - Public bucket: ENABLED (toggle ON)
--    - File size limit: 1 MB (1048576 bytes) or higher
--    - Allowed MIME types: image/webp, image/jpeg, image/png, image/gif
-- 4. Click: "Create bucket"
--
-- ===========================================
-- STEP 1: Run These SQL Commands
-- ===========================================
-- Run these in: SQL Editor (left sidebar)

-- Policy 1: Allow anyone to view images (public read)
CREATE POLICY "Public read access for blog-images"
ON storage.objects
FOR SELECT
TO public
USING (bucket_id = 'blog-images');

-- Policy 2: Allow service role to upload images
CREATE POLICY "Service role can upload to blog-images"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'blog-images'
    AND auth.role() = 'service_role'
);

-- Policy 3: Allow service role to update images
CREATE POLICY "Service role can update blog-images"
ON storage.objects
FOR UPDATE
TO authenticated
USING (
    bucket_id = 'blog-images'
    AND auth.role() = 'service_role'
)
WITH CHECK (
    bucket_id = 'blog-images'
    AND auth.role() = 'service_role'
);

-- Policy 4: Allow service role to delete images
CREATE POLICY "Service role can delete from blog-images"
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'blog-images'
    AND auth.role() = 'service_role'
);
--
-- ===========================================
-- STEP 3: Verify Setup
-- ===========================================
-- Test the bucket is working:
-- 1. Go to: Storage > blog-images
-- 2. Try uploading a test image manually
-- 3. Click the image and copy the public URL
-- 4. Open the URL in an incognito browser - it should display
--
-- ===========================================
-- Folder Structure (created automatically)
-- ===========================================
-- When the blog generator uploads images, folders are created automatically:
--
--   blog-images/
--   ├── golf-tips/
--   │   ├── best-drivers-2025.webp
--   │   └── how-to-fix-slice.webp
--   ├── equipment-reviews/
--   │   └── titleist-review.webp
--   └── fitness/
--       └── golf-exercises.webp
--
-- You do NOT need to pre-create these folders.
--
-- ===========================================
-- Image URL Format
-- ===========================================
-- After upload, images are accessible at:
--
--   {SUPABASE_URL}/storage/v1/object/public/blog-images/{category}/{slug}.webp
--
-- Example:
--   https://abc123.supabase.co/storage/v1/object/public/blog-images/golf-tips/best-drivers-2025.webp
--
-- ===========================================
-- Troubleshooting
-- ===========================================
--
-- Error: "Bucket not found"
--   → Make sure bucket name is exactly "blog-images"
--
-- Error: "Not authorized" on upload
--   → Make sure you're using SUPABASE_SERVICE_KEY (not anon key)
--
-- Error: "File type not allowed"
--   → Check allowed MIME types include image/webp
--
-- Images not displaying publicly
--   → Verify "Public bucket" is enabled
--   → Check policies allow SELECT for public
--
-- ===========================================
