<script lang="ts">
	import { browser } from '$app/environment';
	import type { ImageType, PostType, UserType } from '$lib/server/db/schema';
	import Loader from 'virtual:icons/lucide/loader';
	import Ratio from 'virtual:icons/lucide/ratio';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();

	import Chat from 'virtual:icons/fluent-color/chat-24';
	import ImageIcon from 'virtual:icons/fluent-color/image-24';
	import SlideTextSparkle from 'virtual:icons/fluent-color/slide-text-sparkle-24';

	import Avatar from '$lib/components/Avatar.svelte';
	import TabsItem from '$lib/components/base/tabs-item.svelte';

	import AvatarPicker from '$lib/components/AvatarPicker.svelte';
	import Image from '$lib/components/Image.svelte';
	import Post from '$lib/components/Post.svelte';
	import Dialog from '$lib/components/base/dialog.svelte';

	let bio_tab = $state('bio');
	let saving = $state(false);

	let tab = $state('posts');
	let user = $state<UserType>(data.user);
	let posts = $state<PostType[]>(data.posts);
	let images = $state<Partial<ImageType>[]>(data.images);

	// Initialize nested objects if they don't exist
	$effect(() => {
		if (!user.location) {
			user.location = { city: '', state_province: '', country: '' };
		}
		if (!user.personality_traits) {
			user.personality_traits = {
				openness: 3,
				conscientiousness: 3,
				extraversion: 3,
				agreeableness: 3,
				neuroticism: 3
			};
		}
		if (!user.writing_style) {
			user.writing_style = {
				languages: [],
				emoji_frequency: 0,
				formality: '',
				puncuation_style: '',
				slang_usage: ''
			};
		}
		if (!user.appearance) {
			user.appearance = {
				gender_expression: '',
				body_type: '',
				height: '',
				hair: { color: '', style: '', length: '' },
				eyes: { color: '', shape: '' },
				skin_tone: '',
				facial_features: [],
				clothing_style: '',
				accessories: []
			};
		}
		if (!user.appearance.hair) {
			user.appearance.hair = { color: '', style: '', length: '' };
		}
		if (!user.appearance.eyes) {
			user.appearance.eyes = { color: '', shape: '' };
		}
	});

	let relationships = $state<
		Array<{
			id: number;
			name: string;
			pronouns: string;
			image_id: number | null;
			relationship_type: string | null;
			description: string | null;
		}>
	>(data.relationships);

	let creating = $state(false);
	let open = $state(false);
	let prompt = $state('');
	let aspect = $state('square');
	const newPost = (e: Event) => {
		e.preventDefault();
		creating = true;
		fetch(`/users/${data.id}/posts`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `prompt=${encodeURIComponent(prompt)}`
		})
			.then((response) => response.json())
			.then((body) => {
				posts = [body, ...posts];
				creating = false;
				open = false;
				prompt = '';
			})
			.catch(() => {
				creating = false;
			});
	};
	const newImage = (e: Event) => {
		e.preventDefault();
		creating = true;
		fetch(`/users/${data.id}/image`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `prompt=${encodeURIComponent(prompt)}&aspect=${aspect}`
		})
			.then((response) => response.json())
			.then((body) => {
				if (!prompt && user) {
					user.image_id = body.id;
				}
				images.push(body);
				creating = false;
				open = false;
				prompt = '';
			})
			.catch(() => {
				creating = false;
			});
	};
	const saveMetadata = async (e: Event) => {
		e.preventDefault();
		saving = true;
		try {
			const response = await fetch(`/users/${data.id}`, {
				method: 'PATCH',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(user)
			});
			if (response.ok) {
				const updatedUser = await response.json();
				user = updatedUser;
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
			<AvatarPicker {user} {images} />
			<div class="ms-auto text-end">
				<h1 class="text-xl font-semibold text-gray-800 dark:text-gray-200">{user.name}</h1>
				<p class="text-sm text-gray-400">
					{user.pronouns} &middot; {user.occupation}
				</p>
			</div>
			<a
				href="/users/{user.id}/chat"
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
				<p>{user.location?.city}, {user.location?.state_province}, {user.location?.country}</p>
				<p>
					{#each user.writing_style?.languages || [] as language}
						{language}&ensp;
					{/each}
				</p>
				<p class="whitespace-pre-wrap">{user.backstory_snippet}</p>
			{:else if bio_tab == 'interests'}
				<ul class="list-inside list-disc">
					{#each user.interests || [] as interest}
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
								{#each relationships as relationship}
									<a
										href="/users/{relationship.id}"
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
							<span class="text-xs text-gray-600 dark:text-gray-400">Backstory Snippet</span>
							<textarea
								bind:value={user.backstory_snippet}
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
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">
							Personality Traits (1-10 scale)
						</h3>
						<div class="grid gap-2">
							<label class="flex items-center justify-between gap-2">
								<span class="text-sm text-gray-600 dark:text-gray-400">Openness</span>
								<input
									type="number"
									min="1"
									max="10"
									step="0.1"
									bind:value={user.personality_traits!.openness}
									class="w-20 rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex items-center justify-between gap-2">
								<span class="text-sm text-gray-600 dark:text-gray-400">Conscientiousness</span>
								<input
									type="number"
									min="1"
									max="10"
									step="0.1"
									bind:value={user.personality_traits!.conscientiousness}
									class="w-20 rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex items-center justify-between gap-2">
								<span class="text-sm text-gray-600 dark:text-gray-400">Extraversion</span>
								<input
									type="number"
									min="1"
									max="10"
									step="0.1"
									bind:value={user.personality_traits!.extraversion}
									class="w-20 rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex items-center justify-between gap-2">
								<span class="text-sm text-gray-600 dark:text-gray-400">Agreeableness</span>
								<input
									type="number"
									min="1"
									max="10"
									step="0.1"
									bind:value={user.personality_traits!.agreeableness}
									class="w-20 rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex items-center justify-between gap-2">
								<span class="text-sm text-gray-600 dark:text-gray-400">Neuroticism</span>
								<input
									type="number"
									min="1"
									max="10"
									step="0.1"
									bind:value={user.personality_traits!.neuroticism}
									class="w-20 rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
						</div>
					</div>

					<!-- Writing Style -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">Writing Style</h3>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400"
								>Languages (comma-separated)</span
							>
							<input
								type="text"
								value={user.writing_style?.languages?.join(', ') || ''}
								oninput={(e) => {
									if (!user.writing_style) {
										user.writing_style = {
											languages: [],
											emoji_frequency: 0,
											formality: '',
											puncuation_style: '',
											slang_usage: ''
										};
									}
									user.writing_style.languages = e.currentTarget.value
										.split(',')
										.map((s) => s.trim())
										.filter((s) => s.length > 0);
								}}
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
							/>
						</label>
						<div class="grid gap-2 sm:grid-cols-2">
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Formality</span>
								<input
									type="text"
									bind:value={user.writing_style!.formality}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Emoji Frequency</span>
								<input
									type="number"
									min="0"
									max="10"
									step="0.1"
									bind:value={user.writing_style!.emoji_frequency}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
						</div>
						<div class="grid gap-2 sm:grid-cols-2">
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Slang Usage</span>
								<input
									type="text"
									bind:value={user.writing_style!.slang_usage}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Punctuation Style</span>
								<input
									type="text"
									bind:value={user.writing_style!.puncuation_style}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
						</div>
					</div>

					<!-- Appearance -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">Appearance</h3>
						<div class="grid gap-2 sm:grid-cols-2">
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Gender Expression</span>
								<input
									type="text"
									bind:value={user.appearance!.gender_expression}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Body Type</span>
								<input
									type="text"
									bind:value={user.appearance!.body_type}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
						</div>
						<div class="grid gap-2 sm:grid-cols-2">
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Height</span>
								<input
									type="text"
									bind:value={user.appearance!.height}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Skin Tone</span>
								<input
									type="text"
									bind:value={user.appearance!.skin_tone}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
						</div>
						<div class="grid gap-2 sm:grid-cols-3">
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Hair Color</span>
								<input
									type="text"
									bind:value={user.appearance!.hair!.color}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Hair Style</span>
								<input
									type="text"
									bind:value={user.appearance!.hair!.style}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Hair Length</span>
								<input
									type="text"
									bind:value={user.appearance!.hair!.length}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
						</div>
						<div class="grid gap-2 sm:grid-cols-2">
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Eye Color</span>
								<input
									type="text"
									bind:value={user.appearance!.eyes!.color}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
							<label class="flex flex-col gap-1">
								<span class="text-xs text-gray-600 dark:text-gray-400">Eye Shape</span>
								<input
									type="text"
									bind:value={user.appearance!.eyes!.shape}
									class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
								/>
							</label>
						</div>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400">Clothing Style</span>
							<input
								type="text"
								bind:value={user.appearance!.clothing_style}
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400"
								>Facial Features (comma-separated)</span
							>
							<input
								type="text"
								value={user.appearance!.facial_features?.join(', ') || ''}
								oninput={(e) => {
									if (!user.appearance) {
										user.appearance = {
											gender_expression: '',
											body_type: '',
											height: '',
											hair: { color: '', style: '', length: '' },
											eyes: { color: '', shape: '' },
											skin_tone: '',
											facial_features: [],
											clothing_style: '',
											accessories: []
										};
									}
									user.appearance.facial_features = e.currentTarget.value
										.split(',')
										.map((s) => s.trim())
										.filter((s) => s.length > 0);
								}}
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-600 dark:text-gray-400"
								>Accessories (comma-separated)</span
							>
							<input
								type="text"
								value={user.appearance!.accessories?.join(', ') || ''}
								oninput={(e) => {
									if (!user.appearance) {
										user.appearance = {
											gender_expression: '',
											body_type: '',
											height: '',
											hair: { color: '', style: '', length: '' },
											eyes: { color: '', shape: '' },
											skin_tone: '',
											facial_features: [],
											clothing_style: '',
											accessories: []
										};
									}
									user.appearance.accessories = e.currentTarget.value
										.split(',')
										.map((s) => s.trim())
										.filter((s) => s.length > 0);
								}}
								class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
							/>
						</label>
					</div>

					<!-- System Flags -->
					<div class="grid gap-3">
						<h3 class="font-semibold text-gray-800 dark:text-gray-200">System Flags</h3>
						<div class="flex gap-4">
							<label class="flex items-center gap-2">
								<input
									type="checkbox"
									bind:checked={user.is_human}
									class="rounded border-gray-300 dark:border-gray-600"
								/>
								<span class="text-sm text-gray-600 dark:text-gray-400">Is Human</span>
							</label>
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
		<div class="mb-4 flex items-center justify-between gap-4">
			<div class="flex items-center gap-3 text-xl font-semibold text-gray-800 dark:text-gray-200">
				<TabsItem bind:active={tab} value="posts">Posts</TabsItem>
				<TabsItem bind:active={tab} value="images">Images</TabsItem>
			</div>
			{#if browser}
				<button
					onclick={() => (open = true)}
					type="button"
					class="rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
				>
					<span class="sr-only">Add AI {tab == 'posts' ? 'post' : 'image'}</span>
					{#if tab == 'posts'}
						<SlideTextSparkle class="size-4" />
					{:else if tab == 'images'}
						<ImageIcon class="size-4" />
					{/if}
				</button>
				<Dialog title="Add AI {tab == 'posts' ? 'post' : 'image'}" bind:open>
					<form class="grid gap-2" onsubmit={tab == 'posts' ? newPost : newImage} method="POST">
						<textarea
							bind:value={prompt}
							name="message"
							rows="6"
							class="flex w-full rounded border border-gray-300 bg-transparent px-2 py-1 text-sm shadow-sm transition-colors placeholder:text-gray-300 focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none disabled:opacity-50 dark:border-gray-500 dark:placeholder:text-gray-600"
							placeholder="{tab == 'posts' ? 'Post' : 'Image'} prompt (optional)"
						></textarea>
						{#if tab == 'images'}
							<div class="flex items-center gap-2 rounded focus-within:ring">
								<Ratio class="size-4 text-gray-400 dark:text-gray-500" />
								<label
									class="has-checked:text-blue-600 has-checked:underline dark:has-checked:text-blue-400"
								>
									<input type="radio" class="sr-only" bind:group={aspect} value="square" />
									Square
								</label>
								<label
									class="has-checked:text-blue-600 has-checked:underline dark:has-checked:text-blue-400"
								>
									<input type="radio" class="sr-only" bind:group={aspect} value="landscape" />
									Wide
								</label>
								<label
									class="has-checked:text-blue-600 has-checked:underline dark:has-checked:text-blue-400"
								>
									<input type="radio" class="sr-only" bind:group={aspect} value="portrait" />
									Tall
								</label>
							</div>
						{/if}
						{#if creating}
							<Loader class="mx-auto my-2 size-4 animate-spin text-gray-600 dark:text-gray-400" />
						{:else}
							<button
								type="submit"
								class="rounded-2xl px-2 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
							>
								Create {tab == 'posts' ? 'Post' : 'Image'}
							</button>
						{/if}
					</form>
				</Dialog>
			{/if}
		</div>

		{#if tab == 'posts'}
			{#each posts as post}
				<Post {post} {user} />
			{/each}
		{:else if tab == 'images'}
			<div class="grid grid-cols-2 gap-2 md:grid-cols-3">
				{#each images as image}
					<Image {image} />
				{/each}
				{#if creating}
					<div class="flex aspect-square w-full bg-gray-200 dark:bg-gray-800">
						<Loader class="m-auto size-8 animate-spin text-gray-600 dark:text-gray-400" />
					</div>
				{/if}
			</div>
		{/if}
	</section>
</div>
