import {
	get_model as get_chat_model,
	init as chat_init,
	fetch_models as fetch_chat_models
} from '$lib/server/chat';
import {
	backend as sd_backend,
	fetch_models as fetch_sd_models,
	init as sd_init,
	init_style as sd_init_style,
	model as sd_model,
	style as sd_style,
	supportsModelSelection
} from '$lib/server/sd';
import { json } from '@sveltejs/kit';

export async function GET() {
	const chat_model = await get_chat_model();
	return json({
		chat_models: await fetch_chat_models(),
		chat_model,
		sd_backend,
		sd_models: await fetch_sd_models(),
		sd_model,
		sd_style,
		sd_supports_model_selection: supportsModelSelection()
	});
}

export async function POST({ request }) {
	const body = await request.json();
	chat_init(body.chat_model);
	const chat_model = await get_chat_model();
	if (body.sd_style) {
		await sd_init_style(body.sd_style);
	} else if (body.sd_model) {
		await sd_init(body.sd_model);
	}
	return json({
		sd_backend,
		chat_model,
		sd_model,
		sd_style,
		sd_supports_model_selection: supportsModelSelection()
	});
}
