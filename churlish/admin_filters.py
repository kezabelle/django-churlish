from django.contrib.admin.filters import SimpleListFilter
from django.core.exceptions import ValidationError
from django.contrib.admin.options import IncorrectLookupParameters
from django.utils.translation import ugettext_lazy as _
from django.db.models.fields import BooleanField
from django.db.models import Q

try:
    from django.utils.timezone import now
except ImportError:
    from datetime import datetime
    now = datetime.now

from .models import (SimpleAccessRestriction, GroupAccessRestriction,
                     UserAccessRestriction)


class RedirectFilter(SimpleListFilter):
    title = _("Redirect")
    parameter_name = '_redirect'

    def lookups(self, request, model_admin):
        return (
            ('0', _('Yes')),
            ('1', _('No'))
        )

    def queryset(self, request, queryset):
        if self.parameter_name in self.used_parameters:
            param = self.used_parameters[self.parameter_name]
            bool_val = True if param == '1' else False
            final_qs_val = {'urlredirect__isnull': bool_val}
            try:
                return queryset.filter(**final_qs_val)
            except ValidationError as e:
                raise IncorrectLookupParameters(e)
        return queryset


class AccessFilter(SimpleListFilter):
    title = _("Access Restiction")
    parameter_name = '_access'

    def lookups(self, request, model_admin):
        fields = SimpleAccessRestriction._meta.get_fields_with_model()
        bools = (x[0] for x in fields if isinstance(x[0], BooleanField))
        values_and_names = ((x.get_attname(), x.verbose_name) for x in bools)
        return tuple(values_and_names)

    def queryset(self, request, queryset):
        if self.parameter_name in self.used_parameters:
            param = self.used_parameters[self.parameter_name]
            final = 'simpleaccessrestriction__{}'.format(param)
            final_qs_val = {final: True}
            try:
                return queryset.filter(**final_qs_val)
            except ValidationError as e:
                raise IncorrectLookupParameters(e)
        return queryset


class PublishedFilter(SimpleListFilter):
    title = _("Publishing Status")
    parameter_name = '_is_published'

    def lookups(self, request, model_admin):
        return (
            ('0', _('Unpublished')),
            ('1', _('Published'))
        )

    def queryset(self, request, queryset):
        if self.parameter_name in self.used_parameters:
            param = self.used_parameters[self.parameter_name]
            is_published = True if param == '1' else False
            current = now()
            if not is_published:
                try:
                    return queryset.filter(
                        Q(urlvisible__unpublish_on__lte=current) |
                        Q(urlvisible__publish_on__gte=current))
                except ValidationError as e:
                    raise IncorrectLookupParameters(e)
            else:
                doesnt_exist = Q(urlvisible__isnull=True)
                maybe_published = (
                    Q(urlvisible__unpublish_on__gte=current) |
                    Q(urlvisible__unpublish_on__isnull=True)
                )
                definitely_published = Q(urlvisible__publish_on__lte=current)
                published_together = maybe_published & definitely_published
                all_together = doesnt_exist | published_together
                try:
                    return queryset.filter(all_together)
                except ValidationError as e:
                    raise IncorrectLookupParameters(e)
        return queryset


class GroupFilter(SimpleListFilter):
    title = _("Group Restriction")
    parameter_name = '_group_pk'

    def lookups(self, request, model_admin):
        group_cls = GroupAccessRestriction.group.field.rel.to
        return tuple((x.pk, x.name) for x in group_cls.objects.all().iterator())

    def queryset(self, request, queryset):
        if self.parameter_name in self.used_parameters:
            param = self.used_parameters[self.parameter_name]
            try:
                return queryset.filter(groupaccessrestriction__group__pk=param)
            except ValidationError as e:
                raise IncorrectLookupParameters(e)
        return queryset


class UserFilter(SimpleListFilter):
    title = _("User Restriction")
    parameter_name = '_user_pk'

    def lookups(self, request, model_admin):
        user_cls = UserAccessRestriction.user.field.rel.to
        return tuple((x.pk, x.name) for x in user_cls.objects.all().iterator())

    def queryset(self, request, queryset):
        if self.parameter_name in self.used_parameters:
            param = self.used_parameters[self.parameter_name]
            try:
                return queryset.filter(useraccessrestriction__user__pk=param)
            except ValidationError as e:
                raise IncorrectLookupParameters(e)
        return queryset
