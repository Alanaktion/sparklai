import { fetch_models as fetch_chat_models, model as chat_model } from '$lib/server/chat';
import { fetch_models as fetch_sd_models, model as sd_model } from '$lib/server/sd';
import { json } from '@sveltejs/kit';
import { init as chat_init } from '$lib/server/chat';
import { init as sd_init } from '$lib/server/sd';

export async function GET() {
	return json({
		chat_models: await fetch_chat_models(),
		chat_model,
		sd_models: await fetch_sd_models(),
		sd_model
	});
}

export async function POST({ request }) {
	const body = await request.json();
	chat_init(body.chat_model);
	await sd_init(body.sd_model);
	return new Response(null, { status: 204 });
}
