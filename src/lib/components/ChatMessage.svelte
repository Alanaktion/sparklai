<script lang="ts">
let { chat } = $props()
const cls = chat.role == 'user' ? 'bg-sky-500 dark:bg-sky-600 text-white self-end' : 'bg-slate-50 dark:bg-slate-900 self-start'
</script>

<div class="{cls} px-3 py-1 max-w-lg rounded-2xl">
  <p class="whitespace-pre-wrap">{chat.message}</p>
</div>
