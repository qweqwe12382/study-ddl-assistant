const entrances = new WeakMap()

// The handout opens once when it is actually visible; reading and input always win.
export function createFolioEntrance(element, platform = window) {
  const preference = platform.matchMedia?.('(prefers-reduced-motion: reduce)')
  if (preference?.matches || typeof element.animate !== 'function') return () => {}

  const page = platform.document
  let observer
  let animation
  let stopped = false

  function stop() {
    if (stopped) return
    stopped = true
    observer?.disconnect()
    animation?.cancel()
    preference?.removeEventListener?.('change', onPreferenceChange)
    page.removeEventListener('visibilitychange', onVisibilityChange)
    element.removeEventListener('pointerdown', stop)
    element.removeEventListener('focusin', stop)
  }

  function onPreferenceChange() { if (preference.matches) stop() }
  function onVisibilityChange() { if (page.hidden) stop() }

  function enter() {
    if (stopped || animation) return
    observer?.disconnect()
    if (preference?.matches || page.hidden || !element.isConnected) { stop(); return }
    try {
      animation = element.animate([
        { opacity: .7, transform: 'perspective(1000px) rotateY(-9deg)', clipPath: 'inset(-15% -15% -15% 6% round 10px)' },
        { opacity: 1, transform: 'perspective(1000px) rotateY(0deg)', clipPath: 'inset(-15% -15% -15% -15% round 10px)' },
      ], { duration: 640, easing: 'cubic-bezier(0.16, 1, 0.3, 1)' })
      animation.finished.then(stop, stop)
    } catch {
      stop()
    }
  }

  preference?.addEventListener?.('change', onPreferenceChange)
  page.addEventListener('visibilitychange', onVisibilityChange)
  element.addEventListener('pointerdown', stop, { once: true })
  element.addEventListener('focusin', stop, { once: true })
  if (platform.IntersectionObserver) {
    observer = new platform.IntersectionObserver((entries) => {
      if (entries.some(entry => entry.isIntersecting)) enter()
    }, { threshold: .12, rootMargin: '0px 0px -24px 0px' })
    observer.observe(element)
  } else {
    enter()
  }
  return stop
}

export const vFolioEnter = {
  mounted(element) { entrances.set(element, createFolioEntrance(element)) },
  beforeUnmount(element) { entrances.get(element)?.(); entrances.delete(element) },
}
