from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import (
    Case,
    CharField,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Round
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Campista, Pago

EXCHANGE_RATE = Decimal('36.67')
TOTAL_CAMPA_USD = Decimal('30')


def _qs_campistas_anotado():
    """Una sola agregación SQL por campista: total pagado en USD y última moneda (evita N+1)."""
    nio_a_usd = ExpressionWrapper(
        F('pagos__monto') / Value(EXCHANGE_RATE, output_field=DecimalField(max_digits=24, decimal_places=8)),
        output_field=DecimalField(max_digits=24, decimal_places=8),
    )
    suma_usd = Sum(
        Case(
            When(pagos__moneda='USD', then=F('pagos__monto')),
            When(pagos__moneda='NIO', then=nio_a_usd),
            default=Value(Decimal('0')),
            output_field=DecimalField(max_digits=24, decimal_places=8),
        )
    )
    tp_usd = Coalesce(
        suma_usd,
        Value(Decimal('0')),
        output_field=DecimalField(max_digits=24, decimal_places=8),
    )
    ultima_mon = Subquery(
        Pago.objects.filter(campista_id=OuterRef('pk')).order_by('-fecha').values('moneda')[:1],
        output_field=CharField(max_length=3),
    )
    return Campista.objects.annotate(tp_usd=tp_usd, ultima_mon=ultima_mon)


def _qs_con_total_redondeado():
    """Redondeo a 2 decimales como total_pagado() del modelo (evita desajuste filtro vs estado)."""
    return _qs_campistas_anotado().annotate(tp_round=Round(F('tp_usd'), 2))


def _aplicar_filtros_campistas(qs, search_name='', filter_talla='', filter_estado=''):
    if search_name:
        qs = qs.filter(nombre__icontains=search_name)
    if filter_talla:
        qs = qs.filter(talla_camisa=filter_talla)
    if filter_estado == 'Pendiente':
        qs = qs.filter(tp_round=Decimal('0'))
    elif filter_estado == 'Abonando':
        qs = qs.filter(tp_round__gt=0, tp_round__lt=TOTAL_CAMPA_USD)
    elif filter_estado == 'Cancelado':
        qs = qs.filter(tp_round__gte=TOTAL_CAMPA_USD)
    return qs


def _fila_lista_desde_anotaciones(tp_round, ultima_mon):
    """Misma lógica visual que total_pagado_display / saldo_pendiente_display / estado()."""
    tp = tp_round if tp_round is not None else Decimal('0')
    ultima = ultima_mon or 'USD'
    tp = tp.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if tp == 0:
        estado = 'Pendiente'
    elif tp >= TOTAL_CAMPA_USD:
        estado = 'Cancelado'
    else:
        estado = 'Abonando'
    saldo = TOTAL_CAMPA_USD - tp if TOTAL_CAMPA_USD > tp else Decimal('0')
    if ultima == 'NIO':
        tp_nio = (tp * EXCHANGE_RATE).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        saldo_nio = (saldo * EXCHANGE_RATE).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        pagado_display = f'C$ {tp_nio}'
        saldo_display = f'C$ {saldo_nio}'
    else:
        saldo_usd = saldo.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        pagado_display = f'$ {tp}'
        saldo_display = f'$ {saldo_usd}'
    return estado, pagado_display, saldo_display


def _enriquecer_campista_lista(c):
    estado, pd, sd = _fila_lista_desde_anotaciones(c.tp_round, c.ultima_mon)
    c.lista_estado = estado
    c.lista_pagado_display = pd
    c.lista_saldo_display = sd
    return c


def _total_recaudado_global():
    """Suma de todos los pagos registrados (pendientes no aportan; abonando + cancelados sí)."""
    nio_a_usd = ExpressionWrapper(
        F('monto') / Value(EXCHANGE_RATE, output_field=DecimalField(max_digits=24, decimal_places=8)),
        output_field=DecimalField(max_digits=24, decimal_places=8),
    )
    total_usd = Pago.objects.aggregate(
        s=Coalesce(
            Sum(
                Case(
                    When(moneda='USD', then=F('monto')),
                    When(moneda='NIO', then=nio_a_usd),
                    default=Value(Decimal('0')),
                    output_field=DecimalField(max_digits=24, decimal_places=8),
                )
            ),
            Value(Decimal('0')),
            output_field=DecimalField(max_digits=24, decimal_places=8),
        )
    )['s'] or Decimal('0')
    total_usd = total_usd.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_nio = (total_usd * EXCHANGE_RATE).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return {
        'usd': f'$ {total_usd}',
        'nio': f'C$ {total_nio}',
    }


def _conteos_generales():
    tallas_counts = Campista.objects.filter(talla_camisa__isnull=False).exclude(talla_camisa='') \
        .values('talla_camisa').annotate(total=Count('id')).order_by('talla_camisa')

    base = _qs_con_total_redondeado()
    agg = base.aggregate(
        pendiente=Count('pk', filter=Q(tp_round=Decimal('0'))),
        abonando=Count('pk', filter=Q(tp_round__gt=0, tp_round__lt=TOTAL_CAMPA_USD)),
        cancelado=Count('pk', filter=Q(tp_round__gte=TOTAL_CAMPA_USD)),
    )
    estado_counts = {
        'Pendiente': agg['pendiente'] or 0,
        'Abonando': agg['abonando'] or 0,
        'Cancelado': agg['cancelado'] or 0,
    }

    return tallas_counts, estado_counts, _total_recaudado_global()


def lista_campistas(request):
    search_name = request.GET.get('nombre', '').strip()
    filter_talla = request.GET.get('talla_camisa', '')
    filter_estado = request.GET.get('estado', '')

    qs = _aplicar_filtros_campistas(
        _qs_con_total_redondeado(), search_name, filter_talla, filter_estado
    ).order_by('-fecha_registro')
    campistas = [_enriquecer_campista_lista(c) for c in qs]
    tallas_counts, estado_counts, total_recaudado = _conteos_generales()

    return render(request, 'lista.html', {
        'campistas': campistas,
        'search_name': search_name,
        'filter_talla': filter_talla,
        'filter_estado': filter_estado,
        'tallas_counts': tallas_counts,
        'estado_counts': estado_counts,
        'total_recaudado': total_recaudado,
        'exchange_rate': EXCHANGE_RATE,
        'tallas': ['4','6','8','10','12','14','16','18','XS','S','M','L','XL'],
    })


def campistas_data(request):
    search_name = request.GET.get('nombre', '').strip()
    filter_talla = request.GET.get('talla_camisa', '')
    filter_estado = request.GET.get('estado', '')
    page_number = request.GET.get('page', 1)

    qs = _aplicar_filtros_campistas(
        _qs_con_total_redondeado(), search_name, filter_talla, filter_estado
    ).order_by('-fecha_registro')
    paginator = Paginator(qs, 8)
    page_obj = paginator.get_page(page_number)

    tallas_counts, estado_counts, total_recaudado = _conteos_generales()

    total_nio_str = str((TOTAL_CAMPA_USD * EXCHANGE_RATE).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    campistas_data = []
    for c in page_obj.object_list:
        estado, pagado_d, saldo_d = _fila_lista_desde_anotaciones(c.tp_round, c.ultima_mon)
        campistas_data.append({
            'id': c.id,
            'nombre': c.nombre,
            'telefono': c.telefono,
            'quiere_camisa': c.quiere_camisa,
            'talla_camisa': c.talla_camisa,
            'total': str(TOTAL_CAMPA_USD),
            'total_nio': total_nio_str,
            'total_pagado_display': pagado_d,
            'saldo_pendiente_display': saldo_d,
            'estado': estado,
        })

    return JsonResponse({
        'campistas': campistas_data,
        'tallas_counts': list(tallas_counts),
        'estado_counts': estado_counts,
        'total_recaudado': total_recaudado,
        'total_items': paginator.count,
        'num_pages': paginator.num_pages,
        'current_page': page_obj.number,
    })

def _validar_campista_data(nombre, telefono):
    import re
    nombre = (nombre or '').strip()
    telefono = (telefono or '').strip()
    if not nombre or not re.fullmatch(r'[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s]+', nombre):
        return 'Nombre inválido. Sólo se permiten letras y espacios.'
    if not telefono.isdigit() or len(telefono) != 8:
        return 'Teléfono inválido. Debe contener exactamente 8 dígitos.'
    return None


def agregar_campista(request):
    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        telefono = (request.POST.get('telefono') or '').strip()
        quiere_camisa = request.POST.get('quiere_camisa') == 'on'
        talla = request.POST.get('talla_camisa') if quiere_camisa else ''

        error = _validar_campista_data(nombre, telefono)
        if error:
            return render(request, 'agregar.html', {
                'error': error,
                'nombre': nombre,
                'telefono': telefono,
                'quiere_camisa': quiere_camisa,
                'talla_camisa': talla,
                'tallas': ['4','6','8','10','12','14','16','18','XS','S','M','L','XL'],
                'campista': None,
            })

        Campista.objects.create(
            nombre=nombre,
            telefono=telefono,
            quiere_camisa=quiere_camisa,
            talla_camisa=talla
        )

        return redirect('lista_campistas')

    return render(request, 'agregar.html', {
        'tallas': ['4','6','8','10','12','14','16','18','XS','S','M','L','XL'],
        'campista': None,
    })


def editar_campista(request, campista_id):
    campista = get_object_or_404(Campista, id=campista_id)

    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        telefono = (request.POST.get('telefono') or '').strip()
        quiere_camisa = request.POST.get('quiere_camisa') == 'on'
        talla = request.POST.get('talla_camisa') if quiere_camisa else ''

        error = _validar_campista_data(nombre, telefono)
        if error:
            return render(request, 'agregar.html', {
                'error': error,
                'campista': campista,
                'nombre': nombre,
                'telefono': telefono,
                'quiere_camisa': quiere_camisa,
                'talla_camisa': talla,
                'edit': True,
                'tallas': ['4','6','8','10','12','14','16','18','XS','S','M','L','XL'],
            })

        campista.nombre = nombre
        campista.telefono = telefono
        campista.quiere_camisa = quiere_camisa
        campista.talla_camisa = talla
        campista.save()
        return redirect('lista_campistas')

    return render(request, 'agregar.html', {
        'campista': campista,
        'edit': True,
        'tallas': ['4','6','8','10','12','14','16','18','XS','S','M','L','XL'],
    })

def agregar_pago(request, campista_id):
    campista = get_object_or_404(Campista, id=campista_id)

    if campista.estado() == 'Cancelado':
        # Mensaje único en la plantilla (bloque "cancelado"), sin duplicar con {% if error %}
        return render(request, 'agregar_pago.html', {'campista': campista})

    if request.method == 'POST':
        monto = request.POST.get('monto')
        moneda = request.POST.get('moneda')

        # Normalizar monto según moneda y mantener valores enteros para NIO
        monto_decimal = Decimal(monto)
        if moneda == 'NIO':
            monto_decimal = monto_decimal.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        else:
            monto_decimal = monto_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Validar no pagar más del saldo pendiente
        if moneda == 'NIO':
            saldo_nio = campista.saldo_pendiente_nio()
            if monto_decimal > saldo_nio:
                return render(request, 'agregar_pago.html', {
                    'campista': campista,
                    'error': 'No puede pagar más de la deuda pendiente en NIO.'
                })
        else:
            saldo_usd = campista.saldo_pendiente()
            if monto_decimal > saldo_usd:
                return render(request, 'agregar_pago.html', {
                    'campista': campista,
                    'error': 'No puede pagar más de la deuda pendiente en USD.'
                })

        Pago.objects.create(
            campista=campista,
            monto=monto_decimal,
            moneda=moneda
        )

        return redirect('lista_campistas')

    return render(request, 'agregar_pago.html', {'campista': campista})


#ELIMINAR CAMPISTA
def eliminar_campista(request, campista_id):
    campista = get_object_or_404(Campista, id=campista_id)
    campista.delete()
    return redirect('lista_campistas')