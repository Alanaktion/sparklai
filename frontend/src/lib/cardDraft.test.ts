import { describe, expect, it } from 'vitest';

import {
	cardFromDraft,
	draftFromCard,
	draftProblems,
	emptyDraft,
	emptyEntry,
	readJsonObject,
	type JsonObject
} from './cardDraft';

/** A card carrying data the editor knows nothing about, at every level. */
function fullCard(): JsonObject {
	return {
		spec: 'chara_card_v2',
		spec_version: '2.0',
		future_top_level: { keep: true },
		data: {
			name: 'Haruhi',
			description: 'A blunt student.',
			personality: 'Bold.',
			scenario: 'The club room.',
			first_mes: 'Hi!',
			mes_example: 'example',
			creator_notes: 'Notes.',
			system_prompt: 'You are {{char}}.',
			post_history_instructions: 'Stay in character.',
			alternate_greetings: ['Oh, it is you.', 'Hey.'],
			tags: ['anime', 'school'],
			creator: 'tests',
			character_version: '1.1',
			future_data_key: ['keep', 'me'],
			extensions: { card_ext: { nested: 'value' } },
			character_book: {
				name: 'Club',
				description: 'Lore.',
				scan_depth: 4,
				token_budget: 512,
				recursive_scanning: true,
				future_book_key: 42,
				extensions: { book_ext: { keep: true } },
				entries: [
					{
						keys: ['brigade', 'club'],
						secondary_keys: ['sos'],
						content: 'The SOS Brigade.',
						enabled: true,
						insertion_order: 10,
						case_sensitive: true,
						selective: true,
						constant: false,
						position: 'before_char',
						priority: 5,
						id: 1,
						comment: 'lore',
						name: 'Brigade',
						future_entry_key: 'keep',
						extensions: { entry_ext: [1, 2, 3] }
					}
				]
			}
		}
	};
}

function data(card: JsonObject): JsonObject {
	return card.data as JsonObject;
}

function book(card: JsonObject): JsonObject {
	return data(card).character_book as JsonObject;
}

function entry(card: JsonObject): JsonObject {
	return (book(card).entries as JsonObject[])[0] as JsonObject;
}

/**
 * Stand in for Svelte's `$state`, which deep-proxies plain objects. The HTML spec
 * makes `structuredClone` throw `DataCloneError` on a `Proxy`, which is how the
 * editor used to crash when handed a loaded character.
 */
function reactive<T>(value: T): T {
	if (typeof value !== 'object' || value === null) return value;
	return new Proxy(value, {
		get(target, key, receiver) {
			return reactive(Reflect.get(target, key, receiver) as unknown) as unknown;
		}
	}) as T;
}

describe('emptyDraft', () => {
	it('produces a valid V2 envelope with no character book', () => {
		const card = cardFromDraft(emptyDraft());

		expect(card.spec).toBe('chara_card_v2');
		expect(card.spec_version).toBe('2.0');
		expect(data(card).name).toBe('');
		expect(data(card).first_mes).toBe('');
		expect(data(card).mes_example).toBe('');
		expect(data(card).alternate_greetings).toEqual([]);
		expect(data(card).tags).toEqual([]);
		expect(data(card).extensions).toEqual({});
		expect('character_book' in data(card)).toBe(false);
	});
});

describe('round trips', () => {
	it('accepts reactive state without throwing', () => {
		const card = fullCard();
		const proxied = reactive(card);

		// The failure mode being worked around: structuredClone rejects proxies.
		expect(() => structuredClone(proxied)).toThrow();
		expect(() => draftFromCard(proxied)).not.toThrow();
		// A proxy must behave exactly like the plain object it wraps, including
		// preserving the keys this editor does not understand.
		const saved = cardFromDraft(draftFromCard(proxied));
		expect(saved).toEqual(cardFromDraft(draftFromCard(card)));
		expect(entry(saved).future_entry_key).toBe('keep');
		expect(book(saved).future_book_key).toBe(42);
	});

	it('keeps unknown keys at every level', () => {
		const card = fullCard();
		const saved = cardFromDraft(draftFromCard(card));

		expect(saved.future_top_level).toEqual({ keep: true });
		expect(data(saved).future_data_key).toEqual(['keep', 'me']);
		expect(book(saved).future_book_key).toBe(42);
		expect(entry(saved).future_entry_key).toBe('keep');
	});

	it('keeps extensions at card, book and entry level', () => {
		const card = fullCard();
		const saved = cardFromDraft(draftFromCard(card));

		expect(data(saved).extensions).toEqual({ card_ext: { nested: 'value' } });
		expect(book(saved).extensions).toEqual({ book_ext: { keep: true } });
		expect(entry(saved).extensions).toEqual({ entry_ext: [1, 2, 3] });
	});

	it('keeps every supported field', () => {
		const saved = cardFromDraft(draftFromCard(fullCard()));

		expect(data(saved).name).toBe('Haruhi');
		expect(data(saved).creator_notes).toBe('Notes.');
		expect(data(saved).system_prompt).toBe('You are {{char}}.');
		expect(data(saved).post_history_instructions).toBe('Stay in character.');
		expect(data(saved).alternate_greetings).toEqual(['Oh, it is you.', 'Hey.']);
		expect(data(saved).tags).toEqual(['anime', 'school']);
		expect(data(saved).creator).toBe('tests');
		expect(data(saved).character_version).toBe('1.1');

		expect(book(saved).name).toBe('Club');
		expect(book(saved).scan_depth).toBe(4);
		expect(book(saved).token_budget).toBe(512);
		expect(book(saved).recursive_scanning).toBe(true);

		expect(entry(saved).keys).toEqual(['brigade', 'club']);
		expect(entry(saved).secondary_keys).toEqual(['sos']);
		expect(entry(saved).content).toBe('The SOS Brigade.');
		expect(entry(saved).insertion_order).toBe(10);
		expect(entry(saved).case_sensitive).toBe(true);
		expect(entry(saved).selective).toBe(true);
		expect(entry(saved).position).toBe('before_char');
		expect(entry(saved).priority).toBe(5);
		expect(entry(saved).id).toBe(1);
		expect(entry(saved).comment).toBe('lore');
		expect(entry(saved).name).toBe('Brigade');
	});

	it('writes numbers as numbers, not strings', () => {
		const saved = cardFromDraft(draftFromCard(fullCard()));
		expect(typeof book(saved).scan_depth).toBe('number');
		expect(typeof entry(saved).insertion_order).toBe('number');
		expect(typeof entry(saved).priority).toBe('number');
	});

	it('leaves a card without a character book alone', () => {
		const card = fullCard();
		delete data(card).character_book;

		const saved = cardFromDraft(draftFromCard(card));
		expect('character_book' in data(saved)).toBe(false);
	});

	it('omits optional entry fields that are blank', () => {
		const saved = cardFromDraft(draftFromCard({ data: { name: 'Empty' } }));
		expect('character_book' in data(saved)).toBe(false);

		const draft = draftFromCard(fullCard());
		draft.book!.entries[0]!.position = '';
		draft.book!.entries[0]!.priority = '';
		draft.book!.entries[0]!.id = '';
		draft.book!.entries[0]!.name = '';
		draft.book!.entries[0]!.comment = '';
		draft.book!.entries[0]!.secondaryKeys = '';

		const trimmed = entry(cardFromDraft(draft));
		for (const key of ['position', 'priority', 'id', 'name', 'comment', 'secondary_keys']) {
			expect(key in trimmed).toBe(false);
		}
	});

	it('only writes the false-by-default flags when they are set', () => {
		const draft = draftFromCard(fullCard());
		const draftEntry = draft.book!.entries[0]!;
		draftEntry.caseSensitive = false;
		draftEntry.selective = false;
		draftEntry.constant = false;
		draft.book!.recursiveScanning = false;

		const saved = cardFromDraft(draft);
		for (const key of ['case_sensitive', 'selective', 'constant']) {
			expect(key in entry(saved)).toBe(false);
		}
		expect('recursive_scanning' in book(saved)).toBe(false);
	});

	it('always writes `enabled`, because false is meaningful', () => {
		const draft = draftFromCard(fullCard());
		draft.book!.entries[0]!.enabled = false;
		expect(entry(cardFromDraft(draft)).enabled).toBe(false);
	});

	it('drops blank list rows', () => {
		const draft = draftFromCard(fullCard());
		draft.tags = ['anime', '  ', ''];
		draft.alternateGreetings = ['only'];
		draft.extensions = [{ key: '  ', value: '1' }, ...draft.extensions];

		const saved = cardFromDraft(draft);
		expect(data(saved).tags).toEqual(['anime']);
		expect(data(saved).alternate_greetings).toEqual(['only']);
		expect(data(saved).extensions).toEqual({ card_ext: { nested: 'value' } });
	});

	it('adds a character book when one is created in the editor', () => {
		const draft = draftFromCard({ data: { name: 'Fresh' } });
		draft.book = {
			base: {},
			name: '',
			description: '',
			scanDepth: '8',
			tokenBudget: '',
			recursiveScanning: false,
			extensions: '{}',
			entries: [{ ...emptyEntry(), keys: 'club', content: 'Lore.' }]
		};

		const saved = book(cardFromDraft(draft));
		expect(saved.scan_depth).toBe(8);
		expect('token_budget' in saved).toBe(false);
		expect((saved.entries as JsonObject[])[0]!.keys).toEqual(['club']);
	});
});

describe('draftProblems', () => {
	it('accepts a well-formed draft', () => {
		expect(draftProblems(draftFromCard(fullCard()))).toEqual([]);
	});

	it('requires a name', () => {
		const draft = emptyDraft();
		expect(draftProblems(draft)).toContain('Name is required.');
	});

	it('reports invalid JSON in an extension value', () => {
		const draft = draftFromCard(fullCard());
		draft.extensions = [{ key: 'broken', value: '{not json' }];
		expect(draftProblems(draft)).toContain('Extension "broken" is not valid JSON.');
	});

	it('reports duplicate extension keys', () => {
		const draft = draftFromCard(fullCard());
		draft.extensions = [
			{ key: 'same', value: '1' },
			{ key: 'same', value: '2' }
		];
		expect(draftProblems(draft)).toContain('Duplicate extension key "same".');
	});

	it('reports non-numeric book and entry numbers', () => {
		const draft = draftFromCard(fullCard());
		draft.book!.scanDepth = 'deep';
		draft.book!.entries[0]!.priority = 'soon';
		const problems = draftProblems(draft);

		expect(problems).toContain('Scan depth must be a number.');
		expect(problems).toContain('Brigade: priority must be a number.');
	});
});

describe('readJsonObject', () => {
	it('accepts an object', () => {
		const result = readJsonObject('{"spec":"chara_card_v2"}');
		expect(result.ok && result.value.spec).toBe('chara_card_v2');
	});

	it('rejects invalid JSON', () => {
		const result = readJsonObject('{oops');
		expect(result.ok).toBe(false);
	});

	it('rejects a non-object', () => {
		const result = readJsonObject('[1, 2, 3]');
		expect(result.ok).toBe(false);
		expect(result.ok === false && result.error).toBe('The card must be a JSON object');
	});
});
