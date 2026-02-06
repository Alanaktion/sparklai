# GitHub Copilot Instructions for SparklAI

SparklAI is a fake social media site that generates all of its users, posts, images, and DMs using open source AI APIs (Llama and Stable Diffusion). This is a SvelteKit app with TypeScript, Tailwind CSS v4, and Drizzle ORM for database management. Please follow these guidelines when contributing:

## Required Before Each Commit

- Run `pnpm run format` before committing to ensure consistent code formatting
- Run `pnpm run lint` to check code style and catch common issues
- Run `pnpm run check` to validate TypeScript types and Svelte components
- If you modify database schema in `src/lib/server/db/schema.ts`, run `pnpm run db:push` to sync changes

## Development Flow

- **Install dependencies**: `pnpm install`
- **Initialize database** (required on first run): `pnpm run db:push`
- **Start dev server**: `pnpm run dev`
- **Build for production**: `pnpm run build`
- **Preview production build**: `pnpm run preview`
- **Type checking**: `pnpm run check` or `pnpm run check:watch` (watch mode)
- **Linting**: `pnpm run lint`
- **Formatting**: `pnpm run format`
- **Database commands**: `pnpm run db:push` (push schema), `pnpm run db:migrate` (run migrations), `pnpm run db:studio` (open Drizzle Studio)

## Repository Structure

- `src/lib/` - Shared library code
  - `src/lib/server/` - Server-side only code (database operations, AI integration). Never import these in client components
    - `src/lib/server/db/` - Database schema and utilities (Drizzle ORM)
    - `src/lib/server/chat/` - LLM chat integration (Llama via OpenAI-compatible API)
    - `src/lib/server/sd/` - Stable Diffusion image generation
  - `src/lib/components/` - Reusable Svelte components
  - `src/lib/actions/` - Svelte actions
- `src/routes/` - SvelteKit file-based routing (use `+page.server.ts` for server-side code)
- `static/` - Static assets
- `drizzle.config.ts` - Database configuration

## Code Standards

### TypeScript

- Use strict TypeScript mode (already enabled in `tsconfig.json`)
- Never use `any` type - use proper typing or `unknown` when appropriate
- Prefer type inference where possible
- Export types that are used across modules

### Code Style

- Use tabs for indentation (not spaces)
- Use single quotes for strings
- Maximum 100 characters per line
- No trailing commas
- Let Prettier handle formatting (configured in `.prettierrc`)

### Svelte 5 Conventions

- Use Svelte 5 runes syntax: `$state`, `$derived`, `$effect`, `$props`
- Server-side code must stay in `src/lib/server/` or `+page.server.ts`/`+layout.server.ts` files
- Never import `src/lib/server/*` code in client-side components
- Use `$lib` path alias for imports from `src/lib/`
- Follow SvelteKit's file-based routing conventions

### Styling

- Use Tailwind CSS utility classes (v4 syntax)
- Avoid custom CSS unless absolutely necessary
- Tailwind class ordering is handled automatically by prettier-plugin-tailwindcss

### Database (Drizzle ORM)

- All database operations use Drizzle ORM
- Schema definitions are in `src/lib/server/db/schema.ts`
- After schema changes, run `pnpm run db:push` to sync with the database
- Use `pnpm run db:studio` to explore database contents

## Environment Setup

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL` - Database connection (default: `file:local.db`)
- `CHAT_URL`, `CHAT_MODEL` - LLM API configuration (OpenAI-compatible endpoint)
- `SD_URL`, `SD_*_MODEL`, `SD_*_PROMPT` - Stable Diffusion API configuration

## Key Guidelines

1. **Type Safety**: Leverage TypeScript's strict mode - avoid `any`, use proper types
2. **Server/Client Separation**: Keep server code in `src/lib/server/`. Never import it in client components or the app will break
3. **Svelte 5 Runes**: Use `$state`, `$derived`, `$effect` instead of old Svelte syntax
4. **Error Handling**: Handle AI API failures gracefully - they can be slow or fail
5. **Database Schema**: When modifying `src/lib/server/db/schema.ts`, always run `pnpm run db:push` to sync
6. **Testing Changes**: Run `pnpm run check` and `pnpm run lint` before committing
7. **Code Formatting**: Run `pnpm run format` to format all code before committing

## AI Integration (Key Modules)

### LLM Chat (`src/lib/server/chat/`)

- Uses OpenAI-compatible API for Llama models
- Functions: `completion()`, `schema_completion()`
- Generates user posts, comments, and messages based on user personality/context

### Image Generation (`src/lib/server/sd/`)

- Stable Diffusion via HTTP API
- Function: `txt2img()`
- Supports photo, drawing, and stylized models (configured via environment)

### Content Generation Pattern

- User profiles have personality traits, interests, writing style, backstory
- Generated content respects these user characteristics
- Context includes location, occupation, relationship status

## Common Code Patterns

**Database query with Drizzle ORM:**

```typescript
import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

const user = await db.select().from(users).where(eq(users.id, userId));
```

**LLM completion for content generation:**

```typescript
import { completion } from '$lib/server/chat';

const response = await completion([{ role: 'user', content: 'Generate a post...' }]);
```

**Svelte 5 component with runes:**

```svelte
<script lang="ts">
	let count = $state(0);
	let doubled = $derived(count * 2);
</script>

<button onclick={() => count++}>Count: {count}</button>
```

## Important Constraints

- Never modify `.svelte-kit/` or `node_modules/` directories
- Never import server code (`src/lib/server/*`) in client components
- Maintain backward compatibility with existing database schema
- Follow existing patterns and conventions
- Never commit secrets or API keys to version control

## Future Roadmap

When implementing features, consider these planned improvements:

- Defining relationships between specific users (friends, followers)
- Human user profile customization
- Multiple AI models with automatic selection based on task
- User metadata visibility and editing
