<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import Avatar from '$lib/components/Avatar.svelte';
	import AvatarPicker from '$lib/components/AvatarPicker.svelte';
	import TabsItem from '$lib/components/base/tabs-item.svelte';
	import type { ImageType, UserType } from '$lib/server/db/schema';
	import Chat from 'virtual:icons/fluent-color/chat-24';
	import type { LayoutProps } from './$types';
	import { setUserProfileContext, type UserProfileState } from '$lib/user-profile-context';

	let { data, children }: LayoutProps = $props();

	let bio_tab = $state('bio');

	let profileState = $state<UserProfileState>({
		user: {} as UserType,
		images: [],
		avatarRenderKey: 0
	});

	setUserProfileContext(profileState);

	let user = $derived(profileState.user);
	let images = $derived(profileState.images);

	let isOwner = $derived(data.isOwner ?? false);
	const activeCreator = $derived(
		(data as { activeCreator?: { id: number } | null }).activeCreator ?? null
	);
	const isImagesRoute = $derived(page.url.pathname.endsWith('/images'));
	const isEditRoute = $derived(page.url.pathname.endsWith('/edit'));

	$effect(() => {
		profileState.user = structuredClone(data.user);
		profileState.images = data.images;
	});

	$effect(() => {
		if (!profileState.user.location) {
			profileState.user.location = { city: '', state_province: '', country: '' };
		}
	});

	let relationships = $derived<
		Array<{
			id: number;
			name: string;
			pronouns: string;
			image_id: number | null;
			relationship_type: string | null;
			description: string | null;
		}>
	>(data.relationships);

	function handleAvatarChange(imageId: number, image?: Partial<ImageType>) {
		profileState.user.image_id = imageId;
		if (
			image &&
			!profileState.images.some(
				(existingImage: Partial<ImageType>) => existingImage.id === image.id
			)
		) {
			profileState.images = [...profileState.images, image];
		}
		profileState.avatarRenderKey += 1;
	}

	function routeTabClass(active: boolean) {
		return `cursor-pointer border-b-2 ${active ? 'border-blue-500' : 'border-transparent'}`;
	}
</script>

<svelte:head>
	<title>{user.name}</title>
</svelte:head>

<div class="mx-auto my-4 max-w-2xl px-4">
	<header
		class="rounded border-b border-gray-200 bg-gray-50 p-4 shadow-lg shadow-gray-500/10 dark:border-gray-700 dark:bg-gray-800 dark:shadow-gray-900/20"
	>
		<div class="flex items-center gap-4">
			<AvatarPicker {user} {images} onAvatarChange={handleAvatarChange} />
			<div class="ms-auto text-end">
				<h1 class="text-xl font-semibold text-gray-800 dark:text-gray-200">{user.name}</h1>
				<p class="text-sm text-gray-400">
					{user.pronouns} &middot; {user.occupation}
				</p>
			</div>
			{#if activeCreator && isOwner}
				<span
					class="rounded bg-blue-100 px-2 py-1 text-xs text-blue-600 dark:bg-blue-900 dark:text-blue-400"
					>your AI</span
				>
			{/if}
			<a
				href={resolve(`/chat/${user.id}`)}
				class="rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				<span class="sr-only">Messages</span>
				<Chat class="size-6" />
			</a>
		</div>
	</header>

	<section class="px-6 py-4">
		<div class="flex items-center gap-3 font-semibold text-gray-800 dark:text-gray-200">
			<TabsItem bind:active={bio_tab} value="bio">Bio</TabsItem>
			<TabsItem bind:active={bio_tab} value="detail">Detail</TabsItem>
			<TabsItem bind:active={bio_tab} value="interests">Interests</TabsItem>
			<TabsItem bind:active={bio_tab} value="relationships">Relationships</TabsItem>
		</div>
		<div class="font-sm grid gap-1 py-4 text-gray-700 dark:text-gray-400">
			{#if bio_tab == 'bio'}
				<p class="whitespace-pre-wrap">{user.bio}</p>
			{:else if bio_tab == 'detail'}
				<p>
					{[user.location?.city, user.location?.state_province, user.location?.country]
						.filter(Boolean)
						.join(', ')}
				</p>
				{#if user.writing_style}
					<p class="text-sm">{user.writing_style}</p>
				{/if}
			{:else if bio_tab == 'interests'}
				<ul class="list-inside list-disc">
					{#each user.interests || [] as interest (interest)}
						<li>{interest}</li>
					{/each}
				</ul>
			{:else if bio_tab == 'relationships'}
				<div class="grid gap-4">
					<div>
						<h3 class="mb-2 font-semibold text-gray-800 dark:text-gray-200">
							Relationships ({relationships.length})
						</h3>
						{#if relationships.length > 0}
							<div class="grid gap-2">
								{#each relationships as relationship (relationship.id)}
									<a
										href={resolve(`/users/${relationship.id}`)}
										class="flex items-center gap-2 rounded p-2 hover:bg-gray-100 dark:hover:bg-gray-700"
									>
										<Avatar user={relationship} class="size-8" />
										<div class="flex-1">
											<div class="text-sm font-medium text-gray-800 dark:text-gray-200">
												{relationship.name}
											</div>
											<div class="text-xs text-gray-500">{relationship.pronouns}</div>
											{#if relationship.relationship_type}
												<div class="text-xs text-gray-600 dark:text-gray-400">
													{relationship.relationship_type}
												</div>
											{/if}
											{#if relationship.description}
												<div class="mt-1 text-xs text-gray-600 dark:text-gray-400">
													{relationship.description}
												</div>
											{/if}
										</div>
									</a>
								{/each}
							</div>
						{:else}
							<p class="text-sm text-gray-500">No relationships defined</p>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	</section>

	<section class="px-6 py-4">
		<div
			class="mb-4 flex items-center gap-3 text-xl font-semibold text-gray-800 dark:text-gray-200"
		>
			<a href={resolve(`/users/${data.id}`)} class={routeTabClass(!isImagesRoute && !isEditRoute)}
				>Posts</a
			>
			<a href={resolve(`/users/${data.id}/images`)} class={routeTabClass(isImagesRoute)}>Images</a>
			{#if isOwner}
				<a href={resolve(`/users/${data.id}/edit`)} class={routeTabClass(isEditRoute)}>Edit</a>
			{/if}
		</div>

		{@render children()}
	</section>
</div>
