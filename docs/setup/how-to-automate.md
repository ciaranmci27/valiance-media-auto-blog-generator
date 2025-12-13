# How to Automate

Run the blog generator on a schedule using GitHub Actions.

## Quick Start

1. Fork this repository
2. Add secrets and variables to your fork
3. Enable the workflow
4. Posts generate automatically on schedule

The workflow file already exists at `.github/workflows/generate-blogs.yml`.

---

## Step 1: Fork the Repository

1. Click **Fork** in the top right of this repo
2. Choose your account/organization
3. Clone your fork locally to customize prompts

---

## Step 2: Add Repository Secrets

Go to your fork's **Settings** → **Secrets and variables** → **Actions** → **Secrets** tab → **New repository secret**

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `GEMINI_API_KEY` | If using images | Google AI API key |

---

## Step 3: Add Repository Variables

Go to **Settings** → **Secrets and variables** → **Actions** → **Variables** tab → **New repository variable**

### Required Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `DEFAULT_AUTHOR_SLUG` | `staff-writer` | Author slug for posts |
| `DEFAULT_STATUS` | `published` | Post status (`draft` or `published`) |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` | Claude model to use |
| `MAX_TURNS` | `15` | Max agent loop iterations |
| `ALLOW_NEW_CATEGORIES` | `true` | Allow AI to create categories |
| `DEFAULT_CATEGORY_SLUG` | | Fallback category slug |
| `ENABLE_IMAGE_GENERATION` | `false` | Enable Gemini images |
| `GEMINI_MODEL` | `gemini-2.0-flash-exp-image-generation` | Gemini model |
| `IMAGE_ASPECT_RATIO` | `21:9` | Image aspect ratio |
| `IMAGE_WIDTH` | `1600` | Image width in pixels |
| `IMAGE_QUALITY` | `85` | WebP quality (1-100) |
| `SUPABASE_STORAGE_BUCKET` | `blog-images` | Storage bucket name |

---

## Step 4: Enable the Workflow

1. Go to your fork's **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. The workflow runs daily at 9 PM UTC by default

---

## Manual Trigger

Run the workflow manually anytime:

1. Go to **Actions** → **Generate Blog Posts**
2. Click **Run workflow**
3. Enter the number of posts to generate (default: 1)
4. Click **Run workflow**

---

## Change the Schedule

Edit `.github/workflows/generate-blogs.yml` to change the cron schedule:

```yaml
schedule:
  # Current: Daily at 9 PM UTC
  - cron: '0 21 * * *'

  # Every day at 9 AM UTC
  # - cron: '0 9 * * *'

  # Every Monday and Thursday at 2 PM UTC
  # - cron: '0 14 * * 1,4'

  # Every 6 hours
  # - cron: '0 */6 * * *'
```

Use [crontab.guru](https://crontab.guru/) to build cron expressions.

---

## Customizing Your Fork

### 1. Create Your Niche Prompt

```bash
cp prompts/niche/golf.md prompts/niche/your-niche.md
```

Edit the file with your niche's tone, topics, and guidelines.

### 2. Update the Workflow

Add `NICHE_PROMPT_PATH` to your repository variables:

| Variable | Value |
|----------|-------|
| `NICHE_PROMPT_PATH` | `prompts/niche/your-niche.md` |

### 3. Seed Your Queue

Add ideas to your Supabase `blog_ideas` table:

```sql
INSERT INTO blog_ideas (topic, description, priority) VALUES
  ('Topic 1', 'Description', 90),
  ('Topic 2', 'Description', 85),
  ('Topic 3', 'Description', 80);
```

---

## Monitoring

### Check Workflow Runs

Go to **Actions** tab to see run history, logs, and any failures.

### Check Queue Status

The workflow automatically shows queue status before generating. Check the logs to see pending ideas.

---

## Cost Estimation

Running daily with 1 post (default):
- ~$0.20/post × 30 days = ~$6/month
- GitHub Actions: Free for public repos, 2000 mins/month for private

---

## Troubleshooting

**Workflow not running on schedule**
→ GitHub disables scheduled workflows after 60 days of repo inactivity. Push a commit or run manually to re-enable.

**"Secret not found" errors**
→ Check secret names match exactly (case-sensitive). Secrets go in Secrets tab, variables go in Variables tab.

**Posts not appearing**
→ Check `DEFAULT_STATUS` variable is set to `published`, or posts will be drafts.

**Queue empty**
→ Add more ideas to `blog_ideas` table in Supabase.

**Timeout errors**
→ The workflow has a 30-minute timeout. If posts are complex, reduce the count or increase `MAX_TURNS`.
