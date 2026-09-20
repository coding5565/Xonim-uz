"""Yetkazib berish platformalari ushlab qoladigan ulush.

Uzum va Yandex sotuv summasining bir qismini o'zida qoldiradi: mijoz 100 000
to'lasa, hisobga shartnomaga qarab 70 000 tushadi. Shartnoma o'zgarishi mumkin,
shuning uchun foiz shu yerdan boshqariladi.

Eng muhim qoida: bu yerdagi o'zgarish FAQAT yangi sotuvlarga tegishli. Har bir
buyurtma o'z foizini sotuv paytida `Order.channel_commission` ga muzlatib
oladi, shuning uchun o'tgan oyning hisoboti bugungi tahrirdan keyin ham
o'zgarmaydi.
"""
from decimal import Decimal

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.i18n import _
from users.permissions import OwnerOnly

from .models import DEFAULT_PLATFORM_COMMISSION, DELIVERY_CHANNELS, SALE_CHANNEL_LABELS, ChannelFee
from .services import audit


class ChannelFeeInput(serializers.Serializer):
    channel = serializers.ChoiceField(choices=DELIVERY_CHANNELS)
    commission = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'),
    )


def fee_rows(branch):
    saved = {item.channel: item for item in ChannelFee.objects.filter(branch=branch)}
    rows = []
    for channel in DELIVERY_CHANNELS:
        item = saved.get(channel)
        rows.append({
            'channel': channel,
            'label': SALE_CHANNEL_LABELS.get(channel, channel),
            'commission': str(item.commission if item else DEFAULT_PLATFORM_COMMISSION),
            # Bizga qoladigan ulush — foizni o'qishning eng tabiiy yo'li.
            'net_share': str(100 - (item.commission if item else DEFAULT_PLATFORM_COMMISSION)),
            'updated_at': item.updated_at if item else None,
            'configured': bool(item),
        })
    return rows


class ChannelFeeView(APIView):
    """Superadmin platforma ulushini ko'radi va o'zgartiradi."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        return Response({
            'rows': fee_rows(request.user.branch),
            'default': str(DEFAULT_PLATFORM_COMMISSION),
        })

    def put(self, request):
        data = ChannelFeeInput(data=request.data)
        data.is_valid(raise_exception=True)
        channel, commission = data.validated_data['channel'], data.validated_data['commission']
        # Eski qiymat oldin o'qiladi: jurnalda «nimadan nimaga» ko'rinib tursin.
        previous = ChannelFee.objects.filter(branch=request.user.branch, channel=channel).first()
        before = previous.commission if previous else DEFAULT_PLATFORM_COMMISSION
        ChannelFee.objects.update_or_create(
            branch=request.user.branch, channel=channel, defaults={'commission': commission},
        )
        if before != commission or not previous:
            audit(
                request.user, 'channel.fee',
                f'{SALE_CHANNEL_LABELS.get(channel, channel)} · ushlanma {before}% -> {commission}% · '
                f'bizga {100 - commission}%',
            )
        return Response({
            'rows': fee_rows(request.user.branch),
            'default': str(DEFAULT_PLATFORM_COMMISSION),
            'detail': _('Saqlandi. Yangi foiz shu paytdan keyingi sotuvlarga qo‘llanadi.'),
        })
