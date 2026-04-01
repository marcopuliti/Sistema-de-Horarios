from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.contrib.auth.models import User
from django.db.models import Count, Prefetch

from .models import Carrera, Materia, Horario, HorarioBloque, MateriaAsignacion
from .forms import (
    CarreraForm, MateriaForm, HorarioForm, HorarioBloqueFormSet,
    MateriaAsignacionForm, HorarioFiltroForm,
    UsuarioCrearForm, UsuarioEditarForm,
)
from .decorators import (
    admin_required, editor_or_admin_required, manager_or_admin_required,
    is_admin, is_manager_or_admin,
)

DIA_ORDER = {d: i for i, (d, _) in enumerate(HorarioBloque.DIA_CHOICES)}


# ─── Vistas públicas ──────────────────────────────────────────────────────────

def home(request):
    carreras = Carrera.objects.annotate(n_materias=Count('materias'))
    return render(request, 'horarios/home.html', {'carreras': carreras})


_CAL_PX_PER_HOUR = 80
_CAL_COLORS = [
    'cal-blue', 'cal-green', 'cal-red', 'cal-orange',
    'cal-purple', 'cal-teal', 'cal-pink', 'cal-indigo',
]
_DIA_DISPLAY = dict(HorarioBloque.DIA_CHOICES)


def carrera_detail(request, pk):
    carrera = get_object_or_404(Carrera, pk=pk)
    ano = int(request.GET.get('ano', 1))
    cuatrimestre = int(request.GET.get('cuatrimestre', 1))
    ano = max(1, min(ano, carrera.duracion_anos))
    cuatrimestre = max(1, min(cuatrimestre, 2))

    ano_range = range(1, carrera.duracion_anos + 1)

    # Incluir anuales (cuatrimestre=3) en ambas vistas
    horarios = (
        Horario.objects
        .filter(
            materia__carrera=carrera,
            materia__ano=ano,
            materia__cuatrimestre__in=[cuatrimestre, 3],
        )
        .select_related('materia')
        .prefetch_related('bloques')
    )

    bloques_por_dia = {}
    for h in horarios:
        for bloque in h.bloques.all():
            entry = {
                'materia': h.materia.nombre,
                'docente': h.docente,
                'aula': bloque.aula,
                'primer_dia': h.primer_dia_actividades,
                'hora_inicio': bloque.hora_inicio,
                'hora_fin': bloque.hora_fin,
            }
            bloques_por_dia.setdefault(bloque.dia_semana, []).append(entry)

    dias_ordenados = sorted(bloques_por_dia.keys(), key=lambda d: DIA_ORDER.get(d, 99))
    for dia in dias_ordenados:
        bloques_por_dia[dia].sort(key=lambda b: b['hora_inicio'])

    # Calcular posiciones para la grilla calendario
    all_blocks = [b for blocks in bloques_por_dia.values() for b in blocks]

    if all_blocks:
        min_min = min(b['hora_inicio'].hour * 60 + b['hora_inicio'].minute for b in all_blocks)
        max_min = max(b['hora_fin'].hour * 60 + b['hora_fin'].minute for b in all_blocks)
        min_min = (min_min // 60) * 60        # piso a la hora
        max_min = ((max_min + 59) // 60) * 60  # techo a la hora

        total_height = (max_min - min_min) * _CAL_PX_PER_HOUR // 60

        time_labels = [
            {'label': f"{h:02d}:00", 'top': (h * 60 - min_min) * _CAL_PX_PER_HOUR // 60}
            for h in range(min_min // 60, max_min // 60 + 1)
        ]

        # Asignar color por materia (consistente entre días)
        materias_unicas = sorted({b['materia'] for b in all_blocks})
        color_map = {m: _CAL_COLORS[i % len(_CAL_COLORS)] for i, m in enumerate(materias_unicas)}

        for blocks in bloques_por_dia.values():
            for b in blocks:
                start_m = b['hora_inicio'].hour * 60 + b['hora_inicio'].minute
                end_m   = b['hora_fin'].hour * 60 + b['hora_fin'].minute
                b['top']    = (start_m - min_min) * _CAL_PX_PER_HOUR // 60
                b['height'] = max(28, (end_m - start_m) * _CAL_PX_PER_HOUR // 60)
                b['color']  = color_map[b['materia']]
    else:
        total_height = 0
        time_labels = []

    # Siempre mostrar todos los días de la semana, tengan bloques o no
    todos_los_dias = [dia for dia, _ in HorarioBloque.DIA_CHOICES]
    horarios_agrupados = [
        {
            'dia': dia,
            'dia_display': _DIA_DISPLAY[dia],
            'bloques': bloques_por_dia.get(dia, []),
        }
        for dia in todos_los_dias
    ]

    return render(request, 'horarios/carrera_detail.html', {
        'carrera': carrera,
        'ano': ano,
        'cuatrimestre': cuatrimestre,
        'ano_range': ano_range,
        'horarios_agrupados': horarios_agrupados,
        'time_labels': time_labels,
        'total_height': total_height,
    })


# ─── Panel dashboard ──────────────────────────────────────────────────────────

@editor_or_admin_required
def panel_dashboard(request):
    user = request.user
    if is_admin(user):
        context = {
            'total_carreras': Carrera.objects.count(),
            'total_materias': Materia.objects.count(),
            'total_horarios': Horario.objects.count(),
            'total_usuarios': User.objects.count(),
            'is_admin_user': True,
            'is_manager_user': False,
        }
    elif is_manager_or_admin(user):
        from django.contrib.auth.models import Group
        editor_group = Group.objects.filter(name='editor').first()
        total_editores = User.objects.filter(groups=editor_group).count() if editor_group else 0
        context = {
            'total_editores': total_editores,
            'total_asignaciones': MateriaAsignacion.objects.count(),
            'is_admin_user': False,
            'is_manager_user': True,
        }
    else:
        asignaciones = MateriaAsignacion.objects.filter(
            usuario=user
        ).select_related('materia__carrera')
        context = {
            'asignaciones': asignaciones,
            'total_horarios': Horario.objects.filter(
                materia__asignaciones__usuario=user
            ).count(),
            'is_admin_user': False,
            'is_manager_user': False,
        }
    return render(request, 'horarios/admin_panel/dashboard.html', context)


# ─── Horarios: lista de materias con su estado ───────────────────────────────

@editor_or_admin_required
def horario_materia_list(request):
    """Lista de materias filtrada por carrera/año/cuatrimestre para gestionar horarios."""
    user = request.user
    filtro = HorarioFiltroForm(request.GET or None)

    materias = None
    carrera_sel = None

    if filtro.is_valid():
        carrera_sel = filtro.cleaned_data.get('carrera')
        ano = filtro.cleaned_data.get('ano')
        cuatrimestre = filtro.cleaned_data.get('cuatrimestre')

        if carrera_sel:
            qs = Materia.objects.filter(carrera=carrera_sel).select_related('carrera')

            if not is_admin(user):
                ids_asignados = MateriaAsignacion.objects.filter(
                    usuario=user
                ).values_list('materia_id', flat=True)
                qs = qs.filter(id__in=ids_asignados)

            if ano:
                qs = qs.filter(ano=ano)
            if cuatrimestre:
                qs = qs.filter(cuatrimestre=cuatrimestre)

            # Anotar si cada materia tiene horario
            qs = qs.prefetch_related(
                Prefetch('horario', queryset=Horario.objects.prefetch_related('bloques'))
            )
            materias = qs.order_by('ano', 'cuatrimestre', 'nombre')

    return render(request, 'horarios/admin_panel/horario/materia_list.html', {
        'filtro': filtro,
        'materias': materias,
        'carrera_sel': carrera_sel,
        'is_admin_user': is_admin(user),
    })


# ─── Editar/crear horario de una materia ─────────────────────────────────────

@editor_or_admin_required
def horario_editar(request, materia_pk):
    materia = get_object_or_404(Materia.objects.select_related('carrera'), pk=materia_pk)
    user = request.user

    if not is_admin(user):
        if not MateriaAsignacion.objects.filter(usuario=user, materia=materia).exists():
            return HttpResponseForbidden("No tenés permisos para editar el horario de esta materia.")

    # Obtener o crear el Horario de esta materia
    horario = getattr(materia, 'horario', None)

    if request.method == 'POST':
        form = HorarioForm(request.POST, instance=horario)
        formset = HorarioBloqueFormSet(request.POST, instance=horario or Horario())

        if form.is_valid():
            horario_obj = form.save(commit=False)
            horario_obj.materia = materia
            horario_obj.save()

            formset = HorarioBloqueFormSet(request.POST, instance=horario_obj)
            if formset.is_valid():
                formset.save()
                messages.success(request, f'Horario de {materia.nombre} guardado.')
                url = reverse('horario_materia_list')
                return redirect(
                    f"{url}?carrera={materia.carrera_id}"
                    f"&ano={materia.ano}&cuatrimestre={materia.cuatrimestre}"
                )
    else:
        form = HorarioForm(instance=horario)
        formset = HorarioBloqueFormSet(instance=horario or Horario())

    return render(request, 'horarios/admin_panel/horario/form.html', {
        'materia': materia,
        'form': form,
        'formset': formset,
        'horario': horario,
    })


@editor_or_admin_required
def horario_eliminar(request, materia_pk):
    materia = get_object_or_404(Materia.objects.select_related('carrera'), pk=materia_pk)
    user = request.user

    if not is_admin(user):
        if not MateriaAsignacion.objects.filter(usuario=user, materia=materia).exists():
            return HttpResponseForbidden("No tenés permisos.")

    horario = getattr(materia, 'horario', None)
    if not horario:
        messages.warning(request, 'Esta materia no tiene horario cargado.')
        return redirect('horario_materia_list')

    if request.method == 'POST':
        horario.delete()
        messages.success(request, f'Horario de {materia.nombre} eliminado.')
        return redirect('horario_materia_list')

    return render(request, 'horarios/admin_panel/horario/confirm_delete.html', {
        'materia': materia,
        'horario': horario,
    })


# ─── Carreras (solo admin) ────────────────────────────────────────────────────

@admin_required
def carrera_list_panel(request):
    carreras = Carrera.objects.annotate(
        n_materias=Count('materias'),
        n_horarios=Count('materias__horario'),
    )
    return render(request, 'horarios/admin_panel/carrera/list.html', {'carreras': carreras})


@admin_required
def carrera_create(request):
    form = CarreraForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Carrera creada correctamente.')
        return redirect('carrera_list_panel')
    return render(request, 'horarios/admin_panel/carrera/form.html', {
        'form': form, 'titulo': 'Nueva Carrera'
    })


@admin_required
def carrera_edit(request, pk):
    carrera = get_object_or_404(Carrera, pk=pk)
    form = CarreraForm(request.POST or None, instance=carrera)
    if form.is_valid():
        form.save()
        messages.success(request, 'Carrera actualizada.')
        return redirect('carrera_list_panel')
    return render(request, 'horarios/admin_panel/carrera/form.html', {
        'form': form, 'titulo': 'Editar Carrera', 'object': carrera
    })


@admin_required
def carrera_delete(request, pk):
    carrera = get_object_or_404(Carrera, pk=pk)
    if request.method == 'POST':
        carrera.delete()
        messages.success(request, 'Carrera eliminada.')
        return redirect('carrera_list_panel')
    n_materias = carrera.materias.count()
    n_horarios = Horario.objects.filter(materia__carrera=carrera).count()
    return render(request, 'horarios/admin_panel/carrera/confirm_delete.html', {
        'object': carrera, 'n_materias': n_materias, 'n_horarios': n_horarios
    })


# ─── Materias (solo admin) ────────────────────────────────────────────────────

@admin_required
def materia_list_panel(request):
    carrera_id = request.GET.get('carrera')
    carreras = Carrera.objects.all()
    materias = Materia.objects.select_related('carrera')
    if carrera_id:
        materias = materias.filter(carrera_id=carrera_id)
    return render(request, 'horarios/admin_panel/materia/list.html', {
        'materias': materias,
        'carreras': carreras,
        'carrera_id_selected': carrera_id,
    })


@admin_required
def materia_create(request):
    form = MateriaForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Materia creada correctamente.')
        return redirect('materia_list_panel')
    return render(request, 'horarios/admin_panel/materia/form.html', {
        'form': form, 'titulo': 'Nueva Materia'
    })


@admin_required
def materia_edit(request, pk):
    materia = get_object_or_404(Materia, pk=pk)
    form = MateriaForm(request.POST or None, instance=materia)
    if form.is_valid():
        form.save()
        messages.success(request, 'Materia actualizada.')
        return redirect('materia_list_panel')
    return render(request, 'horarios/admin_panel/materia/form.html', {
        'form': form, 'titulo': 'Editar Materia', 'object': materia
    })


@admin_required
def materia_delete(request, pk):
    materia = get_object_or_404(Materia, pk=pk)
    if request.method == 'POST':
        materia.delete()
        messages.success(request, 'Materia eliminada.')
        return redirect('materia_list_panel')
    try:
        n_bloques = materia.horario.bloques.count()
    except Horario.DoesNotExist:
        n_bloques = 0
    return render(request, 'horarios/admin_panel/materia/confirm_delete.html', {
        'object': materia, 'n_horarios': n_bloques
    })


# ─── Asignaciones (admin + manager) ──────────────────────────────────────────

@manager_or_admin_required
def asignacion_list(request):
    asignaciones = MateriaAsignacion.objects.select_related(
        'usuario', 'materia__carrera'
    ).order_by('usuario__username', 'materia__carrera__nombre', 'materia__ano')
    return render(request, 'horarios/admin_panel/asignacion/list.html', {
        'asignaciones': asignaciones
    })


@manager_or_admin_required
def asignacion_create(request):
    form = MateriaAsignacionForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Asignación creada.')
        return redirect('asignacion_list')
    return render(request, 'horarios/admin_panel/asignacion/form.html', {
        'form': form, 'titulo': 'Nueva Asignación'
    })


@manager_or_admin_required
def asignacion_delete(request, pk):
    asignacion = get_object_or_404(MateriaAsignacion, pk=pk)
    if request.method == 'POST':
        asignacion.delete()
        messages.success(request, 'Asignación eliminada.')
        return redirect('asignacion_list')
    return render(request, 'horarios/admin_panel/asignacion/confirm_delete.html', {
        'object': asignacion
    })


# ─── Usuarios editores (admin + manager) ─────────────────────────────────────

@manager_or_admin_required
def usuario_list(request):
    from django.contrib.auth.models import Group
    editor_group = Group.objects.filter(name='editor').first()
    if is_admin(request.user):
        usuarios = User.objects.prefetch_related('groups').order_by('username')
    else:
        usuarios = User.objects.filter(
            groups=editor_group
        ).prefetch_related('groups').order_by('username')
    return render(request, 'horarios/admin_panel/usuario/list.html', {
        'usuarios': usuarios,
    })


def _materias_por_carrera():
    """Devuelve lista de (carrera, [materias]) ordenada para el checklist."""
    from itertools import groupby
    qs = Materia.objects.select_related('carrera').order_by(
        'carrera__nombre', 'ano', 'cuatrimestre', 'nombre'
    )
    resultado = []
    for carrera, mats in groupby(qs, key=lambda m: m.carrera):
        resultado.append((carrera, list(mats)))
    return resultado


def _guardar_asignaciones(usuario, materia_ids):
    MateriaAsignacion.objects.filter(usuario=usuario).delete()
    if materia_ids:
        MateriaAsignacion.objects.bulk_create([
            MateriaAsignacion(usuario=usuario, materia_id=mid)
            for mid in materia_ids
        ])


@manager_or_admin_required
def usuario_create(request):
    creator_is_admin = is_admin(request.user)
    form = UsuarioCrearForm(request.POST or None, creator_is_admin=creator_is_admin)
    if form.is_valid():
        user = form.save()
        materia_ids = [int(x) for x in request.POST.getlist('materias')]
        _guardar_asignaciones(user, materia_ids)
        messages.success(request, f'Usuario "{user.username}" creado correctamente.')
        return redirect('usuario_list')
    return render(request, 'horarios/admin_panel/usuario/form.html', {
        'form': form,
        'titulo': 'Nuevo usuario',
        'carreras_materias': _materias_por_carrera(),
        'asignadas_ids': set(int(x) for x in request.POST.getlist('materias')),
    })


@manager_or_admin_required
def usuario_edit(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if not is_admin(request.user) and is_admin(usuario):
        return HttpResponseForbidden("No podés editar un administrador.")
    creator_is_admin = is_admin(request.user)
    form = UsuarioEditarForm(request.POST or None, instance=usuario, creator_is_admin=creator_is_admin)
    if form.is_valid():
        form.save()
        materia_ids = [int(x) for x in request.POST.getlist('materias')]
        _guardar_asignaciones(usuario, materia_ids)
        messages.success(request, 'Usuario actualizado.')
        return redirect('usuario_list')
    # Para el GET, cargar las asignaciones actuales
    if request.method == 'GET':
        asignadas_ids = set(
            MateriaAsignacion.objects.filter(usuario=usuario).values_list('materia_id', flat=True)
        )
    else:
        asignadas_ids = set(int(x) for x in request.POST.getlist('materias'))
    return render(request, 'horarios/admin_panel/usuario/form.html', {
        'form': form,
        'titulo': f'Editar usuario: {usuario.username}',
        'object': usuario,
        'carreras_materias': _materias_por_carrera(),
        'asignadas_ids': asignadas_ids,
    })


@manager_or_admin_required
def usuario_delete(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if not is_admin(request.user) and is_admin(usuario):
        return HttpResponseForbidden("No podés eliminar un administrador.")
    if request.method == 'POST':
        usuario.delete()
        messages.success(request, 'Usuario eliminado.')
        return redirect('usuario_list')
    n_asignaciones = MateriaAsignacion.objects.filter(usuario=usuario).count()
    return render(request, 'horarios/admin_panel/usuario/confirm_delete.html', {
        'object': usuario, 'n_asignaciones': n_asignaciones,
    })
