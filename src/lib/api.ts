export const loadJson = async (path: string, init?: RequestInit) => {
	const response = await fetch(`http://127.0.0.1:5000/${path}`, init);
	return await response.json();
};
