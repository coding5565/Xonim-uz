export interface PaymentMethod { method: string; label: string }
export interface MethodRevenue { method: string; label: string; revenue: string }
export interface User { id: number; username: string; name: string; role: 'owner' | 'cashier' | 'kitchen'; branch: string; branch_slug: string | null; payment_methods: PaymentMethod[] }
/** Zaxira nusxa holati: Telegram ulanganmi va serverda nima saqlangan. */
export interface BackupFile { name: string; size: string; created_at: string; kind: 'db' | 'media' }
export interface BackupState {
  telegram: { configured: boolean; chat: string; recipients: number }
  backups: BackupFile[]
  keep_days: number
}
export type Station = 'kitchen' | 'counter'
export type TableZone = 'hall_left' | 'hall_right' | 'outside'
/** Stol ustidagi ochiq hisob. `payable` — mijoz to'laydigan summa. */
export interface TableOpenOrder { id: number; total: string; service_charge: string; payable: string; items: number; waiter: string; created_at: string }
export interface Table {
  id: number
  number: number
  name: string
  seats: number
  zone: TableZone
  seating: 'divan' | 'chair'
  active: boolean
  label: string
  open_order: TableOpenOrder | null
}
export interface Category { id: number; name: string; position: number; station: Station }
export interface Dish { id: number; category: number; category_name: string; name: string; description: string; price: string; portion: string; image: string | null; available: boolean; archived: boolean; station: Station | ''; print_station: Station }
export interface Line { id: number; dish: number; name: string; price: string; quantity: number; note: string; added: boolean }
export type OrderStatus = 'open' | 'paid' | 'cancelled' | 'refunded'
export type SaleChannel = 'hall' | 'takeaway' | 'uzum' | 'yandex'
export interface Order {
  id: number
  table: string
  waiter: string
  /** Ro‘yxatdagi ofitsiant; qo‘lda yozilgan ism bo‘lsa bo‘sh qoladi. */
  waiter_ref: number | null
  /** Sotuv paytida muzlatilgan foiz — keyin o‘zgarsa ham bu o‘zgarmaydi. */
  waiter_commission: string
  waiter_fee: string
  channel: SaleChannel
  channel_label: string
  status: OrderStatus
  status_label: string
  /** Taomlar summasi — restoran tushumi. Xizmat haqi bunga kirmaydi. */
  total: string
  /** Stolga xizmat haqi: hisob ustiga qo‘shiladi va ofitsiantniki bo‘ladi. */
  service_charge: string
  /** Mijoz to‘laydigan summa: total + service_charge. */
  payable: string
  /** Chegirma summasi; `total` allaqachon undan ayirilgan. */
  discount: string
  discount_reason: string
  payment_method: string
  created_at: string
  paid_at: string | null
  cashier_name: string
  preparation_status: 'queued' | 'preparing' | 'ready' | 'served'
  started_at: string | null
  ready_at: string | null
  served_at: string | null
  lines: Line[]
  print_problems: string[]
  /** Bekor qilingan yoki qaytarilgan bo'lsa to'ldiriladi. */
  void_reason: string
  voided_at: string | null
  voided_by_name: string
}
export interface Expense { id: number; category: string; purpose: string; recipient: string; amount: string; payment_method: string; date: string; actor_name: string }
export interface Ingredient { id: number; name: string; unit: string; quantity: string; minimum: string; unit_cost: string; stock_value: string }
export interface Movement { id: number; ingredient_name: string; unit: string; kind: string; quantity: string; unit_cost: string; cost_total: string; date: string; note: string }
export interface Dashboard { revenue: string; expenses: string; net_cash: string; cost: string; gross_profit: string; gross_margin: string; paid_count: number; open_count: number; previous_revenue: string; by_method: MethodRevenue[]; low_stock: number; trend: {date: string; revenue: string; expenses: string}[]; period: {kind: 'days' | 'month'; start: string; end: string}; months: string[]; expense_categories: {category: string; total: string}[]; recent_orders: Order[]; as_of: string; basis: string }
export interface SalesReport { filters:{start:string;end:string;group:'day'|'month';category:number|null;dish:number|null}; summary:{revenue:string;cost:string;gross_profit:string;gross_margin:string;orders:number;items:number;average_check:string;by_method:MethodRevenue[]}; trend:{date:string;revenue:string;orders:number;items:number}[]; categories:{category_id:number;category:string;quantity:number;revenue:string;cost:string;gross_profit:string;orders:number}[]; dishes:{dish_id:number;dish:string;category:string;quantity:number;revenue:string;cost:string;gross_profit:string;orders:number}[] }
export interface SalesBoard {
  filters: { start: string; end: string; category: number | null; dish: number | null; mine: boolean }
  summary: { revenue: string; orders: number; items: number; average_check: string; top_dish: string | null; peak_hour: number | null; peak_hour_revenue: string | null }
  methods: { method: string; label: string; orders: number; revenue: string }[]
  hours: { hour: number; orders: number; revenue: string }[]
  days: { date: string; orders: number; revenue: string }[]
  dishes: { dish_id: number; dish: string; category: string; quantity: number; orders: number; revenue: string }[]
  categories: { category_id: number; category: string; quantity: number; orders: number; revenue: string }[]
  channels: ChannelRow[]
  cashiers: { name: string; orders: number; quantity: number; revenue: string }[]
  checks: { id: number; table: string; waiter: string; total: string; payment_method: string; payment_label: string; channel: SaleChannel; channel_label: string; paid_at: string; cashier_name: string; items: number }[]
}
export interface SalesTotals { revenue: string; orders: number }
export interface SalesSummary { today: SalesTotals; yesterday: SalesTotals; last_7_days: SalesTotals; mine_today: SalesTotals; open: SalesTotals; today_by_method: {method: string; label: string; revenue: string}[]; today_by_channel: ChannelRow[]; as_of: string }
export interface RecipeLine { id:number; ingredient:number; ingredient_name:string; unit:string; unit_price:string; quantity:string; batch_cost:string }
export interface Recipe { id:number; dish:number|null; dish_name:string; name:string; yield_quantity:string; yield_unit:string; selling_price:string; active:boolean; updated_at:string; lines:RecipeLine[]; batch_cost:string; unit_cost:string; gross_profit:string }
export interface ActivityEvent { id: number; action: string; label: string; group: string; description: string; created_at: string; actor_id: number; actor: string }
export interface ActivityFacet { action: string; label: string; group: string; count: number }
export interface ActivityActor { id: number; name: string; count: number }
export interface ActivityLog {
  results: ActivityEvent[]
  page: number
  pages: number
  count: number
  page_size: number
  total: number
  actions: ActivityFacet[]
  actors: ActivityActor[]
}
/** Bir xodimning hafta ichidagi bitta kuni. */
export interface PayrollDay {
  date: string
  weekday: string
  rest: boolean
  /** null — hali belgilanmagan. «Belgilanmagan» bilan «kelmadi» bir xil emas. */
  present: boolean | null
  future: boolean
}
export interface PayrollEmployee {
  id: number
  name: string
  username: string
  role: string
  role_label: string
  active: boolean
  daily_wage: string
  week_wage: string
  week: PayrollDay[]
  week_days: number
  week_earned: string
  today: 'present' | 'absent' | null
  days_worked: number
  earned: string
  paid: string
  /** Yig'ilgan haq − berilgan pul. Manfiy bo'lsa — avans. */
  balance: string
  advance: boolean
  payments: number
  last_paid_on: string | null
}
export interface PayrollPayment {
  id: number
  employee: number
  employee_name: string
  amount: string
  payment_method: string
  payment_label: string
  paid_on: string
  note: string
  actor_name: string
}
export interface Payroll {
  today: string
  /** Yakshanba: bu kunga haq hisoblanmaydi. */
  rest_day: boolean
  week: {
    start: string
    end: string
    label: string
    current: boolean
    days: { date: string; weekday: string; name: string; rest: boolean; today: boolean; future: boolean; marked: number; present: number }[]
  }
  month: string
  month_label: string
  months: string[]
  summary: {
    staff_count: number
    daily_total: string
    week_wage: string
    week_earned: string
    earned: string
    paid: string
    balance: string
    marked_today: number
    present_today: number
    unmarked_today: number
    month_paid: string
    month_count: number
    by_method: { method: string; label: string; amount: string; count: number }[]
    work_days: number
    without_wage: number
  }
  employees: PayrollEmployee[]
  payments: PayrollPayment[]
  trend: { period: string; label: string; total: string; count: number }[]
  all_time: { total: string; payments: number }
}
export interface StockUsageRow {
  id: number
  name: string
  unit: string
  opening: string
  received: string
  received_value: string
  used: string
  used_value: string
  sold: string
  sold_value: string
  manual: string
  manual_value: string
  closing: string
  per_day: string
  days_left: string
  unit_cost: string
  stock_value: string
  share: string
  low: boolean
}
export interface StockUsage {
  filters: { start: string; end: string; group: 'day' | 'month'; ingredient: number | null }
  summary: {
    /** Bo‘sh bo‘lsa birliklar aralash — miqdor jamlanmaydi, faqat pul. */
    unit: string
    received: string
    received_value: string
    used: string
    used_value: string
    sold_value: string
    manual_value: string
    moves: number
    unpriced_moves: number
    days: number
    per_day_value: string
    stock_value: string
    items_moved: number
    items_idle: number
  }
  series: { date: string; label: string; received: string; received_value: string; used: string; used_value: string }[]
  ingredients: StockUsageRow[]
  idle: { id: number; name: string; unit: string; quantity: string; unit_cost: string; stock_value: string }[]
  kinds: { kind: string; label: string }[]
}
export interface Finance {
  filters: { start: string; end: string; month: string | null; label: string; days: number }
  months: string[]
  profit: {
    revenue: string
    cogs: string
    gross_profit: string
    gross_margin: string
    expenses: string
    waste: string
    platform_fee: string
    platform_share: string
    net_profit: string
    net_margin: string
    orders: number
    items: number
    average_check: string
  }
  coverage: {
    covered_revenue: string
    share: string
    covered_margin: string
    dishes_total: number
    dishes_with_recipe: number
    menu_without_recipe: number
    sold_uncovered: number
    top_uncovered: { dish_id: number; dish: string; revenue: string }[]
  }
  cash: {
    in: string
    out: string
    platform_fee: string
    net: string
    settled_expenses: string
    stock_purchases: string
    /** Ofitsiantlar uchun yig'ilgan va ularga berilgan pul. */
    service_collected: string
    service_paid: string
    unpaid: string
    bridge: string
  }
  expenses: { category: string; amount: string; share: string; count: number; salary: boolean }[]
  methods: { method: string; label: string; revenue: string; orders: number; share: string }[]
  channels: ChannelRow[]
  salary: {
    total: string
    payments: number
    periods: string[]
    share: string
    manual_total: string
    manual_count: number
  }
  /** Ofitsiant xizmat haqi: yig'ilgan, berilgan va qolgan. */
  service: { collected: string; paid: string; payments: number; owed: string; share: string }
  stock: { value: string; purchases: string; consumed: string; gap: string; gap_share: string }
  trend: {
    period: string
    label: string
    revenue: string
    cogs: string
    expenses: string
    platform_fee: string
    gross_profit: string
    net_profit: string
  }[]
  basis: string
}
export interface DailyUsageLine {
  id: number
  ingredient: number
  name: string
  unit: string
  quantity: string
  value: string
  note: string
  actor: string
  updated_at: string
}
export interface DailyUsageDay {
  date: string
  lines: DailyUsageLine[]
  items: number
  value: string
  actors: string[]
}
export interface DailyUsageLog {
  filters: { start: string; end: string; backdate_days: number }
  days: DailyUsageDay[]
}
export interface UsageCompareRow {
  id: number
  name: string
  unit: string
  /** Tizim retsept bo‘yicha hisoblagan miqdor. */
  expected: string
  /** Admin qo‘lda kiritgan miqdor. */
  counted: string
  gap: string
  gap_value: string
  share: string
  expected_value: string
  counted_value: string
  status: 'ok' | 'alert' | 'missing' | 'extra'
  unit_cost: string
}
export interface UsageComparison {
  filters: { start: string; end: string; days: number }
  summary: {
    system_value: string
    actual_value: string
    gap_value: string
    gap_share: string
    alerts: number
    items: number
    reported_days: number
    missing_days: number
    alert_threshold: string
  }
  rows: UsageCompareRow[]
}
export interface ShiftMethodRow {
  method: string
  label: string
  amount: string
  count: number
  /** Faqat naqd kassada qoladi. */
  in_drawer: boolean
  /** Platforma ushlab qolgan summa — Uzum va Yandexda noldan katta. */
  fee: string
  /** Hisobga haqiqatda tushadigan summa: amount − fee. */
  net: string
}
export interface ShiftDay {
  date: string
  closed: boolean
  expected_cash: string
  revenue: string
  /** Ofitsiantlar uchun yig'ilgan xizmat haqi. Yopilgan kunda bo'lmasligi mumkin. */
  service?: string
  orders: number
  breakdown: ShiftMethodRow[]
  backdate_days: number
  alert_som: string
  /** Yopilmagan kunda bo‘ladi. */
  cash_in?: string
  cash_out?: string
  open_orders?: number
  /** Yopilgan kunda bo‘ladi. */
  actor?: string
  closed_at?: string
  counted_cash?: string
  difference?: string
  note?: string
  alert?: boolean
}
export interface ShiftHistory {
  days: ShiftDay[]
  summary: { closed_days: number; total_difference: string; alerts: number; alert_som: string }
}
/** Kanal kesimi: zal, olib ketish, Uzum, Yandex. */
export interface ChannelRow {
  channel: SaleChannel
  label: string
  revenue: string
  orders: number
  share?: string
  /** Yetkazib berish platformasi — puli kassaga tushmaydi. */
  delivery: boolean
  /** Platforma ushlagani. Faqat moliya sahifasida keladi. */
  fee?: string
  fee_share?: string
  net?: string
}
export interface Waiter {
  id: number
  name: string
  phone: string
  /** Foizda: 5 -> hisobning 5 foizi. */
  commission: string
  active: boolean
}
/** Bitta ofitsiantning davr va umrlik hisobi. */
export interface WaiterBook {
  id: number
  name: string
  orders: number
  revenue: string
  fee: string
  share: string
  /** Umrlik: yig'ilgan, berilgan va qolgan pul. */
  earned: string
  paid: string
  balance: string
  today_sales: string
  today_fee: string
  today_orders: number
}
export interface WaiterEarnings {
  filters: { start: string; end: string }
  summary: {
    revenue: string
    fees: string
    waiters: number
    unassigned_revenue: string
    unassigned_orders: number
    today_sales: string
    today_fee: string
    paid: string
    owed: string
  }
  waiters: WaiterBook[]
}
export interface WaiterPayment {
  id: number
  waiter: number
  amount: string
  payment_method: string
  payment_label: string
  paid_on: string
  note: string
  actor_name: string
}
export interface PrepRow {
  dish: number
  name: string
  prepared: number
  sold: number
  remaining: number
  /** Miqdori kiritilmagan taom cheklanmaydi. */
  tracked: boolean
  out: boolean
  low: boolean
  /** Necha donada ogohlantirish boshlanadi; chegarani server belgilaydi. */
  warn_at: number
}
export interface PrepStatus {
  date: string
  summary: { tracked: number; out: number; low: number; prepared: number; sold: number; remaining: number }
  dishes: PrepRow[]
}
export interface PrepHistory {
  date: string
  rows: { id: number; dish: number; name: string; quantity: number; note: string; actor: string; created_at: string }[]
}
export interface PrepLeftovers {
  date: string
  summary: PrepStatus['summary']
  leftovers: PrepRow[]
}

/** Platforma ushlanmasi — superadmin sozlaydigan foiz. */
export interface ChannelFeeRow {
  channel: SaleChannel
  label: string
  commission: string
  net_share: string
  updated_at: string | null
  configured: boolean
}
export interface ChannelFees { rows: ChannelFeeRow[]; default: string; detail?: string }
