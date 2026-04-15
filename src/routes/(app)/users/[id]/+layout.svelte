<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import Avatar from '$lib/components/Avatar.svelte';
	import AvatarPicker from '$lib/components/AvatarPicker.svelte';
	import TabsItem from '$lib/components/base/tabs-item.svelte';
	import type { ImageType, UserType } from '$lib/server/db/schema';
	import Chat from 'virtual:icons/fluent-color/chat-24';
	import Loader from 'virtual:icons/lucide/loader';
	import type { LayoutProps } from './$types';
	import { setUserProfileContext, type UserProfileState } from '$lib/user-profile-context';

	let { data, children }: LayoutProps = $props();

	let bio_tab = $state('bio');
	let saving = $state(false);

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

	const saveMetadata = async (e: Event) => {
		e.preventDefault();
		saving = true;
		try {
			const response = await fetch(resolve(`/users/${data.id}`), {
				method: 'PATCH',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(profileState.user)
			});
			if (response.ok) {
				profileState.user = await response.json();
			}
		} finally {
			saving = false;
		}
	};
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
			<TabsItem bind:active={bio_tab} value="edit">Edit</TabsItem>
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
			{:else if bio_tab == 'edit'}
				<form class="grid gap-4 py-2" onsubmit={saveMetadata}>
					<!-- Basic Information -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">Basic Information</h3>
						<div class="grid gap-2 sm:grid-cols-2">
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Name</span>
								<input
									type="text"
									bind:value={user.name}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
									required
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Age</span>
								<input
									type="number"
									bind:value={user.age}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
									required
								/>
							</label>
						</div>
						<div class="grid gap-2 sm:grid-cols-2">
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Pronouns</span>
								<input
									type="text"
									bind:value={user.pronouns}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
									required
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Occupation</span>
								<input
									type="text"
									bind:value={user.occupation}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
						</div>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400">Relationship Status</span>
							<input
								type="text"
								bind:value={user.relationship_status}
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400">Bio</span>
							<textarea
								bind:value={user.bio}
								rows="4"
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
							></textarea>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400">Backstory (private)</span>
							<textarea
								bind:value={user.backstory}
								rows="3"
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
							></textarea>
						</label>
					</div>

					<!-- Location -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">Location</h3>
						<div class="grid gap-2 sm:grid-cols-3">
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">City</span>
								<input
									type="text"
									bind:value={user.location!.city}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">State/Province</span>
								<input
									type="text"
									bind:value={user.location!.state_province}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Country</span>
								<input
									type="text"
									bind:value={user.location!.country}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
						</div>
					</div>

					<!-- Interests -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">Interests</h3>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400"
								>Comma-separated list of interests</span
							>
							<input
								type="text"
								value={user.interests?.join(', ') || ''}
								oninput={(e) => {
									user.interests = e.currentTarget.value
										.split(',')
										.map((s) => s.trim())
										.filter((s) => s.length > 0);
								}}
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
							/>
						</label>
					</div>

					<!-- Personality Traits -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">Personality</h3>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400"
								>Describe this person's personality in 2–4 sentences</span
							>
							<textarea
								bind:value={user.personality_traits}
								rows="4"
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								placeholder="e.g. Warm and sociable, she lights up any room she walks into. She's deeply empathetic but can be overly self-critical when things go wrong. Driven by a need to help others, sometimes at the expense of her own needs."
							></textarea>
						</label>
					</div>

					<!-- Writing Style -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">Writing Style</h3>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400"
								>Describe how this person writes in 1–3 sentences</span
							>
							<textarea
								bind:value={user.writing_style}
								rows="3"
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								placeholder="e.g. Writes casually in English with light Spanish phrases; uses ellipses a lot and rarely capitalizes properly. Moderate emoji use, mostly reactions. Doesn't bother with punctuation in texts."
							></textarea>
						</label>
					</div>

					<!-- Appearance -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">Appearance</h3>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400"
								>Describe this person's physical appearance in 2–4 sentences</span
							>
							<textarea
								bind:value={user.appearance}
								rows="4"
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								placeholder="e.g. Tall and slim with warm brown skin and natural 4C hair worn in a loose afro. Dark brown eyes with long lashes and a wide smile. Usually dressed in colorful thrifted outfits — bold prints, wide-leg trousers, and statement earrings."
							></textarea>
						</label>
					</div>

					<!-- System Flags -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">System Flags</h3>
						<div class="flex gap-4">
							<label class="flex items-center gap-2">
								<input
									type="checkbox"
									bind:checked={user.is_active}
									class="rounded border-gray-300 dark:border-gray-600"
								/>
								<span class="text-sm text-gray-600 dark:text-gray-400">Is Active</span>
							</label>
						</div>
					</div>

					<!-- Save Button -->
					<div class="flex justify-end gap-2">
						{#if saving}
							<Loader class="size-4 animate-spin text-gray-600 dark:text-gray-400" />
						{:else}
							<button
								type="submit"
								class="rounded-2xl px-4 py-2 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
							>
								Save Changes
							</button>
						{/if}
					</div>
				</form>
			{/if}
		</div>
	</section>

	<section class="px-6 py-4">
		<div
			class="mb-4 flex items-center gap-3 text-xl font-semibold text-gray-800 dark:text-gray-200"
		>
			<a href={resolve(`/users/${data.id}`)} class={routeTabClass(!isImagesRoute)}>Posts</a>
			<a href={resolve(`/users/${data.id}/images`)} class={routeTabClass(isImagesRoute)}>Images</a>
		</div>

		{@render children()}
	</section>
</div>
