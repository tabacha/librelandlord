from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from datetime import date

from ..models import Renter


@login_required
def emergency_contacts(request):
    """Zeigt alle aktiven Mieter mit ihren Kontaktdaten für Notfälle."""
    today = date.today()

    # Aktive Mieter: noch nicht ausgezogen oder Auszugsdatum in der Zukunft
    renters = Renter.objects.filter(
        Q(move_out_date__isnull=True) | Q(move_out_date__gte=today)
    ).select_related('apartment').order_by(
        'apartment__street',
        'apartment__number',
        'last_name'
    )

    template = loader.get_template('emergency_contacts.html')
    context = {
        'renters': renters,
        'today': today,
    }
    return HttpResponse(template.render(context, request))
