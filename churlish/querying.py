from django.db.models import Q, Manager
from django.db.models.query import QuerySet

try:
    from django.utils.timezone import now
except ImportError:
    from datetime import datetime
    now = datetime.now


class VisbilityQuerySet(QuerySet):
    def published(self):
        current = now()
        maybe_published = (Q(unpublish_on__gte=current) |
                           Q(unpublish_on__isnull=True))
        definitely_published = Q(publish_on__lte=current)
        return self.filter(maybe_published & definitely_published)

    def unpublished(self):
        current = now()
        return self.filter(Q(unpublish_on__lte=current) |
                           Q(publish_on__gte=current))


class VisbilityManager(Manager):
    use_for_related_fields = True

    def get_query_set(self):
        return VisbilityQuerySet(self.model, using=self._db)

    def get_queryset(self):
        return VisbilityQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()

    def unpublished(self):
        return self.get_queryset().unpublished()
