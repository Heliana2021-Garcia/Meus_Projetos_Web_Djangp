/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./apps/**/*.py", "./static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        instic: {
          bg: "#121214",
          surface: "#1a1a1f",
          gold: "#c5a059",
          borda: "#2a2a31",
        },
        texto: {
          principal: "#f5f5f7",
          secundario: "#a1a1aa",
        },
      },
    },
  },
  plugins: [],
};