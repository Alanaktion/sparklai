export type InlineTextSegment = {
	text: string;
	italic: boolean;
};

export function parseInlineItalics(text: string): InlineTextSegment[] {
	const segments: InlineTextSegment[] = [];
	const italicPattern = /\*([^*\n]+)\*/g;
	let cursor = 0;
	let match = italicPattern.exec(text);

	while (match) {
		const start = match.index;
		const end = start + match[0].length;

		if (start > cursor) {
			segments.push({ text: text.slice(cursor, start), italic: false });
		}

		segments.push({ text: match[1], italic: true });
		cursor = end;
		match = italicPattern.exec(text);
	}

	if (cursor < text.length) {
		segments.push({ text: text.slice(cursor), italic: false });
	}

	if (segments.length === 0) {
		segments.push({ text, italic: false });
	}

	return segments;
}
