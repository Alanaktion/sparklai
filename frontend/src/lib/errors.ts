/** Turn an unknown thrown value into a message safe to show to the user. */
export function errorMessage(cause: unknown): string {
	if (cause instanceof Error) return cause.message;
	if (typeof cause === 'string') return cause;
	return 'Something went wrong';
}
