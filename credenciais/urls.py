from django.urls import path
from . import views

urlpatterns = [
    path('', views.CredencialListView.as_view(), name='credencial_list'),
    path('novo/', views.CredencialCreateView.as_view(), name='credencial_create'),
    path('editar/<int:pk>/', views.CredencialUpdateView.as_view(), name='credencial_update'),
    path('excluir/<int:pk>/', views.CredencialDeleteView.as_view(), name='credencial_delete'),
]