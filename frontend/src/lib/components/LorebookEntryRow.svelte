<script lang="ts">
	import type { DraftEntry } from '$lib/cardDraft';

	type Props = {
		entry: DraftEntry;
		index: number;
		total: number;
		dropTarget: boolean;
		onMove: (from: number, to: number) => void;
		onRemove: (index: number) => void;
		onDragStart: (index: number) => void;
		onDragOver: (index: number) => void;
		onDrop: (index: number) => void;
		onDragEnd: () => void;
	};

	let {
		entry,
		index,
		total,
		dropTarget,
		onMove,
		onRemove,
		onDragStart,
		onDragOver,
		onDrop,
		onDragEnd
	}: Props = $props();

	let expanded = $state(false);

	function setPosition(event: Event) {
		const value = (event.currentTarget as HTMLSelectElement).value;
		entry.position = value === 'before_char' || value === 'after_char' ? value : '';
	}
</script>

<li
	class="entry"
	class:drop-target={dropTarget}
	ondragover={(event) => {
		event.preventDefault();
		if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
		onDragOver(index);
	}}
	ondrop={(event) => {
		event.preventDefault();
		onDrop(index);
	}}
>
	<div class="head">
		<span
			class="handle"
			draggable="true"
			title="Drag to reorder"
			aria-hidden="true"
			ondragstart={(event) => {
				if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
				onDragStart(index);
			}}
			ondragend={onDragEnd}
		>
			⠿
		</span>

		<label class="inline enabled">
			<input type="checkbox" bind:checked={entry.enabled} />
			<span>Enabled</span>
		</label>

		<span class="summary">{entry.name.trim() || entry.keys.trim() || `Entry ${index + 1}`}</span>
		<span class="grow"></span>

		<button
			type="button"
			onclick={() => onMove(index, index - 1)}
			disabled={index === 0}
			aria-label={`Move entry ${index + 1} up`}
		>
			↑
		</button>
		<button
			type="button"
			onclick={() => onMove(index, index + 1)}
			disabled={index === total - 1}
			aria-label={`Move entry ${index + 1} down`}
		>
			↓
		</button>
		<button type="button" aria-expanded={expanded} onclick={() => (expanded = !expanded)}>
			{expanded ? 'Collapse' : 'Expand'}
		</button>
		<button type="button" class="danger" onclick={() => onRemove(index)}>Remove</button>
	</div>

	{#if expanded}
		<div class="body">
			<div class="grid">
				<label>
					<span>Name</span>
					<input bind:value={entry.name} />
				</label>
				<label>
					<span>Comment</span>
					<input bind:value={entry.comment} />
				</label>
			</div>

			<div class="grid">
				<label>
					<span>Keys <em>comma separated</em></span>
					<input bind:value={entry.keys} placeholder="sword, blade" />
				</label>
				<label>
					<span>Secondary keys <em>comma separated</em></span>
					<input bind:value={entry.secondaryKeys} />
				</label>
			</div>

			<label>
				<span>Content</span>
				<textarea bind:value={entry.content} rows="4"></textarea>
			</label>

			<div class="grid">
				<label>
					<span>Insertion order</span>
					<input type="number" bind:value={entry.insertionOrder} />
				</label>
				<label>
					<span>Priority</span>
					<input bind:value={entry.priority} inputmode="numeric" />
				</label>
				<label>
					<span>ID</span>
					<input bind:value={entry.id} inputmode="numeric" />
				</label>
				<label>
					<span>Position</span>
					<select value={entry.position} onchange={setPosition}>
						<option value="">Default</option>
						<option value="before_char">Before character</option>
						<option value="after_char">After character</option>
					</select>
				</label>
			</div>

			<div class="flags">
				<label class="inline">
					<input type="checkbox" bind:checked={entry.caseSensitive} />
					<span>Case sensitive</span>
				</label>
				<label class="inline">
					<input type="checkbox" bind:checked={entry.selective} />
					<span>Selective</span>
				</label>
				<label class="inline">
					<input type="checkbox" bind:checked={entry.constant} />
					<span>Constant</span>
				</label>
			</div>

			<label>
				<span>Extensions <em>JSON object</em></span>
				<textarea bind:value={entry.extensions} rows="3" spellcheck="false"></textarea>
			</label>
		</div>
	{/if}
</li>

<style>
	.entry {
		display: grid;
		gap: 0.6rem;
		padding: 0.6rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.entry.drop-target {
		border-color: var(--accent);
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}

	.handle {
		cursor: grab;
		color: var(--muted);
		user-select: none;
	}

	.summary {
		overflow: hidden;
		max-width: 22rem;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.grow {
		flex: 1;
	}

	.head button {
		padding: 0.25rem 0.5rem;
		font-size: 0.82rem;
	}

	.body {
		display: grid;
		gap: 0.6rem;
	}

	.grid {
		display: grid;
		gap: 0.6rem;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
	}

	.flags {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
	}

	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.85rem;
	}

	label em {
		margin-left: 0.3rem;
		font-style: normal;
		font-size: 0.75rem;
		color: var(--muted);
	}

	.inline {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}

	.enabled {
		font-size: 0.82rem;
	}
</style>
