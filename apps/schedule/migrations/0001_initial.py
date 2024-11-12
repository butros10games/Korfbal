# Generated by Django 5.1.1 on 2024-10-11 08:43

import uuidv7.uuidv7
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id_uuid', models.UUIDField(default=uuidv7.uuidv7.uuid7, editable=False, primary_key=True, serialize=False)),
                ('start_time', models.DateTimeField()),
            ],
        ),
        migrations.CreateModel(
            name='Season',
            fields=[
                ('id_uuid', models.UUIDField(default=uuidv7.uuidv7.uuid7, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, unique=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
            ],
        ),
    ]
