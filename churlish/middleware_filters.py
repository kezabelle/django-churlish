from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import redirect

# Always use an RequestFailedTest subclass for the error condition, to
# avoid leaking that some part of the URL may be correct. eg, an error
# triggered by /a/ when visiting /a/this/is/purposefully/a/404/ should not
# reveal that some part of that URL is OK.


class RequestFailedTest(Http404): pass  # noqa


class IsAuthenticated(object):
    __slots__ = ()
    def test(self, request, obj, view):
        return request.user and request.user.is_authenticated()
    __call__ = test


class IsStaff(object):
    __slots__ = ()
    def test(self, request, obj, view):
        return request.user and request.user.is_staff
    __call__ = test


class IsAdmin(object):
    __slots__ = ()
    def test(self, request, obj, view):
        return request.user and request.user.is_superuser
    __call__ = test


class UserRoleRequired(object):
    __slots__ = ()
    def test(self, request, obj, view):
        try:
            access_required = obj.simpleaccessrestriction
        except ObjectDoesNotExist:
            # no restriction exists, so it's true for now.
            return None

        final = []
        if access_required.is_authenticated:
            final.append(
                IsAuthenticated().test(request, obj, None))
        if access_required.is_staff:
            final.append(IsStaff().test(request, obj, None))
        if access_required.is_superuser:
            final.append(IsAdmin().test(request, obj, None))
        return all(final)
    __call__ = test

    def error(self, request, obj, view):
        msg = ("You don't have access to this URL resource, because {} "
               "prevented it".format(obj.path))
        raise RequestFailedTest(msg)


class UserRequired(object):
    __slots__ = ()
    def test(self, request, obj, view):
        users = obj.useraccessrestriction_set.values_list('user_id', flat=True)
        distinct_users = frozenset(users)
        if not distinct_users:
            return None
        not_anonymous = IsAuthenticated().test(request, obj, None)
        return not_anonymous and request.user.pk in distinct_users
    __call__ = test

    def error(self, request, obj, view):
        msg = ("You don't have access to this URL resource, because {} "
               "prevented it".format(obj.path))
        raise RequestFailedTest(msg)


class GroupRequired(object):
    __slots__ = ()
    def test(self, request, obj, view):
        grps = obj.groupaccessrestriction_set.values_list('group_id',
                                                          flat=True)
        distinct_groups = frozenset(grps)
        if not distinct_groups:
            return None
        is_auth = IsAuthenticated().test(request, obj, None)
        if not is_auth:
            return False
        user_groups = frozenset(request.user.groups.values_list('pk',
                                flat=True))
        intersection = grps & user_groups
        return len(intersection) > 0
    __call__ = test

    def error(self, request, obj, view):
        raise RequestFailedTest("You don't have access to this URL resource "
                                "because of your groups")


class RedirectRequired(object):
    __slots__ = ()
    def test(self, request, obj, view):
        try:
            target = obj.urlredirect
            # True + success() means it'll get redirected.
            return True
        except ObjectDoesNotExist:
            return None
    __call__ = test

    def success(self, request, obj, view):
        return redirect(obj.urlredirect.get_absolute_url())


class PublishedRequired(object):
    __slots__ = ()
    def test(self, request, obj, view):
        try:
            publishing_status = obj.urlvisible
        except ObjectDoesNotExist:
            # implicitly published because no URL prevents it.
            return None
        return publishing_status.is_published  # exists, may be published.
    __call__ = test

    def error(self, request, obj, view):
        raise RequestFailedTest("This URL is not published")
