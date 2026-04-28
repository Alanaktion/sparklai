<script lang="ts">
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import ModelSwitcher from '$lib/components/ModelSwitcher.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import { twMerge } from 'tailwind-merge';
	import Sparkles from 'virtual:icons/octicon/sparkles-fill-24';
	import type { LayoutProps } from './$types';
	import { resolve } from '$app/paths';

	let { data, children }: LayoutProps = $props();
</script>

<div class="flex">
	<aside
		class={twMerge([
			'sticky h-svh overflow-y-auto',
			'shrink-0 border-r border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800',
			page.params.id
				? 'hidden w-64 sm:flex sm:flex-col'
				: 'flex w-full flex-col sm:w-64 sm:flex-col'
		])}
	>
		<nav class="flex min-h-full flex-col">
			<a href={resolve('/')} class="mb-2 self-start p-2 text-blue-600 lg:mb-4 dark:text-blue-400">
				<span class="sr-only">SparklAI</span>
				<Sparkles class="size-6 text-amber-500 dark:text-amber-400" />
			</a>
			{#each data.users as user (user.id)}
				<a
					href={resolve(`/chat/${user.id}`)}
					class={twMerge([
						'flex h-16 items-center gap-2 border-b border-gray-200 px-2 py-1 dark:border-gray-700',
						page.params.id == String(user.id)
							? 'bg-blue-600 text-white dark:bg-blue-800'
							: 'hover:bg-gray-100 dark:hover:bg-gray-700'
					])}
				>
					<Avatar {user} class="size-10 shrink-0" />
					<div class="min-w-0">
						<div class="font-medium">{user.name}</div>
						{#if user.chats.length}
							<div class="line-clamp-2 text-xs opacity-65">{user.chats[0].body}</div>
						{/if}
					</div>
				</a>
			{/each}

			{#if browser}
				<div class="@container mt-auto">
					<ModelSwitcher />
				</div>
			{/if}
		</nav>
	</aside>
	<main class={twMerge(['min-w-0 flex-1', !page.params.id && 'hidden sm:block'])}>
		{@render children()}
	</main>
</div>
