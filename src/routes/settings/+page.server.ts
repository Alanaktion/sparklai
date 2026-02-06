import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { error, fail } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { Actions, PageServerLoad } from './$types';

async function fetchHumanProfile() {
	return await db.query.users.findFirst({
		where: eq(users.is_human, true)
	});
}

export const load: PageServerLoad = async () => {
	const profile = await fetchHumanProfile();
	if (!profile) error(404, 'Human user not found');
	return { user: profile };
};

export const actions = {
	default: async ({ request }) => {
		const formData = await request.formData();
		const currentProfile = await fetchHumanProfile();

		if (!currentProfile) return fail(404, { message: 'Human user not found' });

		const extractField = (fieldName: string) => formData.get(fieldName)?.toString() || null;
		const parseAge = (ageStr: string | null) =>
			ageStr ? parseInt(ageStr, 10) : currentProfile.age;

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
			locationParts.cityValue && locationParts.stateValue && locationParts.countryValue
				? {
						city: locationParts.cityValue,
						state_province: locationParts.stateValue,
						country: locationParts.countryValue
					}
				: null;

		const updatedFields = {
			name: extractField('name') || currentProfile.name,
			age: parseAge(extractField('age')),
			pronouns: extractField('pronouns') || currentProfile.pronouns,
			bio: extractField('bio'),
			location: locationObj,
			occupation: extractField('occupation'),
			interests: parsedInterests,
			relationship_status: extractField('relationship_status')
		};

		await db.update(users).set(updatedFields).where(eq(users.id, currentProfile.id));
		return { success: true };
	}
} satisfies Actions;
