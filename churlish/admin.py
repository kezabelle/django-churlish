from itertools import chain
from functools import partial, update_wrapper
try:
    from itertools import izip_longest as zip_longest
except ImportError:  # pragma: no-cover ... Python 3.
    from itertools import zip_longest

from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import admin
from .models import (URL, URLRedirect, URLVisible, SimpleAccessRestriction,
                     GroupAccessRestriction, UserAccessRestriction)
from .admin_filters import (RedirectFilter, AccessFilter, PublishedFilter,
                            GroupFilter, UserFilter)


class URLInline(admin.StackedInline):
    extra = 0

    def get_urladmin_display_func(self, relation_name=None):
        func = partial(self.get_urladmin_display, relation_name=relation_name)
        func2 = update_wrapper(func, self.get_urladmin_display)
        return func2

    def get_urladmin_display(self, obj, relation_name):
        raise NotImplementedError



class RedirectInline(URLInline):
    model = URLRedirect
    max_num = 1

    def get_urladmin_display(self, obj, relation_name):
        try:
            related_instance = getattr(obj, relation_name, None)
        except ObjectDoesNotExist:
            related_instance = None
        if related_instance is None:
            return False
        return len(related_instance.get_absolute_url()) > 0
    get_urladmin_display.short_description = _("Redirect")
    get_urladmin_display.boolean = True

    def get_urladmin_filter_cls(self, *args, **kwargs):
        return RedirectFilter


class VisibleInline(URLInline):
    model = URLVisible
    max_num = 1

    def get_urladmin_display(self, obj, relation_name):
        """
        This one is inverted, so that "is published" is ticked when
        nothing is there
        """
        try:
            related_instance = getattr(obj, relation_name, None)
        except ObjectDoesNotExist:
            related_instance = None
        if related_instance is None:
            return True
        return related_instance.is_published
    get_urladmin_display.short_description = _("Published")
    get_urladmin_display.boolean = True


    def get_urladmin_filter_cls(self, *args, **kwargs):
        return PublishedFilter


class SimpleAccessInline(URLInline):
    model = SimpleAccessRestriction
    extra = 1

    def get_urladmin_display(self, obj, relation_name):
        try:
            related_instance = getattr(obj, relation_name, None)
        except ObjectDoesNotExist:
            related_instance = None
            return False
        return related_instance.has_restriction()
    get_urladmin_display.short_description = _("Login Restricted")
    get_urladmin_display.boolean = True

    def get_urladmin_filter_cls(self, *args, **kwargs):
        return AccessFilter


class GroupAccessInline(URLInline):
    model = GroupAccessRestriction

    def get_urladmin_display(self, obj, relation_name):
        related_instance = getattr(obj, relation_name, None)
        if related_instance is None:
            return False
        return related_instance.exists()
    get_urladmin_display.short_description = _("Group Restricted")
    get_urladmin_display.boolean = True

    def get_urladmin_filter_cls(self, *args, **kwargs):
        return GroupFilter


class UserAccessInline(URLInline):
    model = UserAccessRestriction

    def get_urladmin_display(self, obj, relation_name):
        related_instance = getattr(obj, relation_name, None)
        if related_instance is None:
            return False
        return related_instance.exists()
    get_urladmin_display.short_description = _("User Restricted")
    get_urladmin_display.boolean = True

    def get_urladmin_filter_cls(self, *args, **kwargs):
        return UserFilter


class URLAdmin(admin.ModelAdmin):
    list_display = ['path']
    list_display_links = ['path']
    actions = None
    search_fields = ['^path']
    ordering = ('-modified',)
    inlines = [VisibleInline, SimpleAccessInline, GroupAccessInline,
               UserAccessInline, RedirectInline]

    def get_runtime_relations(self):
        """
        For the middleware, of all things.
        Because this is the best place to find out wtf we might want to
        ask for at runtime without configuration.
        """
        models = (x.model for x in self.inlines[:] if hasattr(x, 'model'))
        fields = (x._meta.get_fields_with_model() for x in models)
        flat_fields = chain(*fields)
        just_fields = (x[0] for x in flat_fields)
        only_rels = (x for x in just_fields
                     if hasattr(x, 'rel'))
        only_good_rels = (x for x in only_rels if x.rel is not None)
        only_ours = (x for x in only_good_rels if x.rel.to == URL)
        accessors = (x.related.get_accessor_name() for x in only_ours
                     if hasattr(x, 'related'))
        return accessors

    def get_runtime_relations_and_inlines(self):
        relations = tuple(self.get_runtime_relations())
        zipped_together = zip_longest(self.inlines[:], relations,
                                      fillvalue=None)
        models_and_inlines = ((inline, inline.model, relation)
                              for inline, relation in zipped_together
                              if inline is not None and relation is not None)
        return models_and_inlines

    def get_queryset(self, *args, **kwargs):
        relations = tuple(self.get_runtime_relations())
        qs = super(URLAdmin, self).get_queryset(*args, **kwargs)
        return qs.select_related(*relations)

    def get_list_display(self, *args, **kwargs):
        models_and_inlines = self.get_runtime_relations_and_inlines()
        instantiated = ((inline(model, self.admin_site), relation)
                        for inline, model, relation in models_and_inlines
                        if hasattr(inline, 'get_urladmin_display')
                        and hasattr(inline, 'get_urladmin_display_func'))
        called = tuple(inline.get_urladmin_display_func(relation)
                       for inline, relation in instantiated)
        return ('path', 'modified') + called

    def get_list_filter(self, *args, **kwargs):
        models_and_inlines = self.get_runtime_relations_and_inlines()
        instantiated = ((inline(model, self.admin_site), relation)
                        for inline, model, relation in models_and_inlines
                        if hasattr(inline, 'get_urladmin_filter_cls'))
        classes = (inline.get_urladmin_filter_cls(*args, **kwargs)
                   for inline, relation in instantiated)
        self.list_filter = tuple(classes)
        return self.list_filter

    def lookup_allowed(self, lookup, value):
        return True
admin.site.register(URL, URLAdmin)
