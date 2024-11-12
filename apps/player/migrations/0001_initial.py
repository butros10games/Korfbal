# Generated by Django 5.1.1 on 2024-10-11 08:43

import uuidv7.uuidv7
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('club', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id_uuid', models.UUIDField(default=uuidv7.uuidv7.uuid7, editable=False, primary_key=True, serialize=False)),
                ('profile_picture', models.ImageField(blank=True, default='/static/images/player/blank-profile-picture.png', upload_to='media/profile_pictures/')),
                ('club_follow', models.ManyToManyField(blank=True, to='club.club')),
            ],
        ),
    ]
