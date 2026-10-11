import { describe, expect, it } from 'vitest'
import { persistedPart, useAppStore } from './useAppStore'

describe('что попадает в localStorage', () => {
  it('внутри Xonim финансы и зарплаты на диск не пишутся, сценарии — пишутся', () => {
    const saved = persistedPart(useAppStore.getState(), true)
    expect(saved).not.toHaveProperty('model')
    expect(saved).not.toHaveProperty('xonim')
    expect(saved.scenarios).toEqual(useAppStore.getState().scenarios)
  })

  it('автономный калькулятор хранит модель, как и раньше', () => {
    const saved = persistedPart(useAppStore.getState(), false)
    expect(saved.model).toBe(useAppStore.getState().model)
    expect(saved).not.toHaveProperty('xonim')
  })
})
