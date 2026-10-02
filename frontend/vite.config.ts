import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API runs on port 8000 (the Compose backend); in the container nginx does the same proxying.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
