<script lang="ts">
	import { browser } from '$app/environment';
	import type { ImageType, PostType, UserType } from '$lib/server/db/schema';
	import { Loader } from 'lucide-svelte';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();

	import Chat from '$lib/icons/Chat.svelte';
	import ImageIcon from '$lib/icons/Image.svelte';
	import SlideTextSparkle from '$lib/icons/SlideTextSparkle.svelte';

	import TabsItem from '$lib/components/base/tabs-item.svelte';

	import AvatarPicker from '$lib/components/AvatarPicker.svelte';
	import Image from '$lib/components/Image.svelte';
	import Post from '$lib/components/Post.svelte';
	import Dialog from '$lib/components/base/dialog.svelte';

	let bio_tab = $state('bio');

	let tab = $state('posts');
	let user = $state<UserType>(data.user);
	let posts = $state<PostType[]>(data.posts);
	let images = $state<Partial<ImageType>[]>(data.images);

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
							<div class="flex gap-2">
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
			</div>
		{/if}
	</section>
</div>
