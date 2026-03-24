<script lang="ts">
	import { tick } from 'svelte';
	import { afterNavigate, beforeNavigate } from '$app/navigation';
	import type { ChatType, UserType } from '$lib/server/db/schema';
	import type { PageProps } from './$types';

	import Avatar from '$lib/components/Avatar.svelte';
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import Dialog from '$lib/components/base/dialog.svelte';
	import Info from 'virtual:icons/lucide/info';
	import Loader from 'virtual:icons/lucide/loader';
	import Send from 'virtual:icons/fluent-color/send-24';
	import SlideTextSparkle from 'virtual:icons/fluent-color/slide-text-sparkle-24';
	import { resolve } from '$app/paths';

	let { data }: PageProps = $props();

	type ChatMessageType = ChatType & {
		image?: { blur: boolean } | null;
	};

	let user = $derived<UserType>(data.user);
	let chats = $state<ChatMessageType[]>([]);
	let infoOpen = $state(false);

	let responding = $state(false);
	let timeoutId: ReturnType<typeof setTimeout>;

	// Populate chats on initial load and after navigation between conversations
	afterNavigate(() => {
		chats = [];
		message = '';
		data.chats.then((result) => {
			chats = result as ChatMessageType[];
			tick().then(() => window.scrollTo(0, document.body.scrollHeight));
		});
	});

	beforeNavigate(() => {
		clearTimeout(timeoutId);
	});

	// Auto-scroll when new messages arrive or typing indicator appears, if near bottom
	$effect.pre(() => {
		void chats.length;
		void responding;
		if (typeof window === 'undefined') return;
		const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 50;
		if (nearBottom) {
			tick().then(() => window.scrollTo(0, document.body.scrollHeight));
		}
	});

	function debounce(callback: () => void, delay = 5e3) {
		return function () {
			clearTimeout(timeoutId);
			timeoutId = setTimeout(callback, delay);
		};
	}

	function onInput() {
		clearTimeout(timeoutId);
	}

	function respond() {
		responding = true;
		fetch(resolve(`/users/${user.id}/chat/respond`), { method: 'POST' })
			.then((r) => r.json())
			.then((body) => {
				responding = false;
				chats = [...chats, body as ChatMessageType];
			})
			.catch(() => (responding = false));
	}

	const debouncedResponse = debounce(respond);

	function delete_message(chat: ChatMessageType) {
		fetch(resolve(`/users/${user.id}/chat/messages/${chat.id}`), { method: 'DELETE' }).then(() => {
			chats = chats.filter((c) => c.id !== chat.id);
		});
	}

	let message = $state('');
	function submit(e: SubmitEvent) {
		e.preventDefault();
		fetch(resolve(`/users/${user.id}/chat/messages`), {
			method: 'POST',
			headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
			body: `message=${encodeURIComponent(message)}`
		})
			.then((r) => r.json())
			.then((body) => {
				chats = [...chats, body as ChatMessageType];
				debouncedResponse();
			});
		message = '';
	}
</script>

<svelte:head>
	<title>Chat with {user.name}</title>
</svelte:head>

<div class="flex min-h-svh flex-col overflow-y-scroll">
	<header
		class="sticky z-10 flex items-center gap-2 border-b border-gray-200 bg-gray-100/80 p-2 shadow-sm backdrop-blur-md dark:border-gray-700 dark:bg-gray-800/80"
	>
		<a
			href={resolve('/chat')}
			class="rounded p-1 text-blue-600 hover:bg-blue-100 sm:hidden dark:text-blue-400 dark:hover:bg-blue-900"
			aria-label="Back to conversations"
		>
			<svg
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				class="size-5"
			>
				<path d="m15 18-6-6 6-6"></path>
			</svg>
		</a>
		<Avatar {user} class="size-10" />
		<a href={resolve(`/users/${user.id}`)} class="font-medium hover:underline">{user.name}</a>
		<button
			type="button"
			class="ml-auto cursor-pointer rounded p-1 text-gray-500 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-700"
			onclick={() => (infoOpen = true)}
			aria-label="User info"
		>
			<Info class="size-5" />
		</button>
	</header>

	<div class="mx-auto w-full max-w-2xl px-4 py-4">
		{#await data.chats}
			<p class="text-center text-sm text-gray-500">Loading messages...</p>
		{:then}
			<div class="flex flex-col gap-2">
				{#each chats as chat, i (chat.id)}
					<ChatMessage
						{chat}
						prevChat={i > 0 ? chats[i - 1] : undefined}
						nextChat={i < chats.length - 1 ? chats[i + 1] : undefined}
						ondelete={delete_message}
					/>
				{/each}
				{#if responding}
					<div class="self-start rounded-2xl bg-gray-50 px-3 py-2 dark:bg-gray-800">
						<svg viewBox="0 0 24 8" class="h-4 w-10 text-gray-500 dark:text-gray-400">
							<circle
								cx="2"
								cy="4"
								r="2"
								fill="currentColor"
								style="animation: typing-dot 1.2s ease-in-out infinite"
							></circle>
							<circle
								cx="12"
								cy="4"
								r="2"
								fill="currentColor"
								style="animation: typing-dot 1.2s ease-in-out infinite 0.2s"
							></circle>
							<circle
								cx="22"
								cy="4"
								r="2"
								fill="currentColor"
								style="animation: typing-dot 1.2s ease-in-out infinite 0.4s"
							></circle>
						</svg>
					</div>
				{/if}
			</div>
		{/await}
	</div>

	<form
		class="sticky bottom-0 mt-auto flex items-center gap-2 border-t border-gray-200 bg-gray-100/80 px-2 py-2 backdrop-blur-md dark:border-gray-700 dark:bg-gray-800/80"
		onsubmit={submit}
	>
		{#if responding}
			<Loader class="mx-1 size-4 shrink-0 animate-spin text-gray-600 dark:text-gray-400" />
		{:else}
			<button
				onclick={respond}
				type="button"
				class="cursor-pointer rounded p-1 text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
				aria-label="Trigger AI response"
			>
				<SlideTextSparkle class="size-5" />
			</button>
		{/if}
		<!-- svelte-ignore a11y_autofocus -->
		<input
			autocomplete="off"
			bind:value={message}
			oninput={onInput}
			name="message"
			autofocus
			required
			class="flex w-full rounded-2xl border border-gray-400 bg-white px-3 py-1 focus:outline-blue-500 dark:border-gray-600 dark:bg-gray-900"
			type="text"
			placeholder="Message"
		/>
		<button
			type="submit"
			class="cursor-pointer rounded-2xl px-2 py-1 text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
		>
			<Send class="size-6" />
			<span class="sr-only">Send</span>
		</button>
	</form>
</div>

<Dialog bind:open={infoOpen} title={user.name}>
	{#if user.pronouns || user.age}
		<p class="text-sm text-gray-500 dark:text-gray-400">
			{user.pronouns}{user.age ? ` · ${user.age}` : ''}
		</p>
	{/if}
	{#if user.bio}
		<p class="mt-2">{user.bio}</p>
	{/if}
</Dialog>
