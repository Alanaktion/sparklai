import { translateToEnglish } from '$lib/server/chat/translate';
import { db } from '$lib/server/db';
import { chats } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';

export async function POST({ params }) {
	const chat = await db.query.chats.findFirst({
		columns: { id: true, body: true, body_en: true },
		where: and(eq(chats.id, Number(params.message_id)), eq(chats.user_id, Number(params.id)))
	});

	if (!chat) {
		return error(404, { message: 'Message not found' });
	}

	if (chat.body_en) {
		return json({ body_en: chat.body_en });
	}

	const body_en = await translateToEnglish(chat.body);

	await db.update(chats).set({ body_en }).where(eq(chats.id, chat.id));

	return json({ body_en });
}
