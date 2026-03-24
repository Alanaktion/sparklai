import { env } from '$env/dynamic/private';
import OpenAI from 'openai';

import post_schema from './schema/post.schema.json';
import post_image_schema from './schema/post_image.schema.json';
import profile_image_schema from './schema/profile_image.schema.json';
import user_schema from './schema/user.schema.json';

import { post_image_system, post_system, profile_image_system, user_system } from './schema';

if (!env.CHAT_URL) throw new Error('CHAT_URL is not set');

function normalize_model(value: string | null | undefined): string {
	const trimmed = (value || '').trim();
	if (!trimmed) return '';
	if (
		(trimmed.startsWith('"') && trimmed.endsWith('"')) ||
		(trimmed.startsWith("'") && trimmed.endsWith("'"))
	) {
		return trimmed.slice(1, -1).trim();
	}
	return trimmed;
}

export let model = normalize_model(env.CHAT_MODEL);
let model_validated = false;
const temperature = 0.7;

const client = new OpenAI({
	apiKey: env.CHAT_API_KEY || 'no-key',
	baseURL: env.CHAT_URL
});

export type LlamaMessage = {
	role: 'user' | 'assistant' | 'system';
	content: string;
};

export function init(new_model: string | null = null) {
	const normalized = normalize_model(new_model);
	if (normalized) {
		model = normalized;
		model_validated = false;
	}
}

type ChatModel = {
	id: string;
};
export async function fetch_models(): Promise<ChatModel[]> {
	const response = await client.models.list();
	return response.data.map((m) => ({ id: m.id }));
}

async function resolve_model(): Promise<string> {
	const models = await fetch_models();
	if (models.length === 0) {
		throw new Error(
			'No chat models available from CHAT_URL. Load a model in the backend or set CHAT_MODEL.'
		);
	}

	const selected = normalize_model(model);
	if (selected && model_validated) return selected;

	if (selected && models.some((availableModel) => availableModel.id === selected)) {
		model = selected;
		model_validated = true;
		return model;
	}

	model = models[0].id;
	model_validated = true;
	return model;
}

export async function get_model(): Promise<string> {
	return await resolve_model();
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

	const allMessages: OpenAI.ChatCompletionMessageParam[] = [
		{ role: 'system', content: system_text },
		...messages
	];
	if (user_prompt !== null) {
		allMessages.push({ role: 'user', content: user_prompt });
	}
	const activeModel = await resolve_model();

	const response = await client.chat.completions.create({
		model: activeModel,
		messages: allMessages,
		temperature,
		response_format: {
			type: 'json_schema',
			json_schema: {
				name: schema_name,
				strict: true,
				schema
			}
		}
	});
	return JSON.parse(response.choices[0].message.content!);
}

export async function completion(
	user_prompt: string | null = null,
	messages: LlamaMessage[] = []
): Promise<string> {
	const allMessages: OpenAI.ChatCompletionMessageParam[] = [...messages];
	if (user_prompt !== null) {
		allMessages.push({ role: 'user', content: user_prompt });
	}
	const activeModel = await resolve_model();

	const response = await client.chat.completions.create({
		model: activeModel,
		messages: allMessages,
		temperature
	});
	return response.choices[0].message.content!;
}
