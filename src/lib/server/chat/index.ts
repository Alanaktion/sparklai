import { env } from '$env/dynamic/private';

import post_schema from './schema/post.schema.json';
import post_image_schema from './schema/post_image.schema.json';
import profile_image_schema from './schema/profile_image.schema.json';
import user_schema from './schema/user.schema.json';

import { post_system, post_image_system, profile_image_system, user_system } from './schema';

if (!env.CHAT_URL) throw new Error('CHAT_URL is not set');

const model = env.CHAT_MODEL;
const temperature = 0.7;

export type LlamaMessage = {
	role: 'user' | 'assistant' | 'system';
	content: string;
};

type LlamaRequest = {
	model: string;
	messages: LlamaMessage[];
	temperature: number;
	response_format?: {
		type: string;
		json_schema?: {
			name: string;
			strict: string;
			schema: unknown;
		};
	};
};

async function fetch_completions(data: LlamaRequest) {
	const response = await fetch(`${env.CHAT_URL}chat/completions`, {
		method: 'POST',
		body: JSON.stringify(data),
		headers: {
			'Content-Type': 'application/json'
		}
	});
	return await response.json();
}

export async function schema_completion(
	schema_name: 'post' | 'post_image' | 'profile_image' | 'user',
	user_prompt: string | null = null,
	messages: LlamaMessage[] = []
) {
	let schema;
	let system_text: string = '';
	if (schema_name == 'post') {
		schema = post_schema;
		system_text = post_system;
	} else if (schema_name == 'post_image') {
		schema = post_image_schema;
		system_text = post_image_system;
	} else if (schema_name == 'profile_image') {
		schema = profile_image_schema;
		system_text = profile_image_system;
	} else if (schema_name == 'user') {
		schema = user_schema;
		system_text = user_system;
	}

	const data: LlamaRequest = {
		model,
		messages: [
			{
				role: 'system',
				content: system_text
			},
			...messages
		],
		temperature,
		response_format: {
			type: 'json_schema',
			json_schema: {
				name: schema_name,
				strict: 'true',
				schema
			}
		}
	};
	if (user_prompt !== null) {
		data.messages.push({
			role: 'user',
			content: user_prompt
		});
	}

	const body = await fetch_completions(data);
	return JSON.parse(body.choices[0].message.content);
}

export async function completion(
	user_prompt: string | null = null,
	messages: LlamaMessage[] = []
): Promise<string> {
	const data: LlamaRequest = {
		model,
		messages,
		temperature
	};
	if (user_prompt !== null) {
		data.messages.push({
			role: 'user',
			content: user_prompt
		});
	}
	const body = await fetch_completions(data);
	return body.choices[0].message.content;
}
