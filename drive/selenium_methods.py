##############################################################################
#
#       Copyright 2017 ViaSat, Inc.
#
#        All rights reserved.  The source may not be copied, transferred,
#        modified or otherwise manipulated without the expressed written
#        authorization of the copyright holder.
#
##############################################################################

import logging
import os
import sys
import time
import uuid
try:
    import common_utils
except:
    pass

from multiprocessing.dummy import Pool as ThreadPool
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

import subprocess
from subprocess import CalledProcessError

WEBDRIVER_LOC = {'windows': 'C:\\chromedriver\\chromedriver.exe',
                 'mac': '',
                 'linux': ''}

# Used to drive sparrow with 'on hover' when indicated in the feature file
HYPERLINK_TEMPLATE_URL = "http://bizzbyster.github.io/sitelists/hyperlink_template.html"
HOVER_TIME = 0.5

def initializeCpes(context, browser_name):
    context.common.cpeInit(browser_name)
    return True

def runWebdriverMultithreaded(context, op_sys, browser_list):

    def callSelenium(args):
        context = args[0]
        browser = args[1]
        os = args[2]

        runWebdriver(context, browser, os)

    args_list = []
    for browser_name in browser_list:
        args_list.append((context, browser_name, op_sys))
        logging.info("running selenium webdriver test on %s now.." % browser_name)

    pool = ThreadPool(len(browser_list))
    results = pool.map(callSelenium, args_list)

    pool.close()
    pool.join()

    return True

def runWebdriverWithTwoCpes(context, op_sys, browser1, browser2):
    browser_list = [browser1, browser2]
    return runWebdriverMultithreaded(context, op_sys=op_sys, browser_list=browser_list)

def runWebdriver(context, browser_name, op_sys):

    browser_dict = context.common.sparrowControllersDict.get(browser_name)
    cpe_ip = browser_dict.get('ip')

    if 'chromiumlike' not in browser_name:
        sparrow_version_info = browser_dict['controller'].getVersionInfo(skipVerifyingFlag=True)
        # sparrow_buildnum is inclulded in the test label
        sparrow_buildnum = sparrow_version_info.sparrowBuildnum
        logging.info("Sparrow buildnum on %s is %s" % (cpe_ip, sparrow_buildnum))
    else:
        sparrow_buildnum = 'chromiumlike'

    cpe_location = browser_dict.get('location')
    logging.info('Using cpe locastion %s for this test...' % cpe_location)

    logging.info("setting test label for test running on %s now..." % cpe_ip)
    test_name = context.scenario.name.replace(' ', '')
    # Add timestamp and either lift name or sparrow buildnum to test label
    label_identifier = context.common.liftName if context.common.liftName else sparrow_buildnum
    test_label = common_utils.createTestLabel(test_name, label_identifier)

    # Used by some analysis steps
    context.common.testIds[browser_name]['test_label'] = test_label

    results = []
    for row in context.table:
        try:
            hover = row['hover'].lower() == 'true'
        except:
            hover = False

        cmdSwitches = generateCmdSwitches(context, row, test_name, browser_name, browser_dict)
        context.listIterations = int(row['iterations'])
        context.sitelistFileName = row['urllist']
        context.urlListFile = os.path.join(context.common.sitelistDir, context.sitelistFileName)

        results.append(runSelenium(context=context, browser_name=browser_name,
                                   browser_dict=browser_dict,
                                   cpeLocation=cpe_location,
                                   cmdSwitches=cmdSwitches, op_sys=op_sys,
                                   cache_state=row['cacheState'],
                                   hover=hover))

    return False if not any(results) else True

def generateCmdSwitches(context, row, test_name, browser_name, browser_dict=None):
    cmdSwitches = []
    try:
        for s in row['cmdSwitch'].split():
            cmdSwitches.append(s)
    except:
        logging.info("no command switch passed from feature file...")

    # using testname + liftName + uid for now.
    # .split('.') in this case removes the prepended outline examples portion of the test name and uses the examples name from the feature file
    # ex: 'verifylikelyneededby--@1.1likelyneededby-eartest-001' becomes '1likelyneededby-eartest-001'

    lift_name = context.common.liftName if context.common.liftName else 'prod'
    scope_prepend = test_name.lower().split('.')
    if len(scope_prepend) > 1:
        context.common.testIds[browser_name]['scope'] = '-'.join(['test', scope_prepend[1][1:], lift_name, str(uuid.uuid4().fields[-1])[:5]])
    else:
        context.common.testIds[browser_name]['scope'] = '-'.join(['test', scope_prepend[0], lift_name, str(uuid.uuid4().fields[-1])[:5]])

    cmdSwitches.append('--hinting-scope=' + context.common.testIds[browser_name].get('scope'))

    # Some cmdSwitches passed through behave are only for sparrow with features enabled
    if "chromiumlike" in browser_name.lower():
        browser_version_info = browser_dict['controller'].getVersionInfo(skipVerifyingFlag=True)
        chromium_version = browser_version_info.chromiumVersion
        ip = browser_dict.get('ip')
            # sparrow_buildnum is inclulded in the test label
        logging.info("Setting chromiumlike cmd switches on %s now. Chromium Version is %s" % (ip, chromium_version))

        cmdSwitches.append('--sparrow-force-fieldtrial=chromiumlike')
        cmdSwitches.append('--user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/%s Safari/537.36"' % chromium_version)
    else:
        cmdSwitches.append('--ihs-hint-url=%s' % context.common.ihsGatewayUrl + '/hint')
        cmdSwitches.append('--sparrow-force-fieldtrial') # disables sparrow field trials

        if not [switch for switch in cmdSwitches if '--viasat-hint-prerequest=' in switch]:
            cmdSwitches.append('--viasat-hint-prerequest=http://www.google.com/')

    cmdSwitches.append('--beer-test-label=' + context.common.testIds[browser_name].get('test_label'))
    cmdSwitches.append('--ihs-beer-url=%s' %  context.common.ihsGatewayUrl + '/feedback')
    cmdSwitches.append('--omaha-server-url=%s' % context.common.environmentConfig.environment['omaha'])
    cmdSwitches.append('--request-beer-ack')

    return cmdSwitches

def runSelenium(context, browser_name, browser_dict, cpeLocation, cmdSwitches, op_sys, cache_state, hover=False):
    sparrow_controller = browser_dict.get('controller')
    cpe_ip = browser_dict.get('ip')

    is_windows = op_sys == 'windows'
    sparrow_controller.stopSparrow()

    # Cleanup leftover .dat files from --bb-on-beer; hopefully this is temporary, waiting on sparrow fix
    sparrow_controller.removeLeftoverBBs()

    if not sparrow_controller.startWebdriver(exe_loc=WEBDRIVER_LOC[op_sys], whitelist_ip=context.common.jenkinsIp):
        return False

    driver_options = Options()
    driver_options.binary_location = sparrow_controller.getSparrowFullPath(op_sys)

    # Account for browser cache state
    user_data_warm = sparrow_controller.getSparrowUserDataWarmPath(op_sys)
    if cache_state.lower() == 'warm':
        driver_options.add_argument('--user-data-dir='+user_data_warm)
        if not sparrow_controller.removeDir(dir_path=user_data_warm):
            return False
        # Initialize new user data dir
        remote, beerstatus_tab, content_tab = start_remote(cpeLocation, driver_options, sparrow_controller)
        load_url("http://www.google.com", remote)
        time.sleep(20)
        try:
            remote.quit()
        except Exception as e:
            logging.exception("Selenium exception caught quiting remote after iteration on cpe %s" % cpe_ip)

    with open(context.urlListFile) as f:
        context.sitelist = f.read().split('\n')

    for s in cmdSwitches:
        driver_options.add_argument(s)
    driver_options.add_experimental_option("excludeSwitches", ["ignore-certificate-errors"])

    # Values used later in analysis
    context.urlListLen = len(context.sitelist)
    context.numClicksTotal = context.listIterations * context.urlListLen
    context.numClicksPerSite = context.listIterations

    logging.info("running webdriver test on %s with sparrow switches: %s now.." % (cpe_ip, "; ".join(cmdSwitches)))
    logging.info("Running selenium webdriver on %s with sitelist: %s" % (cpe_ip, str(context.sitelist)))

    # k = url, v = beerID ; used to verify that the current beer is unique and new
    beer_status_dict = {}
    # initialize
    for site in context.sitelist:
        beer_status_dict[site] = None

    # Pageloads happen here
    site_count = 1
    for i in range(context.listIterations):
        try:
            remote, beerstatus_tab, content_tab = start_remote(cpeLocation, driver_options, sparrow_controller)
            for site in context.sitelist:
                try:
                    if not site:
                        continue

                    logging.info('Loading url: %s on cpe: %s' % (site, cpe_ip))
                    remote.switch_to_window(content_tab)

                    if site[0:15] == 'sparrow://crash':
                        res = load_url_and_crash(site, remote)
                        if cache_state.lower() == 'warm':
                            sparrow_controller.removeDir(dir_path=user_data_warm)
                        return res

                    elif hover:
                        load_on_hover(site, remote)
                    else:
                        load_url(site, remote)

                    logging.info('%s loaded successfully, number of sites loaded on %s: %s' % (site, cpe_ip, site_count))
                    site_count += 1

                    remote.switch_to_window(beerstatus_tab)
                    # Wait up to 20 seconds for beer ack
                    num_tries = 20
                    trys = 0
                    for i in range(num_tries):
                        load_url("sparrow://beerstatus/", remote)
                        if check_beer_status(site, beer_status_dict, remote):
                            break

                        trys += 1
                        time.sleep(1)

                    if trys == num_tries:
                        logging.info("No beer ack recieved for %s" % site)

                except Exception as e:
                    logging.exception("Selenium exception caught during site visit on cpe %s" % cpe_ip)
                    remote, beerstatus_tab, content_tab = start_remote(cpeLocation, driver_options, sparrow_controller)
                    continue

            # Need to quit between iterations in both warm and cold case in order to clean out hint cache
            try:
                remote.quit()
            except Exception as e:
                logging.exception("Selenium exception caught quiting remote after iteration on cpe %s" % cpe_ip)
            continue

        except Exception as e:
            logging.exception("Selenium exception caught during iteration on cpe %s" % cpe_ip)
            continue

    sparrow_controller.stopWebdriver()
    sparrow_controller.stopSparrow()
    # Clean up
    if cache_state.lower() == 'warm':
        sparrow_controller.removeDir(dir_path=user_data_warm)

    return True

def load_on_hover(url, remote, speed_value=None):
    # Add download speed to the hyperlink url for later analysis
    hyperlink = HYPERLINK_TEMPLATE_URL + '?speed_test=%s' % speed_value  if speed_value else HYPERLINK_TEMPLATE_URL

    remote.get(hyperlink)
    element = remote.find_element_by_id("put_hyperlink_here")
    remote.execute_script(
      "arguments[0].innerHTML = '<a href=\"" + url + "\">" + url + "</a>';", element)
    link_element = remote.find_element_by_link_text(url)
    actions = ActionChains(remote)
    actions.move_to_element(link_element)
    actions.perform()
    time.sleep(HOVER_TIME)
    actions.click(link_element)
    actions.perform()

def load_url(url, remote):
    try:
        remote.get(url)
        if url == 'https://fast.com/':
            time.sleep(20)

    except TimeoutException as e:
        logging.exception("Selenium exception caught.")

    return

def load_url_and_crash(url, remote):

    try:
        remote.get(url)
        # if we are here, we have not crash!
        logging.info("Sparrow did not crash, error")
        return False
    except:
        logging.info("Sparrow crashed as expected")

    return True

def extract_value_from_page(remote, element_id):
    element = remote.find_element_by_id(element_id)
    return element.text

def start_remote(cpe_location, driver_options, sparrow_controller=None):

    numtries = 1
    for i in range(10):
        try:
            remote = webdriver.Remote(cpe_location, driver_options.to_capabilities())
            #open two blank tabs to start, one for content, one for beer ack
            remote.execute_script("window.open('about:blank', 'sparrow://beerstatus');")
            all_tabs = remote.window_handles
            beerstatus_tab = all_tabs[0]
            content_tab = all_tabs[-1]

            remote.switch_to_window(beerstatus_tab)
            remote.get("sparrow://beerstatus/")
            break

        except Exception as e:
            logging.exception("Selenium exception caught restarting the remote on %s" % cpe_location)
            logging.info("Trying again to restart the remote on %s.  Numtries = %s" % (cpe_location, str(numtries)))
            numtries += 1
            if sparrow_controller is not None:
                sparrow_controller.stopSparrow()
            else:
                # Running with drive.py locally on a cpe
                stop_sparrow()

            continue

    return remote, beerstatus_tab, content_tab

def stop_sparrow():
    if "darwin" in sys.platform:
        cmd = ["pkill", "-9", "Sparrow"]

    elif "win" in sys.platform:
        cmd = ["taskkill", "/IM", "Sparrow.exe", "/F"]

    # Best effort, not checking return
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def check_beer_status(url, beer_status_dict, remote):

    try:
        beer_entries = remote.find_elements_by_class_name("component")
    except Exception as e:
        logging.exception("Exception caught during remote.find_elements_by_class_name.")
        return False

    # Examine each entry in the table.
    for beer in beer_entries:
        text = str(beer.text)
        if url in text:
            beer_dict = {}
            # Make dictionary out of the table entry
            for line in text.split('\n'):
                entry = line.split(':', 1)
                beer_dict[entry[0]] = entry[1].strip()

            acked = beer_dict.get('Acked')
            if acked == '-1':
                logging.info("Beer Ack is misconfigured, will not check for Ack.")
                return True
            elif acked == '0':
                logging.info("Sparrow did not receive beer ack for %s" % url)
                return True
            elif (acked == '1' and
                  beer_dict.get('BEER for url') == url and
                  beer_dict.get('GUID') != beer_status_dict[url]):

                beer_status_dict[url] = beer_dict['GUID']
                return True

        else:
            # Not the entry we are looking for.
            continue

    return False

