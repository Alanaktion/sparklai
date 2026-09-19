import { describe, expect, it, vi } from 'vitest';

import { canListen, canSpeak, recognitionConstructor, segmentsFrom, speak } from './speech';

/** A stand-in for the shape a SpeechRecognition event really has. */
function event(entries: { transcript: string; isFinal: boolean }[]) {
	return {
		results: Object.assign(
			entries.map((entry) => Object.assign([{ transcript: entry.transcript }], entry)),
			{ length: entries.length }
		)
	};
}

describe('speech availability guards', () => {
	it('reports nothing available in a plain Node environment', () => {
		// vitest runs without the Web Speech APIs.
		expect(canSpeak()).toBe(false);
		expect(canListen()).toBe(false);
		expect(recognitionConstructor()).toBeNull();
	});

	it('does nothing when asked to speak without a synthesiser', () => {
		expect(speak('hello')).toBe(false);
	});
});

describe('segmentsFrom', () => {
	it('returns the transcript and finality of each result', () => {
		const segments = segmentsFrom(
			event([
				{ transcript: 'hello ', isFinal: true },
				{ transcript: 'wor', isFinal: false }
			])
		);

		expect(segments).toEqual([
			{ transcript: 'hello ', isFinal: true },
			{ transcript: 'wor', isFinal: false }
		]);
	});

	it('tolerates junk instead of throwing', () => {
		expect(segmentsFrom(undefined)).toEqual([]);
		expect(segmentsFrom(null)).toEqual([]);
		expect(segmentsFrom('nope')).toEqual([]);
		expect(segmentsFrom({})).toEqual([]);
		expect(segmentsFrom({ results: { length: 1 } })).toEqual([]);
	});

	it('exposes just the final transcript through a spy-friendly shape', () => {
		const onResult = vi.fn();
		onResult(event([{ transcript: 'done', isFinal: true }]));
		const [first] = onResult.mock.calls[0] as [unknown];
		expect(segmentsFrom(first).map((segment) => segment.transcript)).toEqual(['done']);
	});
});
