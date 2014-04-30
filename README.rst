===============
django-churlish
===============

A URLish way to handle enabling or locking down certain things.

Based around the idea that a URL represents, ideally, a namespace of children.

Allows putting in a URL's path component, then using middleware to do things
like mark the URL and it's children as unpublished, or needing authentication,
or redirecting, or whatever.

Goal is to end up with publishing, redirects, permissions etc all available
in database-efficient manner, with customisable exclusion zones
(ie: "never apply the middleware to /a/b/")
