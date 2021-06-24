# Generated by Django 2.2.21 on 2021-06-23 12:20

from django.db import migrations


def forward(apps, schema_editor):
    Switch = apps.get_model("waffle", "Switch")
    Flag = apps.get_model("waffle", "Flag")
    if not Switch.objects.filter(name="subscription").exists():
        Switch.objects.create(
            name="subscription", note="Protecting API endpoints related to subscription"
        )
        Flag.objects.filter(name__startswith="subscription").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_delete_banners"),
    ]

    operations = [migrations.RunPython(forward)]
