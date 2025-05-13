<script>
	let showModal = false;
	let description = '';

	function closeModal() {
		showModal = false;
	}

	function handleSubmit() {
		// Handle the submitted description here (e.g., save it, process it)
		console.log('Description:', description);
		closeModal();
	}
</script>

<button
	class="rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
	on:click={() => (showModal = true)}
>
	Add Description
</button>

{#if showModal}
	<div
		class="bg-opacity-75 fixed top-0 left-0 flex h-full w-full items-center justify-center bg-gray-500"
	>
		<div class="max-w-md rounded bg-white p-8 shadow-lg">
			<h2 class="mb-4 text-2xl font-bold">Add Description</h2>

			<textarea
				class="w-full rounded border p-2"
				bind:value={description}
				placeholder="Enter a description..."
			></textarea>

			<div class="mt-4 flex justify-end space-x-2">
				<button
					class="rounded bg-gray-300 px-3 py-1 font-bold text-gray-800 hover:bg-gray-500"
					on:click={closeModal}
				>
					Cancel
				</button>
				<button
					class="rounded bg-green-500 px-3 py-1 font-bold text-white hover:bg-green-700"
					on:click={handleSubmit}
				>
					Save
				</button>
			</div>
		</div>
	</div>
{/if}
