from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date, timedelta
from typing import List, Dict, Optional


# Define a model representing apartments.


class Apartment(models.Model):
    number = models.CharField(
        max_length=10, verbose_name=_("Apartment Number"))
    name = models.CharField(max_length=30, verbose_name=_("Apartment Name"))
    street = models.CharField(max_length=30, verbose_name=_("Street"))
    postal_code = models.CharField(
        max_length=10, verbose_name=_("Postal Code"))
    city = models.CharField(max_length=30, verbose_name=_("City"))
    size_in_m2 = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name=_("Size in Square Meters"))

    def __str__(self):
        return f"{self.number} {self.name}"

    def get_renters_for_period(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Gibt eine lückenlose Liste aller Mieter-Perioden für diese Wohnung zurück.

        Args:
            start_date: Startdatum des Zeitraums
            end_date: Enddatum des Zeitraums

        Returns:
            Liste von Dictionaries mit:
            - 'start_date': Startdatum der Periode (date)
            - 'end_date': Enddatum der Periode (date)
            - 'renter_id': ID des Mieters oder None bei Leerstand
            - 'renter': Renter-Objekt oder None bei Leerstand

        Die Liste ist lückenlos - Leerstandszeiten werden mit renter_id=None aufgefüllt.
        """
        from .renter import Renter

        # Alle Mieter dieser Wohnung holen, die den Zeitraum überlappen
        renters = Renter.objects.filter(
            apartment=self,
            move_in_date__lte=end_date
        ).filter(
            Q(move_out_date__isnull=True) | Q(move_out_date__gte=start_date)
        ).order_by('move_in_date')

        periods = []
        current_date = start_date

        for renter in renters:
            # Effektives Einzugsdatum (nicht früher als start_date)
            renter_start = max(renter.move_in_date, start_date)

            # Effektives Auszugsdatum (nicht später als end_date)
            if renter.move_out_date:
                renter_end = min(renter.move_out_date, end_date)
            else:
                renter_end = end_date

            # Gibt es eine Lücke vor diesem Mieter?
            if current_date < renter_start:
                periods.append({
                    'start_date': current_date,
                    'end_date': renter_start,
                    'renter_id': None,
                    'renter': None
                })

            # Mieter-Periode hinzufügen
            if renter_start <= renter_end:
                periods.append({
                    'start_date': renter_start,
                    'end_date': renter_end,
                    'renter_id': renter.id,
                    'renter': renter
                })

                # Nächstes Startdatum ist der Tag des Auszuges
                current_date = renter_end

        # Gibt es eine Lücke am Ende?
        if current_date < end_date:
            periods.append({
                'start_date': current_date,
                'end_date': end_date,
                'renter_id': None,
                'renter': None
            })

        return periods
