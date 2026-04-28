<script lang="ts">
	import { browser } from '$app/environment';
	import ModelSwitcher from '$lib/components/ModelSwitcher.svelte';
	import CreatorSwitcher from '$lib/components/CreatorSwitcher.svelte';
	import Sparkles from 'virtual:icons/octicon/sparkles-fill-24';
	import Message from 'virtual:icons/octicon/comment-discussion-16';
	import Settings from 'virtual:icons/octicon/gear-24';
	import { resolve } from '$app/paths';
	import type { LayoutProps } from './$types';

	let { children, data }: LayoutProps = $props();
</script>

<div class="flex items-center px-4 py-4">
	<a href={resolve('/')} class="me-auto text-blue-600 xl:mb-4 dark:text-blue-400">
		<span class="sr-only">SparklAI</span>
		<Sparkles class="size-6 text-amber-500 dark:text-amber-400" />
	</a>
	{#if browser}
		<CreatorSwitcher creators={data.creators} activeCreator={data.activeCreator} />
	{/if}
	<a
		href={resolve('/chat')}
		class="rounded-lg p-2 text-gray-600 transition hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
		title="Chat"
	>
		<span class="sr-only">Chat</span>
		<Message class="size-5" />
	</a>
	<a
		href={resolve('/settings')}
		class="rounded-lg p-2 text-gray-600 transition hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
		title="Profile Settings"
	>
		<span class="sr-only">Settings</span>
		<Settings class="size-5" />
	</a>
</div>

{@render children()}

{#if browser}
	<ModelSwitcher />
{/if}
