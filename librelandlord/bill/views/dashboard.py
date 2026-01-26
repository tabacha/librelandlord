from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from datetime import datetime, date

from ..models import Apartment, Renter, Meter, CostCenter, AccountPeriod


@login_required
def dashboard_stats_api(request):
    """API-Endpunkt für Dashboard-Statistiken (JSON)"""
    stats = {
        'apartments': Apartment.objects.count(),
        'active_renters': Renter.objects.filter(move_out_date__isnull=True).count(),
        'meters': Meter.objects.filter(out_of_order_date__isnull=True).count(),
        'cost_centers': CostCenter.objects.count(),
    }

    def get_active_renters_for_year(year):
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        return Renter.objects.filter(
            move_in_date__lte=year_end
        ).filter(
            Q(move_out_date__isnull=True) |
            Q(move_out_date__gte=year_start)
        ).select_related('apartment').order_by('apartment__number', 'last_name')

    current_year = datetime.now().year
    available_years = []
    for year in range(current_year, current_year - 4, -1):
        if AccountPeriod.objects.filter(billing_year=year).exists():
            renters = get_active_renters_for_year(year)
            available_years.append({
                'year': year,
                'renters': [
                    {'id': r.id, 'name': f"{r.first_name} {r.last_name}",
                        'apartment_number': r.apartment.number}
                    for r in renters
                ]
            })
        if len(available_years) >= 3:
            break

    return JsonResponse({
        **stats,
        'available_years': available_years,
    })
