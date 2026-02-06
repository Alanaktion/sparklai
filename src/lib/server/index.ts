import { eq } from 'drizzle-orm';
import { completion, schema_completion, type LlamaMessage } from './chat';
import { db } from './db';
import {
	comments,
	images,
	posts,
	relationships,
	users,
	type CommentType,
	type PostType,
	type UserType
} from './db/schema';
import { txt2img } from './sd';

export async function generatePost(
	user: UserType,
	prompt: string | null = null
): Promise<PostType> {
	const datetime = new Date().toLocaleString(undefined, {
		weekday: 'long',
		year: 'numeric',
		month: 'long',
		day: 'numeric',
		hour: 'numeric',
		minute: '2-digit'
	});

	let content = `Write a new post for ${user.name} (${user.pronouns}). The current date/time is ${datetime}`;
	if (user.location) {
		content += `\nLocation: ${user.location.city}, ${user.location.state_province}, ${user.location.country}`;
	}
	if (user.occupation) {
		content += `\nOccupation: ${user.occupation}`;
	}
	if (user.interests) {
		content += `\nInterests: ${user.interests}`;
	}
	if (user.writing_style) {
		content += `\nWriting style: ${JSON.stringify(user.writing_style)}`;
	}
	if (user.personality_traits) {
		content += `\nPersonality traits: ${JSON.stringify(user.personality_traits)}`;
	}
	if (user.relationship_status) {
		content += `\nRelationship status: ${user.relationship_status}`;
	}
	if (user.backstory_snippet) {
		content += `\nBackstory: ${user.backstory_snippet}`;
	}

	// Add relationship information
	const followingData = await db
		.select({
			name: users.name,
			pronouns: users.pronouns,
			occupation: users.occupation
		})
		.from(relationships)
		.innerJoin(users, eq(relationships.following_id, users.id))
		.where(eq(relationships.follower_id, user.id));

	if (followingData.length > 0) {
		const followingNames = followingData.map((u) => `${u.name} (${u.pronouns})`).join(', ');
		content += `\nFollowing: ${followingNames}`;
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

	let prompt_content = 'Write the next post for the user.';
	if (prompt) {
		prompt_content += '\n\n' + prompt;
	}
	history.push({ role: 'user', content: prompt_content });

	const response = await schema_completion('post', null, history);

	let img_id = null;
	if (response.image_generation) {
		try {
			const pic = await txt2img(response.image_generation.image_keywords);
			const img_result = await db.insert(images).values({
				user_id: user.id,
				params: pic.params,
				data: pic.data
			});
			img_id = Number(img_result.lastInsertRowid);
		} catch (e) {
			console.error(e);
		}
	}

	const insert_result = await db
		.insert(posts)
		.values({
			user_id: user.id,
			body: response.post_text,
			image_id: img_id
		})
		.returning();

	return insert_result[0];
}

export async function generateComment(user: UserType, post: PostType): Promise<CommentType> {
	const author_result = await db.select().from(users).where(eq(users.id, post.user_id));
	const author = author_result[0];

	const is_own_post = user.id === author.id;

	// Check if there's a relationship between the commenter and the post author
	let relationship_context = '';
	if (!is_own_post) {
		const userFollowsAuthor = await db
			.select()
			.from(relationships)
			.where(eq(relationships.follower_id, user.id))
			.where(eq(relationships.following_id, author.id))
			.limit(1);

		const authorFollowsUser = await db
			.select()
			.from(relationships)
			.where(eq(relationships.follower_id, author.id))
			.where(eq(relationships.following_id, user.id))
			.limit(1);

		if (userFollowsAuthor.length > 0 && authorFollowsUser.length > 0) {
			relationship_context = `\nYou and ${author.name} follow each other.`;
		} else if (userFollowsAuthor.length > 0) {
			relationship_context = `\nYou follow ${author.name}.`;
		} else if (authorFollowsUser.length > 0) {
			relationship_context = `\n${author.name} follows you.`;
		}
	}

	const history: LlamaMessage[] = [
		{
			role: 'system',
			content:
				`You are ${user.name} (${user.pronouns}), writing a comment on the given social media post. It can be a reply to other comments (if any), or directly responding to the post itself. *Do not include any meta-text, only the comment body.*\n` +
				`Your bio: ${user.bio}\n` +
				`Writing style: ${JSON.stringify(user.writing_style)}\n` +
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
