// Minimal Markdown-like parser for character roleplay text.
//
// Roleplay conventions lean on a small subset: *asterisks for actions*,
// **emphasis**, _underscores_, ~~strikethrough~~, `inline code`, fenced code
// blocks and > quotes. Single newlines are kept, because models break replies
// across lines far more often than they intend paragraphs.
//
// The parser returns plain data rather than HTML, and the renderer emits text
// nodes, so message content can never inject markup.

export type Span =
	| { type: 'text'; value: string }
	| { type: 'em'; children: Span[] }
	| { type: 'strong'; children: Span[] }
	| { type: 'del'; children: Span[] }
	| { type: 'code'; value: string };

export type Block =
	| { type: 'paragraph'; spans: Span[] }
	| { type: 'quote'; spans: Span[] }
	| { type: 'code'; value: string };

type InlineKind = 'em' | 'strong' | 'strong-em' | 'del' | 'code';

interface Delimiter {
	marker: string;
	kind: InlineKind;
}

const ESCAPABLE = new Set(['*', '_', '`', '~', '\\']);
const UNDERSCORE_MARKERS = new Set(['_', '__']);

/** Split a message into paragraphs, quotes and code blocks. */
export function parseMessage(input: string): Block[] {
	const lines = input.replace(/\r\n?/g, '\n').split('\n');
	const blocks: Block[] = [];
	let paragraph: string[] = [];

	const flushParagraph = () => {
		if (paragraph.length === 0) return;
		blocks.push({ type: 'paragraph', spans: parseInline(paragraph.join('\n')) });
		paragraph = [];
	};

	for (let index = 0; index < lines.length; index += 1) {
		const line = lines[index] ?? '';

		if (/^\s*```/.test(line)) {
			flushParagraph();
			const body: string[] = [];
			index += 1;
			while (index < lines.length && !/^\s*```/.test(lines[index] ?? '')) {
				body.push(lines[index] ?? '');
				index += 1;
			}
			// The closing fence is consumed by the loop increment below.
			blocks.push({ type: 'code', value: body.join('\n') });
			continue;
		}

		if (/^\s*>/.test(line)) {
			flushParagraph();
			const quoted: string[] = [];
			while (index < lines.length && /^\s*>/.test(lines[index] ?? '')) {
				quoted.push((lines[index] ?? '').replace(/^\s*>\s?/, ''));
				index += 1;
			}
			// Step back so the outer increment lands on the next non-quote line.
			index -= 1;
			blocks.push({ type: 'quote', spans: parseInline(quoted.join('\n')) });
			continue;
		}

		if (line.trim() === '') {
			flushParagraph();
			continue;
		}

		paragraph.push(line);
	}

	flushParagraph();
	return blocks;
}

/** Parse inline emphasis, code spans and escapes within a block of text. */
export function parseInline(input: string): Span[] {
	const spans: Span[] = [];
	let pending = '';
	let index = 0;

	const flush = () => {
		if (pending === '') return;
		spans.push({ type: 'text', value: pending });
		pending = '';
	};

	while (index < input.length) {
		const char = input[index] ?? '';

		// A backslash escapes the next delimiter, so `\*` stays literal.
		const escaped = input[index + 1];
		if (char === '\\' && escaped !== undefined && ESCAPABLE.has(escaped)) {
			pending += escaped;
			index += 2;
			continue;
		}

		const delimiter = delimiterAt(input, index);
		if (delimiter !== null) {
			const contentStart = index + delimiter.marker.length;
			const closing = findClosing(input, contentStart, delimiter);
			if (closing !== -1) {
				const inner = input.slice(contentStart, closing);
				flush();
				if (delimiter.kind === 'code') {
					spans.push({ type: 'code', value: inner });
				} else if (delimiter.kind === 'strong-em') {
					spans.push({
						type: 'strong',
						children: [{ type: 'em', children: parseInline(inner) }]
					});
				} else if (delimiter.kind === 'strong') {
					spans.push({ type: 'strong', children: parseInline(inner) });
				} else if (delimiter.kind === 'del') {
					spans.push({ type: 'del', children: parseInline(inner) });
				} else {
					spans.push({ type: 'em', children: parseInline(inner) });
				}
				index = closing + delimiter.marker.length;
				continue;
			}
			// No closing marker: fall through and treat it as literal text.
		}

		pending += char;
		index += 1;
	}

	flush();
	return spans;
}

function delimiterAt(input: string, index: number): Delimiter | null {
	const rest = input.slice(index, index + 3);

	if (rest.startsWith('***')) return { marker: '***', kind: 'strong-em' };
	if (rest.startsWith('**')) return { marker: '**', kind: 'strong' };
	if (rest.startsWith('~~')) return { marker: '~~', kind: 'del' };
	if (rest.startsWith('*')) return { marker: '*', kind: 'em' };
	if (rest.startsWith('`')) return { marker: '`', kind: 'code' };

	// Underscores only count at word boundaries, so `snake_case_name` survives.
	if (rest.startsWith('__') && opensUnderscore(input, index)) {
		return { marker: '__', kind: 'strong' };
	}
	if (rest.startsWith('_') && opensUnderscore(input, index)) {
		return { marker: '_', kind: 'em' };
	}

	return null;
}

function findClosing(input: string, from: number, delimiter: Delimiter): number {
	let index = input.indexOf(delimiter.marker, from);
	while (index !== -1) {
		if (UNDERSCORE_MARKERS.has(delimiter.marker) && !closesUnderscore(input, index)) {
			index = input.indexOf(delimiter.marker, index + 1);
			continue;
		}
		// A lone `*` must not be closed by part of a `**` run, so that
		// `*she **really** means it*` nests instead of splitting.
		if (delimiter.marker === '*' && !isLoneAsterisk(input, index)) {
			index = input.indexOf(delimiter.marker, index + 1);
			continue;
		}
		return index;
	}
	return -1;
}

function isLoneAsterisk(input: string, index: number): boolean {
	return input[index - 1] !== '*' && input[index + 1] !== '*';
}

function opensUnderscore(input: string, index: number): boolean {
	const before = index > 0 ? input[index - 1] : undefined;
	return before === undefined || !isWordChar(before);
}

function closesUnderscore(input: string, index: number): boolean {
	const after = input[index + 1];
	return after === undefined || !isWordChar(after);
}

function isWordChar(value: string): boolean {
	return /[0-9A-Za-z]/.test(value);
}
