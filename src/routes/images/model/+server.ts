import { init } from '$lib/server/sd';

export async function POST({ request }) {
	const { model } = await request.json();
	await init(model);
	return new Response(null, { status: 204 });
}
