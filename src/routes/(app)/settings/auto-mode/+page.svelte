<script lang="ts">
	import { onDestroy, onMount, untrack } from 'svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import CheckCircle from 'virtual:icons/octicon/check-circle-24';
	import Alert from 'virtual:icons/octicon/alert-24';
	import { resolve } from '$app/paths';
	import type { PageProps } from './$types';

	// Feature-specific response shapes, defined here rather than in `$lib/types.ts` — matches how
	// `ModelPreferencesResponse`/`ImageGenerationJobResponse` are handled (see that file's header
	// comment): only "core" entity shapes are centralized there.
	type CreatorAutoModeSettings = {
		enabled: boolean;
		tick_interval_seconds: number;
		max_posts_per_tick: number;
		max_comments_per_tick: number;
	};
	type UserAutoModeSettings = {
		user_id: number;
		auto_post_enabled: boolean;
		auto_comment_enabled: boolean;
		post_frequency_per_day: number;
		comment_frequency_per_day: number;
	};
	type UserAutoModeItem = {
		user_id: number;
		name: string;
		image_id: number | null;
		settings: UserAutoModeSettings;
	};
	type AutoModeBundle = {
		creator_settings: CreatorAutoModeSettings;
		users: UserAutoModeItem[];
	};
	type AutoModeActivityItem = {
		kind: 'post' | 'comment';
		id: number;
		user_id: number;
		user_name: string;
		post_id: number | null;
		body: string;
		created_at: string | null;
	};

	const DEFAULT_CREATOR_SETTINGS: CreatorAutoModeSettings = {
		enabled: false,
		tick_interval_seconds: 300,
		max_posts_per_tick: 2,
		max_comments_per_tick: 5
	};
	const ACTIVITY_REFRESH_MS = 10000;

	let { data }: PageProps = $props();
	// Snapshotted once into locally-editable state (rather than tracked reactively) — every
	// subsequent change goes through `saveCreatorSettings`/`saveUserSettings`/`refreshActivity`
	// instead, same as `ModelSwitcher.svelte`'s fetch-then-locally-own-it pattern. `untrack` marks
	// that one-time read as intentional so Svelte doesn't warn about capturing a prop's initial
	// value only.
	const bundle: AutoModeBundle | null = untrack(() => data.bundle);

	let creatorSettings = $state<CreatorAutoModeSettings>(
		bundle?.creator_settings ?? DEFAULT_CREATOR_SETTINGS
	);
	let users = $state<UserAutoModeItem[]>(bundle?.users ?? []);
	let activity = $state<AutoModeActivityItem[]>(untrack(() => data.activity) ?? []);
	let feedbackMsg = $state('');
	let hasError = $state(false);
	let activityTimer: ReturnType<typeof setInterval> | undefined;

	function showError(message: string) {
		hasError = true;
		feedbackMsg = message;
	}

	function showSuccess() {
		hasError = false;
		feedbackMsg = '';
	}

	async function saveCreatorSettings() {
		try {
			const response = await fetch('/api/auto-mode', {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(creatorSettings)
			});
			if (response.ok) {
				creatorSettings = await response.json();
				showSuccess();
			} else {
				showError('Failed to update auto-mode settings.');
			}
		} catch {
			showError('Failed to update auto-mode settings.');
		}
	}

	async function saveUserSettings(item: UserAutoModeItem) {
		try {
			const response = await fetch(`/api/auto-mode/users/${item.user_id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(item.settings)
			});
			if (response.ok) {
				item.settings = await response.json();
				showSuccess();
			} else {
				showError(`Failed to update settings for ${item.name}.`);
			}
		} catch {
			showError(`Failed to update settings for ${item.name}.`);
		}
	}

	async function refreshActivity() {
		const response = await fetch('/api/auto-mode/activity');
		if (response.ok) {
			activity = (await response.json()).items;
		}
	}

	onMount(() => {
		activityTimer = setInterval(refreshActivity, ACTIVITY_REFRESH_MS);
	});

	onDestroy(() => {
		if (activityTimer) clearInterval(activityTimer);
	});
</script>

<svelte:head>
	<title>Auto Mode Settings</title>
</svelte:head>

<div class="mx-auto my-8 max-w-4xl px-4">
	<header class="mb-6">
		<h1 class="text-3xl font-bold text-gray-900 dark:text-gray-100">Auto Mode</h1>
		<p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
			Let your characters post and comment on their own in the background, on a schedule you
			control.
		</p>
	</header>

	{#if !bundle}
		<div
			class="rounded-lg border border-gray-200 bg-white p-8 text-center shadow-md dark:border-gray-700 dark:bg-gray-800"
		>
			<p class="mb-3 text-2xl">🤖</p>
			<h2 class="mb-2 text-lg font-semibold text-gray-900 dark:text-gray-100">No active creator</h2>
			<p class="text-sm text-gray-500 dark:text-gray-400">
				Select or create a creator account using the user switcher in the top navigation first.
			</p>
		</div>
	{:else}
		<div
			class="mb-6 rounded-lg border border-gray-200 bg-white p-6 shadow-md dark:border-gray-700 dark:bg-gray-800"
		>
			<div class="mb-4 flex items-center justify-between">
				<div>
					<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Master switch</h2>
					<p class="text-sm text-gray-500 dark:text-gray-400">
						Turns the background scheduler on or off for your own roster.
					</p>
				</div>
				<label class="inline-flex cursor-pointer items-center gap-2">
					<input
						type="checkbox"
						bind:checked={creatorSettings.enabled}
						onchange={saveCreatorSettings}
						class="size-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
					/>
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300">
						{creatorSettings.enabled ? 'On' : 'Off'}
					</span>
				</label>
			</div>

			<div class="grid gap-4 md:grid-cols-3">
				<div>
					<label
						for="tickInterval"
						class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Check interval (seconds)
					</label>
					<input
						id="tickInterval"
						type="number"
						min="30"
						step="30"
						bind:value={creatorSettings.tick_interval_seconds}
						onchange={saveCreatorSettings}
						class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
					/>
				</div>
				<div>
					<label
						for="maxPosts"
						class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Max posts per check
					</label>
					<input
						id="maxPosts"
						type="number"
						min="0"
						bind:value={creatorSettings.max_posts_per_tick}
						onchange={saveCreatorSettings}
						class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
					/>
				</div>
				<div>
					<label
						for="maxComments"
						class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Max comments per check
					</label>
					<input
						id="maxComments"
						type="number"
						min="0"
						bind:value={creatorSettings.max_comments_per_tick}
						onchange={saveCreatorSettings}
						class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
					/>
				</div>
			</div>

			{#if feedbackMsg}
				<div
					class="mt-4 flex items-center gap-2 rounded-md p-3 {hasError
						? 'bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400'
						: 'bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400'}"
				>
					{#if hasError}
						<Alert class="size-5" />
					{:else}
						<CheckCircle class="size-5" />
					{/if}
					<span class="text-sm font-medium">{feedbackMsg}</span>
				</div>
			{/if}
		</div>

		<div
			class="mb-6 rounded-lg border border-gray-200 bg-white p-6 shadow-md dark:border-gray-700 dark:bg-gray-800"
		>
			<h2 class="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">Characters</h2>
			{#if users.length === 0}
				<p class="text-sm text-gray-500 dark:text-gray-400">No active characters yet.</p>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm">
						<thead>
							<tr
								class="border-b border-gray-200 text-gray-500 dark:border-gray-700 dark:text-gray-400"
							>
								<th class="py-2 pr-4 font-medium">Character</th>
								<th class="py-2 pr-4 font-medium">Auto-post</th>
								<th class="py-2 pr-4 font-medium">Posts/day</th>
								<th class="py-2 pr-4 font-medium">Auto-comment</th>
								<th class="py-2 pr-4 font-medium">Comments/day</th>
							</tr>
						</thead>
						<tbody>
							{#each users as item (item.user_id)}
								<tr class="border-b border-gray-100 dark:border-gray-800">
									<td class="py-2 pr-4">
										<div class="flex items-center gap-2">
											<Avatar user={item} class="size-8" />
											<span class="text-gray-900 dark:text-gray-100">{item.name}</span>
										</div>
									</td>
									<td class="py-2 pr-4">
										<input
											type="checkbox"
											bind:checked={item.settings.auto_post_enabled}
											onchange={() => saveUserSettings(item)}
											class="size-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
										/>
									</td>
									<td class="py-2 pr-4">
										<input
											type="number"
											min="0"
											step="0.1"
											bind:value={item.settings.post_frequency_per_day}
											onchange={() => saveUserSettings(item)}
											class="w-20 rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
										/>
									</td>
									<td class="py-2 pr-4">
										<input
											type="checkbox"
											bind:checked={item.settings.auto_comment_enabled}
											onchange={() => saveUserSettings(item)}
											class="size-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
										/>
									</td>
									<td class="py-2 pr-4">
										<input
											type="number"
											min="0"
											step="0.1"
											bind:value={item.settings.comment_frequency_per_day}
											onchange={() => saveUserSettings(item)}
											class="w-20 rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
										/>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>

		<div
			class="rounded-lg border border-gray-200 bg-white p-6 shadow-md dark:border-gray-700 dark:bg-gray-800"
		>
			<h2 class="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">Recent activity</h2>
			{#if activity.length === 0}
				<p class="text-sm text-gray-500 dark:text-gray-400">Nothing generated yet.</p>
			{:else}
				<ul class="space-y-3">
					{#each activity as item (`${item.kind}-${item.id}`)}
						<li class="text-sm">
							<span class="font-medium text-gray-900 dark:text-gray-100">{item.user_name}</span>
							<span class="text-gray-500 dark:text-gray-400">
								{item.kind === 'post' ? 'posted' : 'commented'}:
							</span>
							<span class="text-gray-700 dark:text-gray-300">{item.body}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<div class="mt-6">
			<a
				href={resolve('/settings')}
				class="text-sm text-gray-600 underline hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
			>
				Back to Profile Settings
			</a>
		</div>
	{/if}
</div>
