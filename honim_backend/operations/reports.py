from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from html import escape
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.utils import timezone
from rest_framework import serializers

from catalog.models import Category, Dish
from .models import SALE_CHANNEL_LABELS, SALE_PAYMENT_LABELS, Order, OrderLine
from core.i18n import _


class ReportFilters(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    category = serializers.IntegerField(min_value=1, required=False)
    dish = serializers.IntegerField(min_value=1, required=False)
    group = serializers.ChoiceField(choices=['day', 'month', 'auto'], default='auto')

    def validate(self, attrs):
        today = timezone.localdate()
        attrs['end'] = attrs.get('end', today)
        attrs['start'] = attrs.get('start', attrs['end'].replace(day=1))
        if attrs['start'] > attrs['end']:
            raise serializers.ValidationError(_('Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.'))
        if attrs['end'] > today:
            raise serializers.ValidationError(_('Kelajakdagi sana uchun savdo hisoboti tuzilmaydi.'))
        if (attrs['end'] - attrs['start']).days > 1095:
            raise serializers.ValidationError(_('Bir hisobot oralig‘i ko‘pi bilan 3 yil.'))
        request = self.context['request']
        category = None
        if attrs.get('category'):
            category = Category.objects.filter(branch=request.user.branch, pk=attrs['category']).first()
            if not category:
                raise serializers.ValidationError({'category': _('Kategoriya topilmadi.')})
        if attrs.get('dish'):
            dish = Dish.objects.filter(branch=request.user.branch, pk=attrs['dish']).first()
            if not dish or (category and dish.category_id != category.id):
                raise serializers.ValidationError({'dish': _('Taom tanlangan kategoriyaga tegishli emas.')})
        if attrs['group'] == 'auto':
            attrs['group'] = 'month' if (attrs['end'] - attrs['start']).days > 62 else 'day'
        return attrs


def _period_key(value, group):
    local = timezone.localtime(value)
    return local.date().replace(day=1) if group == 'month' else local.date()


def build_sales_report(user, filters):
    orders = Order.objects.filter(
        branch=user.branch,
        status='paid',
        paid_at__date__gte=filters['start'],
        paid_at__date__lte=filters['end'],
    ).order_by('paid_at', 'id')
    lines = OrderLine.objects.filter(order__in=orders).select_related('order', 'dish__category')
    if filters.get('category'):
        lines = lines.filter(dish__category_id=filters['category'])
    if filters.get('dish'):
        lines = lines.filter(dish_id=filters['dish'])
    line_rows = list(lines)
    included_order_ids = {line.order_id for line in line_rows}
    included_orders = [order for order in orders if order.id in included_order_ids]

    revenue = sum((line.price * line.quantity for line in line_rows), Decimal('0'))
    cost = sum((line.cost_total for line in line_rows), Decimal('0'))
    items_sold = sum(line.quantity for line in line_rows)
    order_count = len(included_orders)
    order_method = {order.id: order.payment_method for order in included_orders}
    method_map = defaultdict(Decimal)

    trend_map = defaultdict(lambda: {'revenue': Decimal('0'), 'cost': Decimal('0'), 'orders': set(), 'items': 0})
    category_map = defaultdict(lambda: {'category_id': 0, 'category': '', 'quantity': 0, 'revenue': Decimal('0'), 'cost': Decimal('0'), 'orders': set()})
    dish_map = defaultdict(lambda: {'dish_id': 0, 'dish': '', 'category': '', 'quantity': 0, 'revenue': Decimal('0'), 'cost': Decimal('0'), 'orders': set()})
    for line in line_rows:
        period = _period_key(line.order.paid_at, filters['group'])
        amount = line.price * line.quantity
        trend_map[period]['revenue'] += amount
        trend_map[period]['cost'] += line.cost_total
        trend_map[period]['orders'].add(line.order_id)
        trend_map[period]['items'] += line.quantity
        category = line.dish.category
        cat = category_map[category.id]
        cat.update(category_id=category.id, category=category.name)
        cat['quantity'] += line.quantity
        cat['revenue'] += amount
        cat['cost'] += line.cost_total
        cat['orders'].add(line.order_id)
        item = dish_map[line.dish_id]
        item.update(dish_id=line.dish_id, dish=line.name, category=category.name)
        item['quantity'] += line.quantity
        item['revenue'] += amount
        item['cost'] += line.cost_total
        item['orders'].add(line.order_id)
        method_map[order_method.get(line.order_id, '')] += amount

    trend = []
    cursor = filters['start'].replace(day=1) if filters['group'] == 'month' else filters['start']
    final = filters['end'].replace(day=1) if filters['group'] == 'month' else filters['end']
    while cursor <= final:
        point = trend_map[cursor]
        trend.append({'date': cursor.isoformat(), 'revenue': str(point['revenue']), 'cost': str(point['cost']), 'gross_profit': str(point['revenue'] - point['cost']), 'orders': len(point['orders']), 'items': point['items']})
        if filters['group'] == 'month':
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            cursor += timedelta(days=1)

    def finalize(row):
        return {**row, 'revenue': str(row['revenue']), 'cost': str(row['cost']), 'gross_profit': str(row['revenue'] - row['cost']), 'orders': len(row['orders'])}

    categories = sorted((finalize(row) for row in category_map.values()), key=lambda row: Decimal(row['revenue']), reverse=True)
    dishes = sorted((finalize(row) for row in dish_map.values()), key=lambda row: Decimal(row['revenue']), reverse=True)
    return {
        'filters': {
            'start': filters['start'], 'end': filters['end'], 'group': filters['group'],
            'category': filters.get('category'), 'dish': filters.get('dish'),
        },
        'summary': {
            'revenue': str(revenue), 'cost': str(cost), 'gross_profit': str(revenue - cost),
            'gross_margin': str((revenue - cost) / revenue * 100 if revenue else 0), 'orders': order_count, 'items': items_sold,
            'average_check': str(revenue / order_count if order_count else 0),
            'by_method': [
                {'method': method, 'label': SALE_PAYMENT_LABELS.get(method, method or '—'), 'revenue': str(total)}
                for method, total in sorted(method_map.items(), key=lambda row: row[1], reverse=True)
            ],
        },
        'trend': trend,
        'categories': categories,
        'dishes': dishes,
    }


def _column(number):
    value = ''
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _sheet(rows, widths=None):
    cells = []
    for row_number, row in enumerate(rows, 1):
        row_cells = []
        for column_number, value in enumerate(row, 1):
            ref = f'{_column(column_number)}{row_number}'
            style = '1' if row_number == 1 else ('2' if isinstance(value, Decimal) else '0')
            if isinstance(value, (int, float, Decimal)):
                row_cells.append(f'<c r="{ref}" s="{style}"><v>{value}</v></c>')
            else:
                row_cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{escape(str(value or ""))}</t></is></c>')
        cells.append(f'<row r="{row_number}">{"".join(row_cells)}</row>')
    cols = ''.join(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>' for index, width in enumerate(widths or [], 1))
    last_cell = f'{_column(len(rows[0]))}{len(rows)}'
    # Element order follows the OOXML worksheet schema. Excel may silently repair
    # out-of-order elements and then show an apparently empty worksheet.
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:{last_cell}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/><cols>{cols}</cols><sheetData>{"".join(cells)}</sheetData><autoFilter ref="A1:{last_cell}"/><pageMargins left="0.5" right="0.5" top="0.75" bottom="0.75" header="0.3" footer="0.3"/></worksheet>'


def sales_report_xlsx(report):
    start, end = report['filters']['start'], report['filters']['end']
    summary = [
        ['Ko‘rsatkich', 'Qiymat'], ['Hisobot boshi', start.isoformat()], ['Hisobot oxiri', end.isoformat()],
        ['Jami tushum', Decimal(report['summary']['revenue'])], ['Buyurtmalar', report['summary']['orders']],
        ['Sotilgan porsiya', report['summary']['items']], ['Tannarx', Decimal(report['summary']['cost'])], ['Yalpi foyda', Decimal(report['summary']['gross_profit'])], ['Yalpi marja, %', Decimal(report['summary']['gross_margin'])], ['O‘rtacha chek', Decimal(report['summary']['average_check'])],
        *[[row['label'], Decimal(row['revenue'])] for row in report['summary']['by_method']],
    ]
    daily = [['Sana', 'Tushum', 'Tannarx', 'Yalpi foyda', 'Buyurtmalar', 'Porsiyalar']] + [[row['date'], Decimal(row['revenue']), Decimal(row['cost']), Decimal(row['gross_profit']), row['orders'], row['items']] for row in report['trend']]
    categories = [['Kategoriya', 'Tushum', 'Tannarx', 'Yalpi foyda', 'Porsiyalar', 'Buyurtmalar']] + [[row['category'], Decimal(row['revenue']), Decimal(row['cost']), Decimal(row['gross_profit']), row['quantity'], row['orders']] for row in report['categories']]
    dishes = [['Taom', 'Kategoriya', 'Tushum', 'Tannarx', 'Yalpi foyda', 'Porsiyalar', 'Buyurtmalar']] + [[row['dish'], row['category'], Decimal(row['revenue']), Decimal(row['cost']), Decimal(row['gross_profit']), row['quantity'], row['orders']] for row in report['dishes']]
    sheets = [('Umumiy', summary, [24, 22]), ('Davrlar', daily, [16, 20, 20, 20, 16, 16]), ('Kategoriyalar', categories, [28, 20, 20, 20, 16, 16]), ('Taomlar', dishes, [30, 25, 20, 20, 20, 16, 16])]
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets)+1)) + '</Types>')
        archive.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + ''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_,_) in enumerate(sheets,1)) + '</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1)) + f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        archive.writestr('xl/styles.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF17694F"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"/><xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs></styleSheet>')
        for index, (_, rows, widths) in enumerate(sheets, 1):
            archive.writestr(f'xl/worksheets/sheet{index}.xml', _sheet(rows, widths))
    return output.getvalue()


class SalesBoardFilters(serializers.Serializer):
    """Filters for the till-facing sales board. Defaults to today."""

    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    category = serializers.IntegerField(min_value=1, required=False)
    dish = serializers.IntegerField(min_value=1, required=False)
    mine = serializers.BooleanField(default=False)

    def validate(self, attrs):
        today = timezone.localdate()
        attrs['end'] = attrs.get('end', today)
        attrs['start'] = attrs.get('start', attrs['end'])
        if attrs['start'] > attrs['end']:
            raise serializers.ValidationError(_('Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.'))
        if attrs['end'] > today:
            raise serializers.ValidationError(_('Kelajakdagi sana uchun savdo ko‘rsatilmaydi.'))
        if (attrs['end'] - attrs['start']).days > 366:
            raise serializers.ValidationError(_('Bir ko‘rinishda ko‘pi bilan 1 yil.'))
        branch = self.context['request'].user.branch
        category = None
        if attrs.get('category'):
            category = Category.objects.filter(branch=branch, pk=attrs['category']).first()
            if not category:
                raise serializers.ValidationError({'category': _('Kategoriya topilmadi.')})
        if attrs.get('dish'):
            dish = Dish.objects.filter(branch=branch, pk=attrs['dish']).first()
            if not dish or (category and dish.category_id != category.id):
                raise serializers.ValidationError({'dish': _('Taom tanlangan kategoriyaga tegishli emas.')})
        return attrs


def build_sales_board(user, filters):
    """What the till actually sold: totals, busiest hours, dishes and who rang them up.

    Every figure is grouped in the database, so a wide date range stays one query
    per section instead of one per row. Recipe cost and margin are deliberately
    left out: this board is for the people selling, not for costing.
    """
    branch = user.branch
    money = DecimalField(max_digits=18, decimal_places=2)
    revenue_sum = Sum(F('price') * F('quantity'), output_field=money)

    lines = OrderLine.objects.filter(
        order__branch=branch,
        order__status='paid',
        order__paid_at__date__gte=filters['start'],
        order__paid_at__date__lte=filters['end'],
    )
    if filters.get('mine'):
        lines = lines.filter(order__cashier=user)
    if filters.get('category'):
        lines = lines.filter(dish__category_id=filters['category'])
    if filters.get('dish'):
        lines = lines.filter(dish_id=filters['dish'])

    totals = lines.aggregate(revenue=revenue_sum, items=Sum('quantity'), orders=Count('order_id', distinct=True))
    revenue = totals['revenue'] or Decimal('0')
    order_count = totals['orders'] or 0

    def cash(value):
        return str(value or Decimal('0'))

    def grouped(*fields, sort='-revenue'):
        return list(
            lines.values(*fields)
            .annotate(revenue=revenue_sum, quantity=Sum('quantity'), orders=Count('order_id', distinct=True))
            .order_by(sort)
        )

    dishes = [
        {'dish_id': row['dish_id'], 'dish': row['name'], 'category': row['dish__category__name'],
         'quantity': row['quantity'], 'orders': row['orders'], 'revenue': cash(row['revenue'])}
        for row in grouped('dish_id', 'name', 'dish__category__name')
    ]
    categories = [
        {'category_id': row['dish__category_id'], 'category': row['dish__category__name'],
         'quantity': row['quantity'], 'orders': row['orders'], 'revenue': cash(row['revenue'])}
        for row in grouped('dish__category_id', 'dish__category__name')
    ]
    cashiers = [
        {'name': row['order__cashier__first_name'] or row['order__cashier__username'],
         'orders': row['orders'], 'quantity': row['quantity'], 'revenue': cash(row['revenue'])}
        for row in grouped('order__cashier_id', 'order__cashier__first_name', 'order__cashier__username')
    ]
    methods = [
        {'method': row['order__payment_method'],
         'label': SALE_PAYMENT_LABELS.get(row['order__payment_method'], row['order__payment_method'] or '—'),
         'orders': row['orders'], 'revenue': cash(row['revenue'])}
        for row in grouped('order__payment_method')
    ]
    # Kanal kesimi: buyurtma qayerdan kelgani — zal, olib ketish, Uzum, Yandex.
    channels = [
        {'channel': row['order__channel'],
         'label': SALE_CHANNEL_LABELS.get(row['order__channel'], row['order__channel']),
         'orders': row['orders'], 'revenue': cash(row['revenue']),
         'delivery': row['order__channel'] in ('uzum', 'yandex')}
        for row in grouped('order__channel')
    ]
    hours = [
        {'hour': row['hour'], 'orders': row['orders'], 'revenue': cash(row['revenue'])}
        for row in lines.annotate(hour=ExtractHour('order__paid_at')).values('hour')
        .annotate(revenue=revenue_sum, orders=Count('order_id', distinct=True)).order_by('hour')
    ]
    days = [
        {'date': row['day'].isoformat(), 'orders': row['orders'], 'revenue': cash(row['revenue'])}
        for row in lines.annotate(day=TruncDate('order__paid_at')).values('day')
        .annotate(revenue=revenue_sum, orders=Count('order_id', distinct=True)).order_by('day')
    ]

    checks = Order.objects.filter(
        branch=branch, status='paid',
        paid_at__date__gte=filters['start'], paid_at__date__lte=filters['end'],
    )
    if filters.get('mine'):
        checks = checks.filter(cashier=user)
    if filters.get('category') or filters.get('dish'):
        checks = checks.filter(id__in=lines.values('order_id'))

    busiest = max(hours, key=lambda row: Decimal(row['revenue'])) if hours else None
    return {
        'filters': {
            'start': filters['start'], 'end': filters['end'],
            'category': filters.get('category'), 'dish': filters.get('dish'), 'mine': filters.get('mine', False),
        },
        'summary': {
            'revenue': cash(revenue),
            'orders': order_count,
            'items': totals['items'] or 0,
            'average_check': cash((revenue / order_count).quantize(Decimal('0.01')) if order_count else Decimal('0')),
            'top_dish': dishes[0]['dish'] if dishes else None,
            'peak_hour': busiest['hour'] if busiest else None,
            'peak_hour_revenue': busiest['revenue'] if busiest else None,
        },
        'methods': methods,
        'channels': channels,
        'hours': hours,
        'days': days,
        'dishes': dishes,
        'categories': categories,
        'cashiers': cashiers,
        'checks': [
            {'id': order.id, 'table': order.table, 'waiter': order.waiter, 'total': str(order.total),
             'payment_method': order.payment_method,
             'payment_label': SALE_PAYMENT_LABELS.get(order.payment_method, order.payment_method or '—'),
             'paid_at': order.paid_at,
             'cashier_name': order.cashier.first_name or order.cashier.username,
             'items': sum(line.quantity for line in order.lines.all())}
            for order in checks.select_related('cashier').prefetch_related('lines')[:20]
        ],
    }
