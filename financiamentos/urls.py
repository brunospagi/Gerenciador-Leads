from django.urls import path
from .views import KanbanView, FichaCreateView, FichaUpdateView, update_ficha_status

urlpatterns = [
    path('', KanbanView.as_view(), name='financiamentos_kanban'),
    path('nova/', FichaCreateView.as_view(), name='financiamentos_create'),
    path('editar/<int:pk>/', FichaUpdateView.as_view(), name='financiamentos_update'),
    path('api/update-status/', update_ficha_status, name='financiamentos_api_update'),
]