# -*- coding: utf-8 -*-
#
#  Copyright (c) 2008—2012 Andy Mikhailenko
#
#  This file is part of django-autoslug.
#
#  django-autoslug is free software under terms of the GNU Lesser
#  General Public License version 3 (LGPLv3) as published by the Free
#  Software Foundation. See the file README for copying conditions.
#

# django
from django.db.models.fields import SlugField

# 3rd-party
try:
    from south.modelsinspector import introspector
except ImportError:
    introspector = lambda self: [], {}

# this app
from autoslug.settings import slugify
from autoslug import utils
from warnings import warn


__all__ = ['AutoSlugField']

SLUG_INDEX_SEPARATOR = '-'    # the "-" in "foo-2"

try:                 # pragma: nocover
    # Python 2.x
    basestring
except NameError:    # pragma: nocover
    # Python 3.x
    basestring = str


class AutoSlugField(SlugField):
    """
    AutoSlugField is an extended SlugField able to automatically resolve name
    clashes.

    AutoSlugField can also perform the following tasks on save:

    - populate itself from another field/s (using `populate_from`),
    - use custom `slugify` function (using `slugify` or :doc:`settings`), and
    - preserve uniqueness of the value (using `unique` or `unique_with`).

    None of the tasks is mandatory, i.e. you can have auto-populated non-unique
    fields, manually entered unique ones (absolutely unique or within a given
    date) or both.

    Uniqueness is preserved by checking if the slug is unique with given constraints
    (`unique_with`) or globally (`unique`) and adding a number to the slug to make
    it unique.

    :param always_update: boolean: if True, the slug is updated each time the
        model instance is saved. Use with care because `cool URIs don't
        change`_ (and the slug is usually a part of object's URI). Note that
        even if the field is editable, any manual changes will be lost when
        this option is activated.
    :param populate_from: string, list, tuple or callable: if string is given, it is considered
        as the name of attribute from which to fill the slug. If callable is given,
        it should accept `instance` parameter and return a value to fill the slug
        with. If list or tuple are given, the values are considered the name of attributes from 
        wich to fill slug -without add index- in order of preference. If all list values 
        are yet used we choose first one adding index
    :param sep: string: if defined, overrides default separator for automatically
        incremented slug index (i.e. the "-" in "foo-2").
    :param slugify: callable: if defined, overrides `AUTOSLUG_SLUGIFY_FUNCTION`
        defined in :doc:`settings`.
    :param unique: boolean: ensure total slug uniqueness (unless more precise
        `unique_with` is defined).
    :param unique_with: string or tuple of strings: name or names of attributes
        to check for "partial uniqueness", i.e. there will not be two objects
        with identical slugs if these objects share the same values of given
        attributes. For instance, ``unique_with='pub_date'`` tells AutoSlugField
        to enforce slug uniqueness of all items published on given date. The
        slug, however, may reappear on another date. If more than one field is
        given, e.g. ``unique_with=('pub_date', 'author')``, then the same slug may
        reappear within a day or within some author's articles but never within
        a day for the same author. Foreign keys are also supported, i.e. not only
        `unique_with='author'` will do, but also `unique_with='author__name'`.
    :param unique_warning: boolean, default = True: if True, warning when slug is 
        not unique 

    .. _cool URIs don't change: http://w3.org/Provider/Style/URI.html

    .. note:: always place any slug attribute *after* attributes referenced
        by it (i.e. those from which you wish to `populate_from` or check
        `unique_with`). The reasoning is that autosaved dates and other such
        fields must be already processed before using them in the AutoSlugField.

    Example usage::

        from django.db import models
        from autoslug import AutoSlugField

        class Article(models.Model):
            '''An article with title, date and slug. The slug is not totally
            unique but there will be no two articles with the same slug within
            any month.
            '''
            title = models.CharField(max_length=200)
            pub_date = models.DateField(auto_now_add=True)
            slug = AutoSlugField(populate_from='title', unique_with='pub_date__month')


    More options::

        # slugify but allow non-unique slugs
        slug = AutoSlugField()

        # globally unique, silently fix on conflict ("foo" --> "foo-1".."foo-n")
        slug = AutoSlugField(unique=True)

        # autoslugify value from attribute named "title"; editable defaults to False
        slug = AutoSlugField(populate_from='title')

        # same as above but force editable=True
        slug = AutoSlugField(populate_from='title', editable=True)

        # ensure that slug is unique with given date (not globally)
        slug = AutoSlugField(unique_with='pub_date')

        # ensure that slug is unique with given date AND category
        slug = AutoSlugField(unique_with=('pub_date','category'))

        # ensure that slug in unique with an external object
        # assuming that author=ForeignKey(Author)
        slug = AutoSlugField(unique_with='author')

        # ensure that slug in unique with a subset of external objects (by lookups)
        # assuming that author=ForeignKey(Author)
        slug = AutoSlugField(unique_with='author__name')

        # mix above-mentioned behaviour bits
        slug = AutoSlugField(populate_from='title', unique_with='pub_date')

        # minimum date granularity is shifted from day to month
        slug = AutoSlugField(populate_from='title', unique_with='pub_date__month')

        # autoslugify value from a dynamic attribute (i.e. a method)
        slug = AutoSlugField(populate_from='get_full_name')

        # autoslugify value from a custom callable
        # (ex. usage: user profile models)
        slug = AutoSlugField(populate_from=lambda instance: instance.user.get_full_name())

        # specify model manager for looking up slugs shared by subclasses

        class Article(models.Model):
            '''An article with title, date and slug. The slug is not totally
            unique but there will be no two articles with the same slug within
            any month.
            '''
            objects = models.Manager()
            title = models.CharField(max_length=200)
            slug = AutoSlugField(populate_from='title', unique_with='pub_date__month', manager=objects)

        class NewsArticle(Article):
            pass

        # autoslugify value using custom `slugify` function
        from autoslug.settings import slugify as default_slugify
        def custom_slugify(value):
            return default_slugify(value).replace('-', '_')
        slug = AutoSlugField(slugify=custom_slugify)
    """
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 50)

        # autopopulated slug is not editable unless told so
        self.populate_from = kwargs.pop('populate_from', None)
        if self.populate_from:
            kwargs.setdefault('editable', False)

        # unique_with value can be string or tuple
        self.unique_with = kwargs.pop('unique_with', ())
        if isinstance(self.unique_with, basestring):
            self.unique_with = (self.unique_with,)

        self.slugify = kwargs.pop('slugify', slugify)
        assert hasattr(self.slugify, '__call__')

        self.index_sep = kwargs.pop('sep', SLUG_INDEX_SEPARATOR)

        # backward compatibility
        if kwargs.get('unique_with_date'):
            warn('Using unique_with_date="foo" in AutoSlugField is deprecated, '
                 'use unique_with=("foo",) instead.', DeprecationWarning)
            self.unique_with += (kwargs['unique_with_date'],)

        kwargs['unique'] = kwargs.pop('unique', True)
        if self.unique_with:
            # we will do "manual" granular check below
            kwargs['unique'] = False

        # Set db_index=True unless it's been set manually.
        if 'db_index' not in kwargs:
            kwargs['db_index'] = True

        # When using model inheritence, set manager to search for matching
        # slug values
        self.manager = kwargs.pop('manager', None)

        self.always_update = kwargs.pop('always_update', False)

        self.unique_warning = kwargs.pop('unique_warning', True)

        super(SlugField, self).__init__(*args, **kwargs)

    def pre_save(self, instance, add):
        # get actual value field
        value = self.value_from_object(instance)

        manager = self.manager

        # if autopopulate
        if self.always_update or (self.populate_from and not value):
            # get prepopulated values
            values = utils.get_prepopulated_value(self, instance)

            # pragma: nocover
            if __debug__ and not values and not self.blank:
                print('Failed to populate slug %s.%s from %s' % \
                    (instance._meta.object_name, self.name, self.populate_from))
        else: 
            # force values to be a list
            values = [value]

        # remove possible empty values
        values = [value for value in values if value]

        # if prepopulation return no values
        if not values: 
            if self.default and isinstance(self.default, basestring): 
                values = [self.default]
                warn (u'Failed to populate slug %s.%s from %s. Set default' % \
                    (instance._meta.object_name, self.name, self.populate_from))
            elif self.blank: 
                if self.null: 
                    setattr(instance, self.name, None)
                    warn (u'Failed to populate slug %s.%s from %s. Set null' % \
                        (instance._meta.object_name, self.name, self.populate_from))
                    return None 
                else: 
                    setattr(instance, self.name, u'')
                    warn (u'Failed to populate slug %s.%s from %s. Set blank' % \
                        (instance._meta.object_name, self.name, self.populate_from))
                    return u'' 
            else: 
                values = [instance._meta.module_name]
                warn (u'Failed to populate slug %s.%s from %s. Set model name' % \
                    (instance._meta.object_name, self.name, self.populate_from))

        slugs = [self.slugify(value) for value in values]

        if not slugs: 
            warn (u'Failed to populate slug %s.%s from %s' % \
                (instance._meta.object_name, self.name, self.populate_from))
            return 

        assert slugs, 'slugs are defined before trying to ensure uniqueness'

        slugs = [utils.crop_slug(self, slug) for slug in slugs]

        # ensure the slug is unique (if required)
        if self.unique or self.unique_with:
            slug = utils.generate_unique_slug(self, instance, slugs, manager)

        if not slug: 
            warn (u'Failed to populate slug %s.%s from %s' % \
                (instance._meta.object_name, self.name, self.populate_from))
            return 

        assert slug, 'value must be filled before saving'

        if slug: 
            # make the updated slug available as instance attribute
            setattr(instance, self.name, slug)

        return slug

    def south_field_triple(self):
        "Returns a suitable description of this field for South."
        args, kwargs = introspector(self)
        kwargs.update({
            'populate_from': 'None' if callable(self.populate_from) else repr(self.populate_from),
            'unique_with': repr(self.unique_with)
        })
        return ('autoslug.fields.AutoSlugField', args, kwargs)
