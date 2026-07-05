import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        base: '#0d1117',
        panel: '#1a1a2e',
        'border-muted': '#2a2a3a',
        accent: '#ecad0a',
        blue: '#209dd7',
        purple: '#753991',
        up: '#3fb950',
        down: '#f85149',
      },
      fontFamily: {
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Consolas',
          '"Liberation Mono"',
          'monospace',
        ],
      },
    },
  },
  plugins: [],
};

export default config;
