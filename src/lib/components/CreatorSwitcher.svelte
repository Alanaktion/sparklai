<script lang="ts">
	import type { CreatorType } from '$lib/server/db/schema';
	import Dialog from '$lib/components/base/dialog.svelte';
	import { resolve } from '$app/paths';
	import { invalidateAll } from '$app/navigation';
	import UserIcon from 'virtual:icons/octicon/person-16';
	import LogOut from 'virtual:icons/octicon/sign-out-16';
	import Plus from 'virtual:icons/octicon/plus-16';
	import ChevronDown from 'virtual:icons/octicon/chevron-down-16';
	import Loader from 'virtual:icons/octicon/issue-draft-16';

	type Props = {
		creators: CreatorType[];
		activeCreator: CreatorType | null;
	};
	let { creators, activeCreator }: Props = $props();

	let switcherOpen = $state(false);
	let loginDialogOpen = $state(false);
	let createDialogOpen = $state(false);
	let selectedCreator = $state<CreatorType | null>(null);

	let pin = $state('');
	let loginError = $state('');
	let loggingIn = $state(false);

	let newName = $state('');
	let newPronouns = $state('they/them');
	let newPin = $state('');
	let creating = $state(false);
	let createError = $state('');

	const openLoginDialog = (creator: CreatorType) => {
		selectedCreator = creator;
		pin = '';
		loginError = '';
		loginDialogOpen = true;
		switcherOpen = false;
	};

	const login = async (e: Event) => {
		e.preventDefault();
		if (!selectedCreator) return;
		loggingIn = true;
		loginError = '';
		try {
			const res = await fetch(resolve(`/api/creators/${selectedCreator.id}`), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ pin })
			});
			if (res.ok) {
				loginDialogOpen = false;
				pin = '';
				await invalidateAll();
			} else {
				const body = await res.json().catch(() => ({}));
				loginError = body.message ?? 'Invalid PIN';
			}
		} finally {
			loggingIn = false;
		}
	};

	const logout = async () => {
		await fetch(resolve('/api/creators/session'), { method: 'DELETE' });
		await invalidateAll();
	};

	const createCreator = async (e: Event) => {
		e.preventDefault();
		if (!newName.trim() || !newPin.trim()) return;
		creating = true;
		createError = '';
		try {
			const res = await fetch(resolve('/api/creators'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: newName.trim(), pronouns: newPronouns.trim(), pin: newPin })
			});
			if (res.ok) {
				const creator: CreatorType = await res.json();
				const savedPin = newPin;
				createDialogOpen = false;
				newName = '';
				newPronouns = 'they/them';
				newPin = '';
				// auto-login the new creator
				await fetch(resolve(`/api/creators/${creator.id}`), {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ pin: savedPin })
				});
				await invalidateAll();
			} else {
				const body = await res.json().catch(() => ({}));
				createError = body.message ?? 'Failed to create account';
			}
		} finally {
			creating = false;
		}
	};
</script>

<div class="relative">
	<button
		type="button"
		onclick={() => (switcherOpen = !switcherOpen)}
		class="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-gray-600 transition hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
		title="Switch creator"
	>
		{#if activeCreator}
			<span class="max-w-24 truncate text-xs">{activeCreator.name}</span>
		{:else}
			<UserIcon class="size-5" />
		{/if}
		<ChevronDown class="size-3.5 opacity-60" />
	</button>

	{#if switcherOpen}
		<div
			role="presentation"
			class="fixed inset-0 z-40"
			onclick={() => (switcherOpen = false)}
		></div>
		<div
			class="absolute right-0 z-50 mt-1 min-w-48 rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-900"
		>
			{#if creators.length}
				<div class="border-b border-gray-100 px-3 py-2 dark:border-gray-800">
					<p class="text-xs font-medium text-gray-400 dark:text-gray-500">Switch creator</p>
				</div>
				{#each creators as creator (creator.id)}
					<button
						type="button"
						onclick={() => openLoginDialog(creator)}
						class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800 {activeCreator?.id ===
						creator.id
							? 'text-blue-600 dark:text-blue-400'
							: 'text-gray-700 dark:text-gray-300'}"
					>
						<div class="min-w-0 flex-1">
							<p class="truncate font-medium">{creator.name}</p>
							<p class="text-xs text-gray-400">{creator.pronouns}</p>
						</div>
						{#if activeCreator?.id === creator.id}
							<span class="text-xs text-blue-500">active</span>
						{/if}
					</button>
				{/each}
			{/if}

			<div class="border-t border-gray-100 p-1 dark:border-gray-800">
				<button
					type="button"
					onclick={() => {
						switcherOpen = false;
						createDialogOpen = true;
					}}
					class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800"
				>
					<Plus class="size-4" />
					Add creator
				</button>
				{#if activeCreator}
					<button
						type="button"
						onclick={() => {
							switcherOpen = false;
							void logout();
						}}
						class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800"
					>
						<LogOut class="size-4" />
						Sign out
					</button>
				{/if}
			</div>
		</div>
	{/if}
</div>

<!-- PIN login dialog -->
<Dialog title="Sign in as {selectedCreator?.name ?? ''}" bind:open={loginDialogOpen}>
	<form class="grid gap-3" onsubmit={login}>
		<div class="grid gap-1">
			<label for="pin-input" class="text-sm font-medium text-gray-700 dark:text-gray-300">PIN</label
			>
			<input
				id="pin-input"
				type="password"
				bind:value={pin}
				placeholder="Enter your PIN"
				autocomplete="off"
				required
				class="rounded border border-gray-300 bg-transparent px-2 py-1.5 text-sm shadow-sm transition-colors focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none dark:border-gray-500"
			/>
		</div>
		{#if loginError}
			<p class="text-sm text-red-500">{loginError}</p>
		{/if}
		{#if loggingIn}
			<Loader class="mx-auto my-1 size-4 animate-spin text-gray-500" />
		{:else}
			<button
				type="submit"
				class="rounded-2xl px-2 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				Sign in
			</button>
		{/if}
	</form>
</Dialog>

<!-- Create new creator dialog -->
<Dialog title="Add creator" bind:open={createDialogOpen}>
	<form class="grid gap-3" onsubmit={createCreator}>
		<div class="grid gap-1">
			<label for="new-name" class="text-sm font-medium text-gray-700 dark:text-gray-300"
				>Name <span class="text-red-500">*</span></label
			>
			<input
				id="new-name"
				type="text"
				bind:value={newName}
				placeholder="Your name"
				required
				class="rounded border border-gray-300 bg-transparent px-2 py-1.5 text-sm shadow-sm transition-colors focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none dark:border-gray-500"
			/>
		</div>
		<div class="grid gap-1">
			<label for="new-pronouns" class="text-sm font-medium text-gray-700 dark:text-gray-300"
				>Pronouns</label
			>
			<input
				id="new-pronouns"
				type="text"
				bind:value={newPronouns}
				placeholder="they/them"
				class="rounded border border-gray-300 bg-transparent px-2 py-1.5 text-sm shadow-sm transition-colors focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none dark:border-gray-500"
			/>
		</div>
		<div class="grid gap-1">
			<label for="new-pin" class="text-sm font-medium text-gray-700 dark:text-gray-300"
				>PIN <span class="text-red-500">*</span></label
			>
			<input
				id="new-pin"
				type="password"
				bind:value={newPin}
				placeholder="Choose a PIN"
				autocomplete="new-password"
				required
				class="rounded border border-gray-300 bg-transparent px-2 py-1.5 text-sm shadow-sm transition-colors focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none dark:border-gray-500"
			/>
		</div>
		{#if createError}
			<p class="text-sm text-red-500">{createError}</p>
		{/if}
		{#if creating}
			<Loader class="mx-auto my-1 size-4 animate-spin text-gray-500" />
		{:else}
			<button
				type="submit"
				disabled={!newName.trim() || !newPin.trim()}
				class="rounded-2xl px-2 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 disabled:opacity-40 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				Create
			</button>
		{/if}
	</form>
</Dialog>
