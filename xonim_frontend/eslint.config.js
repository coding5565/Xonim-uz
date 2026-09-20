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
      // Ma'lumotni yuklash uchun `useEffect(() => { load() }, [load])` —
      // React'da ma'lumot kutubxonasisiz ishlaydigan odatiy naqsh, va bu
      // yerdagi setState `await` dan KEYIN bajariladi, ya'ni sinxron emas.
      // Qoida (react-hooks v6 da paydo bo'lgan) buni ajrata olmaydi va
      // loyihadagi har bir sahifada ishlaydi.
      //
      // Ilgari u «warn» edi, lekin CI ogohlantirishlarni sanamasdi — ya'ni
      // qoida amalda hech narsa qilmasdi, faqat 25 ta shovqin berardi.
      // Endi CI har qanday ogohlantirishda to'xtaydi, shuning uchun bu
      // qoida ataylab O'CHIRILDI: yolg'on signal butun tekshiruvni
      // ishlatib bo'lmaydigan qilib qo'yardi.
      'react-hooks/set-state-in-effect': 'off',
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
  {
    // Fast Refresh qoidasi shu ikki faylda ma'noga ega emas:
    //   · main.tsx — ilovaning kirish nuqtasi, u umuman eksport qilmaydi;
    //   · i18n/index.tsx — provayder va uning hook'lari birga turadi, bu
    //     React kontekstining odatiy ko'rinishi.
    // Boshqa hamma joyda qoida kuchida qoladi.
    files: ['src/main.tsx', 'src/i18n/index.tsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
)
