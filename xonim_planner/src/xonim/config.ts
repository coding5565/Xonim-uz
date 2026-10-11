/**
 * Режим «внутри Xonim».
 *
 * Включается сборкой с `--mode xonim` (скрипты `dev:xonim` и `build:xonim`).
 * Тогда калькулятор лежит на том же сайте, что и Xonim (по адресу `/planner/`),
 * берёт данные из его API и открывается только суперадмину. Без этого режима
 * приложение работает как раньше — автономно, с данными в браузере.
 *
 * Флаг берётся из режима сборки, а не из `.env`-файла: такие файлы не попадают
 * в Docker-образ Xonim (их отсекает `.dockerignore` — там лежат секреты).
 */
export const XONIM = import.meta.env.MODE === 'xonim'

/** Адреса Xonim — относительные: калькулятор и Xonim работают на одном сайте. */
export const XONIM_HOME = '/'
export const XONIM_LOGIN = '/login'
export const XONIM_API = '/api/v1'

/** Ключ, под которым Xonim хранит язык интерфейса (тот же сайт — тот же localStorage). */
export const XONIM_LANG_KEY = 'xonim-lang'
