import { json } from '@sveltejs/kit';

const COOKIE_NAME = 'human_user_id';

export async function DELETE({ cookies }) {
	cookies.delete(COOKIE_NAME, { path: '/' });
	return json({ success: true });
}
