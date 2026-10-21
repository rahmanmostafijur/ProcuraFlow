import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    // vite.config.js and vite.config.d.ts are emitted by `tsc -b` from vite.config.ts.
    ignores: ["dist", "coverage", "vite.config.js", "vite.config.d.ts"],
  },
  js.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    extends: [...tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      parserOptions: {
        projectService: {
          // Root config files that no tsconfig includes still get a type-aware program.
          allowDefaultProject: ["tailwind.config.ts"],
        },
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    extends: [reactHooks.configs.flat.recommended, jsxA11y.flatConfigs.recommended, reactRefresh.configs.vite],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    files: ["*.{js,ts}"],
    languageOptions: {
      globals: globals.node,
    },
  },
  // Last, so formatting is left entirely to Prettier.
  prettier,
);
