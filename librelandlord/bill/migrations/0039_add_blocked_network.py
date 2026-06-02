from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bill', '0038_add_renter_token_updated_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlockedNetwork',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('network', models.CharField(max_length=50, unique=True, verbose_name='Netzwerk/IP')),
                ('last_seen', models.DateTimeField(verbose_name='Zuletzt gesehen')),
                ('reason', models.CharField(blank=True, max_length=255, verbose_name='Grund')),
            ],
            options={
                'verbose_name': 'Geblockte IP/Netz',
                'verbose_name_plural': 'Geblockte IPs/Netze',
                'ordering': ['-last_seen'],
            },
        ),
    ]
