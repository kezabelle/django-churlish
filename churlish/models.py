import logging
from itertools import chain
from datetime import timedelta
from django import VERSION
from django.utils.encoding import python_2_unicode_compatible
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
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
    path = models.CharField(max_length=2048)

    def __str__(self):
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

    def get_ancestors(self):
        parent_urls = tuple(self.get_path_ancestry())
        if not parent_urls:
            return self.__class__.objects.none()
        return self.__class__.objects.filter(path__in=parent_urls)

    def get_ancestor_count(self):
        return self.get_ancestors().count()

    def get_descendants(self):
        return self.__class__.objects.filter(path__startswith=self.path)

    def get_descendant_count(self):
        return self.get_descendants().count()

    def get_parent(self):
        parent_urls = tuple(self.get_path_ancestry())
        if not parent_urls:
            return None
        closest_parent = parent_urls[-1]
        try:
            return self.__class__.objects.get(path=closest_parent)
        except self.__class__.DoesNotExist:
            return None

    def get_siblings(self):
        raise NotImplementedError

    def get_children(self):
        raise NotImplementedError

    def get_children_count(self):
        raise NotImplementedError

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

    def is_child_of(self, node):
        prefix = self.path.startswith(node.path)
        longer = len(node.path) > len(self.path)
        return all((prefix, longer))

    def is_descendant_of(self, node):
        """
        opposite of is_child_of
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

    class Meta:
        ordering = ('-path',)
        verbose_name = _("URL")
        verbose_name_plural = _("URLs")
        db_table = 'churlish_url'


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
        db_table = "churlish_urlredirect"


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
        db_table = 'churlish_urlvisible'
