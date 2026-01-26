"""
View für die Steuerübersicht.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import decimal

from ...models import Bill, AccountPeriod, Renter
from .common import render_calculation_error, render_not_found_error


@login_required
@require_http_methods(["GET"])
def tax_overview(request, billing_year: int):
    """
    View für die Steuerübersicht: Zeigt alle Rechnungen eines Jahres und deren
    Verteilung auf Häuser, aufgeteilt nach steuerrelevant (normale Mieter) und
    nicht steuerrelevant (Owner Occupied).

    URL: /tax-overview/<year>/

    Returns:
        Gerenderte HTML-Seite mit Steuerübersicht
    """
    try:
        # Alle AccountPeriods für das Jahr holen
        account_periods = AccountPeriod.objects.filter(
            billing_year=billing_year
        ).order_by('start_date')

        if not account_periods.exists():
            return render_not_found_error(request, billing_year)

        # Struktur für die Ergebnisse:
        # {
        #   'house_key': {
        #       'street': str,
        #       'postal_code': str,
        #       'city': str,
        #       'bills': [
        #           {
        #               'bill': Bill,
        #               'tax_relevant': Decimal,  # Anteil für normale Mieter
        #               'owner_occupied': Decimal,  # Anteil für Eigentümer
        #               'percentage_tax': float,
        #               'percentage_owner': float,
        #           }
        #       ],
        #       'total_tax_relevant': Decimal,
        #       'total_owner_occupied': Decimal,
        #   }
        # }
        houses = {}
        # Struktur für Leerstandsdetails:
        # {vacancy_key: {apartment_name, period_start, period_end, bills: [...], total}}
        vacancies = {}

        # Alle Bills für die AccountPeriods holen (nur die für Steuerübersicht markierten)
        all_bills = Bill.objects.filter(
            account_period__in=account_periods,
            show_in_tax_overview=True
        ).select_related('cost_center', 'account_period').order_by('bill_date')

        for bill in all_bills:
            cost_center = bill.cost_center

            # CostCenter-Berechnung durchführen
            try:
                calculation = cost_center.calculate_total_consumption(
                    start_date=bill.account_period.start_date,
                    end_date=bill.account_period.end_date,
                    bills=[bill] if cost_center.distribution_type == 'DIRECT' else None
                )
            except ValueError:
                # Bei Berechnungsfehlern (z.B. Leerstand bei DIRECT) überspringen
                continue

            if not calculation.contribution_results:
                continue

            # Für jede Contribution (Wohnung) den Anteil berechnen
            for contrib_result in calculation.contribution_results:
                contribution = contrib_result.contribution
                if not contribution.apartment:
                    continue

                apartment = contribution.apartment
                house_key = f"{apartment.street}|{apartment.postal_code}"

                if house_key not in houses:
                    houses[house_key] = {
                        'street': apartment.street,
                        'postal_code': apartment.postal_code,
                        'city': apartment.city,
                        'bills': {},  # bill_id -> bill_data
                        'total_tax_relevant': decimal.Decimal('0.00'),
                        'total_owner_occupied': decimal.Decimal('0.00'),
                        'total_vacancy': decimal.Decimal('0.00'),
                    }

                # Anteil berechnen
                percentage = contrib_result.percentage
                euro_anteil = decimal.Decimal(str((percentage / 100) * float(bill.value)))

                # Prüfen ob Owner Occupied oder Leerstand
                renter_id = contrib_result.renter_id
                is_owner_occupied = False
                is_vacancy = False

                if renter_id:
                    try:
                        renter = Renter.objects.get(id=renter_id)
                        is_owner_occupied = renter.is_owner_occupied
                    except Renter.DoesNotExist:
                        pass
                else:
                    # Kein Mieter = Leerstand
                    is_vacancy = True

                # Bill in der House-Struktur speichern/aktualisieren
                bill_id = bill.id
                if bill_id not in houses[house_key]['bills']:
                    houses[house_key]['bills'][bill_id] = {
                        'bill': bill,
                        'tax_relevant': decimal.Decimal('0.00'),
                        'owner_occupied': decimal.Decimal('0.00'),
                        'vacancy': decimal.Decimal('0.00'),
                        'percentage_tax': 0.0,
                        'percentage_owner': 0.0,
                        'percentage_vacancy': 0.0,
                    }

                if is_vacancy:
                    houses[house_key]['bills'][bill_id]['vacancy'] += euro_anteil
                    houses[house_key]['bills'][bill_id]['percentage_vacancy'] += percentage
                    houses[house_key]['total_vacancy'] += euro_anteil

                    # Leerstandsdetails sammeln
                    vacancy_key = f"{apartment.id}|{contrib_result.period_start}|{contrib_result.period_end}"
                    if vacancy_key not in vacancies:
                        vacancies[vacancy_key] = {
                            'apartment_name': apartment.name,
                            'apartment_street': apartment.street,
                            'apartment_postal_code': apartment.postal_code,
                            'period_start': contrib_result.period_start,
                            'period_end': contrib_result.period_end,
                            'bills': {},
                            'total_tax_relevant': decimal.Decimal('0.00'),
                            'total_not_tax_relevant': decimal.Decimal('0.00'),
                        }
                    if bill_id not in vacancies[vacancy_key]['bills']:
                        vacancies[vacancy_key]['bills'][bill_id] = {
                            'bill': bill,
                            'amount': decimal.Decimal('0.00'),
                            'percentage': 0.0,
                            'is_tax_relevant': True,
                        }
                    vacancies[vacancy_key]['bills'][bill_id]['amount'] += euro_anteil
                    vacancies[vacancy_key]['bills'][bill_id]['percentage'] += percentage
                    vacancies[vacancy_key]['total_tax_relevant'] += euro_anteil

                elif is_owner_occupied:
                    houses[house_key]['bills'][bill_id]['owner_occupied'] += euro_anteil
                    houses[house_key]['bills'][bill_id]['percentage_owner'] += percentage
                    houses[house_key]['total_owner_occupied'] += euro_anteil
                else:
                    houses[house_key]['bills'][bill_id]['tax_relevant'] += euro_anteil
                    houses[house_key]['bills'][bill_id]['percentage_tax'] += percentage
                    houses[house_key]['total_tax_relevant'] += euro_anteil

        # Konvertiere bills dict zu Liste und sortiere
        for house_key in houses:
            bills_list = list(houses[house_key]['bills'].values())
            bills_list.sort(key=lambda x: x['bill'].bill_date)
            houses[house_key]['bills'] = bills_list

        # Für jeden Leerstand auch die nicht steuerrelevanten Bills hinzufügen (ausgegraut)
        # Hole alle Bills (auch show_in_tax_overview=False)
        all_bills_including_hidden = Bill.objects.filter(
            account_period__in=account_periods
        ).select_related('cost_center', 'account_period').order_by('bill_date')

        for vacancy_key, vacancy_data in vacancies.items():
            apartment_id = int(vacancy_key.split('|')[0])
            period_start = vacancy_data['period_start']
            period_end = vacancy_data['period_end']

            for bill in all_bills_including_hidden:
                # Nur Bills die nicht schon erfasst sind
                if bill.id in vacancy_data['bills']:
                    continue

                cost_center = bill.cost_center

                # Prüfen ob diese Bill für diese Wohnung relevant ist
                try:
                    calculation = cost_center.calculate_total_consumption(
                        start_date=bill.account_period.start_date,
                        end_date=bill.account_period.end_date,
                        bills=[bill] if cost_center.distribution_type == 'DIRECT' else None
                    )
                except ValueError:
                    continue

                if not calculation.contribution_results:
                    continue

                for contrib_result in calculation.contribution_results:
                    contribution = contrib_result.contribution
                    if not contribution.apartment or contribution.apartment.id != apartment_id:
                        continue

                    # Prüfen ob der Zeitraum übereinstimmt (Leerstand)
                    if contrib_result.renter_id is not None:
                        continue
                    if contrib_result.period_start != period_start or contrib_result.period_end != period_end:
                        continue

                    # Bill hinzufügen (als nicht steuerrelevant wenn show_in_tax_overview=False)
                    percentage = contrib_result.percentage
                    euro_anteil = decimal.Decimal(str((percentage / 100) * float(bill.value)))

                    vacancy_data['bills'][bill.id] = {
                        'bill': bill,
                        'amount': euro_anteil,
                        'percentage': percentage,
                        'is_tax_relevant': bill.show_in_tax_overview,
                    }
                    if bill.show_in_tax_overview:
                        vacancy_data['total_tax_relevant'] += euro_anteil
                    else:
                        vacancy_data['total_not_tax_relevant'] += euro_anteil

        # Konvertiere vacancy bills dict zu Liste und sortiere
        for vacancy_key in vacancies:
            bills_list = list(vacancies[vacancy_key]['bills'].values())
            bills_list.sort(key=lambda x: x['bill'].bill_date)
            vacancies[vacancy_key]['bills'] = bills_list

        # Leerstände nach Wohnung und Startdatum sortieren
        sorted_vacancies = sorted(
            vacancies.values(),
            key=lambda v: (v['apartment_street'], v['apartment_name'], v['period_start'])
        )

        # Häuser nach Straße sortieren
        sorted_houses = sorted(houses.values(), key=lambda h: (h['street'], h['postal_code']))

        # Gesamtsummen berechnen
        grand_total_tax = sum(h['total_tax_relevant'] for h in sorted_houses)
        grand_total_owner = sum(h['total_owner_occupied'] for h in sorted_houses)
        grand_total_vacancy = sum(h['total_vacancy'] for h in sorted_houses)
        grand_total = grand_total_tax + grand_total_owner + grand_total_vacancy

        context = {
            'billing_year': billing_year,
            'houses': sorted_houses,
            'vacancies': sorted_vacancies,
            'grand_total_tax_relevant': grand_total_tax,
            'grand_total_owner_occupied': grand_total_owner,
            'grand_total_vacancy': grand_total_vacancy,
            'grand_total': grand_total,
        }

        return render(request, 'tax_overview.html', context)

    except Exception as e:
        return render_calculation_error(request, billing_year, e)
