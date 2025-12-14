/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        midnight: '#0b1021',
        cobalt: '#1a47ff',
        teal: '#38bdf8',
        mint: '#a5f3fc',
        slate: {
          950: '#0f172a'
        }
      },
      boxShadow: {
        glass: '0 10px 40px rgba(0,0,0,0.25)'
      },
      backgroundImage: {
        'gradient-aos': 'linear-gradient(135deg, #0b1021 0%, #0f172a 40%, #1a47ff 100%)'
      }
    }
  },
  plugins: [require('@tailwindcss/forms')]
};
