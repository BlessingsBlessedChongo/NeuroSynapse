import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'dark',
    themes: {
      dark: {
        dark: true,
        colors: {
          background: '#0f172a',
          surface: '#1e293b',
          primary: '#38bdf8',
          secondary: '#94a3b8',
          accent: '#6ee7b7',
          error: '#fca5a5',
          warning: '#fcd34d',
          success: '#6ee7b7',
          info: '#93c5fd',
        },
      },
    },
  },
})

export default vuetify