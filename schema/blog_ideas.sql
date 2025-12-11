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

  -- Targeting (optional hints for the AI)
  target_category_slug text,               -- Suggested category slug
  suggested_tags text[],                   -- Suggested tag slugs
  target_word_count integer,               -- Target word count (default ~1500)

  -- Priority & ordering
  priority integer DEFAULT 50              -- 0-100, higher = do first
    CHECK (priority >= 0 AND priority <= 100),

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
  created_by text,                         -- Who added this idea

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
  ON public.blog_ideas(status, priority DESC, created_at ASC)
  WHERE status = 'pending';

-- Find ideas by status
CREATE INDEX IF NOT EXISTS idx_blog_ideas_status
  ON public.blog_ideas(status);

-- Find ideas by category
CREATE INDEX IF NOT EXISTS idx_blog_ideas_category
  ON public.blog_ideas(target_category_slug)
  WHERE target_category_slug IS NOT NULL;

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
  target_category_slug text,
  suggested_tags text[],
  target_word_count integer,
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
    target_category_slug,
    suggested_tags,
    target_word_count,
    priority
  FROM public.blog_ideas
  WHERE status = 'pending'
  ORDER BY priority DESC, created_at ASC
  LIMIT 1;
$$;

-- =============================================================================
-- Sample data (optional - uncomment to seed with ideas)
-- =============================================================================

/*
INSERT INTO public.blog_ideas (topic, description, priority, target_category_slug, suggested_tags, source) VALUES
  (
    'How to Fix Your Slice: A Complete Guide',
    'Cover the main causes of a slice, grip adjustments, swing path drills, and common mistakes. Include at least 3 actionable drills.',
    90,
    'instruction',
    ARRAY['slice', 'driver', 'swing-mechanics', 'beginner'],
    'manual'
  ),
  (
    'Best Putting Drills for Beginners',
    'Focus on distance control, alignment, and reading greens. Include drills that can be done at home.',
    85,
    'practice',
    ARRAY['putting', 'drills', 'beginner', 'short-game'],
    'manual'
  ),
  (
    'Understanding Golf Club Loft and Lie',
    'Explain what loft and lie angles are, how they affect ball flight, and when to get clubs fitted.',
    70,
    'equipment',
    ARRAY['club-fitting', 'equipment', 'ball-flight'],
    'manual'
  ),
  (
    'Pre-Round Warm-Up Routine for Golfers',
    'A 15-20 minute warm-up routine covering dynamic stretches, putting, chipping, and full swings.',
    75,
    'practice',
    ARRAY['warm-up', 'routine', 'flexibility', 'preparation'],
    'manual'
  ),
  (
    'Mental Game: How to Stay Calm Under Pressure',
    'Breathing techniques, visualization, pre-shot routine, and handling nerves on the first tee and closing holes.',
    80,
    'mental-game',
    ARRAY['mental-game', 'pressure', 'confidence', 'psychology'],
    'manual'
  );
*/

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
