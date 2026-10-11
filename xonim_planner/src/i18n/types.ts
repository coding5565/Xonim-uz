/** Фраза: либо готовая строка, либо набор форм множественного числа CLDR. */
export type Phrase =
  | string
  | ({ other: string } & Partial<Record<Intl.LDMLPluralRule, string>>)

export type TVars = Record<string, string | number>
