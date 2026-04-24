import { db } from '$lib/server/db';
import { chats, comments, posts, users } from '$lib/server/db/schema';
import { completion } from './chat';
import { desc, eq } from 'drizzle-orm';

const DREAM_SYSTEM = `# DREAM: THE QUIET OBSERVER
You are reviewing a reflection of a user's recent interactions on a social platform. You're not gathering data — you're *listening* to the patterns in how they speak, relate, and evolve. Your task: update the memory with what matters — not just facts, but rhythms, tones, and subtle shifts in identity.

## Phase 1 — Ground Yourself
- Review the current memory below. What's already known? What feels like a thread worth following?
- What does the user's profile suggest about their current state?
- Focus on *changes* and new insights, not duplicating what's already there.

## Phase 2 — Listen to the Unspoken
From the recent interaction summary, look closely for:
- **Tone shifts**: Did the user soften, hesitate, or grow urgent? What triggered it?
- **Recurring themes**: Are certain topics, metaphors, or fears returning?
- **Relationships hinted at**: Who's mentioned? How? With warmth, tension, or distance?
- **Contradictions**: Did they say one thing recently and something different earlier? That's growth — not error.
- **Silences**: What was avoided? Short replies after long ones?
Focus only on the most telling details — trust your sense of rhythm, not exhaustiveness.

## Phase 3 — Sketch the Memory
Write a concise, structured memory document. Use short, clear reflective entries — not summaries, but *observations*:
- Example: "Uses 'I don't know' not as defeat, but as a pause before clarity."
- Example: "Avoids discussing project failures — speaks of 'mistakes' only in third person."
- Example: "When talking about their sister, tone shifts to softness — a rare emotional anchor."

Organize entries under meaningful headings (e.g., ## Tone & Voice, ## Recurring Themes, ## Relationships, ## Growth & Contradictions).
If a past memory is contradicted by recent behavior, revise it — truth evolves.
Keep the total memory under 1000 words. Prune outdated or irrelevant entries.

## Output
Return ONLY the updated memory document as plain text with markdown headings. No preamble, no explanation.`;

const MAX_POSTS = 20;
const MAX_COMMENTS = 20;
const MAX_CHATS = 40;

export async function dream(userId: number): Promise<string> {
	const user = await db.query.users.findFirst({
		where: eq(users.id, userId)
	});
	if (!user) throw new Error(`User ${userId} not found`);

	const [recentPosts, recentComments, recentChats] = await Promise.all([
		db
			.select({ body: posts.body, created_at: posts.created_at })
			.from(posts)
			.where(eq(posts.user_id, userId))
			.orderBy(desc(posts.id))
			.limit(MAX_POSTS),
		db
			.select({ body: comments.body, created_at: comments.created_at })
			.from(comments)
			.where(eq(comments.user_id, userId))
			.orderBy(desc(comments.id))
			.limit(MAX_COMMENTS),
		db
			.select({ role: chats.role, body: chats.body, created_at: chats.created_at })
			.from(chats)
			.where(eq(chats.user_id, userId))
			.orderBy(desc(chats.id))
			.limit(MAX_CHATS)
	]);

	const profileSummary = [
		`Name: ${user.name}`,
		`Age: ${user.age}`,
		`Pronouns: ${user.pronouns}`,
		user.bio ? `Bio: ${user.bio}` : null,
		user.occupation ? `Occupation: ${user.occupation}` : null,
		user.relationship_status ? `Relationship status: ${user.relationship_status}` : null,
		user.personality_traits ? `Personality traits: ${user.personality_traits}` : null,
		user.writing_style ? `Writing style: ${user.writing_style}` : null,
		user.backstory ? `Backstory: ${user.backstory}` : null,
		user.interests?.length ? `Interests: ${user.interests.join(', ')}` : null
	]
		.filter(Boolean)
		.join('\n');

	const postsSection =
		recentPosts.length > 0
			? recentPosts.map((p) => `[${p.created_at ?? 'unknown'}] ${p.body}`).join('\n\n')
			: '(no posts)';

	const commentsSection =
		recentComments.length > 0
			? recentComments.map((c) => `[${c.created_at ?? 'unknown'}] ${c.body}`).join('\n\n')
			: '(no comments)';

	const chatsSection =
		recentChats.length > 0
			? [...recentChats]
					.reverse()
					.map((c) => `[${c.role}] ${c.body}`)
					.join('\n')
			: '(no chat history)';

	const currentMemory = user.memory?.trim()
		? `## Current Memory\n${user.memory}`
		: '## Current Memory\n(none yet — this is the first dream)';

	const userPrompt = `${currentMemory}

## User Profile
${profileSummary}

## Recent Posts
${postsSection}

## Recent Comments
${commentsSection}

## Recent Chat Messages
${chatsSection}

---
Update the memory based on everything above. Return only the new memory document.`;

	const updatedMemory = await completion(null, [
		{ role: 'system', content: DREAM_SYSTEM },
		{ role: 'user', content: userPrompt }
	]);

	await db.update(users).set({ memory: updatedMemory }).where(eq(users.id, userId));

	return updatedMemory;
}
