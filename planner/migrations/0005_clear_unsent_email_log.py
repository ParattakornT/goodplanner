from django.db import migrations


def clear(apps, schema_editor):
    # Before Gmail was connected, reminders were printed to the log and wrongly
    # recorded as sent. Clearing the log lets them go out for real.
    apps.get_model('planner', 'EmailLog').objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('planner', '0004_email_reminders')]
    operations = [migrations.RunPython(clear, migrations.RunPython.noop)]
