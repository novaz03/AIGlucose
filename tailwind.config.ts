import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./context/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(210 38% 92%)",
        input: "hsl(210 38% 92%)",
        ring: "hsl(142.1 76.2% 36.3%)",
        background: "hsl(210 40% 96%)",
        foreground: "hsl(222.2 47.4% 11.2%)",
        primary: {
          DEFAULT: "hsl(142.1 76.2% 36.3%)",
          foreground: "hsl(0 0% 100%)"
        },
        secondary: {
          DEFAULT: "hsl(210 30% 96%)",
          foreground: "hsl(222.2 47.4% 11.2%)"
        },
        muted: {
          DEFAULT: "hsl(210 30% 96%)",
          foreground: "hsl(215.4 16.3% 46.9%)"
        },
        accent: {
          DEFAULT: "hsl(210 30% 96%)",
          foreground: "hsl(222.2 47.4% 11.2%)"
        },
        destructive: {
          DEFAULT: "hsl(0 72.2% 50.6%)",
          foreground: "hsl(210 40% 98%)"
        },
        card: {
          DEFAULT: "hsl(0 0% 100%)",
          foreground: "hsl(222.2 47.4% 11.2%)"
        }
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem"
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"]
      }
    }
  },
  plugins: []
};

export default config;
