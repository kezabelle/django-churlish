from django.contrib.admin.filters import SimpleListFilter
from django.core.exceptions import ValidationError
from django.contrib.admin.options import IncorrectLookupParameters
from django.utils.translation import ugettext_lazy as _


class RedirectFilter(SimpleListFilter):
    title = _("Redirect")
    parameter_name = 'urlredirect__isnull'

    def lookups(self, request, model_admin):
        return (
            ('0', _('Yes')),
            ('1', _('No'))
        )

    def queryset(self, request, queryset):
        if self.parameter_name in self.used_parameters:
            param = self.used_parameters[self.parameter_name]
            bool_val = True if param == '1' else False
            final_qs_val = {self.parameter_name: bool_val}
            try:
                return queryset.filter(**final_qs_val)
            except ValidationError as e:
                raise IncorrectLookupParameters(e)
        return queryset
