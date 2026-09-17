# Ma'lumotlar modeli va API rejasi

Bu hujjat konseptual loyiha; yakuniy migratsiyalar va OpenAPI hali yaratilmagan.

## Asosiy bog'lanishlar

| Domen | Asosiy obyektlar | Muhim qoidalar |
| --- | --- | --- |
| Kirish | User, Role, Permission, BranchMembership, Session | Faol a'zolik va amal vakolati majburiy |
| Filial | Branch, BusinessDay, DiningArea, DiningTable | Stol raqami filial/zal ichida noyob |
| Katalog | Category, MenuItem, Variant, Modifier, BranchPrice | Tarixli narx; foydalanilgan taom arxivlanadi |
| Retsept | RecipeVersion, RecipeIngredient, ProductionBatch | Tasdiqlangan versiya o'zgarmaydi; sikl yo'q |
| Buyurtma | Order, OrderLine, LineModifier, OrderEvent | Pul/narx nusxasi; version; status o'tishlari |
| Oshxona | KitchenTicket, KitchenTicketLine | Satr/bosqich bo'yicha dublikat topshiriq yo'q |
| Ombor | StockItem, Unit, Warehouse, Batch, StockMovement, Reservation | Miqdor va qiymat registri; manba noyob |
| Sanash | Stocktake, StocktakeLine | Sanash vaqti, kutilgan/haqiqiy qoldiq, sabab |
| Kunlik sarf | DailyConsumption, DailyConsumptionLine, ConsumptionAllocation | Filial/ombor/kun, me'yor/haqiqiy sarf, partiya taqsimoti, versiya; bir marta posting |
| Xarid | Supplier, PurchaseOrder, GoodsReceipt, SupplierInvoice, SupplierPayment | Qabul, qarz va to'lov ajratiladi |
| Kassa | CashAccount, Shift, CashMovement, CashCount | Hisoblangan va sanalgan naqd alohida |
| To'lov | Payment, PaymentAllocation, Refund | To'lov/refund yakuniy holati va provayder ID |
| Moliya | Expense, ExpenseCategory, JournalEntry, JournalLine | Tasdiqlangan registrda debet = kredit |
| Oylik | Employee, Attendance, SalaryRule, PayrollRun, PayrollLine, Advance | Xodim/davr noyob; tasdiq va to'lov ajratilgan |
| Chek | ReceiptSnapshot, Printer, PrintJob | Qayta chop savdo/to'lovni takrorlamaydi |
| Nazorat | AuditEvent, IdempotencyRecord, OutboxEvent | Takroriy so'rov va crashdan tiklanish |

Filialga tegishli har bir hujjat branch_id saqlaydi. Bog'liq IDlar orqali boshqa filial yozuvini biriktirish rad etiladi. Moliyaviy hujjat raqami filial/davr/tur ichida noyob; raqamdagi bo'shliqlar audit qilinadi. Moliyaviy yozuv hard-delete qilinmaydi.

## Pul registri

Hisoblar minimal to'plami: naqd, bank/karta hisob-kitobi, ombor aktivi, yetkazib beruvchi qarzi, sotuv, tannarx, davr xarajatlari, oylik majburiyati, mijoz avansi, soliq majburiyati, egasi kapitali/olib chiqishi. Xizmat haqi daromadmi yoki xodimga majburiyatmi — siyosat bilan belgilanadi.

Har tasdiqlangan biznes hujjati balanslashgan jurnal yaratadi. UI foydalanuvchidan debet/kredit bilishni talab qilmaydi. Masalan, to'langan xarid omborni oshiradi va pulni kamaytiradi; retsept sarfi ombor qiymatini kamaytirib tannarxni oshiradi. Sotilmagan tayyor mahsulotning ishlab chiqarish sarfi darhol sotuv tannarxi bo'lmaydi.

JournalEntry: source_type/id, branch, effective_at, recorded_at, business_date, status, reversal_of, actor. JournalLine: account, debit, credit, currency, expense_category, counterparty, employee va kerakli analitik bog'lanishlar. Balans va manba noyobligi bitta posting service orqali tekshiriladi. Tasdiqlangan jurnal tahrirlanmaydi.

## API yo'nalishlari

```text
/api/v1/auth/{csrf,login,logout,me,sessions}/
/api/v1/branches/
/api/v1/catalog/{categories,items,variants,prices}/
/api/v1/dining/{areas,tables}/
/api/v1/orders/
/api/v1/orders/{id}/{submit,request-bill,close,cancel}/
/api/v1/kitchen/tickets/{id}/{start,ready}/
/api/v1/payments/
/api/v1/payments/{id}/refunds/
/api/v1/shifts/{id}/{cash-count,close}/
/api/v1/inventory/{items,batches,movements,stocktakes}/
/api/v1/inventory/daily-consumptions/{id}/{post,reverse}/
/api/v1/purchasing/{orders,receipts,invoices,payments}/
/api/v1/finance/{accounts,expenses,journals}/
/api/v1/payroll/runs/{id}/{calculate,approve,pay}/
/api/v1/reporting/{overview,cash-flow,profit-loss,expenses,trends}/
/api/v1/reporting/{receivables,payables,inventory,payroll,audit}/
/api/v1/printing/jobs/{id}/{status,reprint}/
/api/v1/public/menu/{branch_slug}/
```

Ommaviy menyu faqat GET/HEAD, xarid yoki savdo endpointi emas. Xususiy OpenAPI schema va hujjatlar productionda ruxsat bilan. Listlar pagination, ruxsat etilgan filter/sort maydonlari bilan; massiv eksport worker orqali.

Hisobot parametrlari: branch_ids, date_from, date_to, timezone, business_day_mode, granularity, comparison, payment_method, category, employee. Server tanlangan filiallarning har birini tekshiradi. Interval ichki hisobda `[start, end)` bo'ladi.

Hisobot javobida `as_of`, `period`, `comparison_period`, `currency`, `basis`, `filters`, `data`, `data_quality` bo'ladi. Xatoda code, detail, field_errors va request_id. Summalar satr shaklida; vaqt ISO 8601. Eskirgan versiya yoki yopilgan davrga yozish 409; vakolatsiz amal 403.

## Hisoblash misoli

2 × 40 000 + 1 × 20 000 = 100 000. Agar 10% chegirma va chegirmadan keyin 10% xizmat haqi bo'lsa: 90 000 + 9 000 = 99 000. Bu soliqsiz misol; soliq qo'shilishi/ichidaligi sozlama bilan aniq belgilanadi. Hisob snapshotida formula versiyasi saqlanadi.

Xizmat ulushi, soliq va chegirma satrlarga taqsimlanayotganda yaxlitlash qoldig'i deterministik taqsimlanadi; satrlar jami chek jamiga teng. Refund asl snapshot qiymatlaridan va qaytarilgan miqdordan hisoblanadi; qaytarish asl to'lovdan ortmaydi.
