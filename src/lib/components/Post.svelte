<script lang="ts">
	import { formatDate, localDateTime } from '$lib';
	import { looksNonEnglish } from '$lib/language';
	import { parseInlineItalics } from '$lib/text';
	import CommentMultiple from 'virtual:icons/fluent-color/comment-multiple-24';
	import ChevronDown from 'virtual:icons/lucide/chevron-down';
	import { onMount, tick } from 'svelte';
	import Avatar from './Avatar.svelte';
	import PostImage from './PostImage.svelte';
	import { resolve } from '$app/paths';

	let { post, user, full = false } = $props();
	let imgClass = $derived(full ? '' : 'object-cover aspect-16/9');

	let height = $state(0);
	let showExpand = $state(false);
	let expanded = $state(false);
	onMount(() => {
		setInterval(tick, 10e3);
		if (height > 400 && !full) {
			showExpand = true;
		}
	});

	let translating = $state(false);
	let translatedBody = $derived(post.body_en ?? null);
	let bodySegments = $derived.by(() => parseInlineItalics(post.body));

	let shouldOfferTranslation = $derived.by(() => !translatedBody && looksNonEnglish(post.body));

	async function translatePost() {
		if (translating || translatedBody) {
			return;
		}
		translating = true;
		try {
			const response = await fetch(resolve(`/posts/${post.id}/translate`), {
				method: 'POST'
			});
			if (!response.ok) {
				return;
			}
			const body = (await response.json()) as { body_en?: string | null };
			translatedBody = body.body_en ?? null;
		} finally {
			translating = false;
		}
	}
</script>

<div class="mb-4 flex items-start gap-4 px-4 sm:px-0 lg:mb-6">
	<a class="min-w-12" href={resolve(`/users/${post.user_id}`)}>
		<Avatar {user} />
	</a>
	<div>
		<a
			class="font-medium text-blue-600 hover:underline dark:text-blue-400"
			href={resolve(`/users/${post.user_id}`)}
		>
			{user?.name}
		</a>
		{#if post.image_id}
			<div class="my-3">
				<PostImage
					src={resolve(`/images/${post.image_id}`)}
					image={post.image}
					class="w-full rounded {imgClass}"
				/>
			</div>
		{/if}
		{#if post.media_id && post.media?.type?.startsWith('audio/')}
			<audio controls class="mb-4 block w-full">
				<source src={resolve(`/media/${post.media_id}`)} type={post.media.type} />
			</audio>
		{/if}
		{#if post.media_id && post.media?.type?.startsWith('video/')}
			<video controls class="mb-4 block w-full">
				<source src={resolve(`/media/${post.media_id}`)} type={post.media.type} />
			</video>
		{/if}
		<div
			class={['relative mb-2', showExpand && !expanded && 'max-h-96 overflow-hidden']}
			bind:offsetHeight={height}
		>
			<p class="whitespace-pre-wrap">
				{#each bodySegments as segment, i (i)}
					{#if segment.italic}
						<em>{segment.text}</em>
					{:else}
						{segment.text}
					{/if}
				{/each}
			</p>
			{#if shouldOfferTranslation}
				<button
					type="button"
					onclick={translatePost}
					disabled={translating}
					class="mt-2 rounded border border-gray-300 px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100 disabled:cursor-wait disabled:opacity-60 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
				>
					{translating ? 'Translating...' : 'Translate to English'}
				</button>
			{/if}
			{#if translatedBody}
				<p class="mt-2 text-sm whitespace-pre-wrap text-gray-600 dark:text-gray-400">
					{translatedBody}
				</p>
			{/if}
			{#if showExpand && !expanded}
				<div
					class="from:transparent pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-linear-to-b to-white dark:to-gray-900"
				></div>
				<button
					type="button"
					class="absolute inset-x-0 bottom-0 flex cursor-pointer items-center justify-center hover:text-blue-500"
					onclick={() => (expanded = !expanded)}
				>
					<ChevronDown />
					Show more
				</button>
			{/if}
		</div>
		<div class="flex items-center gap-2 border-t border-gray-200 py-2 dark:border-gray-700">
			<a
				href={resolve(`/posts/${post.id}`)}
				class="mr-auto pr-4 text-sm text-gray-400"
				title={localDateTime(post.created_at)}
			>
				<time datetime={post.created_at}>{formatDate(post.created_at)}</time>
			</a>
			{#if !full}
				<a
					href={resolve(`/posts/${post.id}`)}
					class="flex items-center gap-1 rounded px-2 py-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900 dark:hover:text-blue-300"
				>
					<CommentMultiple class="size-4" />
					Comments
				</a>
			{/if}
		</div>
	</div>
</div>
