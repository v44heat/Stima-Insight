import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the Flask API runs on :5000; the proxy avoids CORS entirely.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:5000" } },
  test: { environment: "jsdom", globals: true, setupFiles: "./src/test-setup.js", css: false },
});
