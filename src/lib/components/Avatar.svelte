<script lang="ts">
let { user, class: cls = 'size-12' } = $props()
</script>

{#if user?.image_id}
<img src="http://127.0.0.1:5000/images/{user?.image_id}" alt={user?.name} class="{cls} rounded-full">
{:else}
<div class="{cls} p-2 rounded-full bg-slate-100 dark:bg-slate-600">
  <svg xmlns="http://www.w3.org/2000/svg" class="h-full aspect-square text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </svg>
</div>
{/if}
