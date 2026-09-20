<template>
  <span class="identity-mark" aria-hidden="true">
    <svg viewBox="0 0 32 32" fill="none">
      <path d="M6 6.5h9.5V26L6 22.5V6.5Z" />
      <path d="M19 6.5h7V22l-7 2.5" />
      <path d="m10 14 3 3 7-8" class="identity-check" />
    </svg>
  </span>
</template>

<style scoped>
.identity-mark { display: inline-grid; place-items: center; flex: 0 0 auto; width: 38px; height: 38px; border-radius: 8px; color: #fff; background: var(--ledger-primary); }
svg { width: 29px; height: 29px; stroke: currentColor; stroke-width: 1.65; stroke-linecap: round; stroke-linejoin: round; }
.identity-check { stroke: #b9dcc4; stroke-width: 2; }
</style>
