from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from .models import Carrera, Materia, Horario, HorarioBloque, MateriaAsignacion


BS_INPUT = {'class': 'form-control'}
BS_SELECT = {'class': 'form-select'}


class CarreraForm(forms.ModelForm):
    class Meta:
        model = Carrera
        fields = ['nombre', 'codigo', 'duracion_anos']
        widgets = {
            'nombre': forms.TextInput(attrs=BS_INPUT),
            'codigo': forms.TextInput(attrs=BS_INPUT),
            'duracion_anos': forms.Select(attrs=BS_SELECT),
        }


class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = ['carrera', 'nombre', 'codigo', 'ano', 'cuatrimestre']
        widgets = {
            'carrera': forms.Select(attrs=BS_SELECT),
            'nombre': forms.TextInput(attrs=BS_INPUT),
            'codigo': forms.TextInput(attrs=BS_INPUT),
            'ano': forms.Select(attrs=BS_SELECT),
            'cuatrimestre': forms.Select(attrs=BS_SELECT),
        }


class HorarioForm(forms.ModelForm):
    class Meta:
        model = Horario
        fields = ['docente', 'primer_dia_actividades']
        widgets = {
            'docente': forms.TextInput(attrs=BS_INPUT),
            'primer_dia_actividades': forms.DateInput(attrs={**BS_INPUT, 'type': 'date'}),
        }


class HorarioBloqueForm(forms.ModelForm):
    class Meta:
        model = HorarioBloque
        fields = ['dia_semana', 'hora_inicio', 'hora_fin', 'aula']
        widgets = {
            'dia_semana': forms.Select(attrs=BS_SELECT),
            'hora_inicio': forms.TimeInput(attrs={**BS_INPUT, 'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={**BS_INPUT, 'type': 'time'}),
            'aula': forms.TextInput(attrs=BS_INPUT),
        }


HorarioBloqueFormSet = inlineformset_factory(
    Horario,
    HorarioBloque,
    form=HorarioBloqueForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class MateriaAsignacionForm(forms.ModelForm):
    class Meta:
        model = MateriaAsignacion
        fields = ['usuario', 'materia']
        widgets = {
            'usuario': forms.Select(attrs=BS_SELECT),
            'materia': forms.Select(attrs=BS_SELECT),
        }


ROL_CHOICES_ADMIN   = [('editor', 'Editor'), ('manager', 'Manager')]
ROL_CHOICES_MANAGER = [('editor', 'Editor')]


class UsuarioCrearForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs=BS_INPUT),
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs=BS_INPUT),
    )
    rol = forms.ChoiceField(
        label='Rol',
        choices=ROL_CHOICES_ADMIN,
        widget=forms.Select(attrs=BS_SELECT),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username':   forms.TextInput(attrs=BS_INPUT),
            'first_name': forms.TextInput(attrs=BS_INPUT),
            'last_name':  forms.TextInput(attrs=BS_INPUT),
            'email':      forms.EmailInput(attrs=BS_INPUT),
        }

    def __init__(self, *args, creator_is_admin=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not creator_is_admin:
            self.fields['rol'].choices = ROL_CHOICES_MANAGER
            self.fields['rol'].initial = 'editor'

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            from django.contrib.auth.models import Group
            user.groups.add(Group.objects.get(name=self.cleaned_data['rol']))
        return user


class UsuarioEditarForm(forms.ModelForm):
    password_nueva = forms.CharField(
        label='Nueva contraseña',
        required=False,
        widget=forms.PasswordInput(attrs=BS_INPUT),
        help_text='Dejá en blanco para no cambiarla.',
    )
    rol = forms.ChoiceField(
        label='Rol',
        choices=ROL_CHOICES_ADMIN,
        widget=forms.Select(attrs=BS_SELECT),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username':   forms.TextInput(attrs=BS_INPUT),
            'first_name': forms.TextInput(attrs=BS_INPUT),
            'last_name':  forms.TextInput(attrs=BS_INPUT),
            'email':      forms.EmailInput(attrs=BS_INPUT),
        }

    def __init__(self, *args, creator_is_admin=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not creator_is_admin:
            self.fields['rol'].choices = ROL_CHOICES_MANAGER
        # Pre-seleccionar el rol actual del usuario
        if self.instance and self.instance.pk:
            grupos = list(self.instance.groups.values_list('name', flat=True))
            if 'manager' in grupos:
                self.fields['rol'].initial = 'manager'
            else:
                self.fields['rol'].initial = 'editor'

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get('password_nueva')
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
            from django.contrib.auth.models import Group
            user.groups.set([Group.objects.get(name=self.cleaned_data['rol'])])
        return user


class HorarioFiltroForm(forms.Form):
    """Filtro de carreras/año/cuatrimestre para el listado de materias del panel."""
    carrera = forms.ModelChoiceField(
        queryset=Carrera.objects.all(),
        required=False,
        empty_label='— Seleccionar carrera —',
        widget=forms.Select(attrs=BS_SELECT),
    )
    ano = forms.ChoiceField(
        choices=[('', '— Año —')] + Materia.ANO_CHOICES,
        required=False,
        widget=forms.Select(attrs=BS_SELECT),
    )
    cuatrimestre = forms.ChoiceField(
        choices=[('', '— Todos —')] + Materia.CUATRIMESTRE_CHOICES,
        required=False,
        widget=forms.Select(attrs=BS_SELECT),
    )
