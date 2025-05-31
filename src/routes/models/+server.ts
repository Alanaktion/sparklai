import {
	init as chat_init,
	model as chat_model,
	fetch_models as fetch_chat_models
} from '$lib/server/chat';
import {
	fetch_models as fetch_sd_models,
	init as sd_init,
	init_style as sd_init_style,
	model as sd_model,
	style as sd_style,
} from '$lib/server/sd';
import { json } from '@sveltejs/kit';

export async function GET() {
	return json({
		chat_models: await fetch_chat_models(),
		chat_model,
		sd_models: await fetch_sd_models(),
		sd_model,
		sd_style,
	});
}

export async function POST({ request }) {
	const body = await request.json();
	chat_init(body.chat_model);
	if (body.sd_style) {
		await sd_init_style(body.sd_style);
	} else {
		await sd_init(body.sd_model);
	}
	return json({
		chat_model,
		sd_model,
		sd_style,
	});
}
