import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heading: ["var(--font-manrope)", "system-ui", "sans-serif"],
        body: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      colors: {
        rl: {
          bg: "var(--rl-bg)",
          surface: "var(--rl-surface)",
          text: "var(--rl-text)",
          textStrong: "var(--rl-text-strong)",
          textMuted: "var(--rl-text-muted)",
          border: "var(--rl-border)",
          black: "var(--rl-black)",
          red: "var(--rl-red)",
          redHover: "var(--rl-red-hover)",
          redLight: "var(--rl-red-light)",
          success: "var(--rl-success)",
          successLight: "var(--rl-success-light)",
          warning: "var(--rl-warning)",
          warningLight: "var(--rl-warning-light)",
        },
      },
      borderRadius: {
        rl: "var(--rl-radius)",
        "rl-sm": "var(--rl-radius-sm)",
      },
      boxShadow: {
        card: "var(--rl-shadow)",
        lift: "var(--rl-shadow-lift)",
        focus: "0 0 0 3px rgba(237, 28, 36, 0.22)",
      },
      transitionTimingFunction: {
        "rl-ease": "cubic-bezier(0.25, 0.1, 0.25, 1)",
      },
      animation: {
        "fade-in": "fadeIn var(--rl-duration-fast) ease-out",
        "slide-in-right": "slideInRight var(--rl-duration-fast) ease-out",
        "slide-out-right": "slideOutRight var(--rl-duration-fast) ease-in",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        slideInRight: {
          from: { opacity: "0", transform: "translateX(16px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        slideOutRight: {
          from: { opacity: "1", transform: "translateX(0)" },
          to: { opacity: "0", transform: "translateX(16px)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
