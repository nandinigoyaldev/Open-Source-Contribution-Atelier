"""
Initial migration for events app.
"""

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='DomainEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(db_index=True, max_length=100)),
                ('event_name', models.CharField(db_index=True, max_length=100)),
                ('version', models.IntegerField(default=1)),
                ('data', models.JSONField(default=dict)),
                ('metadata', models.JSONField(default=dict)),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('retry', 'Retry')], db_index=True, default='pending', max_length=20)),
                ('priority', models.IntegerField(choices=[(0, 'Low'), (1, 'Normal'), (2, 'High'), (3, 'Critical')], default=1)),
                ('retry_count', models.IntegerField(default=0)),
                ('max_retries', models.IntegerField(default=3)),
                ('occurred_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_error', models.TextField(blank=True)),
                ('error_stack', models.JSONField(default=list)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='triggered_events', to='auth.user')),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contenttypes.contenttype')),
            ],
            options={
                'ordering': ['-occurred_at'],
                'indexes': [
                    models.Index(fields=['event_type', 'status'], name='events_doma_event_t_5c09ac_idx'),
                    models.Index(fields=['event_name', 'status'], name='events_doma_event_n_af6668_idx'),
                    models.Index(fields=['occurred_at', 'status'], name='events_doma_occurre_7f74e3_idx'),
                    models.Index(fields=['actor', 'event_type'], name='events_doma_actor_i_ee902a_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='EventHandler',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('event_type', models.CharField(max_length=100)),
                ('handler_class', models.CharField(max_length=500)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('error', 'Error')], default='active', max_length=20)),
                ('last_run', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('success_count', models.IntegerField(default=0)),
                ('error_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'unique_together': {('event_type', 'handler_class')},
            },
        ),
        migrations.CreateModel(
            name='EventSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subscriber', models.CharField(max_length=200)),
                ('event_types', models.JSONField(default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('priority', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-priority'],
            },
        ),
    ]