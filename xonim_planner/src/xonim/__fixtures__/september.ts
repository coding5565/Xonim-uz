/**
 * Ответ Xonim за месяц — тот же месяц, что собирает серверный тест
 * `xonim_backend/operations/test_planner.py` (PlannerFactsTests.seed_month):
 * зал со скидкой и сервисным сбором, Uzum с комиссией 30 % и бонусным чаем,
 * старая строка без цены меню, школа, питание сотрудников, списание.
 * Чистая прибыль Xonim за него: −3 564 000.
 */
export const SEPTEMBER = {
  version: 1,
  month: '2026-09',
  start: '2026-09-01',
  end: '2026-09-30',
  days: 30,
  complete: true,
  months: ['2026-10', '2026-09'],
  branch: { name: 'Xonim', seats: 10 },
  sales: { revenue: '174000.00', orders: 3, items: 8, discounts: '10000.00', open_days: 2 },
  cogs: '71000.00',
  platform_fee: '15000.00',
  waste: '7000.00',
  staff_meals: '5000.00',
  partners: { revenue: '280000.00', cogs: '120000.00', profit: '160000.00' },
  net_profit: '-3564000.00',
  channels: [
    { channel: 'hall', label: 'Zal', revenue: '124000.00', fee: '0.00', orders: 2 },
    { channel: 'uzum', label: 'Uzum', revenue: '50000.00', fee: '15000.00', orders: 1 },
  ],
  expenses: [
    { category: 'Ijara', amount: '3000000.00', kind: 'other' },
    { category: 'Ish haqi', amount: '400000.00', kind: 'salary' },
    { category: 'Kommunal', amount: '250000.00', kind: 'other' },
    { category: 'Masalliq', amount: '150000.00', kind: 'produce' },
  ],
  categories: [{ id: 1, name: 'Taom' }],
  dishes: [
    { id: 1, name: 'Osh', category_id: 1, price: '50000.00', unit_cost: '0.00', archived: false, quantity: 3, menu_value: '150000.00', cost: '60000.00' },
    { id: 2, name: 'Choy', category_id: 1, price: '10000.00', unit_cost: '0.00', archived: false, quantity: 2, menu_value: '20000.00', cost: '2000.00' },
    { id: 3, name: 'Somsa', category_id: 1, price: '8000.00', unit_cost: '0.00', archived: true, quantity: 3, menu_value: '24000.00', cost: '9000.00' },
    { id: 4, name: 'Lag‘mon', category_id: 1, price: '40000.00', unit_cost: '8000.00', archived: false, quantity: 0, menu_value: '0.00', cost: '0.00' },
  ],
  payroll: [
    { id: 1, name: 'Ali', position: 'Oshpaz', active: true, daily_wage: '100000.00', days: 3, accrued: '300000.00' },
    { id: 2, name: 'Vali', position: 'Ofitsiant', active: true, daily_wage: '80000.00', days: 0, accrued: '0.00' },
    { id: 4, name: 'Ketgan', position: 'Yordamchi', active: false, daily_wage: '90000.00', days: 1, accrued: '90000.00' },
  ],
}

/** Новый ресторан: месяц только начался, продаж ещё нет. */
export const EMPTY_MONTH = {
  ...SEPTEMBER,
  month: '2026-10',
  days: 1,
  complete: false,
  months: ['2026-10'],
  sales: { revenue: '0.00', orders: 0, items: 0, discounts: '0.00', open_days: 0 },
  cogs: '0.00',
  platform_fee: '0.00',
  waste: '0.00',
  staff_meals: '0.00',
  partners: { revenue: '0.00', cogs: '0.00', profit: '0.00' },
  net_profit: '-150000.00',
  channels: [],
  expenses: [{ category: 'Masalliq', amount: '150000.00', kind: 'produce' }],
  dishes: [
    { id: 1, name: 'Osh', category_id: 1, price: '50000.00', unit_cost: '18000.00', archived: false, quantity: 0, menu_value: '0.00', cost: '0.00' },
  ],
  payroll: [],
}
