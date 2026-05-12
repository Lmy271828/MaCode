import eslint from "@eslint/js";
import tseslint from "typescript-eslint";
import globals from "globals";

export default tseslint.config(
  // Base ignores
  {
    ignores: [
      "node_modules/**",
      "dist/**",
      ".venv*/**",
      "engines/**/dist/**",
      "assets/shaders/lygia/dist/**",
    ],
  },

  // Recommended rules for JS/TS
  eslint.configs.recommended,
  ...tseslint.configs.recommended,

  // TypeScript files
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
      },
    },
    rules: {
      // Relax some rules that are noisy in a creative-coding project
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-empty-object-type": "off",
    },
  },

  // Node.js scripts (.mjs / .cjs / .js in bin/ pipeline/ engines/)
  {
    files: ["bin/**/*.{js,mjs,cjs}", "pipeline/**/*.{js,mjs,cjs}", "engines/**/*.{js,mjs,cjs}"],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
    rules: {
      "@typescript-eslint/no-require-imports": "off",
      "@typescript-eslint/no-var-requires": "off",
      "no-empty": "off",
      "no-useless-assignment": "off",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
    },
  },

  // Browser automation scripts (Playwright)
  {
    files: ["engines/motion_canvas/scripts/playwright-render.mjs", "engines/motion_canvas/scripts/snapshot.mjs"],
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
  }
);
