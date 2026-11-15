import { defineConfig } from "vitest/config";

export default defineConfig({
  // tsconfig keeps `jsx: preserve` for Next.js; component tests need the automatic runtime
  esbuild: { jsx: "automatic" },
  test: {
    environment: "node",
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**"],
  },
});
