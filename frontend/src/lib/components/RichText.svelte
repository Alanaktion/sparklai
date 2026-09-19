<script lang="ts">
	import { parseMessage, type Span } from '$lib/markdown';

	type Props = { text: string };

	let { text }: Props = $props();

	const blocks = $derived(parseMessage(text));
</script>

{#snippet spans(list: Span[])}
	{#each list as span}
		{#if span.type === 'text'}{span.value}{:else if span.type === 'em'}<em
				>{@render spans(span.children)}</em
			>{:else if span.type === 'strong'}<strong>{@render spans(span.children)}</strong
			>{:else if span.type === 'del'}<del>{@render spans(span.children)}</del
			>{:else if span.type === 'code'}<code>{span.value}</code>{/if}
	{/each}
{/snippet}

<div class="rich">
	{#each blocks as block}
		{#if block.type === 'code'}
			<pre><code>{block.value}</code></pre>
		{:else if block.type === 'quote'}
			<blockquote>{@render spans(block.spans)}</blockquote>
		{:else}
			<p>{@render spans(block.spans)}</p>
		{/if}
	{/each}
</div>

<style>
	.rich > :global(*:first-child) {
		margin-top: 0;
	}

	.rich > :global(*:last-child) {
		margin-bottom: 0;
	}

	p,
	blockquote {
		margin: 0 0 0.55rem;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	blockquote {
		padding-left: 0.7rem;
		border-left: 2px solid var(--border);
		color: var(--muted);
	}

	em {
		font-style: italic;
	}

	strong {
		font-weight: 650;
	}

	del {
		color: var(--muted);
	}

	code {
		padding: 0.05rem 0.3rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 4px;
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.9em;
	}

	pre {
		margin: 0 0 0.55rem;
		padding: 0.5rem 0.6rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		overflow-x: auto;
	}

	pre code {
		padding: 0;
		background: none;
		border: none;
	}
</style>
