export const post_system = `Generate a realistic social media post as JSON.

Write like a specific person, not like an assistant. Match the user's age, personality, interests, bio, relationships, life situation, and writing style closely.

The post_text field must:
- contain only the body of the post
- avoid formulaic openings and generic scene-setting
- sound natural, varied, and specific to the character
- reflect the character's likely language, tone, slang, punctuation, and emoji usage
- avoid hashtags unless the user prompt explicitly requires them

Only include image_generation when an image would feel natural for this specific post.`;

export const post_image_system = `Create social media image prompts based on provided context, aligning generated images with post content and user personality.

1. Analyze Context & User Profile: Examine post body and user demographics to understand core message and personality.
2. Generate Keywords for Image Content: Create a list of keywords that accurately represent desired image, considering medium and visual elements.
3. Select Image Style: Choose appropriate image style based on content:
   - 'photo': For realistic, photorealistic content (people in real settings, actual locations, real-world scenes)
   - 'drawing': For anime, cartoon, illustration, or hand-drawn artistic styles
   - 'stylized': For artistic 3D renders, stylized art, abstract or fantasy scenes with enhanced visual effects`;

export const profile_image_system = ``;

export const user_system = `Generate a realistic user profile as a JSON object, adhering to the provided schema for data types and constraints.`;

export const user_themed = (theme: string) =>
	`Generate a realistic user profile as a JSON object, adhering to the provided schema for data types and constraints. The theme of the site is ${theme}.`;
