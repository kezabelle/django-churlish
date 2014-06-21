from rest_framework import serializers
from django.contrib.sites.models import Site
from .models import URL


class SiteSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Site
        fields = ['name', 'domain']


class URLSerializer(serializers.HyperlinkedModelSerializer):
    object_url = serializers.SerializerMethodField('get_object_url')
    site = SiteSerializer(read_only=True)
    depth = serializers.Field(source='depth')
    root = serializers.Field(source='is_root')
    child = serializers.Field(source='is_child_node')
    descendants = serializers.Field(source='get_descendant_count')
    ancestors = serializers.Field(source='get_ancestor_count')

    def save_object(self, obj, **kwargs):
        if not obj.site_id:
            obj.site = Site.objects.get_current()
        return super(URLSerializer, self).save_object(obj=obj, **kwargs)

    def get_object_url(self, obj):
        request = self.context.get('request', None)
        if request is None:
            return None
        return request.build_absolute_uri(obj.path)

    class Meta:
        model = URL
        fields = ['created', 'modified', 'url', 'object_url', 'site', 'path',
                  'root', 'child', 'descendants', 'ancestors']
