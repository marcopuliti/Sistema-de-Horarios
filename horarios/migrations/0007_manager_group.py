from django.db import migrations


def create_manager_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='manager')


def delete_manager_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='manager').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('horarios', '0006_aula_en_bloque'),
    ]

    operations = [
        migrations.RunPython(create_manager_group, delete_manager_group),
    ]
