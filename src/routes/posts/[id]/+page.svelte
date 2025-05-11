<script lang="ts">
import { onMount } from 'svelte'
import { page } from '$app/stores'

import Avatar from '$lib/components/Avatar.svelte'
import Post from '$lib/components/Post.svelte'

let params = $state(null)
page.subscribe(curPage => {
  params = curPage.params
})

let user = $state(null)
let post = $state(null)
let comments = $state([])
onMount(async () => {
  fetch(`http://127.0.0.1:5000/posts/${params.id}`)
    .then(response => response.json())
    .then(body => {
      post = body
      fetch(`http://127.0.0.1:5000/users/${body.user_id}`)
        .then(response => response.json())
        .then(body => {
          user = body
        })
    })
  fetch(`http://127.0.0.1:5000/posts/${params.id}/comments`)
    .then(response => response.json())
    .then(body => comments = body)
})

let creating = $state(false)
function addImage() {
  creating = true
  fetch(`http://127.0.0.1:5000/posts/${params.id}/image`, { method: 'POST' })
    .then(response => response.json())
    .then(body => {
      creating = false
      post = body
    })
    .catch(() => creating = false)
}

let responding = $state(false)
function respond() {
  responding = true
  fetch(`http://127.0.0.1:5000/posts/${params.id}/respond`, { method: 'POST' })
    .then(response => response.json())
    .then(body => {
      responding = false
      comments.push(body)
    })
    .catch(() => responding = false)
}

let form
let message = $state('')
function submit(e) {
  e.preventDefault()
  fetch(`http://127.0.0.1:5000/posts/${params.id}/comments`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: `message=${encodeURIComponent(message)}`
  })
    .then(response => response.json())
    .then(body => comments.push(body))
  message = ''
}

function deletePost() {
  // TODO: CORS for DELETE is not an option, will need to POST with `_method` param or whatevs.
  fetch(`http://127.0.0.1:5000/posts/${params.id}`, { method: 'DELETE' })
    .then(() => location = '/')
}
</script>

<svelte:head>
  <title>Post by {user && user.name}</title>
</svelte:head>

{#if post}
<div class="max-w-xl mx-auto my-4">
  {#if !post.image_id}
  <div class="flex items-center justify-end">
    {#if creating}
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
    <button onclick={addImage} type="button" class="hover:bg-sky-100 dark:hover:bg-sky-800 text-sky-600 dark:text-sky-400 text-sm p-1 rounded">
      <span class="sr-only">Add AI image</span>
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-image-plus size-4">
        <path d="M16 5h6"/>
        <path d="M19 2v6"/>
        <path d="M21 11.5V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7.5"/>
        <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>
        <circle cx="9" cy="9" r="2"/>
      </svg>
    </button>
    {/if}
    <button onclick={deletePost} type="button" class="hover:bg-red-100 dark:hover:bg-red-800 text-red-600 dark:text-red-400 text-sm p-1 rounded">
      <span class="sr-only">Delete post</span>
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-trash-2 size-4">
        <path d="M3 6h18"/>
        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
        <line x1="10" x2="10" y1="11" y2="17"/>
        <line x1="14" x2="14" y1="11" y2="17"/>
      </svg>
    </button>
  </div>
  {/if}

  <Post post={post} user={user} full />

  <div class="mb-4 lg:mb-6">
    <div class="text-slate-700 dark:text-slate-300">Comments</div>

    {#each comments as comment}
    <div class="flex gap-3 my-4">
      <Avatar user={comment.user} class="size-10" />
      <div>
        <div class="leading-tight text-sm">
          {#if comment.user_id}
          <a class="text-sky-600 dark:text-sky-400 hover:underline" href="/users/{comment.user_id}">{comment.user.name}</a>
          {:else}
          <span class="text-slate-500">User</span>
          {/if}
        </div>
        <p>{comment.body}</p>
      </div>
    </div>
    {/each}

    <form bind:this={form} onsubmit={submit} class="flex items-center gap-2 mt-5 py-2">
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
        <span class="sr-only">Add AI comment</span>
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
      <input autocomplete="off" bind:value={message} name="message" autofocus class="flex w-full rounded-2xl border border-slate-500 bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-slate-300 focus:border-sky-600 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500 disabled:opacity-50" type="text" placeholder="Comment">
      <button type="submit" class="hover:bg-sky-100 dark:hover:bg-sky-800 text-sky-600 dark:text-sky-400 text-sm px-2 py-1 rounded-2xl">
        Post
      </button>
    </form>
  </div>
</div>
{:else}
<svg xmlns="http://www.w3.org/2000/svg" class="size-12 mx-auto my-6 text-slate-600 dark:text-slate-400 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 2v4"/>
  <path d="m16.2 7.8 2.9-2.9"/>
  <path d="M18 12h4"/>
  <path d="m16.2 16.2 2.9 2.9"/>
  <path d="M12 18v4"/>
  <path d="m4.9 19.1 2.9-2.9"/>
  <path d="M2 12h4"/>
  <path d="m4.9 4.9 2.9 2.9"/>
</svg>
{/if}
