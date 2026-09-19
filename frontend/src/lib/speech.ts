// Browser speech APIs for the TTS/STT hooks declared in a card's extensions.
//
// Everything is guarded so the module is safe to import during SSR and in
// environments (and tests) where the Web Speech APIs do not exist.

export type SpeakOptions = {
	voice?: string | null;
	lang?: string | null;
	rate?: number | null;
	pitch?: number | null;
};

export type TranscriptSegment = { transcript: string; isFinal: boolean };

/** The browser's speech synthesiser, or null where it is unavailable. */
function synthesis(): SpeechSynthesis | null {
	if (typeof globalThis === 'undefined' || !('speechSynthesis' in globalThis)) {
		return null;
	}
	return globalThis.speechSynthesis ?? null;
}

export function canSpeak(): boolean {
	return synthesis() !== null && typeof SpeechSynthesisUtterance !== 'undefined';
}

/** Queue `text` for speech, replacing anything already playing. */
export function speak(text: string, options: SpeakOptions = {}): boolean {
	const synth = synthesis();
	if (!synth || !text.trim()) return false;

	synth.cancel();
	const utterance = new SpeechSynthesisUtterance(text);
	if (options.lang) utterance.lang = options.lang;
	if (typeof options.rate === 'number') utterance.rate = options.rate;
	if (typeof options.pitch === 'number') utterance.pitch = options.pitch;
	if (options.voice) {
		const match = synth.getVoices().find((voice) => voice.name === options.voice);
		if (match) utterance.voice = match;
	}
	synth.speak(utterance);
	return true;
}

export function stopSpeaking(): void {
	synthesis()?.cancel();
}

// --- speech recognition -----------------------------------------------------
//
// SpeechRecognition is not in the DOM typings (and is still webkit-prefixed in
// some browsers), so it is described structurally rather than via lib.dom.

export type RecognitionResultEvent = { results?: unknown };

export type SpeechRecognitionLike = {
	lang: string;
	continuous: boolean;
	interimResults: boolean;
	start(): void;
	stop(): void;
	onresult: ((event: RecognitionResultEvent) => void) | null;
	onerror: (() => void) | null;
	onend: (() => void) | null;
};

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

export function recognitionConstructor(): SpeechRecognitionCtor | null {
	if (typeof globalThis === 'undefined') return null;
	const scope = globalThis as unknown as {
		SpeechRecognition?: SpeechRecognitionCtor;
		webkitSpeechRecognition?: SpeechRecognitionCtor;
	};
	return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null;
}

export function canListen(): boolean {
	return recognitionConstructor() !== null;
}

/** Flatten a recognition event's results, keeping the final/interim distinction. */
export function segmentsFrom(event: RecognitionResultEvent | unknown): TranscriptSegment[] {
	if (typeof event !== 'object' || event === null) return [];
	const results = (event as { results?: unknown }).results;
	if (typeof results !== 'object' || results === null) return [];

	const list = results as Record<number, unknown> & { length?: number };
	const length = typeof list.length === 'number' ? list.length : 0;
	const segments: TranscriptSegment[] = [];
	for (let index = 0; index < length; index += 1) {
		const result = list[index] as
			| (Record<number, unknown> & { isFinal?: unknown })
			| undefined;
		if (!result) continue;
		const alternative = result[0] as { transcript?: unknown } | undefined;
		if (typeof alternative?.transcript !== 'string') continue;
		segments.push({
			transcript: alternative.transcript,
			isFinal: result.isFinal === true
		});
	}
	return segments;
}
