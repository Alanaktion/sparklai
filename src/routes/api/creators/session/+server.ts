import { json } from '@sveltejs/kit';

const COOKIE_NAME = 'creator_session';

export async function DELETE({ cookies }) {
	cookies.delete(COOKIE_NAME, { path: '/' });
	return json({ success: true });
}
