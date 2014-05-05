from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404
from django.shortcuts import redirect

# Always use an Http404 subclass for the error condition, to avoid leaking 
# that some part of the URL may be correct. eg, an error triggered by /a/
# when visiting /a/this/is/purposefully/a/404/ should not reveal that some
# part of that URL is OK.

class IsAuthenticated(object):
    __slots__ = ()
    def has_object_permission(self, request, obj, view):
        return request.user and request.user.is_authenticated()


class IsStaff(object):
    __slots__ = ()
    def has_object_permission(self, request, obj, view):
        return request.user and request.user.is_staff

        
class IsAdmin(object):
    __slots__ = ()
    def has_object_permission(self, request, obj, view):
        return request.user and request.user.is_superuser


class UserRoleRequired(object):
    __slots__ = ()
    def has_object_permission(self, request, obj, view):
        try:
            access_required = obj.simpleaccessrestriction
        except ObjectDoesNotExist:
            # no restriction exists, so it's true for now.
            return True
        
        final = []
        if access_required.is_authenticated:
            final.append(
                IsAuthenticated().has_object_permission(request, obj, None))
        if access_required.is_staff:
            final.append(IsStaff().has_object_permission(request, obj, None))
        if access_required.is_superuser:
            final.append(IsAdmin().has_object_permission(request, obj, None))
        return all(final)

    def error(self, request, obj):
        msg = ("You don't have access to this URL resource, because {} "
               "prevented it".format(obj.path))
        raise Http404(msg)

        
class UserRequired(object):
    __slots__ = ()
    def has_object_permission(self, request, obj, view):
        users = obj.useraccessrestriction_set.values_list('user_id', flat=True)
        distinct_users = frozenset(users)
        if not distinct_users:
            return True
        not_anonymous = IsAuthenticated().has_object_permission(request, obj, None)
        return not_anonymous and request.user.pk in distinct_users

    def error(self, request, obj):
        msg = ("You don't have access to this URL resource, because {} "
               "prevented it".format(obj.path))
        raise Http404(msg)


class GroupRequired(object):
    __slots__ = ()
    def has_object_permission(self, request, obj, view):
        grps = obj.groupaccessrestriction_set.values_list('group_id', flat=True)
        distinct_groups = frozenset(grps)
        if not distinct_groups:
            return True
        is_auth = IsAuthenticated().has_object_permission(request, obj, None)
        if not is_auth:
            return False
        user_groups = frozenset(request.user.groups.values_list('pk', flat=True))
        intersection = grps & user_groups
        return len(intersection) > 0

    def error(self, request, obj):
        raise Http404("You don't have access to this URL resource "
                      "because of your groups")

class RedirectRequired(object):
    __slots__ = ()
    def has_object_permission(self, request, obj, view):
        try:
            target = obj.urlredirect
            return True
        except ObjectDoesNotExist:
            # no redirect exists, so it's ... maybe bad? IDK.
            return False

    def response(self, request, obj):
        return redirect(obj.urlredirect.get_absolute_url())


class PublishedRequired(object):
    __slots__ = ()
    def has_object_permission(self, request, obj, view):
        try:
            publishing_status = obj.urlvisible
        except ObjectDoesNotExist:
            # implicitly published because no URL prevents it.
            return True
        return publishing_status.is_published # exists, may be published.
    
    def error(self, request, obj):
        raise Http404("This URL is not published")
