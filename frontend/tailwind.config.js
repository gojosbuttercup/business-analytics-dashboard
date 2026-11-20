/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#10233f",
        mint: "#0f766e",
        cloud: "#f7f9fc",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.03), 0 8px 24px rgba(15, 23, 42, 0.04)",
      },
    },
  },
  plugins: [],
};

