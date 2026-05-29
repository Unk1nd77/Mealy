import { defineConfig } from "astro/config"
import react from "@astrojs/react"

export default defineConfig({
  devToolbar: {
    enabled: false,
  },
  integrations: [react()],
  server: {
    host: true,
    port: 4321,
  },
  vite: {
    cacheDir:
      process.env.NODE_ENV === "production" ? "node_modules/.vite-build" : "node_modules/.vite-dev",
  },
})
