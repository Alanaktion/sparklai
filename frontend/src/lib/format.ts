/** Human-readable local timestamp for an ISO-8601 string from the API. */
export function formatDate(iso: string): string {
	const date = new Date(iso);
	if (Number.isNaN(date.getTime())) return iso;
	return date.toLocaleString();
}
