import { schema_completion, type LlamaMessage } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { images, posts, users } from '$lib/server/db/schema';
import { txt2img } from '$lib/server/sd/index.js';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

export async function POST({ params, request }) {
	const user = await db.query.users.findFirst({
		where: eq(users.id, Number(params.id)),
		with: { posts: { columns: { id: true, created_at: true, body: true } } }
	});
	if (!user) {
		return error(404, {
			message: 'Not found'
		});
	}

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

	const history: LlamaMessage[] = [
		{
			role: 'user',
			content
		}
	];
	user.posts.forEach((post) => {
		history.push({
			role: 'assistant',
			content: JSON.stringify({
				timestamp: post.created_at,
				post_text: post.body
			})
		});
	});

	let prompt = 'Write the next post for the user.';
	if (request.headers.get('Content-Type')?.includes('form')) {
		const data = await request.formData();
		if (data.has('prompt')) {
			prompt += '\n\n' + data.get('prompt')?.toString();
		}
	}
	history.push({ role: 'user', content: prompt });

	const response = await schema_completion('post', null, history);

	let img_id = null;
	if (response.image_generation) {
		const pic = await txt2img(response.image_generation.image_keywords);
		const img_result = await db.insert(images).values({
			user_id: user.id,
			params: pic.params,
			data: pic.data
		});
		img_id = Number(img_result.lastInsertRowid);
	}

	const insert_result = await db
		.insert(posts)
		.values({
			user_id: user.id,
			body: response.post_text,
			image_id: img_id
		})
		.returning();

	return json(insert_result[0]);
}
