import { createApp } from 'vue'
import {
  ElAside,
  ElAvatar,
  ElButton,
  ElContainer,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElHeader,
  ElIcon,
  ElLoading,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElTag,
} from 'element-plus'
import './element-plus.css'
import './styles.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

const elementComponents = [
  ElAside,
  ElAvatar,
  ElButton,
  ElContainer,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElHeader,
  ElIcon,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElTag,
]

elementComponents.forEach((component) => app.component(component.name, component))
app.use(ElLoading)
app.use(router)
app.mount('#app')
