# -*- coding: utf-8 -*-
#from __future__ import unicode_literals
from django.db.models.fields import FieldDoesNotExist, DateField
from django.db.utils import IntegrityError
from warnings import warn


def get_prepopulated_value(field, instance):
    """
    Returns list of preliminary values based on `populate_from`.
    """
    if hasattr(field.populate_from, '__call__'):
        # AutoSlugField(populate_from=lambda instance: ...)
        values = field.populate_from(instance)
        if type(values) not in [list, tuple]:
            values = [values]
        return values
    else: 
        fields = field.populate_from

        if isinstance(fields, basestring): 
            fields = [fields]

        values = []
        for field in fields: 
            attr = getattr(instance, field)
            value = callable(attr) and attr() or attr 
            values.append(value)

        return values
    

def generate_unique_slug(field, instance, slugs):
    """
    Pick the first unique slug from given list. If none is unique generates one 
    by adding a number to first given value until no model instance can be found 
    with such slug. If ``unique_with`` (a tuple of field names) was specified for 
    the field, all these fields are included together in the query when looking 
    for a "rival" model instance.
    """


    default_lookups = tuple(get_uniqueness_lookups(field, instance, field.unique_with))

    index = 1

    for add_index in [False, True]: 
        for slug in slugs: 
            original_slug = slug = crop_slug(field, slug)
            # keep changing the slug until it is unique
            while True:
                # find instances with same slug
                lookups = dict(default_lookups, **{field.name: slug})
                rivals = type(instance).objects.filter(**lookups).exclude(pk=instance.pk)

                if not rivals:
                    # the slug is unique, no model uses it
                    return slug
                elif field.unique_warning: 
                    sr = u''
                    for r in rivals: 
                        sr = u"%s'%s %s' and " % (sr, r.id, r)
                    sr = sr.rstrip(u' and ')
                    warn("Initial base slug '%s' for %s is yet used in %s. Adding index" % (slug.encode('utf-8'), instance.pk or 'instance', sr.encode('utf-8')))

                if add_index: 
                    # the slug is not unique; change once more
                    index += 1

                    # ensure the resulting string is not too long
                    tail_length = len(field.index_sep) + len(str(index))
                    combined_length = len(original_slug) + tail_length
                    if field.max_length < combined_length:
                        original_slug = original_slug[:field.max_length - tail_length]

                    # re-generate the slug
                    data = dict(slug=original_slug, sep=field.index_sep, index=index)
                    slug = u'%(slug)s%(sep)s%(index)d' % data
                    # ...next iteration...
                else: 
                    break 

def get_uniqueness_lookups(field, instance, unique_with):
    """
    Returns a dict'able tuple of lookups to ensure uniqueness of a slug.
    """
    for original_lookup_name in unique_with:
        if '__' in original_lookup_name:
            field_name, inner_lookup = original_lookup_name.split('__', 1)
        else:
            field_name, inner_lookup = original_lookup_name, None

        try:
            other_field = instance._meta.get_field(field_name)
        except FieldDoesNotExist:
            raise ValueError('Could not find attribute %s.%s referenced'
                             ' by %s.%s (see constraint `unique_with`)'
                             % (instance._meta.object_name, field_name,
                                instance._meta.object_name, field.name))

        if field == other_field:
            raise ValueError('Attribute %s.%s references itself in `unique_with`.'
                             ' Please use "unique=True" for this case.'
                             % (instance._meta.object_name, field_name))

        value = getattr(instance, field_name)
        if not value:
            if other_field.blank:
                break
            raise ValueError('Could not check uniqueness of %s.%s with'
                             ' respect to %s.%s because the latter is empty.'
                             ' Please ensure that "%s" is declared *after*'
                             ' all fields listed in unique_with.'
                             % (instance._meta.object_name, field.name,
                                instance._meta.object_name, field_name,
                                field.name))
        if isinstance(other_field, DateField):    # DateTimeField is a DateField subclass
            inner_lookup = inner_lookup or 'day'

            if '__' in inner_lookup:
                raise ValueError('The `unique_with` constraint in %s.%s'
                                 ' is set to "%s", but AutoSlugField only'
                                 ' accepts one level of nesting for dates'
                                 ' (e.g. "date__month").'
                                 % (instance._meta.object_name, field.name,
                                    original_lookup_name))

            parts = ['year', 'month', 'day']
            try:
                granularity = parts.index(inner_lookup) + 1
            except ValueError:
                raise ValueError('expected one of %s, got "%s" in "%s"'
                                    % (parts, inner_lookup, original_lookup_name))
            else:
                for part in parts[:granularity]:
                    lookup = '%s__%s' % (field_name, part)
                    yield lookup, getattr(value, part)
        else:
            # TODO: this part should be documented as it involves recursion
            if inner_lookup:
                if not hasattr(value, '_meta'):
                    raise ValueError('Could not resolve lookup "%s" in `unique_with` of %s.%s'
                                     % (original_lookup_name, instance._meta.object_name, field.name))
                for inner_name, inner_value in get_uniqueness_lookups(field, value, [inner_lookup]):
                    yield original_lookup_name, inner_value
            else:
                yield field_name, value

def crop_slug(field, slug):
    if field.max_length < len(slug):
        return slug[:field.max_length]
    return slug
