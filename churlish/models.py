import logging
from itertools import chain
from datetime import timedelta
from django import VERSION
from django.utils.encoding import python_2_unicode_compatible
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.conf import settings
from model_utils.models import TimeStampedModel
from .querying import VisbilityManager

try:
    from django.utils.timezone import now
except ImportError:
    from datetime import datetime
    now = datetime.now


logger = logging.getLogger(__name__)
PATH_SEP = '/'
DJANGO_VERSION = VERSION[0:3]
BOOL_CHOICES = ((True, _('Yes')), (False, _('No')))
publish_label = _("publishing date")
publish_help = _("the date and time on which this object should be visible on "
                 "the website.")
unpublish_label = _("publishing end date")
unpublish_help = _("if filled in, this date and time are when this object "
                   "will cease being available.")


class ModelValidationError(ValidationError):
    pass


@python_2_unicode_compatible
class URL(TimeStampedModel):
    """
    This implements much of the django-treebeard model API
    """
    site = models.ForeignKey('sites.Site', null=False)
    path = models.CharField(max_length=2048, null=False, blank=False)

    def __str__(self):
        return self.path

    def __repr__(self):
        return self.path

    def clean(self):
        self.path = self.path.strip()
        if self.path and not self.path.startswith(PATH_SEP):
            raise ModelValidationError("Invalid URL root")

    def get_path_ancestry(self, include_self=False):
        parts = tuple(x for x in self.path.split(PATH_SEP) if x)
        max_length = len(parts)
        if include_self:
            max_length += 1
        part_range = range(1, len(parts) + 1)
        combos = ('{sep}{path}{sep}'.format(
                  path=PATH_SEP.join(parts[0:x]), sep=PATH_SEP)
                  for x in part_range)
        return chain([PATH_SEP], combos)

    def get_depth(self):
        return len(tuple(self.get_path_ancestry(include_self=True)))

    get_level = get_depth

    @cached_property
    def depth(self):
        return self.get_depth()

    def get_ancestors(self, include_self=False):
        """
        Returns the nearest ancestors first, such that:
            /a/b/c/
        would return
        (/a/b/c/, /a/b/, /a/, /)
        Allowing for naive iteration over them.
        """
        manager = self.__class__.objects
        if self.is_root():
            if include_self is True:
                return self.__class__.get_root_nodes()
            return manager.none()
        parent_urls = tuple(self.get_path_ancestry(include_self=include_self))
        if not parent_urls:
            return manager.none()
        return manager.filter(path__in=parent_urls)

    def get_ancestor_count(self):
        return self.get_ancestors().count()

    def get_descendants(self):
        return self.__class__.objects.filter(path__startswith=self.path)

    def get_descendant_count(self):
        return self.get_descendants().count()

    def get_parent(self):
        if self.is_root():
            return None
        parent_urls = tuple(self.get_path_ancestry())
        if not parent_urls:
            return None
        closest_parent = parent_urls[-1]
        try:
            return self.__class__.objects.get(path=closest_parent)
        except self.__class__.DoesNotExist:
            return None

    def get_qs_extra(self, target_depth):
        field_obj = self._meta.get_field_by_name('path')
        column = field_obj[0].db_column
        params = [column, column, PATH_SEP, PATH_SEP, target_depth]
        qs_extra = ["(LENGTH(%s) - LENGTH(REPLACE(%s, %s, ''))) / LENGTH(%s) = %d"]
        return {
            'where': qs_extra,
            'params': params,
        }

    def get_siblings(self):
        if self.is_root():
            return self.__class__.objects.none()
        ancestors = tuple(self.get_path_ancestry(include_self=False))
        nearest_ancestor = ancestors[-1]
        slash_count = self.path.count(PATH_SEP)
        extras = self.get_qs_extra(target_depth=slash_count)
        return (self.__class__.objects
                .filter(path__startswith=nearest_ancestor)
                .extra(**extras))

    def get_children(self):
        slash_count = self.path.count(PATH_SEP)
        children_count = slash_count + 1
        extras = self.get_qs_extra(target_depth=children_count)
        return self.get_descendants().extra(**extras)

    def get_children_count(self):
        return self.get_children.count()

    @classmethod
    def get_root_nodes(cls):
        return cls.objects.filter(path=PATH_SEP)

    @classmethod
    def get_first_root_node(cls):
        try:
            return cls.get_root_nodes()[0]
        except IndexError:
            return None

    @classmethod
    def get_last_root_node(cls):
        try:
            return cls.get_root_nodes()[0]
        except IndexError:
            return None

    def get_root(self):
        return self.__class__.objects.get(path=PATH_SEP)

    def is_ancestor_of(self, node):
        """
        ???
        """
        url_namespace = node.path.startswith(self.path)
        i_am_shorter = len(self.path) < len(node.path)
        return all((url_namespace, i_am_shorter))

    def is_child_of(self, node):
        """
        If this node starts with the path of the other node,
        and the other node's path is *SHORTER*, it is a child
        """
        prefix = self.path.startswith(node.path)
        longer = len(node.path) < len(self.path)
        return all((prefix, longer))

    def is_descendant_of(self, node):
        """
        If the other node starts with our path, and our path
        is longer, we are a descendant
        """
        prefix = node.path.startswith(self.path)
        longer = len(self.path) > len(node.path)
        return all((prefix, longer))

    def is_root(self):
        return self.path == PATH_SEP

    def is_sibling_of(self, node):
        other = list(x for x in node.path.split(PATH_SEP) if x)
        me = list(x for x in self.path.split(PATH_SEP) if x)
        other_len = len(other)
        me_len = len(me)
        if other_len == me_len and (me_len > 0 and other_len > 0):
            other.pop()
            me.pop()
            return other == me
        return False

    def is_child_node(self):
        return not self.is_root()

    def is_same_as(self, node):
        return self.path == node.path

    class Meta:
        ordering = ('-path',)
        verbose_name = _("URL")
        verbose_name_plural = _("URLs")
        db_table = 'churlish_url'
        unique_together = (('site', 'path'),)


def validate_redirect_target(value):
    if value.startswith(('http://', 'https://')):
        return True
    if value.startswith('//'):
        return True
    if value.startswith(('.', '/.')):
        raise ModelValidationError('URL may not be relative')
    if value.startswith('/'):
        return True
    raise ModelValidationError('URL may not be relative')


@python_2_unicode_compatible
class URLRedirect(TimeStampedModel):
    url = models.OneToOneField('churlish.URL')
    target = models.CharField(max_length=2048,
                              validators=[validate_redirect_target])

    def __str__(self):
        return self.target

    def clean(self):
        self.target = self.target.strip()
        if len(self.target) < 1:
            raise ModelValidationError("Invalid target")

    def get_absolute_url(self):
        return self.target

    def is_permanent(self):
        return True

    class Meta:
        verbose_name = _("Redirect")
        verbose_name_plural = _("Redirects")
        db_table = "churlish_url_redirect"


@python_2_unicode_compatible
class URLVisible(TimeStampedModel):
    url = models.OneToOneField('churlish.URL')
    publish_on = models.DateTimeField(default=now,
                                      verbose_name=publish_label,
                                      help_text=publish_help)
    unpublish_on = models.DateTimeField(default=None, blank=True, null=True,
                                        verbose_name=unpublish_label,
                                        help_text=unpublish_help)
    objects = VisbilityManager()

    def __str__(self):
        return 'from: {!s}, to: {!s}'.format(self.publish_on,
                                             self.unpublish_on)

    def _get_is_published(self):
        """
        :return: Whether or not this object is currently visible
        :rtype: boolean
        """
        current = now()
        if self.unpublish_on is not None:
            # maybe self.unpublish_on >= now >= self.publish_on ???
            return self.unpublish_on >= current and self.publish_on <= current
        else:
            return self.publish_on <= current

    def _set_is_published(self, value):
        current = now() - timedelta(seconds=1)
        if value:
            self.publish_on = current
            self.unpublish_on = None
        else:
            self.publish_on = current
            self.unpublish_on = current

    is_published = property(_get_is_published, _set_is_published)

    def unpublish(self, using=None):
        self.unpublish_on = now() - timedelta(seconds=1)
        save_kwargs = {'using': using}
        if DJANGO_VERSION > (1, 5, 0):
            save_kwargs.update(update_fields=['unpublish_on'])
        return self.save(**save_kwargs)

    class Meta:
        verbose_name = _("Visibility")
        verbose_name_plural = _("Visibility")
        db_table = 'churlish_url_visibility'


@python_2_unicode_compatible
class SimpleAccessRestriction(TimeStampedModel):
    url = models.OneToOneField('churlish.URL')
    is_authenticated = models.BooleanField(default=False,
                                           verbose_name=_("Login required"))
    is_staff = models.BooleanField(default=False, verbose_name=_("Only staff"))
    is_superuser = models.BooleanField(default=False,
                                       verbose_name=_("Only administrators"))

    def has_restriction(self):
        return self.is_authenticated or self.is_staff or self.is_superuser

    def __str__(self):
        if self.has_restriction():
            return 'Restricted'
        return 'Unrestricted'

    class Meta:
        db_table = 'churlish_url_access'


@python_2_unicode_compatible
class GroupAccessRestriction(TimeStampedModel):
    url = models.ForeignKey('churlish.URL')
    group = models.ForeignKey('auth.Group')

    def __str__(self):
        return 'restricted to {}'.format(self.group.name)

    class Meta:
        db_table = 'churlish_url_accessgroup'


@python_2_unicode_compatible
class UserAccessRestriction(TimeStampedModel):
    url = models.ForeignKey('churlish.URL')
    user = models.ForeignKey(getattr(settings, 'AUTH_USER_MODEL', 'auth.User'))

    def __str__(self):
        return self.user

    class Meta:
        db_table = 'churlish_url_accessuser'
