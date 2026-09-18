export interface PaymentMethod { method: string; label: string }
export interface MethodRevenue { method: string; label: string; revenue: string }
export interface User { id: number; username: string; name: string; role: 'owner' | 'admin' | 'cashier' | 'kitchen'; branch: string; payment_methods: PaymentMethod[] }
export type Station = 'kitchen' | 'counter'
export type TableZone = 'hall_left' | 'hall_right' | 'outside'
export interface TableOpenOrder { id: number; total: string; items: number; waiter: string; created_at: string }
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
export interface Order {
  id: number
  table: string
  waiter: string
  status: OrderStatus
  status_label: string
  total: string
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
  cashiers: { name: string; orders: number; quantity: number; revenue: string }[]
  checks: { id: number; table: string; waiter: string; total: string; payment_method: string; payment_label: string; paid_at: string; cashier_name: string; items: number }[]
}
export interface SalesTotals { revenue: string; orders: number }
export interface SalesSummary { today: SalesTotals; yesterday: SalesTotals; last_7_days: SalesTotals; mine_today: SalesTotals; open: SalesTotals; today_by_method: {method: string; label: string; revenue: string}[]; as_of: string }
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
export interface PayrollEmployee {
  id: number
  name: string
  username: string
  role: string
  role_label: string
  active: boolean
  agreed: string
  paid: string
  difference: string
  status: 'paid' | 'partial' | 'unpaid' | 'no_agreement'
  paid_on: string | null
  payment_method: string
  payment_label: string
  note: string
}
export interface Payroll {
  month: string
  month_label: string
  months: string[]
  summary: {
    agreed: string
    paid: string
    remaining: string
    paid_count: number
    staff_count: number
    expected: number
    covered: number
    without_agreement: number
    by_method: { method: string; label: string; amount: string; count: number }[]
  }
  employees: PayrollEmployee[]
  trend: { period: string; label: string; total: string; count: number }[]
  lifetime: { id: number; name: string; total: string; months: number; first: string; last: string }[]
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
    net: string
    settled_expenses: string
    stock_purchases: string
    unpaid: string
    bridge: string
  }
  expenses: { category: string; amount: string; share: string; count: number; salary: boolean }[]
  methods: { method: string; label: string; revenue: string; orders: number; share: string }[]
  salary: {
    total: string
    payments: number
    periods: string[]
    share: string
    manual_total: string
    manual_count: number
  }
  stock: { value: string; purchases: string; consumed: string; gap: string; gap_share: string }
  trend: {
    period: string
    label: string
    revenue: string
    cogs: string
    expenses: string
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
}
export interface ShiftDay {
  date: string
  closed: boolean
  expected_cash: string
  revenue: string
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
