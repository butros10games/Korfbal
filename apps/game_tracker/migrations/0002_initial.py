# Generated by Django 5.1.1 on 2024-10-11 08:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('game_tracker', '0001_initial'),
        ('player', '0001_initial'),
        ('schedule', '0001_initial'),
        ('team', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='matchdata',
            name='match_link',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='schedule.match'),
        ),
        migrations.AddField(
            model_name='matchdata',
            name='players',
            field=models.ManyToManyField(blank=True, related_name='match_data', to='player.player'),
        ),
        migrations.AddField(
            model_name='matchpart',
            name='match_data',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='match_parts', to='game_tracker.matchdata'),
        ),
        migrations.AddField(
            model_name='pause',
            name='match_data',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pauses', to='game_tracker.matchdata'),
        ),
        migrations.AddField(
            model_name='pause',
            name='match_part',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pauses', to='game_tracker.matchpart'),
        ),
        migrations.AddField(
            model_name='playerchange',
            name='match_data',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='player_changes', to='game_tracker.matchdata'),
        ),
        migrations.AddField(
            model_name='playerchange',
            name='match_part',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='player_changes', to='game_tracker.matchpart'),
        ),
        migrations.AddField(
            model_name='playerchange',
            name='player_in',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_changes', to='player.player'),
        ),
        migrations.AddField(
            model_name='playerchange',
            name='player_out',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='player.player'),
        ),
        migrations.AddField(
            model_name='playergroup',
            name='current_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='current_player_groups', to='game_tracker.grouptypes'),
        ),
        migrations.AddField(
            model_name='playergroup',
            name='match_data',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_groups', to='game_tracker.matchdata'),
        ),
        migrations.AddField(
            model_name='playergroup',
            name='players',
            field=models.ManyToManyField(blank=True, related_name='player_groups', to='player.player'),
        ),
        migrations.AddField(
            model_name='playergroup',
            name='starting_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_groups', to='game_tracker.grouptypes'),
        ),
        migrations.AddField(
            model_name='playergroup',
            name='team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_groups', to='team.team'),
        ),
        migrations.AddField(
            model_name='playerchange',
            name='player_group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_changes', to='game_tracker.playergroup'),
        ),
        migrations.AddField(
            model_name='shot',
            name='match_data',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shots', to='game_tracker.matchdata'),
        ),
        migrations.AddField(
            model_name='shot',
            name='match_part',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shots', to='game_tracker.matchpart'),
        ),
        migrations.AddField(
            model_name='shot',
            name='player',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shots', to='player.player'),
        ),
        migrations.AddField(
            model_name='shot',
            name='shot_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shots', to='game_tracker.goaltype'),
        ),
        migrations.AddField(
            model_name='shot',
            name='team',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shots', to='team.team'),
        ),
    ]