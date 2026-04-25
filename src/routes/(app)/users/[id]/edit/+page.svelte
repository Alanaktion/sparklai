<script lang="ts">
	import { resolve } from '$app/paths';
	import Loader from 'virtual:icons/lucide/loader';
	import type { PageProps } from './$types';
	import { getUserProfileContext } from '$lib/user-profile-context';

	let { data }: PageProps = $props();
	const profileState = getUserProfileContext();

	let saving = $state(false);
	let saveError = $state('');
	let saveSuccess = $state('');
	let dreaming = $state(false);
	let dreamError = $state('');
	let dreamSuccess = $state('');

	let user = $derived(profileState.user);

	$effect(() => {
		if (!profileState.user.location) {
			profileState.user.location = { city: '', state_province: '', country: '' };
		}
	});

	const saveMetadata = async (e: Event) => {
		e.preventDefault();
		saving = true;
		saveError = '';
		saveSuccess = '';
		try {
			const response = await fetch(resolve(`/users/${data.id}`), {
				method: 'PATCH',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(profileState.user)
			});
			if (!response.ok) {
				throw new Error('Save failed');
			}
			profileState.user = await response.json();
			saveSuccess = 'Profile saved';
		} catch {
			saveError = 'Unable to save profile right now';
		} finally {
			saving = false;
		}
	};

	const runDream = async () => {
		if (dreaming) {
			return;
		}
		dreaming = true;
		dreamError = '';
		dreamSuccess = '';
		try {
			const response = await fetch(resolve(`/api/users/${data.id}/dream`), {
				method: 'POST'
			});
			if (!response.ok) {
				throw new Error('Dream request failed');
			}
			const body = (await response.json()) as { memory?: string };
			if (typeof body.memory !== 'string') {
				throw new Error('Dream response missing memory');
			}
			profileState.user.memory = body.memory;
			dreamSuccess = 'Memory updated';
		} catch {
			dreamError = 'Unable to update memory right now';
		} finally {
			dreaming = false;
		}
	};
</script>

{#if user.location}
	<form class="grid gap-4 py-2" onsubmit={saveMetadata}>
		<!-- Basic Information -->
		<div class="grid gap-3">
			<h3 class="font-semibold text-gray-800 dark:text-gray-200">Basic Information</h3>
			<div class="grid gap-2 sm:grid-cols-2">
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-600 dark:text-gray-400">Name</span>
					<input
						type="text"
						bind:value={user.name}
						class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
						required
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-600 dark:text-gray-400">Age</span>
					<input
						type="number"
						bind:value={user.age}
						class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
						required
					/>
				</label>
			</div>
			<div class="grid gap-2 sm:grid-cols-2">
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-600 dark:text-gray-400">Pronouns</span>
					<input
						type="text"
						bind:value={user.pronouns}
						class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
						required
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-600 dark:text-gray-400">Occupation</span>
					<input
						type="text"
						bind:value={user.occupation}
						class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
					/>
				</label>
			</div>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-600 dark:text-gray-400">Relationship Status</span>
				<input
					type="text"
					bind:value={user.relationship_status}
					class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-600 dark:text-gray-400">Bio</span>
				<textarea
					bind:value={user.bio}
					rows="4"
					class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
				></textarea>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-600 dark:text-gray-400">Backstory (private)</span>
				<textarea
					bind:value={user.backstory}
					rows="3"
					class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
				></textarea>
			</label>
		</div>

		<!-- Location -->
		<div class="grid gap-3">
			<h3 class="font-semibold text-gray-800 dark:text-gray-200">Location</h3>
			<div class="grid gap-2 sm:grid-cols-3">
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-600 dark:text-gray-400">City</span>
					<input
						type="text"
						bind:value={user.location!.city}
						class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-600 dark:text-gray-400">State/Province</span>
					<input
						type="text"
						bind:value={user.location!.state_province}
						class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-600 dark:text-gray-400">Country</span>
					<input
						type="text"
						bind:value={user.location!.country}
						class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
					/>
				</label>
			</div>
		</div>

		<!-- Interests -->
		<div class="grid gap-3">
			<h3 class="font-semibold text-gray-800 dark:text-gray-200">Interests</h3>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-600 dark:text-gray-400"
					>Comma-separated list of interests</span
				>
				<input
					type="text"
					value={user.interests?.join(', ') || ''}
					oninput={(e) => {
						user.interests = e.currentTarget.value
							.split(',')
							.map((s) => s.trim())
							.filter((s) => s.length > 0);
					}}
					class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
				/>
			</label>
		</div>

		<!-- Personality Traits -->
		<div class="grid gap-3">
			<h3 class="font-semibold text-gray-800 dark:text-gray-200">Personality</h3>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-600 dark:text-gray-400"
					>Describe this person's personality in 2-4 sentences</span
				>
				<textarea
					bind:value={user.personality_traits}
					rows="4"
					class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
					placeholder="e.g. Warm and sociable, she lights up any room she walks into. She's deeply empathetic but can be overly self-critical when things go wrong. Driven by a need to help others, sometimes at the expense of her own needs."
				></textarea>
			</label>
		</div>

		<!-- Writing Style -->
		<div class="grid gap-3">
			<h3 class="font-semibold text-gray-800 dark:text-gray-200">Writing Style</h3>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-600 dark:text-gray-400"
					>Describe how this person writes in 1-3 sentences</span
				>
				<textarea
					bind:value={user.writing_style}
					rows="3"
					class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
					placeholder="e.g. Writes casually in English with light Spanish phrases; uses ellipses a lot and rarely capitalizes properly. Moderate emoji use, mostly reactions. Doesn't bother with punctuation in texts."
				></textarea>
			</label>
		</div>

		<!-- Appearance -->
		<div class="grid gap-3">
			<h3 class="font-semibold text-gray-800 dark:text-gray-200">Appearance</h3>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-600 dark:text-gray-400"
					>Describe this person's physical appearance in 2-4 sentences</span
				>
				<textarea
					bind:value={user.appearance}
					rows="4"
					class="rounded border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
					placeholder="e.g. Tall and slim with warm brown skin and natural 4C hair worn in a loose afro. Dark brown eyes with long lashes and a wide smile. Usually dressed in colorful thrifted outfits - bold prints, wide-leg trousers, and statement earrings."
				></textarea>
			</label>
		</div>

		<!-- System Flags -->
		<div class="grid gap-3">
			<h3 class="font-semibold text-gray-800 dark:text-gray-200">System Flags</h3>
			<div class="flex gap-4">
				<label class="flex items-center gap-2">
					<input
						type="checkbox"
						bind:checked={user.is_active}
						class="rounded border-gray-300 dark:border-gray-600"
					/>
					<span class="text-sm text-gray-600 dark:text-gray-400">Is Active</span>
				</label>
			</div>
		</div>

		<!-- Memory -->
		<div class="grid gap-3">
			<div class="flex items-center gap-2">
				<button
					type="button"
					onclick={runDream}
					disabled={dreaming}
					class="rounded-2xl px-4 py-2 text-sm text-blue-600 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60 dark:text-blue-400 dark:hover:bg-blue-900"
				>
					{#if dreaming}
						<span class="flex items-center gap-2">
							<Loader class="size-4 animate-spin text-gray-600 dark:text-gray-400" />
							Running Dream...
						</span>
					{:else}
						Run Dream
					{/if}
				</button>
				{#if dreamSuccess}
					<p class="text-sm text-green-600 dark:text-green-400">{dreamSuccess}</p>
				{/if}
				{#if dreamError}
					<p class="text-sm text-red-500">{dreamError}</p>
				{/if}
			</div>
			<details>
				<summary class="cursor-pointer font-semibold text-gray-800 dark:text-gray-200">
					Memory (private)
				</summary>
				<div class="mt-2 grid gap-2">
					<p class="text-xs text-gray-600 dark:text-gray-400">
						Dream updates this memory directly. It is not editable from this form.
					</p>
					<pre
						class="max-h-80 overflow-auto rounded bg-gray-100 p-2 text-sm whitespace-pre-wrap text-gray-700 dark:bg-gray-800 dark:text-gray-300">{user.memory?.trim() ||
							'(No memory yet. Click Run Dream to generate one.)'}</pre>
				</div>
			</details>
		</div>

		<div class="flex items-center justify-end gap-3">
			{#if saveSuccess}
				<p class="text-sm text-green-600 dark:text-green-400">{saveSuccess}</p>
			{/if}
			{#if saveError}
				<p class="text-sm text-red-500">{saveError}</p>
			{/if}
			{#if saving}
				<Loader class="size-4 animate-spin text-gray-600 dark:text-gray-400" />
			{:else}
				<button
					type="submit"
					class="rounded-2xl px-4 py-2 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
				>
					Save Changes
				</button>
			{/if}
		</div>
	</form>
{:else}
	<div class="flex items-center justify-center py-10">
		<Loader class="size-5 animate-spin text-gray-600 dark:text-gray-400" />
	</div>
{/if}
