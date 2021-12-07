# Generated by Django 3.2.9 on 2021-12-07 21:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='history',
            name='recipe',
        ),
        migrations.RemoveField(
            model_name='history',
            name='user',
        ),
        migrations.AlterField(
            model_name='machinecontainers',
            name='container_number',
            field=models.IntegerField(choices=[(1, 'first_container_weight'), (2, 'second_container_weight'), (3, 'third_container_weight'), (4, 'fourth_container_weight')], default=0),
        ),
        migrations.AlterField(
            model_name='recipes',
            name='descripction',
            field=models.TextField(default='Brak', max_length=512),
        ),
        migrations.AlterField(
            model_name='teas',
            name='tea_name',
            field=models.CharField(max_length=64),
        ),
        migrations.DeleteModel(
            name='FavoriteRecipes',
        ),
        migrations.DeleteModel(
            name='History',
        ),
    ]