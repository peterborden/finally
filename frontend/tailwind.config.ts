import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Terminal surfaces (no pure black).
        bg: {
          base: '#0d1117',
          panel: '#161b22',
          raised: '#1a1a2e',
          hover: '#21262d',
        },
        border: {
          subtle: '#30363d',
          muted: '#21262d',
        },
        // Brand accents (PLAN §1).
        accent: '#ecad0a',
        brand: '#209dd7',
        submit: '#753991',
        // Market semantics.
        up: '#3fb950',
        down: '#f85149',
        flat: '#8b949e',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      keyframes: {
        'flash-up': {
          '0%': { backgroundColor: 'rgba(63, 185, 80, 0.35)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'flash-down': {
          '0%': { backgroundColor: 'rgba(248, 81, 73, 0.35)' },
          '100%': { backgroundColor: 'transparent' },
        },
      },
      animation: {
        'flash-up': 'flash-up 500ms ease-out',
        'flash-down': 'flash-down 500ms ease-out',
      },
    },
  },
  plugins: [],
};

export default config;
