import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import es from './es.json'

export const LANGUAGES = ['es', 'en'] as const
export type Language = (typeof LANGUAGES)[number]

const STORAGE_KEY = 'pulso.lang'

function isLanguage(value: string | null): value is Language {
  return LANGUAGES.some((l) => l === value)
}

function initialLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (isLanguage(saved)) return saved
  } catch {
    // localStorage no disponible (modo privado, etc.): se usa el idioma del navegador.
  }
  return navigator.language.toLowerCase().startsWith('en') ? 'en' : 'es'
}

export function setLanguage(lang: Language) {
  void i18n.changeLanguage(lang)
}

void i18n.use(initReactI18next).init({
  resources: { es: { translation: es }, en: { translation: en } },
  lng: initialLanguage(),
  fallbackLng: 'es',
  interpolation: { escapeValue: false },
})

// Persistencia y atributo lang del documento, para lectores de pantalla.
function applyLanguage(lang: string) {
  document.documentElement.lang = lang
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // Sin persistencia: la preferencia vale solo para esta sesión.
  }
}
applyLanguage(i18n.language)
i18n.on('languageChanged', applyLanguage)

export default i18n
