from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.db.models import Sum

EXCHANGE_RATE = Decimal('36.67')

class Campista(models.Model):

    ESTADO = (
        ('pendiente', 'Pendiente'),
        ('abonado', 'Abonado'),
        ('cancelado', 'Cancelado'),
    )

    TALLAS = (
        ('2', '2'),
        ('4', '4'),
        ('6', '6'),
        ('8', '8'),
        ('10', '10'),
        ('12', '12'),
        ('14', '14'),
        ('16', '16'),
        ('18', '18'),
        ('XS', 'XS'),
        ('S', 'S'),
        ('M', 'M'),
        ('L', 'L'),
        ('XL', 'XL'),
        ('XXL', 'XXL'),
    )

    nombre = models.CharField(max_length=200)
    telefono = models.CharField(max_length=20, blank=True)
    quiere_camisa = models.BooleanField(default=False)
    talla_camisa = models.CharField(max_length=5, choices=TALLAS, blank=True, null=True)
    subsidizado = models.BooleanField(
        default=False,
        help_text='Si es True: aparece como cancelado y sus pagos no suman al total recaudado.',
    )

    fecha_registro = models.DateTimeField(auto_now_add=True)

   # 🔥 precio base SIEMPRE en USD
    def total(self):
        return Decimal('30')

    def total_pagado(self):
        total = Decimal('0')

        for pago in self.pagos.all():
            total += pago.monto_en_usd()

        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def saldo_pendiente(self):
        saldo = self.total() - self.total_pagado()
        return saldo if saldo > 0 else Decimal('0.00')

    def total_nio(self):
        return (self.total() * EXCHANGE_RATE).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    def total_pagado_nio(self):
        return (self.total_pagado() * EXCHANGE_RATE).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    def saldo_pendiente_nio(self):
        return (self.saldo_pendiente() * EXCHANGE_RATE).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    def estado(self):
        if self.total_pagado() == 0:
            return "Pendiente"
        elif self.total_pagado() < self.total():
            return "Abonando"
        else:
            return "Cancelado"

    def ultima_moneda_pagada(self):
        ultimo_pago = self.pagos.order_by('-fecha').first()
        return ultimo_pago.moneda if ultimo_pago else 'USD'

    def total_pagado_display(self):
        if self.ultima_moneda_pagada() == 'NIO':
            return f"C$ {self.total_pagado_nio()}"
        return f"$ {self.total_pagado()}"

    def saldo_pendiente_display(self):
        if self.ultima_moneda_pagada() == 'NIO':
            return f"C$ {self.saldo_pendiente_nio()}"
        return f"$ {self.saldo_pendiente()}"


    def __str__(self):
        return self.nombre


class Pago(models.Model):

    MONEDA = (
        ('USD', 'Dólares'),
        ('NIO', 'Córdobas'),
    )
    
    campista = models.ForeignKey(Campista, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=8, decimal_places=2)
    moneda = models.CharField(max_length=3, choices=MONEDA)
    fecha = models.DateTimeField(auto_now_add=True)

    def monto_en_usd(self):
        if self.moneda == 'USD':
            return Decimal(self.monto)
        return (Decimal(self.monto) / EXCHANGE_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def monto_en_nio(self):
        if self.moneda == 'NIO':
            return Decimal(self.monto)
        return (Decimal(self.monto) * EXCHANGE_RATE).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    def __str__(self):
        return f"{self.campista.nombre} - {self.monto} {self.moneda}"

