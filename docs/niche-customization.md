# Niche Customization

The generator uses a **modular prompt architecture** that separates universal blog instructions from niche-specific expertise.

## Prompt Structure

```
prompts/
├── system_prompt.md       # Universal: block types, SEO, workflows
└── niche/
    ├── golf.md            # Golf expertise (default, ships as working example)
    └── _template.md       # Blank template for creating your own
```

## How It Works

At runtime, the system loads:
1. `system_prompt.md` - Universal instructions (content blocks, operating modes, SEO)
2. `niche/{your-niche}.md` - Domain-specific expertise (merged automatically)

When running with `--verbose`, you'll see:
```
✓ Niche prompt loaded: prompts/niche/golf.md
```

## Creating Your Niche

### 1. Copy the Template

```bash
cp prompts/niche/_template.md prompts/niche/cooking.md
```

Or copy the golf example for reference:
```bash
cp prompts/niche/golf.md prompts/niche/cooking.md
```

### 2. Customize Your Niche File

Edit with your domain expertise:

- **Voice & persona** - How should the AI "sound"?
- **Terminology** - Correct terms for your field
- **Accuracy requirements** - What facts matter?
- **E-E-A-T signals** - How to demonstrate expertise
- **Image prompt examples** - Visual style for your niche

### 3. Update Configuration

```env
NICHE_PROMPT_PATH=prompts/niche/cooking.md
IMAGE_CONTEXT=kitchen, food photography, warm lighting
```

## What Goes Where

| Content | Location |
|---------|----------|
| Content block definitions | `system_prompt.md` (universal) |
| Operating modes (manual, autonomous) | `system_prompt.md` (universal) |
| SEO guidelines | `system_prompt.md` (universal) |
| Block selection guide | `system_prompt.md` (universal) |
| **Niche terminology** | `niche/{your-niche}.md` |
| **Accuracy requirements** | `niche/{your-niche}.md` |
| **Domain-specific examples** | `niche/{your-niche}.md` |
| **Image prompt examples** | `niche/{your-niche}.md` |
| **Quality checklist for niche** | `niche/{your-niche}.md` |

## Niche Prompt Sections

A good niche prompt should include:

### Identity & Voice

```markdown
## Identity

You are an expert {niche} content writer with deep knowledge of {specific areas}.
Your tone is {adjectives} and you write for {target audience}.
```

### Terminology

```markdown
## Terminology

Always use correct terminology:
- Use "{correct term}" not "{wrong term}"
- The proper name is "{X}" not "{Y}"
```

### Accuracy Requirements

```markdown
## Accuracy

- Always verify {type of facts}
- Never recommend {dangerous things}
- Cite sources when discussing {topics}
```

### E-E-A-T Signals

```markdown
## E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)

Demonstrate expertise by:
- Including specific {examples}
- Referencing {authoritative sources}
- Sharing {practical tips}
```

### Image Prompts

```markdown
## Image Prompts

When generating image prompts, include:
- {Visual style elements}
- {Common settings}
- {Color preferences}

Example: "A {subject} on a {setting}, {lighting}, {style}"
```

## Running Without a Niche

To generate generic content without niche-specific expertise:

```env
NICHE_PROMPT_PATH=
```

The generator will use only the universal `system_prompt.md`.

## Examples

### Golf (Default)

```env
NICHE_PROMPT_PATH=prompts/niche/golf.md
IMAGE_CONTEXT=golf course, outdoor sports, sunny day, green grass
```

### Cooking

```env
NICHE_PROMPT_PATH=prompts/niche/cooking.md
IMAGE_CONTEXT=kitchen, food photography, warm lighting, fresh ingredients
```

### Technology

```env
NICHE_PROMPT_PATH=prompts/niche/tech.md
IMAGE_CONTEXT=modern office, technology, clean workspace, minimal design
```

### Fitness

```env
NICHE_PROMPT_PATH=prompts/niche/fitness.md
IMAGE_CONTEXT=gym, fitness equipment, active lifestyle, healthy living
```
