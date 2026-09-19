import { describe, expect, it } from 'vitest';

import { parseInline, parseMessage, type Span } from './markdown';

/** Render spans to a compact string so expectations stay readable. */
function render(span: Span): string {
	switch (span.type) {
		case 'text':
			return span.value;
		case 'code':
			return `\`${span.value}\``;
		default:
			return `<${span.type}>${span.children.map(render).join('')}</${span.type}>`;
	}
}

function inline(input: string): string {
	return parseInline(input).map(render).join('');
}

function blocks(input: string): string {
	return parseMessage(input)
		.map((block) => {
			if (block.type === 'code') return `[code]${block.value}[/code]`;
			const body = block.spans.map(render).join('');
			return block.type === 'quote' ? `[quote]${body}[/quote]` : body;
		})
		.join('\n');
}

describe('parseInline', () => {
	it('leaves plain prose alone', () => {
		expect(inline('Hi there, how are you?')).toBe('Hi there, how are you?');
	});

	it('parses single asterisks as actions', () => {
		expect(inline('*sighs heavily*')).toBe('<em>sighs heavily</em>');
	});

	it('parses double asterisks as emphasis', () => {
		expect(inline('**very** loud')).toBe('<strong>very</strong> loud');
	});

	it('parses triple asterisks as strong emphasis', () => {
		expect(inline('***both***')).toBe('<strong><em>both</em></strong>');
	});

	it('parses underscores at word boundaries', () => {
		expect(inline('_quietly_ she said')).toBe('<em>quietly</em> she said');
		expect(inline('__loudly__')).toBe('<strong>loudly</strong>');
	});

	it('leaves intra-word underscores alone', () => {
		expect(inline('file_name_here')).toBe('file_name_here');
	});

	it('parses strikethrough and code spans', () => {
		expect(inline('~~gone~~ and `raw *text*`')).toBe(
			'<del>gone</del> and `raw *text*`'
		);
	});

	it('nests emphasis inside emphasis', () => {
		expect(inline('*she **really** means it*')).toBe(
			'<em>she <strong>really</strong> means it</em>'
		);
	});

	it('treats an unmatched marker as literal text', () => {
		expect(inline('a lone * star')).toBe('a lone * star');
		expect(inline('**unclosed')).toBe('**unclosed');
	});

	it('honours backslash escapes', () => {
		expect(inline('literal \\*stars\\* here')).toBe('literal *stars* here');
	});

	it('handles several spans in one message', () => {
		expect(inline('*She nods.* "Fine," she says. **Really.**')).toBe(
			'<em>She nods.</em> "Fine," she says. <strong>Really.</strong>'
		);
	});
});

describe('parseMessage', () => {
	it('keeps single newlines inside a paragraph', () => {
		expect(blocks('line one\nline two')).toBe('line one\nline two');
	});

	it('splits paragraphs on blank lines', () => {
		expect(blocks('first\n\nsecond')).toBe('first\nsecond');
	});

	it('does not parse inside a fenced code block', () => {
		expect(blocks('```\n*not em* **not strong**\n```')).toBe(
			'[code]*not em* **not strong**[/code]'
		);
	});

	it('parses quoted blocks', () => {
		expect(blocks('> *muttered*\n> under breath')).toBe(
			'[quote]<em>muttered</em>\nunder breath[/quote]'
		);
	});

	it('mixes paragraphs, quotes and code', () => {
		const input = 'She speaks.\n\n> quoted line\n\n```\ncode\n```\n\nAfter.';
		expect(blocks(input)).toBe(
			'She speaks.\n[quote]quoted line[/quote]\n[code]code[/code]\nAfter.'
		);
	});

	it('handles empty input', () => {
		expect(parseMessage('')).toEqual([]);
	});
});
