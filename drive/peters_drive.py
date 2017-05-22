'''
What:
  This file can be used to drive a Sparrow automatically.
  It runs forever alternating visiting all the sites in a site list between sparrow and chromiumlike modes
  It uses its own hinting scope which by default causes you to develop your own model and shunt beer to portico

How:
  You will need to pip install the libraries below
  And put Chromedriver (https://sites.google.com/a/chromium.org/chromedriver/downloads) on your PATH
  And change user, binary_location, and sitelist_url to your own if you do not want to use mine
    Note the mac default binary_location is /Applications/Sparrow.app/Contents/MacOS/Sparrow
  run "python drive.py"
'''

import time
import urllib2
import datetime
import os, sys, shutil
from selenium import webdriver
import selenium.webdriver.chrome.service as service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException, WebDriverException, NoSuchWindowException
from selenium.webdriver.common.action_chains import ActionChains

user = 'peter'
#binary_location= '/Users/pete/Git/src/out/Release/Sparrow.app/Contents/MacOS/Sparrow'
binary_location = '/Applications/Sparrow.app/Contents/MacOS/Sparrow'
if (sys.platform == 'win32'):
  binary_location = 'C:\\Users\\viasat\\AppData\\Local\\ViaSat\\Sparrow\\Application\\sparrow.exe'
sitelist_url = 'http://bizzbyster.github.io/sitelists/https.txt'
#sitelist_url = 'http://bizzbyster.github.io/sitelists/basic.txt'
#sitelist_url = 'http://bizzbyster.github.io/sitelists/top5_from_top200.txt'

def check_beer_status(url, beer_status_dict, remote):

    beer_entries = remote.find_elements_by_class_name("component")
    # Examine each entry in the table.
    for beer in beer_entries:
        text = str(beer.text)
        if url in text:
            # Populate the beer_dict from the sparrow://beerstatus entry
            beer_dict = {}
            for line in text.split('\n'):
                entry = line.split(':', 1)
                beer_dict[entry[0]] = entry[1].strip()

            acked = beer_dict.get('Acked')
            if acked == '-1':
                print("Beer Ack is misconfigured, will not check for Ack.")
                return True
            elif acked == '0':
                print("Sparrow did not receive beer ack for %s" % url)
                return True
            elif (acked == '1' and
                  beer_dict.get('GUID') != beer_status_dict[url]):
                beer_status_dict[url] = beer_dict['GUID']
                return True
        else:
            # Not the entry we are looking for.
            continue

    return False

def start_remote(url, capabilities):
  remote = webdriver.Remote(service.service_url, capabilities)
  remote.execute_script("window.open('about:blank', '_blank');")
  all_tabs = remote.window_handles
  beerstatus_tab = all_tabs[0]
  content_tab = all_tabs[-1]
  return remote, beerstatus_tab, content_tab

def visit_sites(service, total, test_settings):

  # Delete user data dir if coldcache
  cache = 'warm'
  if test_settings['cold_cache'][test_settings['mode']]:
    # delete the user-data-dir
    shutil.rmtree('./' + test_settings['mode'], ignore_errors=True)
    if not os.path.exists('./' + test_settings['mode']):
      os.mkdir( './' + test_settings['mode'], 0755 );
    cache = 'cold'

  # Set commandline options
  driver_options = Options()
  if test_settings['mode'] == 'chromiumlike':
    driver_options.add_argument('--sparrow-force-fieldtrial=chromiumlike')
    driver_options.add_argument('--user-agent=\"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2564.5647 Safari/537.36\"')
  else:
    driver_options.add_argument('--sparrow-force-fieldtrial')

  test_label = (sys.platform + '-' + user + '-' + test_settings['mode'] + '-' + cache + '-' +
    test_settings['start_time'])
  print "Starting a pass through the list test_label=" + test_label
  driver_options.add_argument('--beer-test-label=' + test_label)
  driver_options.add_argument('--user-data-dir=' +
      os.path.dirname(os.path.realpath(__file__)) + '/' + test_settings['mode'])
  driver_options.add_argument('--request-beer-ack')
  driver_options.add_argument('--hinting-scope=test' + user)
  driver_options.add_argument('--blackbox-on-beer')
  driver_options.add_argument('--enable-crash-upload')
  driver_options.add_argument('--omaha-server-url=https://omaha.overnight.ihs.viasat.io')
  driver_options.binary_location = binary_location

  capabilities = driver_options.to_capabilities()
  capabilities['loggingPrefs'] = { 'browser':'ALL' }

  # launch sparrow and initial tabs
  remote, beerstatus_tab, content_tab = start_remote(service.service_url, capabilities)

  # Used to verify that the current beer is unique and new
  beer_status_dict = {}
  for site in test_settings['site_list']:
    site = site.strip()
    beer_status_dict[site] = None
  stats['sites'] = 0
  for site in test_settings['site_list']:
    if not site:
      continue

    site = site.strip()

    print site,   # comma is intentional here as it suppresses the /n
    try:
      start_time = time.time()
      remote.switch_to_window(content_tab)
      remote.get("http://bizzbyster.github.io/sitelists/hyperlink_template.html")
      element = remote.find_element_by_id("put_hyperlink_here")
      remote.execute_script(
        "arguments[0].innerHTML = '<a href=\"" + site + "\">" + site + "</a>';", element)
      link_element = remote.find_element_by_link_text(site)
      actions = ActionChains(remote)
      actions.move_to_element(link_element)
      actions.perform()
      time.sleep(0.5)
      actions.click(link_element)
      actions.perform()
      try:
          title = remote.find_element_by_tag_name('title').get_property('text')
          title.decode('ascii')
      except UnicodeDecodeError:
          title = 'title is not ascii-encoded'
      except UnicodeEncodeError:
          title = 'title is not ascii-encoded'
      except NoSuchElementException:
          title = 'no title because no such element'
      except WebDriverException:
          title = 'no title b/c of exception'
      remote.switch_to_window(beerstatus_tab)
    except TimeoutException as e:
        print("Selenium exception caught: %s" % str(e))
        if 'timeout_errors' not in stats:
          stats['timeout_errors'] = 0
        stats['timeout_errors'] += 1
        remote.quit()
        remote, beerstatus_tab, content_tab = start_remote(service.service_url, capabilities)
        continue
    except Exception as e:
        print("Selenium exception caught: %s" % str(e))
        if 'driver_exceptions' not in stats:
          stats['driver_exceptions'] = 0
        stats['driver_exceptions'] += 1
        remote.quit()
        remote, beerstatus_tab, content_tab = start_remote(service.service_url, capabilities)
        continue

    stats['sites'] += 1
    if 'total' not in stats:
      stats['total'] = 0
    stats['total'] += 1
    done_time = time.time()
    stats['time'] = done_time-start_time

    # Wait up to 40 seconds for beer ack
    num_tries = 40
    trys = 0
    while (trys < num_tries):
        remote.get("sparrow://beerstatus")
        if check_beer_status(site, beer_status_dict, remote):
            break

        trys += 1
        time.sleep(1)

    stats['waiting_for_ack'] = time.time()-done_time
    print('\'%s\', stats: %s' % (title, str(stats)))

    if trys == num_tries:
        print("No beer ack recieved for %s" % site)
        remote.quit()
        remote, beerstatus_tab, content_tab = start_remote(service.service_url, capabilities)

  remote.quit()
  return total

service = service.Service('chromedriver')
service.start()
chromiumlike_mode = False

# Loop forever togging between sparrow and chromiumlike modes
stats = {}
stats['total'] = 0

# Start in sparrow cold cache
# then go to chromiumlike cold cache
# then sparrow warm cache
# then chromiumlike warm cache
# then repeat
test_settings = {}
test_settings['start_time'] = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
test_settings['mode'] = 'sparrow'
test_settings['cold_cache'] = {}
test_settings['cold_cache']['chromiumlike'] = True
test_settings['cold_cache']['sparrow'] = True
test_settings['site_list'] = urllib2.urlopen(sitelist_url).read().split("\n")
while True:
  visit_sites(service, stats, test_settings)

  if test_settings['mode'] == 'sparrow':
    test_settings['mode'] = 'chromiumlike'
    test_settings['cold_cache']['sparrow'] = not test_settings['cold_cache']['sparrow']
  elif test_settings['mode'] == 'chromiumlike':
    test_settings['mode'] = 'sparrow'
    test_settings['cold_cache']['chromiumlike'] = not test_settings['cold_cache']['chromiumlike']
