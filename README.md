# SparklAI ✨

This is a fake social media site that generates all of its users, posts, images, and DMs with open source AI APIs like Llama and Stable Diffusion.

Front-end is a SvelteKit app, with source in `src/`, startable with `pnpm run dev`.

Back-end server is a Flask Python app, with source in `server/`, startable by `start.fish`. LM Studio and Stable Diffusion Web UI must have their APIs running to generate content. Browsing existing content does not require them to be running.
