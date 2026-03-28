import { completion, type LlamaMessage } from '$lib/server/chat';

export async function translateToEnglish(text: string): Promise<string> {
	const source = text.trim();
	if (!source) {
		return '';
	}

	const messages: LlamaMessage[] = [
		{
			role: 'system',
			content:
				'You are a translation engine. Translate the user text into natural English. ' +
				'If the text is already English, return it unchanged. Return only translated text and no other commentary.'
		},
		{
			role: 'user',
			content: source
		}
	];

	const translated = await completion(null, messages);
	return translated.trim();
}
