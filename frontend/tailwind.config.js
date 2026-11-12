export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#0b1f33', 900: '#07172a', 800: '#0b1f33', 700: '#16324d', 600: '#28486a' },
        sand: { DEFAULT: '#f7f4ee', 100: '#fbf9f5', 200: '#f1ece2', 300: '#e6dfd1' },
        coral: { DEFAULT: '#f4553f', 600: '#dc3f2b', 700: '#b83322', 50: '#fff1ed', 100: '#ffe0d9' },
        sun: { DEFAULT: '#f6b73c', 50: '#fff7e3' },
        lagoon: { DEFAULT: '#0fa596', 600: '#0b8a7e', 700: '#0a6f66', 50: '#e8f8f5' },
        sky: { DEFAULT: '#3b9eea', 50: '#eef7ff' },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', '"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        sans: ['"Plus Jakarta Sans"', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      letterSpacing: { tightest: '-0.02em' },
      boxShadow: {
        soft: '0 1px 2px rgba(11,31,51,.04), 0 8px 24px -12px rgba(11,31,51,.14)',
        lift: '0 2px 4px rgba(11,31,51,.04), 0 24px 48px -20px rgba(11,31,51,.28)',
        glow: '0 10px 30px -10px rgba(244,85,63,.55)',
        ring: '0 0 0 1px rgba(11,31,51,.06)',
      },
      keyframes: {
        floaty: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-8px)' } },
        pop: { '0%': { transform: 'scale(.92)', opacity: 0 }, '100%': { transform: 'scale(1)', opacity: 1 } },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        marquee: { '0%': { transform: 'translateX(0)' }, '100%': { transform: 'translateX(-50%)' } },
        aurora: { '0%,100%': { transform: 'translate3d(0,0,0) scale(1)' }, '50%': { transform: 'translate3d(4%, -6%, 0) scale(1.12)' } },
        ping2: { '0%': { transform: 'scale(1)', opacity: .7 }, '100%': { transform: 'scale(2.4)', opacity: 0 } },
        dash: { to: { strokeDashoffset: 0 } },
        wiggle: { '0%,100%': { transform: 'rotate(0)' }, '25%': { transform: 'rotate(-8deg)' }, '75%': { transform: 'rotate(8deg)' } },
      },
      animation: {
        floaty: 'floaty 5s ease-in-out infinite', pop: 'pop .28s cubic-bezier(.2,.8,.2,1) both', marquee: 'marquee 38s linear infinite',
        aurora: 'aurora 14s ease-in-out infinite', ping2: 'ping2 1.8s cubic-bezier(0,0,.2,1) infinite', wiggle: 'wiggle .5s ease-in-out',
      },
    },
  },
  plugins: [],
}
