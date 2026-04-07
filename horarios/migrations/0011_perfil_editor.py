from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('horarios', '0010_docente_fk_usuario'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilEditor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('usuario', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='perfil_editor',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('creado_por', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='editores_creados',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Creado por',
                )),
            ],
            options={
                'verbose_name': 'Perfil de editor',
                'verbose_name_plural': 'Perfiles de editores',
            },
        ),
    ]
