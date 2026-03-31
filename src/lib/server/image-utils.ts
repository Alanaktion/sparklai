import sharp from 'sharp';

const MAX_DIMENSION = 1280;
const WEBP_QUALITY = 80;

/**
 * Converts image data to compressed lossy WebP, resizing so the largest
 * dimension is at most MAX_DIMENSION (1280px). Never enlarges images.
 *
 * Copies metadata from the input where possible:
 * - PNG text chunks (e.g. ComfyUI "prompt"/"workflow") are mapped to EXIF IFD0
 *   fields (Make / ImageDescription) with a matching "Prompt: " / "Workflow: " prefix.
 * - Existing EXIF/IPTC/XMP on the input is preserved via withMetadata().
 */
export async function toWebp(input: Buffer | Uint8Array): Promise<Buffer> {
	const inputBuffer = Buffer.from(input);
	const metadata = await sharp(inputBuffer).metadata();

	let pipeline = sharp(inputBuffer).resize(MAX_DIMENSION, MAX_DIMENSION, {
		fit: 'inside',
		withoutEnlargement: true
	});

	// Map PNG text chunks (e.g. ComfyUI workflow/prompt) to EXIF fields
	const exifIFD0: Record<string, string> = {};
	for (const { keyword, text } of metadata.comments ?? []) {
		if (keyword === 'workflow') exifIFD0['ImageDescription'] = `Workflow: ${text}`;
		else if (keyword === 'prompt') exifIFD0['Make'] = `Prompt: ${text}`;
	}

	if (Object.keys(exifIFD0).length > 0) {
		pipeline = pipeline.withMetadata({ exif: { IFD0: exifIFD0 } });
	} else if (metadata.exif || metadata.iptc || metadata.xmp) {
		pipeline = pipeline.withMetadata();
	}

	return pipeline.webp({ quality: WEBP_QUALITY }).toBuffer();
}
