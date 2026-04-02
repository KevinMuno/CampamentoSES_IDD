from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Campista, Pago

EXCHANGE_RATE = Decimal('36.67')


def _filtrar_campistas(search_name='', filter_talla='', filter_estado=''):
    campistas_qs = Campista.objects.all()

    if search_name:
        campistas_qs = campistas_qs.filter(nombre__icontains=search_name)

    if filter_talla:
        campistas_qs = campistas_qs.filter(talla_camisa=filter_talla)

    campistas = list(campistas_qs)
    if filter_estado:
        campistas = [c for c in campistas if c.estado() == filter_estado]

    return campistas


def _conteos_generales():
    tallas_counts = Campista.objects.filter(talla_camisa__isnull=False).exclude(talla_camisa='') \
        .values('talla_camisa').annotate(total=Count('id')).order_by('talla_camisa')

    estados = list(Campista.objects.all())
    estado_counts = {
        'Pendiente': sum(1 for c in estados if c.estado() == 'Pendiente'),
        'Abonando': sum(1 for c in estados if c.estado() == 'Abonando'),
        'Cancelado': sum(1 for c in estados if c.estado() == 'Cancelado'),
    }

    return tallas_counts, estado_counts


def lista_campistas(request):
    search_name = request.GET.get('nombre', '').strip()
    filter_talla = request.GET.get('talla_camisa', '')
    filter_estado = request.GET.get('estado', '')

    campistas = _filtrar_campistas(search_name, filter_talla, filter_estado)
    tallas_counts, estado_counts = _conteos_generales()

    return render(request, 'lista.html', {
        'campistas': campistas,
        'search_name': search_name,
        'filter_talla': filter_talla,
        'filter_estado': filter_estado,
        'tallas_counts': tallas_counts,
        'estado_counts': estado_counts,
    })


def campistas_data(request):
    search_name = request.GET.get('nombre', '').strip()
    filter_talla = request.GET.get('talla_camisa', '')
    filter_estado = request.GET.get('estado', '')
    page_number = request.GET.get('page', 1)

    campistas = _filtrar_campistas(search_name, filter_talla, filter_estado)
    paginator = Paginator(campistas, 8)
    page_obj = paginator.get_page(page_number)

    tallas_counts, estado_counts = _conteos_generales()

    campistas_data = []
    for c in page_obj.object_list:
        campistas_data.append({
            'id': c.id,
            'nombre': c.nombre,
            'telefono': c.telefono,
            'quiere_camisa': c.quiere_camisa,
            'talla_camisa': c.talla_camisa,
            'total': str(c.total()),
            'total_nio': str(c.total_nio()),
            'total_pagado_display': c.total_pagado_display(),
            'saldo_pendiente_display': c.saldo_pendiente_display(),
            'estado': c.estado(),
        })

    return JsonResponse({
        'campistas': campistas_data,
        'tallas_counts': list(tallas_counts),
        'estado_counts': estado_counts,
        'total_items': paginator.count,
        'num_pages': paginator.num_pages,
        'current_page': page_obj.number,
    })

def agregar_campista(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        telefono = request.POST.get('telefono')
        quiere_camisa = request.POST.get('quiere_camisa') == 'on'
        talla = request.POST.get('talla_camisa')
        

        Campista.objects.create(
            nombre=nombre,
            telefono=telefono,
            quiere_camisa=quiere_camisa,
            talla_camisa=talla
        )

        return redirect('lista_campistas')

    return render(request, 'agregar.html')

def agregar_pago(request, campista_id):
    campista = get_object_or_404(Campista, id=campista_id)

    if campista.estado() == 'Cancelado':
        # No permitir pagos si ya está cancelado
        return render(request, 'agregar_pago.html', {
            'campista': campista,
            'error': 'Este campista ya está cancelado y no se pueden registrar más pagos.'
        })

    if request.method == 'POST':
        monto = request.POST.get('monto')
        moneda = request.POST.get('moneda')

        # Normalizar monto según moneda y mantener valores enteros para NIO
        monto_decimal = Decimal(monto)
        if moneda == 'NIO':
            monto_decimal = monto_decimal.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        else:
            monto_decimal = monto_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

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