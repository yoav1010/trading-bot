import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served from https://yoav1010.github.io/trading-bot/
export default defineConfig({
  base: "/trading-bot/",
  plugins: [react()],
});
