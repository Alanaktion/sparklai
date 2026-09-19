<script lang="ts">
	import type { Message, SwipeDirection } from '$lib/api';

	type Props = {
		message: Message;
		speaker: string;
		busy?: boolean;
		showRegenerate?: boolean;
		onSwipe: (direction: SwipeDirection) => void;
		onEdit: (content: string) => Promise<void>;
		onDelete: () => void;
		onRegenerate: () => void;
	};

	let {
		message,
		speaker,
		busy = false,
		showRegenerate = false,
		onSwipe,
		onEdit,
		onDelete,
		onRegenerate
	}: Props = $props();

	let editing = $state(false);
	let draft = $state('');

	function startEdit() {
		draft = message.content;
		editing = true;
	}

	async function save() {
		const value = draft.trim();
		if (!value) return;
		try {
			await onEdit(value);
			editing = false;
		} catch {
			// The page surfaces the failure; keep the editor open so nothing is lost.
		}
	}
</script>

<article
	class="message"
	class:user={message.role === 'user'}
	class:assistant={message.role === 'assistant'}
	class:system={message.role === 'system'}
>
	<p class="speaker">{speaker}</p>

	{#if editing}
		<textarea bind:value={draft} rows="4" aria-label="Edit message"></textarea>
		<div class="actions">
			<button class="primary" onclick={save} disabled={busy}>Save</button>
			<button onclick={() => (editing = false)} disabled={busy}>Cancel</button>
		</div>
	{:else}
		<p class="content">{message.content}</p>
		<div class="actions">
			{#if message.swipe_count > 1}
				<button aria-label="Previous variant" onclick={() => onSwipe('prev')} disabled={busy}>
					‹
				</button>
				<span class="swipes">{message.swipe_index + 1}/{message.swipe_count}</span>
				<button aria-label="Next variant" onclick={() => onSwipe('next')} disabled={busy}>
					›
				</button>
			{/if}
			{#if showRegenerate}
				<button onclick={onRegenerate} disabled={busy}>Regenerate</button>
			{/if}
			<button onclick={startEdit} disabled={busy}>Edit</button>
			<button class="danger" onclick={onDelete} disabled={busy}>Delete</button>
		</div>
	{/if}
</article>

<style>
	.message {
		max-width: 44rem;
		padding: 0.6rem 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.user {
		align-self: flex-end;
		background: var(--surface-2);
	}

	.system {
		align-self: center;
		font-style: italic;
	}

	.speaker {
		margin: 0 0 0.3rem;
		font-size: 0.72rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted);
	}

	.content {
		margin: 0;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-top: 0.5rem;
	}

	.actions button {
		padding: 0.2rem 0.5rem;
		font-size: 0.8rem;
	}

	.swipes {
		font-size: 0.8rem;
		color: var(--muted);
	}
</style>
