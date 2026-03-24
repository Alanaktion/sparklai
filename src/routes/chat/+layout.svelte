<script lang="ts">
	import { page } from '$app/state';
	import Avatar from '$lib/components/Avatar.svelte';
	import { twMerge } from 'tailwind-merge';
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
		<nav class="flex flex-col">
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
							<div class="truncate text-xs opacity-65">{user.chats[0].body}</div>
						{/if}
					</div>
				</a>
			{/each}
		</nav>
	</aside>
	<main class={twMerge(['min-w-0 flex-1', !page.params.id && 'hidden sm:block'])}>
		{@render children()}
	</main>
</div>
