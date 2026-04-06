import { getContext, setContext } from 'svelte';
import type { ImageType, UserType } from '$lib/server/db/schema';

export type UserProfileState = {
	user: UserType;
	images: Partial<ImageType>[];
	avatarRenderKey: number;
};

const userProfileContextKey = Symbol('user-profile');

export function setUserProfileContext(state: UserProfileState) {
	setContext(userProfileContextKey, state);
	return state;
}

export function getUserProfileContext() {
	return getContext<UserProfileState>(userProfileContextKey);
}
