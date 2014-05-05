from django.core.exceptions import ObjectDoesNotExist

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

        
class UserRequired(object):
    __slots__ = ()
    def has_object_permission(self, request, obj, view):
        users = obj.useraccessrestriction_set.values_list('user_id', flat=True)
        distinct_users = frozenset(users)
        not_anonymous = IsAuthenticated().has_object_permission(request, obj, None)
        return not_anonymous and request.user.pk in distinct_users
