import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'

// -----------------------------------------------------------------------------
// NeuroSynapse design system palette.
//
// The component templates reference a Tailwind-style token set (slate-400,
// rose-400, emerald-accent-4, violet, etc.) that is NOT part of Vuetify's
// built-in Material Design color catalogue. Left unregistered, every
// `color="slate-400"` prop and every `.text-slate-400` / `.bg-emerald-accent-4`
// utility class silently resolves to nothing, which is why secondary text and
// status tints were washing out while the few genuinely-valid MD tokens
// (cyan-accent-3, amber-accent-3, purple-accent-2) rendered as raw, unthemed
// neon. Registering the full palette below makes every one of those color
// props and utility classes resolve correctly, with Vuetify auto-deriving
// correct on-color contrast for avatars/chips — no template changes required.
// -----------------------------------------------------------------------------
const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'dark',
    themes: {
      dark: {
        dark: true,
        colors: {
          background: '#0B0F17',
          surface: '#0F172A',
          primary: '#00E5FF',
          secondary: '#94A3B8',
          accent: '#6ee7b7',
          error: '#fca5a5',
          warning: '#fcd34d',
          success: '#6ee7b7',
          info: '#93c5fd',

          // Soft cyan — primary telemetry accent
          cyan: '#00E5FF',
          'cyan-glow': '#22D3EE',

          // Controlled violet/purple — system policy & AI accent
          violet: '#A855F7',
          'violet-accent': '#C084FC',
          'violet-deep': '#7E22CE',
          'violet-soft': 'rgba(168, 85, 247, 0.14)',

          // Slate — text hierarchy & neutral surfaces
          'slate-100': '#F1F5F9',
          'slate-200': '#E2E8F0',
          'slate-300': '#CBD5E1',
          'slate-400': '#94A3B8',
          'slate-500': '#64748B',
          'slate-600': '#475569',
          'slate-700': '#334155',
          'slate-800': '#1E293B',
          'slate-900': '#0F172A',
          'slate-950': '#0B0F17',

          // Rose — critical / error status
          'rose-200': '#FECDD3',
          'rose-300': '#FDA4AF',
          'rose-400': '#FB7185',
          'rose-accent-3': '#F43F5E',

          // Emerald — success / healthy status
          'emerald-accent-3': '#34D399',
          'emerald-accent-4': '#6EE7B7',
        },
      },
    },
  },
})

export default vuetify
