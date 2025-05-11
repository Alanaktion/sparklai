<script type="ts">
let { image } = $props()
let params = JSON.parse(image.params)[0]
let imgClass = ''
let lightbox = $state(false)

function keyup(e) {
  if (e.key == 'Escape') {
    lightbox = false
  }
}
</script>

<img src="http://127.0.0.1:5000/images/{image.id}" alt class="w-full {imgClass}" onclick={() => lightbox = true}>

{#if lightbox}
<div class="fixed inset-0 flex items-center justify-center bg-white/80 dark:bg-black/80" onclick={() => lightbox = false}>
  <img src="http://127.0.0.1:5000/images/{image.id}" alt>
  <p class="text-xs fixed bottom-3 inset-x-3">{params.prompt}</p>
</div>
{/if}

<svelte:window onkeyup={keyup} />
