export const loadJson = async (path: string, init?: RequestInit) => {
	const response = await fetch(`/${path}`, init);
	return await response.json();
};
