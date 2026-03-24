import sharp from 'sharp';

const MAX_DIMENSION = 1280;
const WEBP_QUALITY = 80;

/**
 * Converts image data to compressed lossy WebP, resizing so the largest
 * dimension is at most MAX_DIMENSION (1280px). Never enlarges images.
 */
export async function toWebp(input: Buffer | Uint8Array): Promise<Buffer> {
	return sharp(Buffer.from(input))
		.resize(MAX_DIMENSION, MAX_DIMENSION, {
			fit: 'inside',
			withoutEnlargement: true
		})
		.webp({ quality: WEBP_QUALITY })
		.toBuffer();
}
