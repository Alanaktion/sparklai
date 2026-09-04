// Frontend-owned response types for the FastAPI backend. Replaces the Drizzle-inferred `*Type`
// aliases that used to live in `$lib/server/db/schema.ts` (deleted in BACKEND_MIGRATION.md's
// cleanup pass, along with the rest of `src/lib/server/**`) — these mirror the corresponding
// Pydantic response schemas' fields (`backend/src/app/*/schemas.py`), not the raw DB columns, so
// e.g. binary `data` columns never appear here: the API never serializes those into JSON.

export type Location = {
	city: string;
	state_province: string;
	country: string;
};

export type CreatorType = {
	id: number;
	name: string;
	age: number;
	pronouns: string;
	bio: string | null;
	location: Location | null;
	occupation: string | null;
	interests: string[] | null;
	relationship_status: string | null;
	is_active: boolean;
	created_at: string | null;
};

export type UserType = {
	id: number;
	name: string;
	age: number;
	pronouns: string;
	bio: string | null;
	location: Location | null;
	occupation: string | null;
	interests: string[] | null;
	personality_traits: string | null;
	relationship_status: string | null;
	writing_style: string | null;
	backstory: string | null;
	appearance: string | null;
	memory: string | null;
	image_id: number | null;
	creator_id: number;
	scenario: string | null;
	first_mes: string | null;
	is_active: boolean;
};

export type ImageType = {
	id: number;
	params: Record<string, unknown> | null;
	blur: boolean;
};

export type PostType = {
	id: number;
	user_id: number;
	image_id: number | null;
	media_id: number | null;
	body: string;
	body_en: string | null;
	created_at: string | null;
};

export type CommentType = {
	id: number;
	post_id: number;
	user_id: number | null;
	body: string;
	body_en: string | null;
	created_at: string | null;
};

export type ChatType = {
	id: number;
	user_id: number;
	image_id: number | null;
	role: 'user' | 'assistant' | 'system';
	body: string;
	body_en: string | null;
	created_at: string | null;
};
