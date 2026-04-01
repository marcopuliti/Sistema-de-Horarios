from django.urls import path
from . import views

urlpatterns = [
    # Públicas
    path('', views.home, name='home'),
    path('carrera/<int:pk>/', views.carrera_detail, name='carrera_detail'),

    # Panel dashboard
    path('panel/', views.panel_dashboard, name='panel_dashboard'),

    # Horarios: lista de materias + edición por materia
    path('panel/horarios/', views.horario_materia_list, name='horario_materia_list'),
    path('panel/horarios/materia/<int:materia_pk>/', views.horario_editar, name='horario_editar'),
    path('panel/horarios/materia/<int:materia_pk>/eliminar/', views.horario_eliminar, name='horario_eliminar'),

    # Carreras (solo admin)
    path('panel/carreras/', views.carrera_list_panel, name='carrera_list_panel'),
    path('panel/carreras/nueva/', views.carrera_create, name='carrera_create'),
    path('panel/carreras/<int:pk>/editar/', views.carrera_edit, name='carrera_edit'),
    path('panel/carreras/<int:pk>/eliminar/', views.carrera_delete, name='carrera_delete'),

    # Materias (solo admin)
    path('panel/materias/', views.materia_list_panel, name='materia_list_panel'),
    path('panel/materias/nueva/', views.materia_create, name='materia_create'),
    path('panel/materias/<int:pk>/editar/', views.materia_edit, name='materia_edit'),
    path('panel/materias/<int:pk>/eliminar/', views.materia_delete, name='materia_delete'),

    # Asignaciones (admin + manager)
    path('panel/asignaciones/', views.asignacion_list, name='asignacion_list'),
    path('panel/asignaciones/nueva/', views.asignacion_create, name='asignacion_create'),
    path('panel/asignaciones/<int:pk>/eliminar/', views.asignacion_delete, name='asignacion_delete'),

    # Usuarios editores (admin + manager)
    path('panel/usuarios/', views.usuario_list, name='usuario_list'),
    path('panel/usuarios/nuevo/', views.usuario_create, name='usuario_create'),
    path('panel/usuarios/<int:pk>/editar/', views.usuario_edit, name='usuario_edit'),
    path('panel/usuarios/<int:pk>/eliminar/', views.usuario_delete, name='usuario_delete'),
]
