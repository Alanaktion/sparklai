# GitHub Copilot Instructions for SparklAI

## Project Overview

SparklAI is a fake social media site that generates all of its users, posts, images, and DMs using open source AI APIs (Llama and Stable Diffusion). This project demonstrates AI-generated content in a social media context.

## Tech Stack

- **Framework**: SvelteKit (with Svelte 5)
- **Language**: TypeScript (strict mode enabled)
- **Styling**: Tailwind CSS v4
- **Database**: LibSQL/Turso with Drizzle ORM
- **AI Integration**:
  - LLM: Llama models via OpenAI-compatible API
  - Image Generation: Stable Diffusion via HTTP API
- **Package Manager**: pnpm
- **Build Tool**: Vite

## Project Structure

- `src/lib/` - Shared library code
  - `src/lib/server/` - Server-side only code (database, AI integration)
    - `src/lib/server/db/` - Database schema and utilities
    - `src/lib/server/chat/` - LLM chat integration
    - `src/lib/server/sd/` - Stable Diffusion image generation
  - `src/lib/components/` - Reusable Svelte components
  - `src/lib/actions/` - Svelte actions
- `src/routes/` - SvelteKit file-based routing
- `static/` - Static assets
- Database managed via Drizzle ORM (`drizzle.config.ts`)

## Coding Standards

### TypeScript
- Use strict TypeScript mode
- Avoid `any` type - use proper typing or `unknown` when appropriate
- Prefer type inference where possible
- Export types that are used across modules

### Code Style
- **Indentation**: Use tabs (not spaces)
- **Quotes**: Single quotes for strings
- **Line Length**: Maximum 100 characters
- **Trailing Commas**: None
- **Formatting**: Run `pnpm run format` before committing

### Svelte Conventions
- Use Svelte 5 runes syntax (`$state`, `$derived`, `$effect`, etc.)
- Server-side code must remain in `src/lib/server/` or route `+page.server.ts`/`+layout.server.ts` files
- Use SvelteKit's file-based routing conventions
- Prefer `$lib` path alias for imports from `src/lib/`

### CSS/Styling
- Use Tailwind CSS utility classes
- Apply Tailwind classes in consistent order (prettier-plugin-tailwindcss handles this)
- Avoid custom CSS unless necessary

### Database
- Use Drizzle ORM for all database operations
- Schema definitions in `src/lib/server/db/schema.ts`
- Run `pnpm run db:push` to sync schema changes
- Use `pnpm run db:studio` for database exploration

## Development Commands

```bash
# Install dependencies
pnpm install

# Initialize database (required on first run)
pnpm run db:push

# Start development server
pnpm run dev

# Build for production
pnpm run build

# Preview production build
pnpm run preview

# Type checking
pnpm run check
pnpm run check:watch  # Watch mode

# Linting and formatting
pnpm run lint     # Check code style and run ESLint
pnpm run format   # Format code with Prettier

# Database commands
pnpm run db:push     # Push schema changes
pnpm run db:migrate  # Run migrations
pnpm run db:studio   # Open Drizzle Studio
```

## Environment Setup

The project requires environment variables defined in `.env.example`:
- Database connection (`DATABASE_URL`)
- LLM API configuration (`CHAT_URL`, `CHAT_MODEL`)
- Stable Diffusion API configuration (`SD_URL`, model settings)

Copy `.env.example` to `.env` and configure according to your local setup.

## AI Integration Guidelines

### LLM (Llama)
- Located in `src/lib/server/chat/`
- Uses OpenAI-compatible API interface
- Provides `completion()` and `schema_completion()` functions
- Used for generating user posts, comments, and messages

### Image Generation (Stable Diffusion)
- Located in `src/lib/server/sd/`
- Provides `txt2img()` function
- Supports multiple model types (photo, drawing, stylized)
- Configuration via environment variables

### Content Generation
- User profiles include personality traits, interests, writing style, etc.
- Generated content should respect user characteristics
- Posts and comments are AI-generated based on user context

## Best Practices

1. **Type Safety**: Leverage TypeScript's type system for safer code
2. **Server/Client Separation**: Keep server-only code in `src/lib/server/` to prevent client-side inclusion
3. **Error Handling**: Handle AI API failures gracefully
4. **Testing**: Validate changes with `pnpm run check` and `pnpm run lint`
5. **Performance**: Be mindful of AI API calls - they can be slow or rate-limited
6. **Code Quality**: Run formatter and linter before committing changes

## Common Patterns

### Database Queries
```typescript
import { db } from '$lib/server/db';
import { users, posts } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

// Query example
const user = await db.select().from(users).where(eq(users.id, userId));
```

### AI Content Generation
```typescript
import { completion } from '$lib/server/chat';

// Generate content
const response = await completion([
	{ role: 'user', content: 'Generate a post...' }
]);
```

### Component Structure
```svelte
<script lang="ts">
	// Use Svelte 5 runes
	let count = $state(0);
	let doubled = $derived(count * 2);
</script>

<button onclick={() => count++}>Count: {count}</button>
```

## Constraints

- Never modify files in `.svelte-kit/` or `node_modules/` directories
- Server code must not be imported in client-side components
- Maintain backward compatibility with existing database schema
- Follow existing code patterns and conventions
- Don't commit sensitive data (API keys, secrets) to version control

## Future Improvements

The project roadmap includes:
- Defining relationships between specific users
- Human user profile customization
- Multiple model support with automatic switching
- User metadata visibility/editing

When implementing new features, consider these planned improvements and maintain compatibility.
