# Generated by Django 4.2.17 on 2025-02-07 16:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pretixbase", "0276_item_hidden_if_item_available_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerssoclient",
            name="require_pkce",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customerssogrant",
            name="code_challenge",
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name="customerssogrant",
            name="code_challenge_method",
            field=models.CharField(max_length=255, null=True),
        ),
    ]
