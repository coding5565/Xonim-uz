from datetime import datetime, time, timedelta
from decimal import Decimal
from html import escape
from io import BytesIO
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.contrib.auth import password_validation
from django.db import transaction
from django.db.models import Count
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from operations.models import SALE_PAYMENT_METHODS, SalaryPayment
from operations.services import Conflict, audit, create_expense
from .models import AuditEvent, User, audit_group, audit_label
from .permissions import OwnerOnly
from core.i18n import _


def salary_register_xlsx(payments):
    rows = [['Xodim', 'Login', 'Rol', 'Qaysi oy uchun', 'To‘langan sana', 'Summa', 'To‘lov turi', 'Kiritgan', 'Izoh']]
    rows += [[
        item.employee.first_name or item.employee.username, item.employee.username, item.employee.get_role_display(),
        item.period.strftime('%Y-%m'), item.paid_on.isoformat(), item.amount,
        'Naqd' if item.payment_method == 'cash' else 'Karta', item.actor.first_name or item.actor.username, item.note,
    ] for item in payments]
    def column(index):
        result = ''
        while index:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result
    sheet_rows = []
    for row_number, row in enumerate(rows, 1):
        cells = []
        for cell_number, value in enumerate(row, 1):
            ref = f'{column(cell_number)}{row_number}'
            if isinstance(value, Decimal):
                cells.append(f'<c r="{ref}" s="2"><v>{value}</v></c>')
            else:
                style = '1' if row_number == 1 else '0'
                cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{escape(str(value or ""))}</t></is></c>')
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    last = f'I{len(rows)}'
    worksheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:{last}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="24" customWidth="1"/><col min="2" max="2" width="20" customWidth="1"/><col min="3" max="3" width="16" customWidth="1"/><col min="4" max="5" width="18" customWidth="1"/><col min="6" max="6" width="18" customWidth="1"/><col min="7" max="8" width="17" customWidth="1"/><col min="9" max="9" width="35" customWidth="1"/></cols><sheetData>{"".join(sheet_rows)}</sheetData><autoFilter ref="A1:{last}"/></worksheet>'''
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Oyliklar" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        archive.writestr('xl/styles.xml', '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF17694F"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0"/><xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs></styleSheet>')
        archive.writestr('xl/worksheets/sheet1.xml', worksheet)
    return output.getvalue()


def profile(user):
    return {
        'id': user.id, 'username': user.username, 'name': user.first_name or user.username,
        'role': user.role, 'branch': user.branch.name if user.branch else None,
        # Session bootstrap config: the till and the reports render whatever is listed here.
        'payment_methods': [{'method': method, 'label': label} for method, label in SALE_PAYMENT_METHODS],
    }


class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'csrfToken': get_token(request)})


class LoginThrottle(AnonRateThrottle):
    scope = 'login'


class LoginInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        data = LoginInput(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(request, **data.validated_data)
        if not user or not user.branch_id:
            return Response({'detail': 'Login yoki parol noto‘g‘ri.'}, status=400)
        login(request, user)
        audit(user, 'auth.login', f'{user.first_name or user.username} · {user.get_role_display()}')
        return Response(profile(user))


class MeView(APIView):
    def get(self, request):
        return Response(profile(request.user))


class LogoutView(APIView):
    def post(self, request):
        # Jurnal yozuvi sessiya yopilmasdan oldin yoziladi: keyin request.user
        # anonim bo'lib qoladi.
        audit(request.user, 'auth.logout', f'{request.user.first_name or request.user.username} · {request.user.get_role_display()}')
        logout(request)
        return Response({'detail': 'Sessiya yakunlandi.'})


AUDIT_PAGE_SIZE = 100


class AuditFilters(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    action = serializers.CharField(max_length=100, required=False, allow_blank=True)
    actor = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if attrs.get('start') and attrs.get('end') and attrs['start'] > attrs['end']:
            raise serializers.ValidationError(_('Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.'))
        return attrs


def _day_window(start, end):
    """Mahalliy kunni server vaqt zonasidagi oraliqqa aylantiradi.

    Filtr `created_at__date` emas, balki oraliq bo‘yicha ishlaydi — shunda
    indeks ishlatiladi va jurnal o‘n minglab qator bo‘lsa ham tez qoladi.
    """
    bounds = {}
    if start:
        bounds['created_at__gte'] = timezone.make_aware(datetime.combine(start, time.min))
    if end:
        bounds['created_at__lt'] = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min))
    return bounds


class AuditView(APIView):
    """Superadmin uchun harakatlar jurnali: hammasi saqlanadi, 100 tadan ko‘rsatiladi."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        filters = AuditFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        data = filters.validated_data

        scope = AuditEvent.objects.filter(branch=request.user.branch, **_day_window(data.get('start'), data.get('end')))
        rows = scope
        if data.get('action'):
            rows = rows.filter(action=data['action'])
        if data.get('actor'):
            rows = rows.filter(actor_id=data['actor'])

        count = rows.count()
        pages = max(1, -(-count // AUDIT_PAGE_SIZE))
        page = min(data['page'], pages)
        start_index = (page - 1) * AUDIT_PAGE_SIZE
        window = rows.values('id', 'action', 'description', 'created_at', 'actor_id', 'actor__first_name', 'actor__username')[start_index:start_index + AUDIT_PAGE_SIZE]

        # Ro'yxatlar sana oralig'iga qarab tuziladi, lekin tanlangan harakat turi
        # hisobga olinmaydi — aks holda filtr o'zini o'zi bir bandga qisqartirardi.
        # .order_by() shart: modelning Meta.ordering'i GROUP BY'ni buzadi.
        action_counts = scope.values('action').annotate(total=Count('id')).order_by('-total', 'action')
        actor_counts = scope.values('actor_id', 'actor__first_name', 'actor__username').annotate(total=Count('id')).order_by('-total')

        return Response({
            'results': [{
                'id': row['id'],
                'action': row['action'],
                'label': audit_label(row['action']),
                'group': audit_group(row['action']),
                'description': row['description'],
                'created_at': row['created_at'],
                'actor_id': row['actor_id'],
                'actor': row['actor__first_name'] or row['actor__username'],
            } for row in window],
            'page': page,
            'pages': pages,
            'count': count,
            'page_size': AUDIT_PAGE_SIZE,
            'total': scope.count() if (data.get('action') or data.get('actor')) else count,
            'actions': [{
                'action': row['action'],
                'label': audit_label(row['action']),
                'group': audit_group(row['action']),
                'count': row['total'],
            } for row in action_counts],
            'actors': [{
                'id': row['actor_id'],
                'name': row['actor__first_name'] or row['actor__username'],
                'count': row['total'],
            } for row in actor_counts],
        })


class StaffCreateInput(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    username = serializers.RegexField(r'^[\w.@+-]+$', min_length=3, max_length=150)
    role = serializers.ChoiceField(choices=[User.Role.ADMIN, User.Role.CASHIER, User.Role.KITCHEN])
    password = serializers.CharField(min_length=12, max_length=128, trim_whitespace=False, write_only=True)
    phone = serializers.CharField(max_length=30, allow_blank=True, default='')
    salary = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), default=0)
    hired_at = serializers.DateField(allow_null=True, required=False)
    notes = serializers.CharField(max_length=300, allow_blank=True, default='')

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(_('Bu login band.'))
        return value

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value


class StaffUpdateInput(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    role = serializers.ChoiceField(choices=[User.Role.ADMIN, User.Role.CASHIER, User.Role.KITCHEN], required=False)
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False)
    salary = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False)
    hired_at = serializers.DateField(allow_null=True, required=False)
    notes = serializers.CharField(max_length=300, allow_blank=True, required=False)
    active = serializers.BooleanField(required=False)


class SalaryPaymentInput(serializers.Serializer):
    period = serializers.RegexField(r'^\d{4}-\d{2}$')
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('1'))
    payment_method = serializers.ChoiceField(choices=['cash', 'card'])
    paid_on = serializers.DateField()
    note = serializers.CharField(max_length=250, allow_blank=True, default='')

    def validate_period(self, value):
        try:
            period = datetime.strptime(value, '%Y-%m').date().replace(day=1)
        except ValueError:
            raise serializers.ValidationError(_('Oy noto‘g‘ri.'))
        if period > timezone.localdate().replace(day=1):
            raise serializers.ValidationError(_('Kelajak oyi uchun to‘lov kiritib bo‘lmaydi.'))
        return period

    def validate_paid_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(_('Kelajakdagi to‘lov sanasi mumkin emas.'))
        return value


def staff_payload(user):
    latest = user.salary_payments.order_by('-period').first()
    return {
        'id': user.id,
        'name': user.first_name or user.username,
        'username': user.username,
        'role': user.role,
        'active': user.is_active,
        'phone': user.phone,
        'salary': str(user.salary),
        'hired_at': user.hired_at,
        'notes': user.notes,
        'last_login': user.last_login,
        'last_salary_period': latest.period.strftime('%Y-%m') if latest else None,
        'last_salary_paid_on': latest.paid_on if latest else None,
    }


def branch_employee(request, pk):
    user = User.objects.filter(branch=request.user.branch, pk=pk).first()
    if not user:
        raise serializers.ValidationError(_('Xodim topilmadi.'))
    return user


class StaffView(APIView):
    permission_classes = [OwnerOnly]

    def get(self, request):
        staff = User.objects.filter(branch=request.user.branch).prefetch_related('salary_payments').order_by('role', 'first_name', 'username')
        return Response([staff_payload(user) for user in staff])

    @transaction.atomic
    def post(self, request):
        serializer = StaffCreateInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            first_name=data['name'],
            role=data['role'],
            branch=request.user.branch,
            phone=data['phone'],
            salary=data['salary'],
            hired_at=data.get('hired_at'),
            notes=data['notes'],
        )
        AuditEvent.objects.create(
            branch=request.user.branch,
            actor=request.user,
            action='staff.create',
            description=f'{user.first_name} · {user.get_role_display()}',
        )
        return Response(staff_payload(user), status=201)


class StaffDetailView(APIView):
    permission_classes = [OwnerOnly]

    @transaction.atomic
    def patch(self, request, pk):
        user = branch_employee(request, pk)
        if user.role == User.Role.OWNER:
            raise serializers.ValidationError(_('Superadmin hisobini bu yerdan o‘zgartirib bo‘lmaydi.'))
        serializer = StaffUpdateInput(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        field_map = {'name': 'first_name', 'active': 'is_active'}
        changed = []
        for field, value in data.items():
            model_field = field_map.get(field, field)
            if getattr(user, model_field) != value:
                setattr(user, model_field, value)
                changed.append(model_field)
        if changed:
            user.save(update_fields=changed)
            AuditEvent.objects.create(branch=request.user.branch, actor=request.user, action='staff.update', description=f'{user.first_name} · {", ".join(changed)}')
        return Response(staff_payload(user))


class SalaryPaymentView(APIView):
    permission_classes = [OwnerOnly]

    def get(self, request, pk):
        employee = branch_employee(request, pk)
        payments = SalaryPayment.objects.filter(branch=request.user.branch, employee=employee).select_related('actor')
        return Response([{
            'id': item.id,
            'period': item.period.strftime('%Y-%m'),
            'amount': str(item.amount),
            'payment_method': item.payment_method,
            'paid_on': item.paid_on,
            'note': item.note,
            'actor_name': item.actor.first_name or item.actor.username,
        } for item in payments])

    @transaction.atomic
    def post(self, request, pk):
        employee = User.objects.select_for_update().filter(branch=request.user.branch, pk=pk).first()
        if not employee:
            raise serializers.ValidationError(_('Xodim topilmadi.'))
        if employee.role == User.Role.OWNER:
            raise serializers.ValidationError(_('Superadmin oyligi bu bo‘limda yuritilmaydi.'))
        serializer = SalaryPaymentInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if SalaryPayment.objects.select_for_update().filter(branch=request.user.branch, employee=employee, period=data['period']).exists():
            raise Conflict(_('Bu xodim uchun tanlangan oy oyligi allaqachon to‘langan.'))
        expense = create_expense(request.user, {
            'key': uuid4(),
            'category': 'Ish haqi',
            'purpose': f'{data["period"].strftime("%Y-%m")} oyi uchun oylik',
            'recipient': employee.first_name or employee.username,
            'amount': data['amount'],
            'payment_method': data['payment_method'],
            'date': data['paid_on'],
        })
        payment = SalaryPayment.objects.create(
            branch=request.user.branch,
            employee=employee,
            actor=request.user,
            expense=expense,
            period=data['period'],
            amount=data['amount'],
            payment_method=data['payment_method'],
            paid_on=data['paid_on'],
            note=data['note'],
        )
        AuditEvent.objects.create(branch=request.user.branch, actor=request.user, action='salary.pay', description=f'{employee.first_name} · {payment.period:%Y-%m} · {payment.amount} so‘m')
        return Response({
            'id': payment.id,
            'period': payment.period.strftime('%Y-%m'),
            'amount': str(payment.amount),
            'payment_method': payment.payment_method,
            'paid_on': payment.paid_on,
            'note': payment.note,
            'actor_name': request.user.first_name or request.user.username,
        }, status=201)


class SalaryPaymentExportView(APIView):
    permission_classes = [OwnerOnly]

    def get(self, request):
        payments = SalaryPayment.objects.filter(branch=request.user.branch).select_related('employee', 'actor').order_by('-paid_on', '-id')
        content = salary_register_xlsx(payments)
        response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="honim-umumiy-oyliklar.xlsx"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
