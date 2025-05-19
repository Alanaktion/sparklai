import { sql } from 'drizzle-orm';
import { sqliteTable, text, integer, blob, type AnySQLiteColumn } from 'drizzle-orm/sqlite-core';

type Location = {
	city: string;
	state_province: string;
	country: string;
};
type Personality = {
	agreeableness: number;
	conscientiousness: number;
	extraversion: number;
	neuroticism: number;
	openness: number;
};
type WritingStyle = {
	languages?: string[];
	emoji_frequency: number;
	formality: string;
	puncuation_style: string;
	slang_usage: string;
};
type Appearance = {
	gender_expression?: string;
	body_type?: string;
	height?: string;
	hair?: {
		color: string;
		style: string;
		length?: string;
	};
	eyes?: {
		color: string;
		shape?: string;
	};
	skin_tone?: string;
	facial_features?: string[];
	clothing_style?: string;
	accessories?: string[];
};

// Only properties we actually care about will be defined here:
export type StableDiffusionParams = {
	prompt: string;
	negative_prompt: string;
	width: number;
	height: number;
	cfg_scale: number;
	seed: number;
};

export const users = sqliteTable('users', {
	id: integer().primaryKey(),
	name: text().notNull(),
	age: integer().notNull(),
	pronouns: text().notNull(),
	bio: text(),
	location: text({ mode: 'json' }).$type<Location>(),
	occupation: text(),
	interests: text({ mode: 'json' }).$type<string[]>(),
	personality_traits: text({ mode: 'json' }).$type<Personality>(),
	relationship_status: text(),
	writing_style: text({ mode: 'json' }).$type<WritingStyle>(),
	backstory_snippet: text(),
	appearance: text({ mode: 'json' }).$type<Appearance>(),
	image_id: integer().references((): AnySQLiteColumn => images.id),
	is_human: integer({ mode: 'boolean' }).notNull().default(false),
	is_active: integer({ mode: 'boolean' }).notNull().default(true)
});

export const images = sqliteTable('images', {
	id: integer().primaryKey(),
	user_id: integer()
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	params: text({ mode: 'json' }).$type<StableDiffusionParams>(),
	data: blob().notNull()
});

export const posts = sqliteTable('posts', {
	id: integer().primaryKey(),
	user_id: integer()
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	image_id: integer().references(() => images.id, { onDelete: 'set null' }),
	body: text().notNull(),
	created_at: text().default(sql`CURRENT_TIMESTAMP`)
});

export const comments = sqliteTable('comments', {
	id: integer().primaryKey(),
	post_id: integer()
		.notNull()
		.references(() => posts.id, { onDelete: 'cascade' }),
	user_id: integer().references(() => users.id, { onDelete: 'cascade' }),
	body: text().notNull(),
	created_at: text().default(sql`CURRENT_TIMESTAMP`)
});

export const chats = sqliteTable('chats', {
	id: integer().primaryKey(),
	user_id: integer()
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	image_id: integer().references(() => images.id, { onDelete: 'set null' }),
	role: text().notNull(),
	body: text().notNull(),
	created_at: text().default(sql`CURRENT_TIMESTAMP`)
});
