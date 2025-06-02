import { relations, sql } from 'drizzle-orm';
import { blob, integer, sqliteTable, text, type AnySQLiteColumn } from 'drizzle-orm/sqlite-core';
import type { LlamaMessage } from '../chat';
import type { StableDiffusionParams } from '../sd';

// Field Types
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

// Models
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
	type: text().notNull().default('image/webp'),
	data: blob({ mode: 'buffer' }).notNull(),
	blur: integer({ mode: 'boolean' }).notNull().default(false)
});

export const media = sqliteTable('media', {
	id: integer().primaryKey(),
	user_id: integer()
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	params: text({ mode: 'json' }),
	type: text().notNull(),
	data: blob({ mode: 'buffer' }).notNull()
});

export const posts = sqliteTable('posts', {
	id: integer().primaryKey(),
	user_id: integer()
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	image_id: integer().references(() => images.id, { onDelete: 'set null' }),
	media_id: integer().references(() => media.id, { onDelete: 'set null' }),
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
	role: text().notNull().$type<LlamaMessage['role']>(),
	body: text().notNull(),
	created_at: text().default(sql`CURRENT_TIMESTAMP`)
});

// Model relations
export const userRelations = relations(users, ({ one, many }) => ({
	image: one(images, {
		fields: [users.image_id],
		references: [images.id]
	}),
	posts: many(posts),
	images: many(images),
	media: many(media),
	comments: many(comments),
	chats: many(chats)
}));

export const imageRelations = relations(images, ({ one, many }) => ({
	user: one(users, {
		fields: [images.user_id],
		references: [users.id]
	}),
	posts: many(posts)
}));

export const mediaRelations = relations(media, ({ one, many }) => ({
	user: one(users, {
		fields: [media.user_id],
		references: [users.id]
	}),
	posts: many(posts)
}));

export const postRelations = relations(posts, ({ one, many }) => ({
	user: one(users, {
		fields: [posts.user_id],
		references: [users.id]
	}),
	image: one(images, {
		fields: [posts.image_id],
		references: [images.id]
	}),
	media: one(media, {
		fields: [posts.media_id],
		references: [media.id]
	}),
	comments: many(comments)
}));

export const commentRelations = relations(comments, ({ one }) => ({
	post: one(posts, {
		fields: [comments.post_id],
		references: [posts.id]
	}),
	user: one(users, {
		fields: [comments.user_id],
		references: [users.id]
	})
}));

export const chatRelations = relations(chats, ({ one }) => ({
	user: one(users, {
		fields: [chats.user_id],
		references: [users.id]
	}),
	image: one(images, {
		fields: [chats.image_id],
		references: [images.id]
	})
}));

// Model Types
export type UserType = typeof users.$inferSelect;
export type ImageType = typeof images.$inferSelect;
export type PostType = typeof posts.$inferSelect;
export type CommentType = typeof comments.$inferSelect;
export type ChatType = typeof chats.$inferSelect;
