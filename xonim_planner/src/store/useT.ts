import { useCallback, useMemo } from 'react'
import { getTranslator, type TKey, type Translator } from '@/i18n'
import type { Scenario, ScenarioKind } from '@/core/types'
import { useAppStore } from './useAppStore'

/** Переводчик текущего языка. Меняется только при смене языка. */
export function useT(): Translator {
  const locale = useAppStore((s) => s.locale)
  return useMemo(() => getTranslator(locale), [locale])
}

/**
 * Обозначение валюты. Пустое поле в параметрах бизнеса означает
 * «взять из языка интерфейса»; заданное вручную значение имеет приоритет.
 */
export function useCurrency(): string {
  const custom = useAppStore((s) => s.model.business.currency)
  const t = useT()
  return custom.trim() || t('currency.default')
}

const SCENARIO_KEY: Record<ScenarioKind, TKey> = {
  current: 'scenario.current',
  optimistic: 'scenario.optimistic',
  pessimistic: 'scenario.pessimistic',
  custom: 'scenario.custom',
}

/**
 * Имя сценария. Базовые сценарии хранятся без названия и переводятся на лету;
 * как только пользователь переименовал сценарий, показывается его вариант.
 */
export function useScenarioLabel(): (s: Scenario) => string {
  const t = useT()
  return useCallback(
    (s: Scenario) => s.name.trim() || t(SCENARIO_KEY[s.kind]),
    [t],
  )
}
