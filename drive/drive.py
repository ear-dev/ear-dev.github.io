'''
What:
  This file can be used to drive a Sparrow automatically.
  It runs forever, with the option of alternating, visiting all the sites in a site list between sparrow and chromiumlike modes

How:
  You will need to "pip install -r requirements.txt"
  Put Chromedriver (https://sites.google.com/a/chromium.org/chromedriver/downloads) on your PATH

  You will want to run from a directory that includes:
     1) selenium_methods.py file found in git at IHS/automation/lift_acceptance_tests/steps
     2) your version of config.json
     3) you can put the chromedriver.exe in here for convenience
     4) you can put your sitelist.txt file here for convenience, or you can point to a remote sitelist in the config
     5) you can put ublock_origin.crx here if you want to use ublock. It can be found in IHS/automation/tools

  The json config file contains all information for the drive.py

  Usage: python drive.py -c config.json

  Or, to use a remote config file, then pass the following config.json at the command line

  config.json ex:
  {
    "remote_config_file_location": "http://bizzybyster.github.io/drive/configs/peter/config.json",
  }

'''

import time
import urllib2
import datetime
import os, sys, shutil
from selenium import webdriver
from selenium.webdriver.chrome import service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
import argparse
import logging
import json
import subprocess

try:
    import selenium_methods
except:
    # building pythonpath
    sep = os.sep
    path = sep.join(os.path.realpath(__file__).split(sep)[0:-2])
    sys.path.append(path)
    from lift_acceptance_tests.steps import selenium_methods

USR_AGENT_OSX = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/%s Safari/537.36"
USR_AGENT_WIN = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/%s Safari/537.36"
USR_AGENT_LINUX = "??"
WINDOWS_SPARROW_LOCATION = 'C:\\Users\\viasat\\AppData\\Local\\ViaSat\\Sparrow\\Application\\sparrow.exe'
MAC_SPARROW_LOCATION = '/Applications/Sparrow.app/Contents/MacOS/Sparrow'

class SparrowDriver(object):

    def __init__(self):
        self.stats = {}
        self.get_command_line()

        if os.path.exists(self.json_config_file) is False:
            print("Error, json config file not found")
            sys.exit(1)

        with open(self.json_config_file) as fl:
            json_data = json.load(fl)

        # Check for a remote config file
        self.remote_config_file = json_data.get('remote_config_file_location')
        if self.remote_config_file:
            json_data = self.load_remote_config()

        self.service = service.Service('chromedriver')

        # Read the config file; set attributes
        self.json_config_parser(json_data)

        self.test_start_time = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

    def load_remote_config(self):

        print "Using remote config file at: %s" % self.remote_config_file
        json_data = json.load(urllib2.urlopen(self.remote_config_file))

        # Check the local config for any override values. test_label_prefix is a good example...
        with open(self.json_config_file) as fl:
            possible_overrides = json.load(fl)

        for key, value in possible_overrides.iteritems():
            if key != 'remote_config_file_location':
                json_data[key] = value

        return json_data

    def get_command_line(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--config', required=True, help='path to the configuration directory, which contains json config')

        args = parser.parse_args()

        self.json_config_file = args.config

    def json_config_parser(self, json_data):
        '''Parses the config.json file and sets attributes that will eventually be cmd switches and options passed to selenium'''

        logging_file = json_data.get('log_file', 'drive_log')
        log_level = json_data.get('log_level', 'info')

        if log_level.lower() == 'debug':
            logging_level = logging.DEBUG
        if log_level.lower() == 'warning':
            logging_level = logging.WARNING
        if log_level.lower() == 'info':
            logging_level = logging.INFO
        if log_level.lower() == 'error':
            logging_level = logging.ERROR

        logging.getLogger('').handlers = []   #remove any existing handlers

        logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', filename=logging_file, level=logging_level)

        # set up logging to console
        if json_data.get('log_to_console', False):
            console = logging.StreamHandler()
            console.setLevel(logging_level)
            formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
            console.setFormatter(formatter)
            logging.getLogger('').addHandler(console)

        # Discover chromium version and set user agent for use in chromiumlike mode
        if 'darwin' in sys.platform:
            self.binary_location = json_data.get('sparrow_location_mac',
                MAC_SPARROW_LOCATION)
            p = subprocess.Popen([self.binary_location, '--version'], stdout=subprocess.PIPE)
            if p is None:
                logging.info("Unable to open Sparrow at : %s" % self.binary_location)
                sys.exit(1)
            out, err = p.communicate()
            self.chromium_version = out.strip().split()[1]
            self.user_agent = USR_AGENT_OSX % self.chromium_version

        elif 'win' in sys.platform:
            self.binary_location = json_data.get('sparrow_location_windows',
                WINDOWS_SPARROW_LOCATION)
            
            cmd = ['wmic', 'datafile', 'where', r'name="%s"' % self.binary_location.replace('\\', '\\\\'), 'get', 'Version']
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p is None:
                logging.info("Unable to open Sparrow at : %s" % self.binary_location)
                sys.exit(1)
            out, err = p.communicate()
            self.chromium_version = out.split()[1]
            self.user_agent = USR_AGENT_WIN % self.chromium_version

        self.sitelist_file = json_data.get('sitelist_file')
        if self.sitelist_file.lower().startswith('http'):
            self.sitelist = urllib2.urlopen(self.sitelist_file).read().split("\n")

        elif os.path.exists(self.sitelist_file):
            self.sitelist = open(self.sitelist_file).read().split('\n')

        else:
            logging.info("sitelist: %s not found, exiting" % self.sitelist_file)
            logging.info("Please modify the sitelist entry in %s" % self.json_config_file)
            sys.exit(1)

        # Add fast.com to extract download speed.  Will be attached to the hyperlink template for analysis later.
        if json_data.get('poll_download_speed'):
            self.sitelist = ['https://fast.com/'] + self.sitelist
        logging.info("Using sitelist: %s" % self.sitelist_file)

        self.test_label_prefix = json_data.get('test_label_prefix')
        self.sparrow_only_switches = json_data.get('sparrow_only_switches', '')
        self.common_switches = json_data.get('common_switches', '')

        self.alternate_sparrow_chromium = json_data.get('alternate_sparrow_chromiumlike', False)
        self.alternate_warm_cold_cache = json_data.get('alternate_warm_cold_cache', False)

        if self.alternate_sparrow_chromium:
            self.chromiumlike_user_data_dir = os.path.dirname(os.path.realpath(__file__)) + '/chromiumlike_user_data'
        self.sparrow_user_data_dir = os.path.dirname(os.path.realpath(__file__)) + '/sparrow_user_data'

        self.save_screenshots = json_data.get('save_screenshots', False)
        self.ublock_path = json_data.get('ublock_path')

    def add_options(self, chromiumlike, cache_state):
        ''' Sets a bunch of cmd switches and options passed to selenium'''

        mode = "chromiumlike" if chromiumlike else "sparrow"

        driver_options = Options()

        # Field Trial
        if chromiumlike:
            driver_options.add_argument('--sparrow-force-fieldtrial=chromiumlike')
            driver_options.add_argument('--user-agent=%s' % self.user_agent)
            driver_options.add_argument('--user-data-dir=%s' % self.chromiumlike_user_data_dir)

        else:
            driver_options.add_argument('--sparrow-force-fieldtrial')
            driver_options.add_argument('--user-data-dir=%s' % self.sparrow_user_data_dir)
            for switch in self.sparrow_only_switches:
                driver_options.add_argument(switch)
                logging.debug("Adding switch to sparrow only: %s" % switch)

        # Passed from config file
        for switch in self.common_switches:
            driver_options.add_argument(switch)
            logging.debug("Adding switch: %s" % switch)

        if self.ublock_path:
            if not os.path.exists(self.ublock_path):
                print("Error, ublock crx file not found.")
                sys.exit(1)
                
            driver_options.add_extension(self.ublock_path)

        # Test label
        test_label_entry = "--beer-test-label=%s-%s-%s-%s-%s-%s" % (self.test_label_prefix, self.chromium_version,
                                                                    sys.platform, mode, cache_state, self.test_start_time)
        driver_options.add_argument(test_label_entry)
        logging.info(test_label_entry)

        driver_options.binary_location = self.binary_location
        driver_options.to_capabilities()['loggingPrefs'] = { 'browser':'ALL' }

        return driver_options

    def visit_sites(self, chromiumlike, cache_state):

        driver_options = self.add_options(chromiumlike, cache_state)
        selenium_methods.stop_sparrow()

        # launch sparrow and initial tabs
        remote, beerstatus_tab, content_tab = selenium_methods.start_remote(self.service.service_url, driver_options)

        # Used to verify that the current beer is unique and new
        beer_status_dict = {}
        for site in self.sitelist:
            site = site.strip()
            beer_status_dict[site] = None

        self.stats['sites'] = 0
        self.download_speed = None
        for site in self.sitelist:
            if not site:
                continue

            site = site.strip()

            logging.info(site)

            try:
                remote.switch_to_window(content_tab)
                nav_start_time = time.time()

                if site == 'https://fast.com/':
                    selenium_methods.load_url(site, remote)
                    self.download_speed = selenium_methods.extract_value_from_page(remote, 'speed-value')
                    continue

                else:
                    selenium_methods.load_on_hover(site, remote, speed_value=self.download_speed)

                try:
                    title = remote.find_element_by_tag_name('title').get_property('text')
                    title.decode('ascii')

                    # Screenshot handling if configured
                    # Save screenshot only if title present to prevent hang in some cases
                    if self.save_screenshots:
                        if title != 'No title':
                            screenshot_path = './screenshots/' + site.replace(':','_').replace('/', '_') + '.png'
                            remote.save_screenshot(screenshot_path)

                except UnicodeDecodeError:
                    title = 'title is not ascii-encoded'
                    logging.warning(title)
                except UnicodeEncodeError:
                    title = 'title is not ascii-encoded'
                    logging.warning(title)
                except NoSuchElementException:
                    title = 'no title because no such element'
                    logging.warning(title)
                except WebDriverException:
                    title = 'no title b/c of exception'
                    logging.warning(title)

                remote.switch_to_window(beerstatus_tab)

            except TimeoutException as e:
                logging.warning("Selenium exception caught: %s" % str(e))
                if 'timeout_errors' not in self.stats:
                    self.stats['timeout_errors'] = 0
                self.stats['timeout_errors'] += 1
                remote.quit()
                remote, beerstatus_tab, content_tab = selenium_methods.start_remote(self.service.service_url, driver_options)
                continue
            except Exception as e:
                print("Selenium exception caught: %s" % str(e))
                logging.warning("Selenium exception caught: %s" % str(e))
                if 'driver_exceptions' not in self.stats:
                    self.stats['driver_exceptions'] = 0
                if 'session deleted because of page crash' in str(e):
                    if 'tab_crash_exceptions' not in self.stats:
                        self.stats['tab_crash_exceptions'] = 0
                    self.stats['tab_crash_exceptions'] += 1
                self.stats['driver_exceptions'] += 1
                remote.quit()
                remote, beerstatus_tab, content_tab = selenium_methods.start_remote(self.service.service_url, driver_options)
                continue

            self.stats['sites'] += 1
            if 'total' not in self.stats:
                self.stats['total'] = 0
            self.stats['total'] += 1
            nav_done_time = time.time()
            self.stats['time'] = nav_done_time-nav_start_time

            # Wait up to 40 seconds for beer ack
            num_tries = 40
            trys = 0
            while (trys < num_tries):
                remote.get("sparrow://beerstatus")
                if selenium_methods.check_beer_status(site, beer_status_dict, remote):
                    break

                trys += 1
                time.sleep(1)

            self.stats['waiting_for_ack'] = time.time()-nav_done_time
            logging.info('\'%s\', stats: %s' % (title, str(self.stats)))

            if trys == num_tries:
                print("No beer ack recieved for %s" % site)

        remote.quit()

    def run_service(self):

        self.service.start()

        self.stats['total'] = 0

        if self.save_screenshots:
            if not os.path.exists('./screenshots'):
                os.mkdir( './screenshots', 0755 );

        # Loop forever togging between sparrow and chromiumlike modes if alternate_sparrow_chromium = True
        # Alternate cold and warm cache between runs through the list
        clear_cache = True
        chromiumlike_mode = False
        mode = 'sparrow'
        while True:
            if clear_cache:
                user_data = self.chromiumlike_user_data_dir if chromiumlike_mode else self.sparrow_user_data_dir
                logging.info("Removing user data dir: %s " % user_data)
                shutil.rmtree(user_data, ignore_errors=True)

                self.visit_sites(chromiumlike_mode, "cold")

                if self.alternate_sparrow_chromium:
                    chromiumlike_mode = not chromiumlike_mode
                    mode = "chromiumlike" if chromiumlike_mode else "sparrow"

                    user_data = self.chromiumlike_user_data_dir if chromiumlike_mode else self.sparrow_user_data_dir
                    logging.info("Removing user data dir: %s now" % user_data)
                    shutil.rmtree(user_data, ignore_errors=True)

                    logging.info("Starting cold cache run with %s now" % mode)
                    self.visit_sites(chromiumlike_mode, "cold")

            else:
                logging.info("Starting warm cache run with %s now.." % mode)
                self.visit_sites(chromiumlike_mode, "warm")

                if self.alternate_sparrow_chromium:
                    chromiumlike_mode = not chromiumlike_mode
                    mode = "chromiumlike" if chromiumlike_mode else "sparrow"

                    logging.info("Starting warm cache run with %s now" % mode)
                    self.visit_sites(chromiumlike_mode, "warm")

            clear_cache = not clear_cache if self.alternate_warm_cold_cache else False
            if self.alternate_sparrow_chromium:
                chromiumlike_mode = not chromiumlike_mode
                mode = "chromiumlike" if chromiumlike_mode else "sparrow"

    #################################

            # If remote config, check the file for any changes
            if self.remote_config_file:
                message_str = "Loading remote config file again from %s" % self.remote_config_file
                logging.info(message_str)
                try:
                    json_data = self.load_remote_config()
                    logging.info(json_data)
                    # Set new config values to be run till next iteration
                    self.json_config_parser(json_data)
                    if not self.alternate_sparrow_chromium:
                        chromiumlike_mode = False
                        mode = "sparrow"
                    if not self.alternate_warm_cold_cache:
                        clear_cache = False
                except:
                    message_str = "Failed to load remote config at %s." % self.remote_config_file
                    logging.info(message_str)


    def clean_chromedriver_process(self):
        '''
        Will kill chromedriver process if exists
        otherwise running process might cause problems
        Not supported under cygwin, so need to put it in try /except block
        '''

        import psutil

        for proc in psutil.process_iter():
            if proc.name() == 'chromedriver.exe':
                proc.kill()


if __name__ == '__main__':
    sdrv = SparrowDriver()

    try:
        sdrv.clean_chromedriver_process()
    except:
        pass
    sdrv.run_service()

