import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  globalIgnores([
    "dist/**",
    "renderer/**",
    "installer/**",
    "build/**",
    ".venv/**",
    ".playwright-cli/**",
    "test-results/**",
  ]),
  {
    files: ["src/**/*.{js,jsx}"],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: { "no-unused-vars": ["error", { varsIgnorePattern: "^[A-Z_]" }] },
  },
  {
    files: ["electron/**/*.js", "scripts/**/*.cjs"],
    extends: [js.configs.recommended],
    languageOptions: { sourceType: "commonjs", globals: globals.node },
  },
]);
