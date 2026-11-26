<template>
  <main class="recovery-page">
    <router-link class="recovery-brand" to="/"><BrandMark /> 学伴管家</router-link>
    <section aria-labelledby="recovery-title">
      <h1 id="recovery-title">找回密码</h1>
      <PasswordSecurityForm mode="reset" />
      <router-link class="login-link" to="/login">返回登录</router-link>
    </section>
  </main>
</template>

<script setup>
import BrandMark from '../components/BrandMark.vue'
import PasswordSecurityForm from '../components/PasswordSecurityForm.vue'
</script>

<style scoped>
.recovery-page { max-width: 480px; margin: 5vh auto; padding: 20px; }
.recovery-brand { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 700; }
section { margin-top: 24px; padding: clamp(18px, 4vw, 32px); border-radius: var(--ledger-radius); background: var(--ledger-paper); box-shadow: var(--ledger-shadow); }
h1 { margin: 0 0 16px; font-size: 26px; }
.login-link { display: inline-block; margin-top: 20px; text-decoration: underline; text-underline-offset: 3px; }
</style>
