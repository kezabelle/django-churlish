from functools import partial, update_wrapper
from django.utils.translation import ugettext_lazy as _
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from .models import (URLRedirect, URLVisible, SimpleAccessRestriction,
                     GroupAccessRestriction, UserAccessRestriction)
from .admin_filters import (RedirectFilter, AccessFilter, PublishedFilter,
                            GroupFilter, UserFilter)
from .middleware_filters import (UserRoleRequired, UserRequired, GroupRequired,
                                 RedirectRequired, PublishedRequired)


class URLInline(admin.StackedInline):
    extra = 0

    def get_urladmin_display_func(self, relation_name=None):
        func = partial(self.get_urladmin_display, relation_name=relation_name)
        func2 = update_wrapper(func, self.get_urladmin_display)
        return func2


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

    def get_churlish_middlewares(self):
        return (RedirectRequired,)


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

    def get_churlish_middlewares(self):
        return (PublishedRequired,)


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

    def get_churlish_middlewares(self):
        return (UserRoleRequired,)


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

    def get_churlish_middlewares(self):
        return (GroupRequired,)


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

    def get_churlish_middlewares(self):
        return (UserRequired,)
