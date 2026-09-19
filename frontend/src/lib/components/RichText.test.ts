import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import RichText from './RichText.svelte';

/**
 * Render the component the way a page would, and return clean markup.
 *
 * Svelte's SSR output carries hydration comments and scoped-style classes;
 * both are stripped so assertions can describe the structure that matters.
 */
function html(text: string): string {
	const body = render(RichText, { props: { text } }).body;
	return body
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\s*svelte-[\w-]+/g, '')
		.replace(/ class=""/g, '')
		.trim();
}

describe('RichText', () => {
	it('renders roleplay actions in italics', () => {
		expect(html('*waves cheerfully*')).toContain('<em>waves cheerfully</em>');
	});

	it('keeps the rest of the sentence intact', () => {
		expect(html('"Fine," *she sighs* and **leaves**')).toContain(
			'"Fine," <em>she sighs</em> and <strong>leaves</strong>'
		);
	});

	it('preserves newlines without adding whitespace', () => {
		expect(html('first\nsecond')).toContain('<p>first\nsecond</p>');
	});

	it('renders quoted lines as a blockquote', () => {
		expect(html('> *muttered*')).toContain('<blockquote><em>muttered</em></blockquote>');
	});

	it('renders fenced code without parsing its contents', () => {
		expect(html('```\n*bold*\n```')).toContain('<pre><code>*bold*</code></pre>');
	});

	it('escapes markup in message content', () => {
		const body = html('<img src=x onerror="alert(1)"> and <script>bad()</script>');
		expect(body).not.toContain('<img');
		expect(body).not.toContain('<script>');
		expect(body).toContain('&lt;img');
	});
});
