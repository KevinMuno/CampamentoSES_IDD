from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campamento', '0002_remove_campista_estado_remove_campista_moneda_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='campista',
            name='subsidizado',
            field=models.BooleanField(
                default=False,
                help_text='Si es True: aparece como cancelado y sus pagos no suman al total recaudado.',
            ),
        ),
    ]
