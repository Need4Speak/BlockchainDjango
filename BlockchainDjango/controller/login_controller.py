#!/usr/bin/python3
# -*- coding: UTF-8 -*-

from django.shortcuts import render_to_response
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from BlockchainDjango.service.login_service import doctor_login


def log_page(request):
    return render_to_response('log_page.html')


@csrf_exempt
def login(request):
    if request.POST:
        doctor_id = request.POST['doctor_id']
        password = request.POST['password']

        result = doctor_login(doctor_id, password)

        if result:
            return render(request, 'login_success.html')
        else:
            return render(request, 'login_error.html')

