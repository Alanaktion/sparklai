import {
	applyModelPreferences,
	clearSdModelPreference,
	getModelPreferences,
	setChatModelPreference,
	setSdModelPreference,
	setSdStylePreference
} from '$lib/server/model-preferences';
import { json } from '@sveltejs/kit';

export async function GET({ cookies }) {
	await applyModelPreferences(cookies);
	return json(await getModelPreferences(cookies));
}

export async function POST({ request, cookies }) {
	const body = await request.json().catch(() => ({}));

	if ('chat_model' in body) {
		setChatModelPreference(cookies, body.chat_model);
	}

	if ('sd_style' in body) {
		setSdStylePreference(cookies, body.sd_style);
		clearSdModelPreference(cookies);
	}

	if ('sd_model' in body) {
		setSdModelPreference(cookies, body.sd_model);
	}

	await applyModelPreferences(cookies);
	return json(await getModelPreferences(cookies));
}
