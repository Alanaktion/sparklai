<script lang="ts">
import { onMount } from 'svelte'
import { page } from '$app/stores'

import Avatar from '$lib/components/Avatar.svelte'
import Post from '$lib/components/Post.svelte'
import Image from '$lib/components/Image.svelte'

let params = $state(null)
page.subscribe(curPage => {
  params = curPage.params
})

let tab = $state('posts')
let user = $state(null)
let posts = $state([])
let images = $state([])
const fetchPosts = () => {
  fetch(`http://127.0.0.1:5000/users/${params.id}/posts`)
    .then(response => response.json())
    .then(body => {
      posts = body
    })
}

onMount(async () => {
  fetch(`http://127.0.0.1:5000/users/${params.id}`)
    .then(response => response.json())
    .then(body => {
      user = body
    })
  fetch(`http://127.0.0.1:5000/users/${params.id}/images`)
    .then(response => response.json())
    .then(body => {
      images = body
    })
  fetchPosts()
})

let creating = $state(false)
const newPost = () => {
  creating = true
  fetch(`http://127.0.0.1:5000/users/${params.id}/posts`, {method: 'POST'})
    .then(() => {
      creating = false
      fetchPosts()
    })
    .catch(() => {
      creating = false
    })
}
</script>

<svelte:head>
  <title>{user && user.name}</title>
</svelte:head>

{#if user}
<div class="max-w-2xl px-4 mx-auto my-4">
  <header class="bg-slate-50 dark:bg-slate-900 p-4 border-b border-slate-300 dark:border-slate-700">
    <div class="flex items-center gap-4">
      <Avatar user={user} class="size-24" />
      <div class="text-end ms-auto">
        <h1 class="text-xl font-semibold text-slate-800 dark:text-slate-200">{user.name}</h1>
        <p class="text-sm text-slate-400">{user.pronouns}</p>
      </div>
      <a href="/chat/{user.id}" class="hover:bg-sky-100 dark:hover:bg-sky-800 text-sky-600 dark:text-sky-400 text-sm p-1 rounded">
        <span class="sr-only">Messages</span>
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-message-circle"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>
      </a>
    </div>
  </header>

  <section class="py-4 px-6">
    <div class="text-slate-700 dark:text-slate-400 py-4">
      <p class="text-lg">{user.bio}</p>
    </div>
  </section>

  <section class="py-4 px-6">
    <div class="flex justify-between items-center gap-4 mb-4">
      <div class="flex items-center gap-3 text-xl font-semibold text-slate-800 dark:text-slate-200">
        <button class="cursor-pointer {tab == 'posts' ? 'border-sky-500' : 'border-transparent'} border-b-2" type="button" onclick={() => tab = 'posts'}>Posts</button>
        <button class="cursor-pointer {tab == 'images' ? 'border-sky-500' : 'border-transparent'} border-b-2" type="button" onclick={() => tab = 'images'}>Images</button>
      </div>
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
      <button onclick={newPost} type="button" class="hover:bg-sky-100 dark:hover:bg-sky-800 text-sky-600 dark:text-sky-400 text-sm p-1 rounded">
        <span class="sr-only">Add AI post</span>
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

    {#if tab == 'posts'}
    {#each posts as post}
    <Post post={post} user={user} />
    {/each}
    {:else if tab == 'images'}
    <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
    {#each images as image}
    <Image image={image} />
    {/each}
    </div>
    {/if}

  </section>

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
