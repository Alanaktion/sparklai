<script lang="ts">
import { tick, onMount } from 'svelte'
import Avatar from './Avatar.svelte'

let { post, user, full = false } = $props()
let imgClass = full ? '' : 'object-cover aspect-16/9'

function formatISODate(isoDate) {
  const now = new Date()
  const date = new Date(`${isoDate}-00:00`)

  const seconds = (now - date) / 1000
  if (seconds < 60) {
    return 'just now'
  } else if (seconds < 3600) {
    return `${Math.floor(seconds / 60)} minute${seconds >= 120 ? 's' : ''} ago`
  } else if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)} hour${seconds >= 3600*2 ? 's' : ''} ago`
  }
  return date.toLocaleString()
}

onMount(() => setInterval(tick, 10e3))
</script>

<div class="px-4 sm:px-0 mb-4 lg:mb-6 flex gap-4">
  <Avatar user={user} />
  <div>
    <a class="text-sky-600 dark:text-sky-400 hover:underline font-medium" href="/users/{post.user_id}">{user?.name}</a>
    {#if post.image_id}
    <div class="my-3">
      <img src="http://127.0.0.1:5000/images/{post.image_id}" alt class="w-full {imgClass}">
    </div>
    {/if}
    <p class="mb-2">{post.body}</p>
    <div class="flex gap-2 items-center border-t border-slate-200 dark:border-slate-700 py-2">
      <a href="/posts/{post.id}" class="text-sm text-slate-400 pr-4 mr-auto">{formatISODate(post.created_at)}</a>
      {#if !full}
      <a href="/posts/{post.id}" class="flex items-center gap-1 hover:bg-sky-100 dark:hover:bg-sky-800 text-sky-600 dark:text-sky-400 text-sm px-2 py-1 rounded">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-message-square-more size-4">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          <path d="M8 10h.01"/>
          <path d="M12 10h.01"/>
          <path d="M16 10h.01"/>
        </svg>
        Comments
      </a>
      {/if}
    </div>
  </div>
</div>
