from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Sum
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date
from typing import List, NamedTuple, Dict, Optional
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def __str__(self):
    return f"{self.date} {self.text} {self.value}"


class AccountPeriod(models.Model):
    text = models.CharField(
        max_length=27, verbose_name=_("Account Period Name"))
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(verbose_name=_("End Date"))

    def __str__(self):
        return f"{self.text} {self.start_date} {self.end_date}"

    class CostCenterSummary(NamedTuple):
        """Zusammenfassung der Rechnungen pro CostCenter"""
        cost_center: 'CostCenter'
        bills: List['Bill']
        total_amount: Decimal
        bill_count: int
        date_range: Dict[str, date]  # {'earliest': date, 'latest': date}
        # Verbrauchsberechnung
        cost_center_calculation: Optional['CostCenter.CostCenterCalculation']

    class AccountPeriodCalculation(NamedTuple):
        """Vollständige Berechnung für eine AccountPeriod"""
        account_period: 'AccountPeriod'
        cost_center_summaries: List['CostCenterSummary']
        grand_total: Decimal
        total_bill_count: int
        cost_center_count: int

    def calculate_bills_by_cost_center(self) -> AccountPeriodCalculation:
        """
        Berechnet alle Rechnungen dieser AccountPeriod, gruppiert nach CostCenter.

        Findet alle Bills, die zu dieser AccountPeriod gehören, gruppiert sie nach
        CostCenter und summiert die Beträge auf.

        Returns:
            AccountPeriodCalculation mit allen Details der Berechnung
        """
        from .bill import Bill
        from .cost_center import CostCenter

        # Alle Bills für diese AccountPeriod holen
        bills = Bill.objects.filter(
            account_period=self
        ).select_related('cost_center').order_by('cost_center__text', 'bill_date')

        if not bills.exists():
            return self.AccountPeriodCalculation(
                account_period=self,
                cost_center_summaries=[],
                grand_total=Decimal('0.00'),
                total_bill_count=0,
                cost_center_count=0
            )

        # Nach CostCenter gruppieren
        cost_center_groups = {}
        for bill in bills:
            cost_center = bill.cost_center
            if cost_center not in cost_center_groups:
                cost_center_groups[cost_center] = []
            cost_center_groups[cost_center].append(bill)

        # Zusammenfassungen erstellen
        cost_center_summaries = []
        grand_total = Decimal('0.00')
        total_bill_count = 0

        for cost_center, cost_center_bills in cost_center_groups.items():
            # Summe für dieses CostCenter berechnen
            total_amount = sum(bill.value for bill in cost_center_bills)
            bill_count = len(cost_center_bills)

            # Datumsbereich ermitteln
            bill_dates = [bill.bill_date for bill in cost_center_bills]
            date_range = {
                'earliest': min(bill_dates),
                'latest': max(bill_dates)
            }

            # CostCenterCalculation berechnen (falls möglich)
            cost_center_calculation = None
            try:
                cost_center_calculation = cost_center.calculate_total_consumption(
                    start_date=self.start_date,
                    end_date=self.end_date
                )
            except Exception as e:
                # Falls die Berechnung fehlschlägt (z.B. keine Contributions),
                # loggen wir den Fehler und setzen None
                logger.warning(
                    "CostCenter calculation failed for %s (AccountPeriod: %s, %s-%s): %s",
                    cost_center.text,
                    self.text,
                    self.start_date,
                    self.end_date,
                    str(e)
                )
                cost_center_calculation = None

            # Summary erstellen
            summary = self.CostCenterSummary(
                cost_center=cost_center,
                bills=cost_center_bills,
                total_amount=Decimal(str(total_amount)),
                bill_count=bill_count,
                date_range=date_range,
                cost_center_calculation=cost_center_calculation
            )

            cost_center_summaries.append(summary)
            grand_total += Decimal(str(total_amount))
            total_bill_count += bill_count

        # Nach CostCenter-Text sortieren für konsistente Reihenfolge
        cost_center_summaries.sort(key=lambda x: x.cost_center.text)

        return self.AccountPeriodCalculation(
            account_period=self,
            cost_center_summaries=cost_center_summaries,
            grand_total=grand_total,
            total_bill_count=total_bill_count,
            cost_center_count=len(cost_center_summaries)
        )

    def get_cost_center_total(self, cost_center: 'CostCenter') -> Decimal:
        """
        Berechnet die Gesamtsumme aller Rechnungen für ein spezifisches CostCenter.

        Args:
            cost_center: Das CostCenter für das die Summe berechnet werden soll

        Returns:
            Gesamtsumme als Decimal
        """
        from .bill import Bill

        total = Bill.objects.filter(
            account_period=self,
            cost_center=cost_center
        ).aggregate(
            total=Sum('value')
        )['total']

        return Decimal(str(total)) if total else Decimal('0.00')

    def get_bills_in_date_range(self, start_date: date = None, end_date: date = None):
        """
        Holt alle Bills dieser AccountPeriod in einem bestimmten Datumsbereich.

        Args:
            start_date: Startdatum (optional, default: self.start_date)
            end_date: Enddatum (optional, default: self.end_date)

        Returns:
            QuerySet von Bills
        """
        from .bill import Bill

        if start_date is None:
            start_date = self.start_date
        if end_date is None:
            end_date = self.end_date

        return Bill.objects.filter(
            account_period=self,
            bill_date__gte=start_date,
            bill_date__lte=end_date
        ).select_related('cost_center').order_by('bill_date')
