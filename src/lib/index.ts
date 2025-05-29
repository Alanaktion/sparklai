export function formatDate(isoDate: string) {
	const now = new Date();
	const date = new Date(`${isoDate}Z`);

	const seconds = (now.getTime() - date.getTime()) / 1000;
	if (seconds < 60) {
		return 'just now';
	} else if (seconds < 3600) {
		return `${Math.floor(seconds / 60)} minute${seconds >= 120 ? 's' : ''} ago`;
	} else if (seconds < 64800) {
		return `${Math.floor(seconds / 3600)} hour${seconds >= 3600 * 2 ? 's' : ''} ago`;
	}
	return date.toLocaleString(undefined, {
		weekday: 'short',
		day: 'numeric',
		month: 'short',
		hour: 'numeric',
		minute: '2-digit'
	});
}

export function localDate(isoDate: string) {
	const date = new Date(`${isoDate}Z`);
	return date.toLocaleDateString();
}

export function localDateTime(isoDate: string) {
	const date = new Date(`${isoDate}Z`);
	return date.toLocaleString();
}
