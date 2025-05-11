<script lang="ts">
import { onMount } from 'svelte'
import { page } from '$app/stores'

import Avatar from '$lib/components/Avatar.svelte'
import ChatMessage from '$lib/components/ChatMessage.svelte'

let params = $state(null)
page.subscribe(curPage => {
  params = curPage.params
})

let user = $state(null)
let chats = $state([])
onMount(async () => {
  fetch(`http://127.0.0.1:5000/users/${params.user_id}`)
    .then(response => response.json())
    .then(body => {
      user = body
    })
  fetch(`http://127.0.0.1:5000/chats/${params.user_id}`)
    .then(response => response.json())
    .then(body => {
      chats = body
    })
})


let timeoutId
function debounce(callback, delay=5e3) {
  return function(...args) {
    const context = this
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => {
      callback.apply(context, args)
    }, delay)
  };
}
// TODO: do this but Svelte-y
// onUnmount(() => clearTimeout(timeoutId))
function change() {
  // TODO: cancel handler if user starts typing again so they can queue up a few messages.
  clearTimeout(timeoutId)
}

function respond() {
  responding = true
  fetch(`http://127.0.0.1:5000/chats/${params.user_id}/respond`, { method: 'POST' })
    .then(response => response.json())
    .then(body => {
      responding = false
      chats.push(body)
    })
    .catch(() => responding = false)
}

let responding = $state(false)
const debouncedResponse = debounce(respond)

let form
let message = $state('')
function submit(e) {
  e.preventDefault()
  fetch(`http://127.0.0.1:5000/chats/${params.user_id}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: `message=${encodeURIComponent(message)}`
  })
    .then(response => response.json())
    .then(body => {
      chats.push(body)
      debouncedResponse()
    })
  message = ''
}
</script>

<svelte:head>
  <title>Chat with {user && user.name}</title>
</svelte:head>

{#if user}
<div class="flex flex-col items-center my-2 py-2 sticky top-0 bg-white/80 dark:bg-slate-800/80 backdrop-blur">
  <Avatar user={user} />
  <a href="/users/{user.id}">{user.name}</a>
</div>
{/if}

<div class="max-w-3xl px-4 mx-auto my-4">

  <div class="flex flex-col gap-2">
    {#each chats as chat}
    <ChatMessage chat={chat} />
    {/each}
    {#if responding}
    <div class="bg-slate-50 dark:bg-slate-900 self-start px-3 pt-2 rounded-2xl">
      <svg xmlns="http://www.w3.org/2000/svg" class="size-6 text-slate-500 animate-bounce" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="1"/>
        <circle cx="19" cy="12" r="1"/>
        <circle cx="5" cy="12" r="1"/>
      </svg>
    </div>
    {/if}
  </div>

  <form bind:this={form} onsubmit={submit} class="flex items-center gap-2 mt-6 py-2 sticky bottom-0 bg-white/80 dark:bg-slate-800/80 backdrop-blur">
    {#if responding}
    <svg xmlns="http://www.w3.org/2000/svg" class="size-4 mx-1 text-slate-600 dark:text-slate-400 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 2v4"/>
      <path d="m16.2 7.8 2.9-2.9"/>
      <path d="M18 12h4"/>
      <path d="m16.2 16.2 2.9 2.9"/>
      <path d="M12 18v4"/>
      <path d="m4.9 19.1 2.9-2.9"/>
      <path d="M2 12h4"/>
      <path d="m4.9 4.9 2.9 2.9"/>
    </svg>
    {:else}
    <button onclick={respond} type="button" class="hover:bg-sky-100 dark:hover:bg-sky-800 text-sky-600 dark:text-sky-400 text-sm p-1 rounded">
      <span class="sr-only">Add AI response</span>
      <svg xmlns="http://www.w3.org/2000/svg" class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72"/>
        <path d="m14 7 3 3"/>
        <path d="M5 6v4"/>
        <path d="M19 14v4"/>
        <path d="M10 2v2"/>
        <path d="M7 8H3"/>
        <path d="M21 16h-4"/>
        <path d="M11 3H9"/>
      </svg>
    </button>
    {/if}
    <input autocomplete="off" bind:value={message} onchange={change} name="message" autofocus class="flex w-full rounded-2xl border border-slate-500 bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-slate-300 focus:border-sky-600 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500 disabled:opacity-50" type="text" placeholder="Message">
    <button type="submit" class="hover:bg-sky-100 dark:hover:bg-sky-800 text-sky-600 dark:text-sky-400 text-sm px-2 py-1 rounded-2xl">
      Send
    </button>
  </form>
</div>
