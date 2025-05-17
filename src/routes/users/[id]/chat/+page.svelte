<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { Ellipsis, Loader, WandSparkles } from 'lucide-svelte';

	import type { PageProps } from './$types';
	let { data }: PageProps = $props();

	import { loadJson } from '$lib/api';

	import Avatar from '$lib/components/Avatar.svelte';
	import ChatMessage from '$lib/components/ChatMessage.svelte';

	let user = $state(data.user);
	let chats = $state([]);
	onMount(async () => {
		loadJson(`chats/${user.id}`).then((body) => {
			chats = body;
		});
	});

	let timeoutId: number;
	function debounce(callback: CallableFunction, delay = 5e3) {
		return function () {
			clearTimeout(timeoutId);
			timeoutId = setTimeout(() => {
				callback();
			}, delay);
		};
	}
	onDestroy(() => clearTimeout(timeoutId));
	function change() {
		// TODO: cancel handler if user starts typing again so they can queue up a few messages.
		clearTimeout(timeoutId);
	}

	function respond() {
		responding = true;
		loadJson(`chats/${user.id}/respond`, { method: 'POST' })
			.then((body) => {
				responding = false;
				chats.push(body);
			})
			.catch(() => (responding = false));
	}

	let responding = $state(false);
	const debouncedResponse = debounce(respond);

	let form;
	let message = $state('');
	function submit(e: SubmitEvent) {
		e.preventDefault();
		loadJson(`chats/${user.id}`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `message=${encodeURIComponent(message)}`
		}).then((body) => {
			chats.push(body);
			debouncedResponse();
		});
		message = '';
	}
</script>

<svelte:head>
	<title>Chat with {user && user.name}</title>
</svelte:head>

{#if user}
	<div
		class="sticky top-0 my-2 flex flex-col items-center bg-white/80 py-2 backdrop-blur dark:bg-slate-800/80"
	>
		<Avatar {user} />
		<a href="/users/{user.id}">{user.name}</a>
	</div>
{/if}

<div class="mx-auto my-4 max-w-3xl px-4">
	<div class="flex flex-col gap-2">
		{#each chats as chat}
			<ChatMessage {chat} />
		{/each}
		{#if responding}
			<div class="self-start rounded-2xl bg-slate-50 px-3 pt-2 dark:bg-slate-900">
				<Ellipsis class="size-6 animate-bounce text-slate-500" />
			</div>
		{/if}
	</div>

	<form
		bind:this={form}
		onsubmit={submit}
		class="sticky bottom-0 mt-6 flex items-center gap-2 bg-white/80 py-2 backdrop-blur dark:bg-slate-800/80"
	>
		{#if responding}
			<Loader class="mx-1 size-4 animate-spin text-slate-600 dark:text-slate-400" />
		{:else}
			<button
				onclick={respond}
				type="button"
				class="rounded p-1 text-sm text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
			>
				<span class="sr-only">Add AI response</span>
				<WandSparkles class="size-4" />
			</button>
		{/if}
		<input
			autocomplete="off"
			bind:value={message}
			onchange={change}
			name="message"
			autofocus
			class="flex w-full rounded-2xl border border-slate-500 bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-slate-300 focus:border-sky-600 focus-visible:ring-1 focus-visible:ring-sky-500 focus-visible:outline-none disabled:opacity-50"
			type="text"
			placeholder="Message"
		/>
		<button
			type="submit"
			class="rounded-2xl px-2 py-1 text-sm text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
		>
			Send
		</button>
	</form>
</div>
