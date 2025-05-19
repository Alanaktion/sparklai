import { init } from '$lib/server/chat';

export async function POST({ request }) {
	const { model } = await request.json();
	init(model);
	return new Response(null, { status: 204 });
}
