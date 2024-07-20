from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from .models import Renter


def index(request):
    renter_list = Renter.objects.order_by('last_name')
    template = loader.get_template('index.html')
    context = {
        'renter_list': renter_list
    }
    return HttpResponse(template.render(context, request))
