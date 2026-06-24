import os
import sys

# Set environment variables for testing
os.environ['SECRET_KEY'] = 'django-insecure-test-key-for-testing-only'
os.environ['DEBUG'] = 'True'
os.environ['DJANGO_SETTINGS_MODULE'] = 'backend.settings'

# Run the tests
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    sys.argv = ['manage.py', 'test', 'project_imports', '--verbosity=2']
    execute_from_command_line(sys.argv)
