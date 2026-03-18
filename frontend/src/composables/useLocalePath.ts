import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * Returns a helper to prefix paths with /en when the current locale is English.
 * Polish (default) has no prefix.
 */
export function useLocalePath() {
  const { locale } = useI18n()

  const prefix = computed(() => locale.value === 'en' ? '/en' : '')

  function localePath(path: string): string {
    if (path === '/') return prefix.value || '/'
    return `${prefix.value}${path}`
  }

  return { localePath, localePrefix: prefix }
}
