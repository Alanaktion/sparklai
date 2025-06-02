<script lang="ts">
	import { formatDate, localDateTime } from '$lib';
	import CommentMultiple from 'virtual:icons/fluent-color/comment-multiple-24';
	import ChevronDown from 'virtual:icons/lucide/chevron-down';
	import { onMount, tick } from 'svelte';
	import Avatar from './Avatar.svelte';
	import PostImage from './PostImage.svelte';

	let { post, user, full = false } = $props();
	let imgClass = full ? '' : 'object-cover aspect-16/9';

	let body = $state<HTMLElement>();
	let height = $state(0);
	let showExpand = $state(false);
	let expanded = $state(false);
	onMount(() => {
		setInterval(tick, 10e3);
		if (height > 400 && !full) {
			showExpand = true;
		}
	});
</script>

<div class="mb-4 flex items-start gap-4 px-4 sm:px-0 lg:mb-6">
	<a class="min-w-12" href="/users/{post.user_id}">
		<Avatar {user} />
	</a>
	<div>
		<a
			class="font-medium text-blue-600 hover:underline dark:text-blue-400"
			href="/users/{post.user_id}"
		>
			{user?.name}
		</a>
		{#if post.image_id}
			<div class="my-3">
				<PostImage
					src="/images/{post.image_id}"
					image={post.image}
					class="w-full rounded {imgClass}"
				/>
			</div>
		{/if}
		{#if post.media_id && post.media.type.startsWith('audio/')}
			<audio controls class="block w-full mb-4">
				<source src="/media/{post.media_id}" type={post.media.type} />
			</audio>
		{/if}
		{#if post.media_id && post.media.type.startsWith('video/')}
			<!-- svelte-ignore a11y_media_has_caption -->
			<video controls class="block w-full mb-4">
				<source src="/media/{post.media_id}" type={post.media.type} />
			</video>
		{/if}
		<div
			class={['relative mb-2', showExpand && !expanded && 'max-h-96 overflow-hidden']}
			bind:this={body}
			bind:offsetHeight={height}
		>
			<p class="whitespace-pre-wrap">{post.body}</p>
			{#if showExpand && !expanded}
				<div
					class="from:transparent pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-b to-white dark:to-gray-900"
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
				href="/posts/{post.id}"
				class="mr-auto pr-4 text-sm text-gray-400"
				title={localDateTime(post.created_at)}
			>
				<time datetime={post.created_at}>{formatDate(post.created_at)}</time>
			</a>
			{#if !full}
				<a
					href="/posts/{post.id}"
					class="flex items-center gap-1 rounded px-2 py-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900 dark:hover:text-blue-300"
				>
					<CommentMultiple class="size-4" />
					Comments
				</a>
			{/if}
		</div>
	</div>
</div>
