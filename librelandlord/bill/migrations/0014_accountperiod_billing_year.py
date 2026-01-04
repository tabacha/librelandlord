from django.db import migrations, models
from django.core.validators import MinValueValidator, MaxValueValidator


def populate_billing_year(apps, schema_editor):
    """Setzt billing_year basierend auf dem end_date."""
    AccountPeriod = apps.get_model('bill', 'AccountPeriod')
    for period in AccountPeriod.objects.all():
        period.billing_year = period.end_date.year
        period.save(update_fields=['billing_year'])


def reverse_billing_year(apps, schema_editor):
    """Rückwärts-Migration - nichts zu tun, da Feld entfernt wird."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bill', '0013_alter_meterreading_meter_reading'),
    ]

    operations = [
        # Schritt 1: Feld mit null=True hinzufügen
        migrations.AddField(
            model_name='accountperiod',
            name='billing_year',
            field=models.PositiveIntegerField(
                null=True,
                verbose_name='Billing Year',
                validators=[MinValueValidator(2000), MaxValueValidator(2100)],
                help_text='The billing year for this account period (e.g., 2025)'
            ),
        ),
        # Schritt 2: Daten migrieren
        migrations.RunPython(populate_billing_year, reverse_billing_year),
        # Schritt 3: Feld auf NOT NULL setzen
        migrations.AlterField(
            model_name='accountperiod',
            name='billing_year',
            field=models.PositiveIntegerField(
                verbose_name='Billing Year',
                validators=[MinValueValidator(2000), MaxValueValidator(2100)],
                help_text='The billing year for this account period (e.g., 2025)'
            ),
        ),
    ]
