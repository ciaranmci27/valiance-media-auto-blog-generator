# Getting Started with React

Render your blog content blocks in a React frontend.

## Prerequisites

### 1. Set Up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** in your dashboard
3. Run the schema files in order:

```
schema/blog_tables.sql    → Core tables (posts, categories, authors, tags)
schema/blog_ideas.sql     → Generation queue
```

### 2. Create an Author

```sql
INSERT INTO blog_authors (slug, name, bio) VALUES
  ('staff-writer', 'Staff Writer', 'Expert content from our team.');
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyxxxxx
DEFAULT_AUTHOR_SLUG=staff-writer
```

### 4. Generate Some Content

```bash
pip install -r requirements.txt
python generator.py "Your first topic here"
```

---

## React Setup

Now that you have content in Supabase, build a frontend to display it.

### 1. Create the Block Renderer

```tsx
// components/ContentBlockRenderer.tsx
import React from 'react';

interface Block {
  id: string;
  type: string;
  data: Record<string, any>;
}

interface Props {
  blocks: Block[];
}

export function ContentBlockRenderer({ blocks }: Props) {
  if (!blocks?.length) return null;

  return (
    <article className="blog-content">
      {blocks.map((block) => (
        <BlockSwitch key={block.id} block={block} />
      ))}
    </article>
  );
}

function BlockSwitch({ block }: { block: Block }) {
  switch (block.type) {
    case 'paragraph':
      return <p dangerouslySetInnerHTML={{ __html: block.data.text }} />;

    case 'heading':
      const Tag = `h${block.data.level}` as keyof JSX.IntrinsicElements;
      return <Tag>{block.data.text}</Tag>;

    case 'list':
      const ListTag = block.data.style === 'ordered' ? 'ol' : 'ul';
      return (
        <ListTag>
          {block.data.items.map((item: string, i: number) => (
            <li key={i} dangerouslySetInnerHTML={{ __html: item }} />
          ))}
        </ListTag>
      );

    case 'callout':
      return (
        <div className={`callout callout-${block.data.style}`}>
          {block.data.title && <strong>{block.data.title}</strong>}
          <p dangerouslySetInnerHTML={{ __html: block.data.text }} />
        </div>
      );

    case 'quote':
      return (
        <blockquote>
          <p dangerouslySetInnerHTML={{ __html: block.data.text }} />
          {block.data.attribution && <cite>— {block.data.attribution}</cite>}
        </blockquote>
      );

    case 'image':
      return (
        <figure>
          <img src={block.data.src} alt={block.data.alt} />
          {block.data.caption && <figcaption>{block.data.caption}</figcaption>}
        </figure>
      );

    case 'table':
      return (
        <table>
          <thead>
            <tr>
              {block.data.headers.map((h: string, i: number) => (
                <th key={i}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.data.rows.map((row: string[], i: number) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );

    case 'proscons':
      return (
        <div className="pros-cons">
          <div className="pros">
            <h4>Pros</h4>
            <ul>
              {block.data.pros.map((item: string, i: number) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="cons">
            <h4>Cons</h4>
            <ul>
              {block.data.cons.map((item: string, i: number) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      );

    case 'video':
      if (block.data.platform === 'youtube') {
        return (
          <div className="video-embed">
            <iframe
              src={`https://www.youtube.com/embed/${block.data.videoId}`}
              title={block.data.title}
              allowFullScreen
            />
          </div>
        );
      }
      return null;

    case 'divider':
      return <hr />;

    default:
      return null;
  }
}
```

### 2. Use in Your Blog Page

```tsx
// pages/blog/[slug].tsx
import { ContentBlockRenderer } from '@/components/ContentBlockRenderer';

export default function BlogPost({ post }) {
  return (
    <main>
      <h1>{post.title}</h1>
      <p className="excerpt">{post.excerpt}</p>

      <ContentBlockRenderer blocks={post.content} />
    </main>
  );
}
```

### 3. Fetch from Supabase

```tsx
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// Get single post
export async function getPost(slug: string) {
  const { data } = await supabase
    .from('blog_posts')
    .select('*, blog_categories(*), blog_authors(*)')
    .eq('slug', slug)
    .eq('status', 'published')
    .single();

  return data;
}

// Get all posts
export async function getPosts() {
  const { data } = await supabase
    .from('blog_posts')
    .select('id, slug, title, excerpt, featured_image, created_at')
    .eq('status', 'published')
    .order('created_at', { ascending: false });

  return data;
}
```

### 4. Add Basic Styles

```css
/* styles/blog.css */
.blog-content {
  max-width: 720px;
  margin: 0 auto;
  line-height: 1.7;
}

.callout {
  padding: 1rem;
  border-radius: 8px;
  margin: 1.5rem 0;
}

.callout-tip { background: #e8f5e9; border-left: 4px solid #4caf50; }
.callout-warning { background: #fff3e0; border-left: 4px solid #ff9800; }
.callout-info { background: #e3f2fd; border-left: 4px solid #2196f3; }

.pros-cons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.video-embed {
  position: relative;
  padding-bottom: 56.25%;
}

.video-embed iframe {
  position: absolute;
  width: 100%;
  height: 100%;
}

blockquote {
  border-left: 4px solid #ccc;
  padding-left: 1rem;
  font-style: italic;
}

figure {
  margin: 1.5rem 0;
}

figure img {
  max-width: 100%;
  height: auto;
}

figcaption {
  font-size: 0.875rem;
  color: #666;
  text-align: center;
}
```

---

## Next Steps

- See [content-blocks.md](../content-blocks.md) for the full list of block types
- See [database-setup.md](../database-setup.md) for queue management and RLS policies
- See [configuration.md](../configuration.md) for all environment variables
