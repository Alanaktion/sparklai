<script lang="ts">
	import { tick, onMount } from 'svelte';
	import { MessageSquareMore } from 'lucide-svelte';
	import Avatar from './Avatar.svelte';
	import PostImage from './PostImage.svelte';

	let { post, user, full = false } = $props();
	let imgClass = full ? '' : 'object-cover aspect-16/9';

	function formatISODate(isoDate: string) {
		const now = new Date();
		const date = new Date(`${isoDate}-00:00`);

		const seconds = (now.getTime() - date.getTime()) / 1000;
		if (seconds < 60) {
			return 'just now';
		} else if (seconds < 3600) {
			return `${Math.floor(seconds / 60)} minute${seconds >= 120 ? 's' : ''} ago`;
		} else if (seconds < 86400) {
			return `${Math.floor(seconds / 3600)} hour${seconds >= 3600 * 2 ? 's' : ''} ago`;
		}
		return date.toLocaleString();
	}

	onMount(() => setInterval(tick, 10e3));
</script>

<div class="mb-4 flex items-start gap-4 px-4 sm:px-0 lg:mb-6">
	<a class="min-w-12" href="/users/{post.user_id}">
		<Avatar {user} />
	</a>
	<div>
		<a
			class="font-medium text-sky-600 hover:underline dark:text-sky-400"
			href="/users/{post.user_id}"
		>
			{user?.name}
		</a>
		{#if post.image_id}
			<div class="my-3">
				<PostImage src="/images/{post.image_id}" class="w-full rounded {imgClass}" />
			</div>
		{/if}
		<p class="mb-2 whitespace-pre-wrap">{post.body}</p>
		<div class="flex items-center gap-2 border-t border-slate-200 py-2 dark:border-slate-700">
			<a href="/posts/{post.id}" class="mr-auto pr-4 text-sm text-slate-400">
				{formatISODate(post.created_at)}
			</a>
			{#if !full}
				<a
					href="/posts/{post.id}"
					class="flex items-center gap-1 rounded px-2 py-1 text-sm text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
				>
					<MessageSquareMore class="size-4" />
					Comments
				</a>
			{/if}
		</div>
	</div>
</div>
