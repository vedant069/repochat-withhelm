/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f6f5ff',
          100: '#edebfe',
          200: '#dcd7fe',
          300: '#cabffd',
          400: '#ac94fa',
          500: '#9061f9',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
          950: '#2e1065',
        },
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: 'none',
            code: {
              backgroundColor: 'rgb(243 244 246)',
              padding: '0.2em 0.4em',
              borderRadius: '0.25rem',
              fontWeight: '400',
            },
            'code::before': {
              content: '""',
            },
            'code::after': {
              content: '""',
            },
          },
        },
      },
      keyframes: {
        'fade-in': {
          '0%': { 
            opacity: '0', 
            transform: 'translateY(10px)' 
          },
          '100%': { 
            opacity: '1', 
            transform: 'translateY(0)' 
          },
        },
        'slide-up': {
          '0%': { 
            opacity: '0', 
            transform: 'translateY(20px)' 
          },
          '100%': { 
            opacity: '1', 
            transform: 'translateY(0)' 
          },
        },
        pulse: {
          '0%, 100%': {
            opacity: '1',
          },
          '50%': {
            opacity: '0.8',
          },
        },
        'scale-up': {
          '0%': { 
            transform: 'scale(0.95)',
            opacity: '0' 
          },
          '100%': { 
            transform: 'scale(1)',
            opacity: '1' 
          },
        }
      },
      animation: {
        'fade-in': 'fade-in 0.6s ease-out forwards',
        'slide-up': 'slide-up 0.8s ease-out',
        'pulse': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scale-up': 'scale-up 0.5s ease-out forwards'
      },
    },
  },
  plugins: [
    require('tailwind-scrollbar'),
  ],
};