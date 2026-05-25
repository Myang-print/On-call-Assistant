import { defineConfig } from "vite";

export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/v1": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/v2": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  }
});
