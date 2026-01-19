-- =============================================================================
-- Blog Ideas Table
-- Queue for autonomous blog generation
-- =============================================================================

-- Run this in your Supabase SQL Editor to create the blog_ideas table

CREATE TABLE IF NOT EXISTS public.blog_ideas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),

  -- The topic/idea
  topic text NOT NULL,                    -- Main topic: "How to fix your slice"
  description text,                        -- Optional longer description of what to cover
  notes text,                              -- Any additional notes/guidance for the AI

  -- Priority & ordering (NULL for completed/failed/skipped items)
  priority integer DEFAULT 50              -- 0-999, higher = do first
    CHECK (priority IS NULL OR (priority >= 0 AND priority <= 999)),

  -- Status tracking
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),

  -- Timestamps
  created_at timestamp with time zone DEFAULT now(),
  started_at timestamp with time zone,     -- When AI started working on it
  completed_at timestamp with time zone,   -- When AI finished

  -- Result tracking
  blog_post_id uuid,                       -- Link to created post (if successful)
  error_message text,                      -- Error details (if failed)
  attempts integer DEFAULT 0,              -- Number of generation attempts

  -- Metadata
  source text DEFAULT 'manual'             -- Where idea came from
    CHECK (source IN ('manual', 'ai_suggested', 'trending', 'user_request', 'content_gap')),

  -- Constraints
  CONSTRAINT blog_ideas_pkey PRIMARY KEY (id),
  CONSTRAINT blog_ideas_blog_post_id_fkey
    FOREIGN KEY (blog_post_id) REFERENCES public.blog_posts(id) ON DELETE SET NULL
);

-- =============================================================================
-- Indexes for efficient querying
-- =============================================================================

-- Primary query: Get next pending idea by priority
CREATE INDEX IF NOT EXISTS idx_blog_ideas_pending_priority
  ON public.blog_ideas(status, priority DESC NULLS LAST, created_at ASC)
  WHERE status = 'pending';

-- Find ideas by status
CREATE INDEX IF NOT EXISTS idx_blog_ideas_status
  ON public.blog_ideas(status);

-- =============================================================================
-- Row Level Security (RLS)
-- =============================================================================

-- Enable RLS
ALTER TABLE public.blog_ideas ENABLE ROW LEVEL SECURITY;

-- Policy: Service role can do everything (for the blog generator)
CREATE POLICY "Service role full access" ON public.blog_ideas
  FOR ALL
  USING (true)
  WITH CHECK (true);

-- =============================================================================
-- Helper function to get next idea
-- =============================================================================

CREATE OR REPLACE FUNCTION get_next_blog_idea()
RETURNS TABLE (
  id uuid,
  topic text,
  description text,
  notes text,
  priority integer
)
LANGUAGE sql
SECURITY DEFINER
AS $$
  SELECT
    id,
    topic,
    description,
    notes,
    priority
  FROM public.blog_ideas
  WHERE status = 'pending'
  ORDER BY priority DESC NULLS LAST, created_at ASC
  LIMIT 1;
$$;

-- =============================================================================
-- Useful queries for managing ideas
-- =============================================================================

-- View all pending ideas ordered by priority:
-- SELECT topic, priority, created_at FROM blog_ideas WHERE status = 'pending' ORDER BY priority DESC;

-- View completed ideas with their posts:
-- SELECT bi.topic, bp.title, bp.slug, bi.completed_at
-- FROM blog_ideas bi
-- JOIN blog_posts bp ON bi.blog_post_id = bp.id
-- WHERE bi.status = 'completed';

-- View failed ideas:
-- SELECT topic, error_message, attempts FROM blog_ideas WHERE status = 'failed';

-- Reset a failed idea to try again:
-- UPDATE blog_ideas SET status = 'pending', error_message = NULL WHERE id = 'uuid-here';
