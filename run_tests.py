#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.conf import settings
import os, sys

settings.configure(
    INSTALLED_APPS=('autoslug',),
    AUTOSLUG_SLUGIFY_FUNCTION='django.template.defaultfilters.slugify',
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',     
        }    
    }
)

from django.test.simple import DjangoTestSuiteRunner
test_runner = DjangoTestSuiteRunner(verbosity=1)
failures = test_runner.run_tests(['autoslug', ])
if failures: 
    sys.exit(failures)
