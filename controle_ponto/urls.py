from django.urls import path
from . import views

app_name = 'controle_ponto'

urlpatterns = [
    path('', views.relogio_ponto, name='relogio'),
]