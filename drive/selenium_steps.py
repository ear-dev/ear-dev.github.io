##############################################################################
#
#       Copyright 2017 ViaSat, Inc.
#
#        All rights reserved.  The source may not be copied, transferred,
#        modified or otherwise manipulated without the expressed written
#        authorization of the copyright holder.
#
##############################################################################

import selenium_methods

@given('I initialize the cpe running "{browser_name}"')
def initializeCpes(context, browser_name):
    assert selenium_methods.initializeCpes(context, browser_name)

@when('I run selenium webdriver on "{op_sys}" with "{browser1}" and "{browser2}" concurrently')
def runWebdriverWithTwoCpes(context, op_sys, browser1, browser2):
    assert selenium_methods.runWebdriverWithTwoCpes(context, op_sys, browser1, browser2)

@when('I run selenium webdriver with "{browser_name}" on "{op_sys}"')
def runWebdriver(context, browser_name, op_sys):
    assert selenium_methods.runWebdriver(context, browser_name, op_sys)
