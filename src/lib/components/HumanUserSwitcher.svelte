<script lang="ts">
	import type { UserType } from '$lib/server/db/schema';
	import Dialog from '$lib/components/base/dialog.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import { resolve } from '$app/paths';
	import { invalidateAll } from '$app/navigation';
	import UserIcon from 'virtual:icons/lucide/user';
	import LogOut from 'virtual:icons/lucide/log-out';
	import Plus from 'virtual:icons/lucide/plus';
	import ChevronDown from 'virtual:icons/lucide/chevron-down';
	import Loader from 'virtual:icons/lucide/loader';

	type Props = {
		humanUsers: UserType[];
		activeHumanUser: UserType | null;
	};
	let { humanUsers, activeHumanUser }: Props = $props();

	let switcherOpen = $state(false);
	let loginDialogOpen = $state(false);
	let createDialogOpen = $state(false);
	let selectedUser = $state<UserType | null>(null);

	let pin = $state('');
	let loginError = $state('');
	let loggingIn = $state(false);

	let newName = $state('');
	let newPronouns = $state('they/them');
	let newPin = $state('');
	let creating = $state(false);
	let createError = $state('');

	const openLoginDialog = (user: UserType) => {
		selectedUser = user;
		pin = '';
		loginError = '';
		loginDialogOpen = true;
		switcherOpen = false;
	};

	const login = async (e: Event) => {
		e.preventDefault();
		if (!selectedUser) return;
		loggingIn = true;
		loginError = '';
		try {
			const res = await fetch(resolve(`/api/human-users/${selectedUser.id}`), {
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
		await fetch(resolve('/api/human-users/session'), { method: 'DELETE' });
		await invalidateAll();
	};

	const createUser = async (e: Event) => {
		e.preventDefault();
		if (!newName.trim()) return;
		creating = true;
		createError = '';
		try {
			const res = await fetch(resolve('/api/human-users'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: newName.trim(), pronouns: newPronouns.trim(), pin: newPin })
			});
			if (res.ok) {
				const user: UserType = await res.json();
				createDialogOpen = false;
				newName = '';
				newPronouns = 'they/them';
				newPin = '';
				// auto-login the new user
				await fetch(resolve(`/api/human-users/${user.id}`), {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ pin: newPin })
				});
				await invalidateAll();
			} else {
				createError = 'Failed to create user';
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
		title="Switch user"
	>
		{#if activeHumanUser}
			<Avatar user={activeHumanUser} class="size-5 rounded-full" />
			<span class="max-w-24 truncate text-xs">{activeHumanUser.name}</span>
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
			{#if humanUsers.length}
				<div class="border-b border-gray-100 px-3 py-2 dark:border-gray-800">
					<p class="text-xs font-medium text-gray-400 dark:text-gray-500">Switch user</p>
				</div>
				{#each humanUsers as user (user.id)}
					<button
						type="button"
						onclick={() => openLoginDialog(user)}
						class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800 {activeHumanUser?.id ===
						user.id
							? 'text-blue-600 dark:text-blue-400'
							: 'text-gray-700 dark:text-gray-300'}"
					>
						<Avatar {user} class="size-7 rounded-full" />
						<div class="min-w-0 flex-1">
							<p class="truncate font-medium">{user.name}</p>
							<p class="text-xs text-gray-400">{user.pronouns}</p>
						</div>
						{#if activeHumanUser?.id === user.id}
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
					Add human user
				</button>
				{#if activeHumanUser}
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
<Dialog title="Sign in as {selectedUser?.name ?? ''}" bind:open={loginDialogOpen}>
	<form class="grid gap-3" onsubmit={login}>
		{#if selectedUser && !selectedUser.password_hash}
			<p class="text-sm text-gray-500 dark:text-gray-400">
				No PIN set. Press sign in to continue or enter a new PIN to set one.
			</p>
		{/if}
		<div class="grid gap-1">
			<label for="pin-input" class="text-sm font-medium text-gray-700 dark:text-gray-300">PIN</label
			>
			<input
				id="pin-input"
				type="password"
				bind:value={pin}
				placeholder="Enter PIN (leave blank if none)"
				autocomplete="off"
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

<!-- Create new human user dialog -->
<Dialog title="Add human user" bind:open={createDialogOpen}>
	<form class="grid gap-3" onsubmit={createUser}>
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
				>PIN (optional)</label
			>
			<input
				id="new-pin"
				type="password"
				bind:value={newPin}
				placeholder="Leave blank for no PIN"
				autocomplete="new-password"
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
				disabled={!newName.trim()}
				class="rounded-2xl px-2 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 disabled:opacity-40 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				Create
			</button>
		{/if}
	</form>
</Dialog>
