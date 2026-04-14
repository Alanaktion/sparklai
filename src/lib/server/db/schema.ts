import { relations, sql } from 'drizzle-orm';
import { blob, integer, sqliteTable, text, type AnySQLiteColumn } from 'drizzle-orm/sqlite-core';
import type { LlamaMessage } from '../chat';
import type {
	ImageGenerationJobStatus,
	ImageGenerationJobTarget,
	SDBackend,
	SDStyle,
	StableDiffusionParams
} from '../sd/types';

// Field Types
export type NumberScale = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;
type Location = {
	city: string;
	state_province: string;
	country: string;
};
export type Personality = {
	agreeableness: NumberScale;
	conscientiousness: NumberScale;
	extraversion: NumberScale;
	neuroticism: NumberScale;
	openness: NumberScale;
};
export type WritingStyle = {
	languages?: string[];
	emoji_frequency: NumberScale;
	formality: string;
	punctuation_style: string;
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
export const creators = sqliteTable('creators', {
	id: integer().primaryKey(),
	name: text().notNull(),
	age: integer().notNull().default(25),
	pronouns: text().notNull().default('they/them'),
	bio: text(),
	location: text({ mode: 'json' }).$type<Location>(),
	occupation: text(),
	interests: text({ mode: 'json' }).$type<string[]>(),
	relationship_status: text(),
	password_hash: text().notNull(),
	is_active: integer({ mode: 'boolean' }).notNull().default(true),
	created_at: text().default(sql`CURRENT_TIMESTAMP`)
});

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
	backstory: text(),
	additional_prompt: text().notNull().default(''),
	appearance: text({ mode: 'json' }).$type<Appearance>(),
	image_id: integer().references((): AnySQLiteColumn => images.id),
	creator_id: integer()
		.notNull()
		.references(() => creators.id, { onDelete: 'cascade' }),
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
	body_en: text(),
	created_at: text().default(sql`CURRENT_TIMESTAMP`)
});

export const comments = sqliteTable('comments', {
	id: integer().primaryKey(),
	post_id: integer()
		.notNull()
		.references(() => posts.id, { onDelete: 'cascade' }),
	user_id: integer().references(() => users.id, { onDelete: 'cascade' }),
	body: text().notNull(),
	body_en: text(),
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
	body_en: text(),
	created_at: text().default(sql`CURRENT_TIMESTAMP`)
});

export const imageGenerationJobs = sqliteTable('image_generation_jobs', {
	id: integer().primaryKey(),
	user_id: integer()
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	post_id: integer().references(() => posts.id, { onDelete: 'cascade' }),
	image_id: integer().references(() => images.id, { onDelete: 'set null' }),
	provider: text().notNull().$type<SDBackend>(),
	status: text().notNull().$type<ImageGenerationJobStatus>().default('queued'),
	target: text().notNull().$type<ImageGenerationJobTarget>(),
	image_style: text().notNull().$type<SDStyle>(),
	prompt: text().notNull(),
	negative_prompt: text(),
	width: integer().notNull(),
	height: integer().notNull(),
	include_default_prompt: integer({ mode: 'boolean' }).notNull().default(true),
	set_as_user_image: integer({ mode: 'boolean' }).notNull().default(false),
	provider_job_id: text(),
	provider_metadata: text({ mode: 'json' }).$type<Record<string, unknown>>(),
	error: text(),
	created_at: text().default(sql`CURRENT_TIMESTAMP`),
	updated_at: text().default(sql`CURRENT_TIMESTAMP`),
	started_at: text(),
	completed_at: text()
});

export const relationships = sqliteTable('relationships', {
	id: integer().primaryKey(),
	user_id: integer()
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	related_user_id: integer()
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	relationship_type: text(),
	description: text(),
	created_at: text().default(sql`CURRENT_TIMESTAMP`)
});

// Model relations
export const creatorRelations = relations(creators, ({ many }) => ({
	users: many(users)
}));

export const userRelations = relations(users, ({ one, many }) => ({
	creator: one(creators, {
		fields: [users.creator_id],
		references: [creators.id]
	}),
	image: one(images, {
		fields: [users.image_id],
		references: [images.id]
	}),
	posts: many(posts),
	images: many(images),
	media: many(media),
	comments: many(comments),
	chats: many(chats),
	imageGenerationJobs: many(imageGenerationJobs),
	relationships: many(relationships, { relationName: 'user' })
}));

export const imageRelations = relations(images, ({ one, many }) => ({
	user: one(users, {
		fields: [images.user_id],
		references: [users.id]
	}),
	posts: many(posts),
	imageGenerationJobs: many(imageGenerationJobs)
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
	comments: many(comments),
	imageGenerationJobs: many(imageGenerationJobs)
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

export const imageGenerationJobRelations = relations(imageGenerationJobs, ({ one }) => ({
	user: one(users, {
		fields: [imageGenerationJobs.user_id],
		references: [users.id]
	}),
	post: one(posts, {
		fields: [imageGenerationJobs.post_id],
		references: [posts.id]
	}),
	image: one(images, {
		fields: [imageGenerationJobs.image_id],
		references: [images.id]
	})
}));

export const relationshipRelations = relations(relationships, ({ one }) => ({
	user: one(users, {
		fields: [relationships.user_id],
		references: [users.id],
		relationName: 'user'
	}),
	relatedUser: one(users, {
		fields: [relationships.related_user_id],
		references: [users.id]
	})
}));

// Model Types
export type CreatorType = typeof creators.$inferSelect;
export type UserType = typeof users.$inferSelect;
export type ImageType = typeof images.$inferSelect;
export type ImageGenerationJobType = typeof imageGenerationJobs.$inferSelect;
export type PostType = typeof posts.$inferSelect;
export type CommentType = typeof comments.$inferSelect;
export type ChatType = typeof chats.$inferSelect;
export type RelationshipType = typeof relationships.$inferSelect;
