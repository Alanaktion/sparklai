<script lang="ts">
import { onMount } from 'svelte'

import Post from '$lib/components/Post.svelte'
import Avatar from '$lib/components/Avatar.svelte'

let users = $state([])
let posts = $state([])
const loadData = () => {
  fetch(`http://127.0.0.1:5000/users`)
    .then(response => response.json())
    .then(body => {
      users = body
    })
  fetch(`http://127.0.0.1:5000/posts`)
    .then(response => response.json())
    .then(body => {
      posts = body
    })
}
onMount(loadData)

let creating = $state(false)
const newUser = () => {
  creating = true
  fetch(`http://127.0.0.1:5000/users`, {method: 'POST'})
    .then(() => {
      creating = false
      fetchPosts()
    })
    .catch(() => creating = false)
}

const user = id => {
  const matches = users.filter(u => u.id == id)
  return matches ? matches[0] : {}
}
</script>

<svelte:head>
  <title>Home ✨</title>
</svelte:head>

{#if users && posts}
<div class="max-w-4xl sm:mx-auto px-4 gap-6 lg:gap-8 sm:grid grid-cols-3 my-4">

  <div class="col-span-2">
    <h2 class="text-xl mb-4">Posts</h2>

    {#if posts.length}
    {#each posts as post}
    <Post post={post} user={user(post.user_id)} />
    {/each}
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
  </div>

  <div>
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl">Users</h2>
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
      <button onclick={newUser} type="button" class="hover:bg-sky-100 dark:hover:bg-sky-800 text-sky-600 dark:text-sky-400 text-sm p-1 rounded">
        <span class="sr-only">Add AI user</span>
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
    </div>

    <div class="shadow bg-slate-50 dark:bg-slate-900 rounded sticky top-4">
      {#if users.length}
      {#each users as user}
      <div class="flex items-center border-slate-200 dark:border-slate-700 border-b first:rounded-t last:rounded-b last:border-none p-3 hover:bg-slate-100 dark:hover:bg-slate-700 relative">
        <Avatar user={user} class="size-10 mr-3" />
        <div>
          <a class="block text-slate-700 dark:text-slate-300 font-medium text-sm" href="/users/{user.id}">
            <div class="absolute inset-0"></div>
            {user.name}
          </a>
          <p class="text-sm text-slate-400 dark:text-slate-500">{user.pronouns}</p>
        </div>
      </div>
      {/each}
      {:else}
      <svg xmlns="http://www.w3.org/2000/svg" class="size-12 mx-auto py-2 text-slate-600 dark:text-slate-400 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
    </div>
  </div>

</div>
{/if}
