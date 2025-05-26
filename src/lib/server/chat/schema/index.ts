export const post_system = `Generate realistic social media posts the given character in a JSON format, incorporating their personality, background, and relationships. Include image generation keywords if the post should include an image.`;

export const post_image_system = `Create social media image prompts based on provided context, aligning generated images with post content and user personality.

1. Analyze Context & User Profile: Examine post body and user demographics to understand core message and personality.
2. Generate Keywords for Image Content: Create a list of keywords that accurately represent desired image, considering medium and visual elements.`;

export const profile_image_system = ``;

export const user_system = `Generate a realistic user profile as a JSON object, adhering to the provided schema for data types and constraints.`;

export const user_themed = (theme: string) =>
	`Generate a realistic user profile as a JSON object, adhering to the provided schema for data types and constraints. The theme of the site is ${theme}.`;
