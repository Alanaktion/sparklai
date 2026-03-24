<script lang="ts">
	import type { ChatType } from '$lib/server/db/schema';
	import Dialog from '$lib/components/base/dialog.svelte';
	import { twMerge } from 'tailwind-merge';

	type ChatMessageType = ChatType & {
		image?: {
			blur: boolean;
		} | null;
	};

	const {
		chat,
		prevChat = undefined,
		nextChat = undefined,
		ondelete
	}: {
		chat: ChatMessageType;
		prevChat?: ChatMessageType;
		nextChat?: ChatMessageType;
		ondelete?: (chat: ChatMessageType) => void;
	} = $props();

	let prefix = $derived.by(() => {
		const d2 = new Date(`${chat.created_at}Z`);
		let diff;
		if (!prevChat) {
			diff = Date.now() - d2.getTime();
			if (diff < 43200e3) {
				return null;
			}
		} else {
			const d1 = new Date(`${prevChat.created_at}Z`);
			diff = d2.getTime() - d1.getTime();
		}
		if (diff > 43200e3) {
			return d2.toLocaleString(undefined, {
				weekday: 'short',
				day: diff > 43200e4 ? 'numeric' : undefined,
				month: diff > 43200e4 ? 'short' : undefined,
				hour: 'numeric',
				minute: '2-digit'
			});
		}
		if (diff > 900e3) {
			return d2.toLocaleTimeString(undefined, {
				hour: 'numeric',
				minute: '2-digit'
			});
		}
	});

	let rounded = $derived.by(() => {
		const classes: string[] = [];
		if (prevChat && prevChat.role == chat.role) {
			classes.push(chat.role == 'user' ? 'rounded-tr-sm' : 'rounded-tl-sm');
			classes.push('-mt-1');
		}
		if (nextChat && nextChat.role == chat.role) {
			classes.push(chat.role == 'user' ? 'rounded-br-sm' : 'rounded-bl-sm');
			classes.push('md:-mb-1');
		}
		if ((!nextChat || nextChat.role != chat.role) && (!prevChat || prevChat.role != chat.role)) {
			classes.push(chat.role == 'user' ? 'rounded-br-sm' : 'rounded-bl-sm');
		}
		return classes;
	});

	let confirmation = $state(false);
	const delete_message = () => {
		confirmation = false;
		ondelete?.(chat);
	};
</script>

{#if prefix}
	<div
		class={twMerge([
			'mt-4 text-sm text-gray-600 first:mt-2 md:mt-6 lg:mt-8 dark:text-gray-400',
			chat.role == 'user' && 'self-end',
			chat.role == 'assistant' && 'self-start'
		])}
	>
		{prefix}
	</div>
{/if}

<div
	class={twMerge([
		'group flex gap-2',
		chat.role == 'user' && 'flex-row-reverse self-end',
		chat.role == 'assistant' && 'self-start'
	])}
>
	<div
		class={twMerge([
			'max-w-lg rounded-3xl px-4 py-2',
			chat.role == 'user' && 'bg-blue-600 text-white dark:bg-blue-800',
			chat.role == 'assistant' && 'bg-gray-50 dark:bg-gray-800',
			...rounded
		])}
	>
		<p class="text-pretty whitespace-pre-wrap">{chat.body}</p>
	</div>
	{#if ondelete}
		<button
			class="relative size-6 cursor-pointer rounded-full bg-gray-200 leading-none text-black opacity-0 transition-opacity group-hover:opacity-100 dark:bg-gray-700 dark:text-white"
			type="button"
			onclick={() => (confirmation = true)}
			title="Delete message"
		>
			<span class="sr-only">Delete message</span>
			<span aria-hidden="true">&times;</span>
		</button>
	{/if}
</div>

{#if chat.image_id}
	<div
		class={twMerge([
			'relative max-w-sm overflow-hidden rounded',
			chat.role == 'user' && 'self-end',
			chat.role == 'assistant' && 'self-start'
		])}
	>
		<img src="/images/{chat.image_id}" alt="" class="w-full" loading="lazy" />
		{#if chat.image?.blur}
			<div class="absolute inset-0 backdrop-blur-xl"></div>
		{/if}
	</div>
{/if}

<Dialog bind:open={confirmation} title="Delete message">
	<p>Are you sure you want to delete this message?</p>
	<div class="mt-4 flex gap-3">
		<button
			type="button"
			onclick={() => (confirmation = false)}
			class="cursor-pointer rounded bg-gray-300 px-2 py-1 dark:bg-gray-700"
		>
			Cancel
		</button>
		<button
			type="button"
			onclick={delete_message}
			class="cursor-pointer rounded bg-rose-600 px-2 py-1 text-white"
		>
			Delete
		</button>
	</div>
</Dialog>
