import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The bundle lands inside the Python package (WP67 §2.5); `vault-agent ui` serves it at `/`.
// In development `vite` proxies /api to the running backend.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "../src/vault_agent/ui/static", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"], globals: false, fileParallelism: false },
});
