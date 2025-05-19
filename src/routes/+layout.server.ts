import type { LayoutServerLoad } from './$types';
import { fetch_models as fetch_chat_models, model as chat_model } from '$lib/server/chat';
import { fetch_models as fetch_sd_models, model as sd_model } from '$lib/server/sd';

export const load: LayoutServerLoad = async () => {
	return {
		chat_models: await fetch_chat_models(),
		chat_model,
		sd_models: await fetch_sd_models(),
		sd_model
	};
};
