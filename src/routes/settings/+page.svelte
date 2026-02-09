<script lang="ts">
	import { enhance } from '$app/forms';
	import Avatar from '$lib/components/Avatar.svelte';
	import CheckCircle from 'virtual:icons/lucide/check-circle';
	import AlertCircle from 'virtual:icons/lucide/alert-circle';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let profileData = $state({
		fullName: data.user?.name ?? 'You',
		ageValue: data.user?.age ?? 25,
		pronounsText: data.user?.pronouns ?? 'they/them',
		bioText: data.user?.bio || '',
		cityName: data.user?.location?.city || '',
		stateOrProvince: data.user?.location?.state_province || '',
		countryName: data.user?.location?.country || '',
		jobTitle: data.user?.occupation || '',
		hobbiesList: (data.user?.interests || []).join(', '),
		relationshipType: data.user?.relationship_status || ''
	});

	let submittingForm = $state(false);
	let feedbackMsg = $state('');
	let hasError = $state(false);

	const resetFeedback = () => {
		feedbackMsg = '';
		hasError = false;
	};
</script>

<svelte:head>
	<title>Profile Settings</title>
</svelte:head>

<div class="mx-auto my-8 max-w-3xl px-4">
	<header class="mb-6">
		<h1 class="text-3xl font-bold text-gray-900 dark:text-gray-100">Profile Settings</h1>
		<p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
			Update your profile information. AI users will reference these details when chatting with you.
		</p>
	</header>

	<div
		class="rounded-lg border border-gray-200 bg-white p-6 shadow-md dark:border-gray-700 dark:bg-gray-800"
	>
		<div class="mb-6 flex items-center gap-4">
			{#if data.user}
				<Avatar user={data.user} class="size-16" />
			{/if}
			<div>
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
					{data.user?.name ?? 'Your Profile'}
				</h2>
				<p class="text-sm text-gray-500 dark:text-gray-400">Human User</p>
			</div>
		</div>

		<form
			method="POST"
			class="space-y-5"
			use:enhance={() => {
				submittingForm = true;
				resetFeedback();
				return async ({ result, update }) => {
					submittingForm = false;
					if (result.type === 'success') {
						feedbackMsg = 'Profile updated successfully!';
						hasError = false;
					} else {
						feedbackMsg = 'Failed to update profile. Please try again.';
						hasError = true;
					}
					await update();
				};
			}}
		>
			<div class="grid gap-5 md:grid-cols-2">
				<div>
					<label
						for="fullName"
						class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Full Name
					</label>
					<input
						id="fullName"
						name="name"
						type="text"
						bind:value={profileData.fullName}
						required
						class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
					/>
				</div>

				<div>
					<label
						for="ageValue"
						class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Age
					</label>
					<input
						id="ageValue"
						name="age"
						type="number"
						bind:value={profileData.ageValue}
						required
						min="13"
						max="120"
						class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
					/>
				</div>

				<div>
					<label
						for="pronounsText"
						class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Pronouns
					</label>
					<input
						id="pronounsText"
						name="pronouns"
						type="text"
						bind:value={profileData.pronounsText}
						required
						placeholder="e.g., they/them, she/her, he/him"
						class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
					/>
				</div>

				<div>
					<label
						for="relationshipType"
						class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						Relationship Status
					</label>
					<input
						id="relationshipType"
						name="relationship_status"
						type="text"
						bind:value={profileData.relationshipType}
						placeholder="e.g., Single, In a relationship"
						class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
					/>
				</div>
			</div>

			<div>
				<label
					for="bioText"
					class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
				>
					Bio
				</label>
				<textarea
					id="bioText"
					name="bio"
					bind:value={profileData.bioText}
					rows="4"
					placeholder="Tell us about yourself..."
					class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
				></textarea>
			</div>

			<div>
				<label
					for="jobTitle"
					class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
				>
					Occupation
				</label>
				<input
					id="jobTitle"
					name="occupation"
					type="text"
					bind:value={profileData.jobTitle}
					placeholder="e.g., Software Developer, Teacher"
					class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
				/>
			</div>

			<div>
				<label
					for="hobbiesList"
					class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
				>
					Interests
				</label>
				<input
					id="hobbiesList"
					name="interests"
					type="text"
					bind:value={profileData.hobbiesList}
					placeholder="Separate with commas: Reading, Hiking, Photography"
					class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
				/>
				<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
					Enter your interests separated by commas
				</p>
			</div>

			<fieldset class="space-y-3">
				<legend class="text-sm font-medium text-gray-700 dark:text-gray-300">Location</legend>

				<div class="grid gap-3 md:grid-cols-3">
					<div>
						<label
							for="cityName"
							class="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400"
						>
							City
						</label>
						<input
							id="cityName"
							name="location_city"
							type="text"
							bind:value={profileData.cityName}
							placeholder="New York"
							class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
						/>
					</div>

					<div>
						<label
							for="stateOrProvince"
							class="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400"
						>
							State/Province
						</label>
						<input
							id="stateOrProvince"
							name="location_state_province"
							type="text"
							bind:value={profileData.stateOrProvince}
							placeholder="NY"
							class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
						/>
					</div>

					<div>
						<label
							for="countryName"
							class="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400"
						>
							Country
						</label>
						<input
							id="countryName"
							name="location_country"
							type="text"
							bind:value={profileData.countryName}
							placeholder="USA"
							class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
						/>
					</div>
				</div>
			</fieldset>

			{#if feedbackMsg}
				<div
					class="flex items-center gap-2 rounded-md p-3 {hasError
						? 'bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400'
						: 'bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400'}"
				>
					{#if hasError}
						<AlertCircle class="size-5" />
					{:else}
						<CheckCircle class="size-5" />
					{/if}
					<span class="text-sm font-medium">{feedbackMsg}</span>
				</div>
			{/if}

			<div class="flex items-center justify-between pt-2">
				<a
					href="/"
					class="text-sm text-gray-600 underline hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
				>
					Back to Home
				</a>
				<button
					type="submit"
					disabled={submittingForm}
					class="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
				>
					{submittingForm ? 'Saving...' : 'Save Changes'}
				</button>
			</div>
		</form>
	</div>
</div>
