const NON_LATIN_SCRIPT_PATTERN =
	/[\p{Script=Arabic}\p{Script=Cyrillic}\p{Script=Devanagari}\p{Script=Greek}\p{Script=Han}\p{Script=Hebrew}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}\p{Script=Thai}]/u;

function isAscii(value: string): boolean {
	for (const character of value) {
		if ((character.codePointAt(0) ?? 0) > 0x7f) {
			return false;
		}
	}
	return true;
}

export function looksNonEnglish(text: string): boolean {
	const trimmed = text.trim();
	if (!trimmed) {
		return false;
	}

	if (NON_LATIN_SCRIPT_PATTERN.test(trimmed)) {
		return true;
	}

	if (isAscii(trimmed)) {
		return false;
	}

	// Ignore common symbols and emoji-like glyphs; focus on letter content.
	const lettersOnly = trimmed.replace(
		/[\p{N}\p{P}\p{S}\p{Z}\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu,
		''
	);
	if (!lettersOnly) {
		return false;
	}

	let nonAsciiLetterCount = 0;
	for (const character of lettersOnly) {
		if ((character.codePointAt(0) ?? 0) > 0x7f) {
			nonAsciiLetterCount += 1;
		}
	}

	return nonAsciiLetterCount >= 2;
}
