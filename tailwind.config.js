// CLI config for Tailwind compilation at Docker build time.
// Keep theme in sync with static/js/tailwind.config.js (used by CDN Play in local dev).
module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  theme: {
    extend: {
      colors: {
        forest: {
          50:  '#f2f7f0',
          100: '#ddecd8',
          200: '#bcd9b4',
          300: '#8fbe82',
          400: '#63a054',
          500: '#448540',
          600: '#326832',
          700: '#28522a',
          800: '#1e3d20',
          900: '#152c17',
        },
        cream:      '#faf7f2',
        parchment:  '#f4efe6',
        stone:      '#e8e0d5',
        terracotta: '#c5602a',
        gold:       '#b8860b',
      },
      fontFamily: {
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        sans:  ['"DM Sans"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'card':    '0 2px 12px 0 rgba(0,0,0,0.07)',
        'card-lg': '0 8px 32px 0 rgba(0,0,0,0.13)',
      },
    },
  },
};
