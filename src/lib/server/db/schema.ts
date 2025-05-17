import { sql } from 'drizzle-orm';
import { sqliteTable, text, integer, blob } from 'drizzle-orm/sqlite-core';

export const users = sqliteTable('users', {
	id: integer('id').primaryKey(),
	name: text('name').notNull(),
	age: integer('age').notNull(),
	pronouns: text('pronouns').notNull(),
	bio: text('bio'),
	location: text('location', { mode: 'json' }),
	occupation: text('occupation'),
	interests: text('interests', { mode: 'json' }),
	personality_traits: text('personality_traits', { mode: 'json' }),
	relationship_status: text('relationship_status'),
	writing_style: text('writing_style', { mode: 'json' }),
	backstory_snippet: text('backstory_snippet'),
	appearance: text('appearance', { mode: 'json' }),
	image_id: integer('image_id'), // TODO: FK
	is_human: integer('is_human').notNull().default(0), // bool
	is_active: integer('is_active').notNull().default(1) // bool
});

export const images = sqliteTable('images', {
	id: integer('id').primaryKey(),
	user_id: integer('user_id')
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	params: text('params', { mode: 'json' }),
	data: blob('data').notNull()
});

export const posts = sqliteTable('posts', {
	id: integer('id').primaryKey(),
	user_id: integer('user_id')
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	image_id: integer('image_id').references(() => images.id, { onDelete: 'set null' }),
	body: text('body').notNull(),
	created_at: text('created_at').default(sql`CURRENT_TIMESTAMP`)
});

export const comments = sqliteTable('comments', {
	id: integer('id').primaryKey(),
	post_id: integer('post_id')
		.notNull()
		.references(() => posts.id, { onDelete: 'cascade' }),
	user_id: integer('user_id')
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	body: text('body').notNull(),
	created_at: text('created_at').default(sql`CURRENT_TIMESTAMP`)
});

export const chats = sqliteTable('chats', {
	id: integer('id').primaryKey(),
	user_id: integer('user_id')
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	// image_id: integer('image_id').references(() => images.id, { onDelete: 'set null' }),
	role: text('role').notNull(),
	body: text('body').notNull(), // was previously "message" but I'd prefer to be more consistent
	created_at: text('created_at').default(sql`CURRENT_TIMESTAMP`)
});
