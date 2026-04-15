import { and, eq } from 'drizzle-orm';
import { completion, schema_completion, type LlamaMessage } from './chat';
import { db } from './db';
import {
	comments,
	posts,
	relationships,
	users,
	type CommentType,
	type PostType,
	type UserType
} from './db/schema';
import { enqueueImageJob } from './sd/jobs';

export type GeneratedPostResult = {
	post: PostType;
	image_job: Awaited<ReturnType<typeof enqueueImageJob>> | null;
};

function buildPostPrompt(user: UserType, datetime: string) {
	const profileBits = [
		`You are generating a post for ${user.name} (${user.pronouns}), age ${user.age}.`,
		`Current local date/time for the character: ${datetime}. Use this only as situational context, not as literal text to print.`,
		'Write exactly like this person would post on social media.',
		"Match the user's personality, age, bio, backstory, interests, relationships, and writing style as closely as possible.",
		'Do not start with a date, time, weekday, or journal-like timestamp.',
		'Avoid generic openings, bland summaries of the day, and assistant-sounding phrasing.',
		'Vary sentence structure, pacing, and openings across posts.',
		"Keep the post grounded in concrete specifics that fit this user's life and voice."
	];

	if (user.backstory) {
		profileBits.push(`Backstory: ${user.backstory}`);
	}
	if (user.location) {
		profileBits.push(
			`Location: ${user.location.city}, ${user.location.state_province}, ${user.location.country}`
		);
	}
	if (user.occupation) {
		profileBits.push(`Occupation: ${user.occupation}`);
	}
	if (user.interests?.length) {
		profileBits.push(`Interests: ${user.interests.join(', ')}`);
	}
	if (user.relationship_status) {
		profileBits.push(`Relationship status: ${user.relationship_status}`);
	}
	if (user.personality_traits) {
		profileBits.push(`Personality traits: ${user.personality_traits}`);
	}
	if (user.writing_style) {
		profileBits.push(`Writing style: ${user.writing_style}`);
	}
	if (user.backstory) {
		profileBits.push(`Backstory: ${user.backstory}`);
	}

	return profileBits.join('\n');
}

export async function generatePost(
	user: UserType,
	prompt: string | null = null
): Promise<GeneratedPostResult> {
	const datetime = new Date().toLocaleString(undefined, {
		weekday: 'long',
		year: 'numeric',
		month: 'long',
		day: 'numeric',
		hour: 'numeric',
		minute: '2-digit'
	});

	let content = buildPostPrompt(user, datetime);

	// Add relationship information
	const relationshipsData = await db
		.select({
			name: users.name,
			pronouns: users.pronouns,
			occupation: users.occupation,
			relationship_type: relationships.relationship_type,
			description: relationships.description
		})
		.from(relationships)
		.innerJoin(users, eq(relationships.related_user_id, users.id))
		.where(eq(relationships.user_id, user.id));

	if (relationshipsData.length > 0) {
		const relationshipsText = relationshipsData
			.map((r) => {
				let text = `${r.name} (${r.pronouns})`;
				if (r.relationship_type) {
					text += ` - ${r.relationship_type}`;
				}
				if (r.description) {
					text += `: ${r.description}`;
				}
				return text;
			})
			.join('; ');
		content += `\nRelationships: ${relationshipsText}`;
	}

	const history: LlamaMessage[] = [
		{
			role: 'user',
			content
		}
	];

	const posts_result = await db.query.posts.findMany({
		where: eq(posts.user_id, user.id),
		columns: { id: true, created_at: true, body: true }
		// limit: 5
	});
	posts_result.forEach((post) => {
		history.push({
			role: 'assistant',
			content: JSON.stringify({
				timestamp: post.created_at,
				post_text: post.body
			})
		});
	});

	let prompt_content =
		'Write the next post for the user. Make it feel distinct from prior posts, specific to this person, and naturally written for a social feed.';
	if (prompt) {
		prompt_content += '\n\n' + prompt;
	}
	history.push({ role: 'user', content: prompt_content });

	const response = await schema_completion('post', null, history);

	const insert_result = await db
		.insert(posts)
		.values({
			user_id: user.id,
			body: response.post_text
		})
		.returning();
	const post = insert_result[0];

	let image_job: Awaited<ReturnType<typeof enqueueImageJob>> | null = null;
	if (response.image_generation) {
		try {
			const image_style = response.image_generation.image_style || 'photo';
			image_job = await enqueueImageJob({
				user_id: user.id,
				post_id: post.id,
				target: 'post_generation',
				prompt: response.image_generation.image_keywords,
				negative_prompt: null,
				width: 512,
				height: 512,
				include_default_prompt: true,
				image_style
			});
		} catch (e) {
			console.error(e);
		}
	}

	return {
		post,
		image_job
	};
}

export async function generateComment(user: UserType, post: PostType): Promise<CommentType> {
	const author_result = await db.select().from(users).where(eq(users.id, post.user_id));
	const author = author_result[0];

	const is_own_post = user.id === author.id;

	// Check if there's a relationship between the commenter and the post author
	let relationship_context = '';
	if (!is_own_post) {
		const relationship = await db
			.select({
				relationship_type: relationships.relationship_type,
				description: relationships.description
			})
			.from(relationships)
			.where(and(eq(relationships.user_id, user.id), eq(relationships.related_user_id, author.id)))
			.limit(1);

		if (relationship.length > 0) {
			const rel = relationship[0];
			relationship_context = `\nYour relationship with ${author.name}`;
			if (rel.relationship_type) {
				relationship_context += `: ${rel.relationship_type}`;
			}
			if (rel.description) {
				relationship_context += ` - ${rel.description}`;
			}
		}
	}

	const history: LlamaMessage[] = [
		{
			role: 'system',
			content:
				`You are ${user.name} (${user.pronouns}), writing a comment on the given social media post. It can be a reply to other comments (if any), or directly responding to the post itself. *Do not include any meta-text, only the comment body.*\n` +
				`Your backstory: ${user.backstory}\n` +
				`Writing style: ${user.writing_style}\n` +
				relationship_context +
				"Write a new comment. Do not include any roleplay or metatext, just write the actual response. If you don't know the language the original post is in, you can use your preferred language."
		},
		{
			role: 'user',
			content: is_own_post
				? `This is your own post that you wrote: ${post.body}`
				: `Post by ${author.name} (${author.pronouns}): ${post.body}`
		}
	];

	const comments_result = await db
		.select({ id: comments.id, body: comments.body, name: users.name })
		.from(comments)
		.leftJoin(users, eq(users.id, comments.user_id))
		.where(eq(comments.post_id, post.id));
	comments_result.forEach((comment) => {
		history.push({
			role: 'user',
			content: `Comment by ${comment.name}: ${comment.body}`
		});
	});

	const response = await completion(null, history);
	const result = await db.insert(comments).values({
		post_id: post.id,
		user_id: user.id,
		body: response
	});

	const comment = await db.query.comments.findFirst({
		with: {
			user: { columns: { id: true, name: true, image_id: true } }
		},
		where: eq(comments.id, Number(result.lastInsertRowid))
	});

	if (!comment) {
		throw new Error('Comment not found after insert');
	}

	return comment;
}
