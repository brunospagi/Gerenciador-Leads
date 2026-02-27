from django.urls import path
from . import views

app_name = 'financeiro'

urlpatterns = [
    path('', views.TransacaoListView.as_view(), name='lista_transacoes'),
    path('nova/', views.TransacaoCreateView.as_view(), name='nova_transacao'),
    path('<int:pk>/editar/', views.TransacaoUpdateView.as_view(), name='editar_transacao'),
    path('<int:pk>/apagar/', views.TransacaoDeleteView.as_view(), name='apagar_transacao'),
    path('relatorio/', views.RelatorioDREView.as_view(), name='relatorio_dre'),
]