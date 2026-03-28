<script lang="ts">
	import type { ChatType } from '$lib/server/db/schema';
	import { looksNonEnglish } from '$lib/language';
	import Dialog from '$lib/components/base/dialog.svelte';
	import { resolve } from '$app/paths';
	import { twMerge } from 'tailwind-merge';
	import Image from './Image.svelte';

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

	type BodySegment = {
		text: string;
		italic: boolean;
	};

	const isSingleEmojiMessage = (text: string): boolean => {
		const trimmed = text.trim();
		if (!trimmed) {
			return false;
		}

		const graphemes =
			typeof Intl.Segmenter === 'function'
				? Array.from(
						new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(trimmed),
						(s) => s.segment
					)
				: Array.from(trimmed);

		if (graphemes.length !== 1) {
			return false;
		}

		const [grapheme] = graphemes;
		return /\p{Extended_Pictographic}|\p{Regional_Indicator}|[#*0-9]\uFE0F?\u20E3/u.test(grapheme);
	};

	const parseInlineItalics = (text: string): BodySegment[] => {
		const segments: BodySegment[] = [];
		const italicPattern = /\*([^*\n]+)\*/g;
		let cursor = 0;
		let match = italicPattern.exec(text);

		while (match) {
			const start = match.index;
			const end = start + match[0].length;

			if (start > cursor) {
				segments.push({ text: text.slice(cursor, start), italic: false });
			}

			segments.push({ text: match[1], italic: true });
			cursor = end;
			match = italicPattern.exec(text);
		}

		if (cursor < text.length) {
			segments.push({ text: text.slice(cursor), italic: false });
		}

		if (segments.length === 0) {
			segments.push({ text, italic: false });
		}

		return segments;
	};

	let bodySegments = $derived.by(() => parseInlineItalics(chat.body));
	let isSingleEmoji = $derived.by(() => isSingleEmojiMessage(chat.body));
	let translating = $state(false);
	let translatedBody = $derived(chat.body_en ?? null);

	let shouldOfferTranslation = $derived.by(() => !translatedBody && looksNonEnglish(chat.body));

	async function translateChat() {
		if (translating || translatedBody) {
			return;
		}

		translating = true;
		try {
			const response = await fetch(
				resolve(`/users/${chat.user_id}/chat/messages/${chat.id}/translate`),
				{ method: 'POST' }
			);
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
			!isSingleEmoji && chat.role == 'user' && 'bg-blue-600 text-white dark:bg-blue-800',
			!isSingleEmoji && chat.role == 'assistant' && 'bg-gray-50 dark:bg-gray-800',
			isSingleEmoji && 'bg-transparent px-1 py-0 text-5xl leading-none md:text-6xl',
			...(!isSingleEmoji ? rounded : [])
		])}
	>
		<p
			class={twMerge([
				'text-pretty whitespace-pre-wrap',
				isSingleEmoji && 'leading-none whitespace-normal'
			])}
		>
			{#each bodySegments as segment, i (i)}
				{#if segment.italic}
					<em>{segment.text}</em>
				{:else}
					{segment.text}
				{/if}
			{/each}
		</p>
		{#if !isSingleEmoji && shouldOfferTranslation}
			<button
				type="button"
				onclick={translateChat}
				disabled={translating}
				class={twMerge([
					'mt-2 rounded border px-2 py-0.5 text-xs',
					chat.role == 'user' &&
						'border-blue-300/60 text-blue-100 hover:bg-blue-500/25 disabled:opacity-60 dark:border-blue-300/40',
					chat.role == 'assistant' &&
						'border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-60 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700'
				])}
			>
				{translating ? 'Translating...' : 'Translate to English'}
			</button>
		{/if}
		{#if !isSingleEmoji && translatedBody}
			<p
				class={twMerge([
					'mt-2 text-xs whitespace-pre-wrap',
					chat.role == 'user' && 'text-blue-100/90',
					chat.role == 'assistant' && 'text-gray-600 dark:text-gray-400'
				])}
			>
				{translatedBody}
			</p>
		{/if}
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
		<Image image={chat.image} />
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
