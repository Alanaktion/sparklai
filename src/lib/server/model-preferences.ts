import {
	fetch_models as fetchChatModels,
	get_model as getChatModel,
	init as initChatModel,
	model as currentChatModel
} from '$lib/server/chat';
import {
	backend as sdBackend,
	fetch_models as fetchSdModels,
	init as initSdModel,
	init_style as initSdStyle,
	model as currentSdModel,
	style as currentSdStyle,
	supportsModelSelection
} from '$lib/server/sd';
import { sdStyleNames, type SDStyle } from '$lib/server/sd/types';
import type { Cookies } from '@sveltejs/kit';

export const chatModelCookieName = 'chat_model';
export const sdStyleCookieName = 'sd_style';
export const sdModelCookieName = 'sd_model';

const cookieOptions = {
	path: '/',
	httpOnly: true,
	sameSite: 'lax' as const
};

type ChatModel = Awaited<ReturnType<typeof fetchChatModels>>[number];
type SDModel = Awaited<ReturnType<typeof fetchSdModels>>[number];

function normalizeCookieValue(value: string | null | undefined) {
	const normalized = value?.trim();
	return normalized ? normalized : null;
}

function parseSdStyle(value: string | null | undefined): SDStyle | null {
	if (!value) {
		return null;
	}

	return sdStyleNames.find((styleName) => styleName === value) ?? null;
}

function pickChatModel(
	requestedModel: string | null,
	chatModels: ChatModel[],
	fallbackModel: string
) {
	if (requestedModel && chatModels.some((model) => model.id === requestedModel)) {
		return requestedModel;
	}

	if (chatModels.some((model) => model.id === fallbackModel)) {
		return fallbackModel;
	}

	return chatModels[0]?.id ?? '';
}

function pickSdModel(requestedModel: string | null, sdModels: SDModel[], fallbackModel: string) {
	if (requestedModel && sdModels.some((model) => model.model_name === requestedModel)) {
		return requestedModel;
	}

	if (sdModels.some((model) => model.model_name === fallbackModel)) {
		return fallbackModel;
	}

	return sdModels[0]?.model_name ?? '';
}

export async function applyModelPreferences(cookies: Cookies) {
	const requestedChatModel = normalizeCookieValue(cookies.get(chatModelCookieName));
	if (requestedChatModel && requestedChatModel !== currentChatModel) {
		initChatModel(requestedChatModel);
	}

	const requestedSdStyle = parseSdStyle(cookies.get(sdStyleCookieName));
	if (requestedSdStyle && requestedSdStyle !== currentSdStyle) {
		await initSdStyle(requestedSdStyle);
	}

	if (!supportsModelSelection()) {
		return;
	}

	const requestedSdModel = normalizeCookieValue(cookies.get(sdModelCookieName));
	if (requestedSdModel && requestedSdModel !== currentSdModel) {
		await initSdModel(requestedSdModel);
	}
}

export async function getModelPreferences(cookies: Cookies) {
	const chat_models = await fetchChatModels();
	const fallbackChatModel = await getChatModel();
	const chat_model = pickChatModel(
		normalizeCookieValue(cookies.get(chatModelCookieName)),
		chat_models,
		fallbackChatModel
	);

	const sd_models = await fetchSdModels();
	const sd_style = parseSdStyle(cookies.get(sdStyleCookieName)) ?? currentSdStyle;
	const sd_model = supportsModelSelection()
		? pickSdModel(normalizeCookieValue(cookies.get(sdModelCookieName)), sd_models, currentSdModel)
		: currentSdModel;

	return {
		chat_models,
		chat_model,
		sd_backend: sdBackend,
		sd_model,
		sd_models,
		sd_style,
		sd_styles: [...sdStyleNames],
		sd_supports_model_selection: supportsModelSelection()
	};
}

export function setChatModelPreference(cookies: Cookies, model: string | null | undefined) {
	const normalized = normalizeCookieValue(model);
	if (!normalized) {
		cookies.delete(chatModelCookieName, { path: cookieOptions.path });
		return;
	}

	cookies.set(chatModelCookieName, normalized, cookieOptions);
}

export function setSdStylePreference(cookies: Cookies, style: string | null | undefined) {
	const normalized = parseSdStyle(style);
	if (!normalized) {
		cookies.delete(sdStyleCookieName, { path: cookieOptions.path });
		return;
	}

	cookies.set(sdStyleCookieName, normalized, cookieOptions);
}

export function setSdModelPreference(cookies: Cookies, model: string | null | undefined) {
	if (!supportsModelSelection()) {
		cookies.delete(sdModelCookieName, { path: cookieOptions.path });
		return;
	}

	const normalized = normalizeCookieValue(model);
	if (!normalized) {
		cookies.delete(sdModelCookieName, { path: cookieOptions.path });
		return;
	}

	cookies.set(sdModelCookieName, normalized, cookieOptions);
}

export function clearSdModelPreference(cookies: Cookies) {
	cookies.delete(sdModelCookieName, { path: cookieOptions.path });
}
