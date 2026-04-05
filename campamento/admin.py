from django.contrib import admin
from django.contrib import messages
from django.db.models import Sum, Case, When, Value, DecimalField, ExpressionWrapper, F
from django.urls import reverse
from django.utils.html import format_html
from decimal import Decimal
from .models import Campista, Pago

EXCHANGE_RATE = Decimal('36.67')
TOTAL_CAMPA_USD = Decimal('30')

@admin.register(Campista)
class CampistaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'subsidizado', 'estado_display', 'total_pagado_display', 'saldo_pendiente_display', 'marcar_subsidiado_boton')
    list_filter = ('subsidizado', 'quiere_camisa', 'talla_camisa')
    search_fields = ('nombre', 'telefono')
    actions = ['marcar_subsidiado_action']

    class Media:
        js = ('campamento/admin_subsidiado.js',)

    def estado_display(self, obj):
        return obj.estado()
    estado_display.short_description = 'Estado'

    def total_pagado_display(self, obj):
        return obj.total_pagado_display()
    total_pagado_display.short_description = 'Total Pagado'

    def saldo_pendiente_display(self, obj):
        return obj.saldo_pendiente_display()
    saldo_pendiente_display.short_description = 'Saldo Pendiente'

    def marcar_subsidiado_boton(self, obj):
        if obj.subsidizado:
            return format_html('<span style="color: green; font-weight: bold;">Subsidiado</span>')
        
        return format_html(
            '<button type="button" class="btn btn-warning btn-sm" onclick="marcarSubsidiado({})" style="background: #f39c12; border-color: #e67e22; color: white;">Marcar Subsidiado</button>',
            obj.id
        )
    
    marcar_subsidiado_boton.short_description = 'Acción'
    marcar_subsidiado_boton.allow_tags = True

    def marcar_subsidiado_action(self, request, queryset):
        marcados = 0
        ya_subsidiados = 0

        for campista in queryset:
            if campista.subsidizado:
                ya_subsidiados += 1
                continue

            campista.subsidizado = True
            campista.save(update_fields=['subsidizado'])
            marcados += 1

        if marcados > 0:
            self.message_user(request, f'{marcados} campista(s) marcado(s) como subsidiado(s).', messages.SUCCESS)
        if ya_subsidiados > 0:
            self.message_user(request, f'{ya_subsidiados} campista(s) ya estaban subsidiado(s).', messages.WARNING)

    marcar_subsidiado_action.short_description = 'Marcar como subsidiado'

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('campista', 'monto', 'moneda', 'fecha')
    list_filter = ('moneda', 'fecha')
    search_fields = ('campista__nombre',)
