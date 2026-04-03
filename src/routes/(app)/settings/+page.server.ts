import { db } from '$lib/server/db';
import { creators } from '$lib/server/db/schema';
import { fail } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	return { creator: locals.creator ?? null };
};

export const actions = {
	default: async ({ request, locals }) => {
		if (!locals.creator) {
			fail(401, { error: 'No active creator' });
			return;
		}

		const formData = await request.formData();
		const currentProfile = locals.creator;

		const extractField = (fieldName: string) => formData.get(fieldName)?.toString() || null;
		const parseAge = (ageStr: string | null, defaultAge: number = 25) => {
			if (!ageStr) return defaultAge;
			const parsed = parseInt(ageStr, 10);
			return isNaN(parsed) ? defaultAge : parsed;
		};

		const interestsList = extractField('interests');
		const parsedInterests = interestsList
			? interestsList
					.split(',')
					.map((item) => item.trim())
					.filter(Boolean)
			: null;

		const locationParts = {
			cityValue: extractField('location_city'),
			stateValue: extractField('location_state_province'),
			countryValue: extractField('location_country')
		};

		const locationObj =
			locationParts.cityValue || locationParts.stateValue || locationParts.countryValue
				? {
						city: locationParts.cityValue || '',
						state_province: locationParts.stateValue || '',
						country: locationParts.countryValue || ''
					}
				: null;

		const name = extractField('name') || currentProfile.name;
		const age = parseAge(extractField('age'), currentProfile.age);
		const pronouns = extractField('pronouns') || currentProfile.pronouns;

		const fieldsToSave = {
			name,
			age,
			pronouns,
			bio: extractField('bio'),
			location: locationObj,
			occupation: extractField('occupation'),
			interests: parsedInterests,
			relationship_status: extractField('relationship_status')
		};

		await db.update(creators).set(fieldsToSave).where(eq(creators.id, currentProfile.id));

		return { success: true };
	}
} satisfies Actions;
