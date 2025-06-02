<script lang="ts">
	import { browser } from '$app/environment';
	import type { ChatType, UserType } from '$lib/server/db/schema';
	import Ellipsis from 'virtual:icons/lucide/ellipsis';
	import Loader from 'virtual:icons/lucide/loader';
	import { onDestroy, onMount } from 'svelte';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();

	import Avatar from '$lib/components/Avatar.svelte';
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import Send from 'virtual:icons/fluent-color/send-24';
	import SlideTextSparkle from 'virtual:icons/fluent-color/slide-text-sparkle-24';

	let user = $state<UserType>(data.user);
	let chats = $state<ChatType[]>([]);
	onMount(async () => {
		fetch(`/users/${user.id}/chat/messages`)
			.then((response) => response.json())
			.then((body) => {
				chats = body;
			});
	});

	let timeoutId: number | NodeJS.Timeout;
	function debounce(callback: CallableFunction, delay = 5e3) {
		return function () {
			clearTimeout(timeoutId);
			timeoutId = setTimeout(() => {
				callback();
			}, delay);
		};
	}
	onDestroy(() => clearTimeout(timeoutId));
	function onInput() {
		// TODO: should user still respond after some period of inactivity?
		clearTimeout(timeoutId);
	}

	function respond() {
		responding = true;
		fetch(`/users/${user.id}/chat/respond`, { method: 'POST' })
			.then((response) => response.json())
			.then((body) => {
				responding = false;
				chats.push(body);
			})
			.catch(() => (responding = false));
	}

	let responding = $state(false);
	const debouncedResponse = debounce(respond);

	let form = $state<HTMLFormElement>();
	let message = $state('');
	function submit(e: SubmitEvent) {
		e.preventDefault();
		fetch(`/users/${user.id}/chat/messages`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `message=${encodeURIComponent(message)}`
		})
			.then((response) => response.json())
			.then((body) => {
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
		class="sticky top-0 my-2 flex flex-col items-center bg-white/80 py-2 backdrop-blur dark:bg-gray-900/80"
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
			<div class="self-start rounded-2xl bg-gray-50 px-3 pt-2 dark:bg-gray-900">
				<Ellipsis class="size-6 animate-bounce text-gray-500" />
			</div>
		{/if}
	</div>

	{#if browser}
		<form
			bind:this={form}
			onsubmit={submit}
			class="sticky bottom-0 mt-6 flex items-center gap-2 bg-white/80 py-2 backdrop-blur dark:bg-gray-900/80"
		>
			{#if responding}
				<Loader class="mx-1 size-4 animate-spin text-gray-600 dark:text-gray-400" />
			{:else}
				<button
					onclick={respond}
					type="button"
					class="rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
				>
					<span class="sr-only">Add AI response</span>
					<SlideTextSparkle class="size-4" />
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
				class="flex w-full rounded-2xl border border-gray-500 bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-gray-300 focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none disabled:opacity-50 dark:placeholder:text-gray-600"
				type="text"
				placeholder="Message"
			/>
			<button
				type="submit"
				class="rounded-2xl px-2 py-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				<Send class="size-6" />
				<span class="sr-only">Send</span>
			</button>
		</form>
	{/if}
</div>
