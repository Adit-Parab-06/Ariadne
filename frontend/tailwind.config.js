/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-2": "var(--bg-2)",
        "bg-3": "var(--bg-3)",
        label: "var(--label)",
        "label-2": "var(--label-2)",
        "label-3": "var(--label-3)",
        sep: "var(--sep)",
        fill: "var(--fill)",
        blue: "var(--blue)",
        green: "var(--green)",
        orange: "var(--orange)",
        red: "var(--red)",
        indigo: "var(--indigo)",
        purple: "var(--purple)",
        teal: "var(--teal)",
        material: "var(--material)",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "'SF Pro Text'",
          "'SF Pro Display'",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "'SF Mono'",
          "Menlo",
          "monospace",
        ],
      },
      borderRadius: {
        button: "12px",
        card: "20px",
        sheet: "28px",
        pill: "9999px",
      },
      boxShadow: {
        apple: "var(--shadow)",
      },
    },
  },
  plugins: [],
}
