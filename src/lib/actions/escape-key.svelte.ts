import { SvelteSet } from 'svelte/reactivity';

// Track components using escape key action
const activeKeyListeners: Set<HTMLElement> = new SvelteSet();

export function escapeKey(node: HTMLElement, callback: (event: KeyboardEvent) => void) {
	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			// Execute the callback of top most element
			const elements = Array.from(activeKeyListeners);
			const topmostElement = elements[elements.length - 1];
			if (node === topmostElement) callback(event);
		}
	}

	$effect(() => {
		activeKeyListeners.add(node);
		document.addEventListener('keydown', handleKeydown);

		return () => {
			activeKeyListeners.delete(node);
			document.removeEventListener('keydown', handleKeydown);
		};
	});
}
