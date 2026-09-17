// proposito: teto de 350 linhas por arquivo e checagem de erro no JS do painel
import js from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: ["node_modules/**", "venv/**", "output/**", "user_data/**", "__pycache__/**"],
  },
  {
    // Os arquivos de web/ sao carregados como <script> classico e compartilham o
    // escopo global. sourceType "module" (o default do flat config) faria o ESLint
    // tratar cada um como modulo isolado e acusar no-undef em tudo.
    files: ["web/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: globals.browser,
    },
    rules: {
      ...js.configs.recommended.rules,
      // Desligado de proposito: as funcoes de um arquivo sao chamadas pelos outros
      // pelo escopo global, e o ESLint nao tem como saber disso em script classico.
      // Religar exige converter o painel pra ES modules, o que quebraria os 26
      // pontos de onclick que dependem do global.
      "no-undef": "off",
      "max-lines": ["warn", { max: 350, skipBlankLines: false, skipComments: false }],
    },
  },
  {
    files: ["scripts/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "commonjs",
      globals: globals.node,
    },
    rules: {
      ...js.configs.recommended.rules,
      "max-lines": ["warn", { max: 350, skipBlankLines: false, skipComments: false }],
    },
  },
];
