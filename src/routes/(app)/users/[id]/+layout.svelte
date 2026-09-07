<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import Avatar from '$lib/components/Avatar.svelte';
	import AvatarPicker from '$lib/components/AvatarPicker.svelte';
	import TabsItem from '$lib/components/base/tabs-item.svelte';
	import type { ImageType, UserType } from '$lib/types';
	import Chat from 'virtual:icons/octicon/comment-discussion-24';
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

	type RelationshipItem = {
		relationship_id: number;
		id: number;
		name: string;
		pronouns: string;
		image_id: number | null;
		relationship_type: string | null;
		description: string | null;
	};
	let relationships = $derived<RelationshipItem[]>(data.relationships);

	type RelationshipCandidate = { id: number; name: string; is_active: boolean };
	const creatorUsers = $derived<RelationshipCandidate[]>(
		(data as { creatorUsers?: RelationshipCandidate[] }).creatorUsers ?? []
	);
	let availableRelationshipTargets = $derived(
		creatorUsers.filter(
			(candidate) =>
				candidate.is_active &&
				candidate.id !== user.id &&
				!relationships.some((rel) => rel.id === candidate.id)
		)
	);

	const EMPTY_RELATIONSHIP_FORM = {
		related_user_id: '' as number | '',
		relationship_type: '',
		description: '',
		mutual: true,
		reverse_relationship_type: '',
		reverse_description: ''
	};
	let relationshipForm = $state({ ...EMPTY_RELATIONSHIP_FORM });
	let editingRelationshipId = $state<number | null>(null);
	let relationshipSubmitting = $state(false);
	let relationshipError = $state('');

	function startEditRelationship(relationship: RelationshipItem) {
		editingRelationshipId = relationship.relationship_id;
		relationshipForm = {
			...EMPTY_RELATIONSHIP_FORM,
			related_user_id: relationship.id,
			relationship_type: relationship.relationship_type ?? '',
			description: relationship.description ?? ''
		};
		relationshipError = '';
	}

	function cancelEditRelationship() {
		editingRelationshipId = null;
		relationshipForm = { ...EMPTY_RELATIONSHIP_FORM };
		relationshipError = '';
	}

	async function submitRelationship(e: SubmitEvent) {
		e.preventDefault();
		relationshipSubmitting = true;
		relationshipError = '';
		try {
			const response = editingRelationshipId
				? await fetch(`/api/users/${user.id}/relationships/${editingRelationshipId}`, {
						method: 'PATCH',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							relationship_type: relationshipForm.relationship_type || null,
							description: relationshipForm.description || null
						})
					})
				: await fetch(`/api/users/${user.id}/relationships`, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							related_user_id: relationshipForm.related_user_id,
							relationship_type: relationshipForm.relationship_type || null,
							description: relationshipForm.description || null,
							mutual: relationshipForm.mutual,
							reverse_relationship_type: relationshipForm.reverse_relationship_type || null,
							reverse_description: relationshipForm.reverse_description || null
						})
					});
			if (response.ok) {
				cancelEditRelationship();
				await invalidateAll();
			} else {
				const body = await response.json().catch(() => null);
				relationshipError = body?.detail || 'Failed to save relationship.';
			}
		} catch {
			relationshipError = 'Failed to save relationship.';
		} finally {
			relationshipSubmitting = false;
		}
	}

	async function removeRelationship(relationship: RelationshipItem) {
		if (!confirm(`Remove relationship with ${relationship.name}?`)) {
			return;
		}
		const response = await fetch(
			`/api/users/${user.id}/relationships/${relationship.relationship_id}`,
			{ method: 'DELETE' }
		);
		if (response.ok) {
			await invalidateAll();
		}
	}

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
								{#each relationships as relationship (relationship.relationship_id)}
									<div
										class="flex items-center gap-2 rounded p-2 hover:bg-gray-100 dark:hover:bg-gray-700"
									>
										<a
											href={resolve(`/users/${relationship.id}`)}
											class="flex flex-1 items-center gap-2"
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
										{#if isOwner}
											<div class="flex shrink-0 items-center gap-1">
												<button
													type="button"
													onclick={() => startEditRelationship(relationship)}
													class="rounded p-1 text-xs text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-600"
												>
													Edit
												</button>
												<button
													type="button"
													onclick={() => removeRelationship(relationship)}
													class="rounded p-1 text-xs text-red-500 hover:bg-red-100 dark:hover:bg-red-900"
												>
													Remove
												</button>
											</div>
										{/if}
									</div>
								{/each}
							</div>
						{:else}
							<p class="text-sm text-gray-500">No relationships defined</p>
						{/if}
					</div>

					{#if isOwner}
						<div class="rounded border border-gray-200 p-3 dark:border-gray-700">
							<h4 class="mb-2 text-sm font-semibold text-gray-800 dark:text-gray-200">
								{editingRelationshipId ? 'Edit relationship' : 'Add relationship'}
							</h4>
							<form class="grid gap-2" onsubmit={submitRelationship}>
								{#if !editingRelationshipId}
									<select
										bind:value={relationshipForm.related_user_id}
										required
										class="rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
									>
										<option value="" disabled>Choose a character…</option>
										{#each availableRelationshipTargets as candidate (candidate.id)}
											<option value={candidate.id}>{candidate.name}</option>
										{/each}
									</select>
									{#if availableRelationshipTargets.length === 0}
										<p class="text-xs text-gray-500 dark:text-gray-400">
											No other characters available to link — every active character you own already
											has a relationship with this one.
										</p>
									{/if}
								{/if}
								<input
									type="text"
									bind:value={relationshipForm.relationship_type}
									placeholder="Relationship type (e.g. best friend, sibling)"
									class="rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 placeholder-gray-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
								/>
								<textarea
									bind:value={relationshipForm.description}
									rows="2"
									placeholder="Description (optional)"
									class="rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 placeholder-gray-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
								></textarea>
								{#if !editingRelationshipId}
									<label class="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
										<input type="checkbox" bind:checked={relationshipForm.mutual} />
										Also add the matching relationship on their profile
									</label>
									{#if relationshipForm.mutual}
										<div
											class="grid gap-2 rounded border border-dashed border-gray-300 p-2 dark:border-gray-600"
										>
											<p class="text-xs text-gray-500 dark:text-gray-400">
												Leave blank to mirror the same type/description on their side (e.g. "best
												friend"). Fill in only if it reads differently from their side — e.g. you're
												adding your "child", they'd call you their "parent".
											</p>
											<input
												type="text"
												bind:value={relationshipForm.reverse_relationship_type}
												placeholder="Their label for you (optional)"
												class="rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 placeholder-gray-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
											/>
											<textarea
												bind:value={relationshipForm.reverse_description}
												rows="2"
												placeholder="Their description of this (optional)"
												class="rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 placeholder-gray-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
											></textarea>
										</div>
									{/if}
								{/if}
								{#if relationshipError}
									<p class="text-xs text-red-600 dark:text-red-400">{relationshipError}</p>
								{/if}
								<div class="flex gap-2">
									<button
										type="submit"
										disabled={relationshipSubmitting ||
											(!editingRelationshipId && !relationshipForm.related_user_id)}
										class="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
									>
										{editingRelationshipId ? 'Save' : 'Add'}
									</button>
									{#if editingRelationshipId}
										<button
											type="button"
											onclick={cancelEditRelationship}
											class="rounded px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
										>
											Cancel
										</button>
									{/if}
								</div>
							</form>
						</div>
					{/if}
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
