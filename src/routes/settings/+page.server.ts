import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { fail } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { Actions, PageServerLoad } from './$types';

async function fetchHumanProfile() {
	return await db.query.users.findFirst({
		where: eq(users.is_human, true)
	});
}

export const load: PageServerLoad = async () => {
	const profile = await fetchHumanProfile();
	// Return null user if no human profile exists - the page will show empty form
	return {
		user: profile || null
	};
};

export const actions = {
	default: async ({ request }) => {
		const formData = await request.formData();
		const currentProfile = await fetchHumanProfile();

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

		const name = extractField('name') || (currentProfile?.name ?? 'You');
		const age = parseAge(extractField('age'), currentProfile?.age ?? 25);
		const pronouns = extractField('pronouns') || (currentProfile?.pronouns ?? 'they/them');

		const fieldsToSave = {
			name,
			age,
			pronouns,
			bio: extractField('bio'),
			location: locationObj,
			occupation: extractField('occupation'),
			interests: parsedInterests,
			relationship_status: extractField('relationship_status'),
			is_human: true
		};

		if (currentProfile) {
			// Update existing human user
			await db.update(users).set(fieldsToSave).where(eq(users.id, currentProfile.id));
		} else {
			// Create new human user if none exists
			await db.insert(users).values(fieldsToSave);
		}

		return { success: true };
	}
} satisfies Actions;
