import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Ma'lumotni yuklash uchun `useEffect(() => { load() }, [])` — React'da
      // ma'lumot kutubxonasisiz ishlaydigan odatiy naqsh, va bu yerdagi
      // setState `await` dan KEYIN bajariladi, ya'ni sinxron emas. Qoida
      // (react-hooks v6 da paydo bo'lgan) buni ajrata olmaydi, shuning uchun
      // ogohlantirish darajasida qoldiriladi: ko'rinib turadi, lekin
      // yig'ishni to'xtatmaydi.
      'react-hooks/set-state-in-effect': 'warn',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // Ishlatilmagan o'zgaruvchi xato, lekin ataylab tashlab ketilgani
      // pastki chiziq bilan belgilanadi: `catch { }` va `[, ikkinchi]` kabi.
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      }],
    },
  },
)
