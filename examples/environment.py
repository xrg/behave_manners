

from behave_manners.site import WebSite


def before_all(context):
    context.site = WebSite()


def before_scenario(context, scenario):
    print "before scenario hook"
    context.site.launch_browser(context)

def after_all(context):
    pass
    print "after all hook"


