#!/usr/bin/python

# Copyright 2014 Google Inc. All Rights Reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time
import urllib2

from utils import command_executer
from utils import logger
from utils import buildbot_json

SLEEP_TIME = 600  # 10 minutes; time between polling of buildbot.
TIME_OUT =  18000 # Decide the build is dead or will never finish
                  # after this time (5 hours).

"""Utilities for launching and accessing ChromeOS buildbots."""

def ParseReportLog (url, build):
    """
    Scrape the trybot image name off the Reports log page.

    This takes the URL for a trybot Reports Stage web page,
    and a trybot build type, such as 'daisy-release'.  It
    opens the web page and parses it looking for the trybot
    artifact name (e.g. something like
    'trybot-daisy-release/R40-6394.0.0-b1389'). It returns the
    artifact name, if found.
    """
    trybot_image = ""
    url += "/text"
    newurl = url.replace ("uberchromegw", "chromegw")
    webpage = urllib2.urlopen(newurl)
    data = webpage.read()
    lines = data.split('\n')
    for l in lines:
      if l.find("Artifacts") and l.find("trybot"):
        trybot_name = "trybot-%s" % build
        start_pos = l.find(trybot_name)
        end_pos = l.find("@https://storage")
        trybot_image = l[start_pos:end_pos]

    return trybot_image


def GetBuildData (buildbot_queue, build_id):
    """
    Find the Reports stage web page for a trybot build.

    This takes the name of a buildbot_queue, such as 'daisy-release'
    and a build id (the build number), and uses the json buildbot api to
    find the Reports stage web page for that build, if it exists.
    """
    builder = buildbot_json.Buildbot(
      "http://chromegw/p/tryserver.chromiumos/").builders[buildbot_queue]
    build_data = builder.builds[build_id].data
    logs = build_data["logs"]
    for l in logs:
      fname = l[1]
      if "steps/Report/" in fname:
        return fname

    return ""


def FindBuildRecordFromLog(description, log_info):
    """
    Find the right build record in the build logs.

    Get the first build record from build log with a reason field
    that matches 'description'. ('description' is a special tag we
    created when we launched the buildbot, so we could find it at this
    point.)
    """

    current_line = 1
    while current_line < len(log_info):
      my_dict = {}
      # Read all the lines from one "Build" to the next into my_dict
      while True:
        key = log_info[current_line].split(":")[0].strip()
        value = log_info[current_line].split(":", 1)[1].strip()
        my_dict[key] = value
        current_line += 1
        if "Build" in key or current_line == len(log_info):
          break
      try:
        # Check to see of the build record is the right one.
        if str(description) in my_dict["reason"]:
          # We found a match; we're done.
          return my_dict
      except:
        print "reason is not in dictionary: '%s'" % repr(my_dict)
      else:
        # Keep going.
        continue

    # We hit the bottom of the log without a match.
    return {}


def GetBuildInfo(file_dir):
    """
    Get all the build records for the trybot builds.

    file_dir is the toolchain_utils directory.
    """
    ce = command_executer.GetCommandExecuter()
    commands = ("{0}/utils/buildbot_json.py builds "
                "http://chromegw/p/tryserver.chromiumos/"
                .format(file_dir))

    _, buildinfo, _ = ce.RunCommand(commands, return_output=True,
                                    print_to_console=False)
    build_log = buildinfo.splitlines()
    return build_log


def GetTrybotImage(chromeos_root, buildbot_name, patch_list, build_tag):
    """
    Launch buildbot and get resulting trybot artifact name.

    This function launches a buildbot with the appropriate flags to
    build the test ChromeOS image, with the current ToT mobile compiler.  It
    checks every 10 minutes to see if the trybot has finished.  When the trybot
    has finished, it parses the resulting report logs to find the trybot
    artifact (if one was created), and returns that artifact name.

    chromeos_root is the path to the ChromeOS root, needed for finding chromite
    and launching the buildbot.

    buildbot_name is the name of the buildbot queue, such as lumpy-release or
    daisy-paladin.

    patch_list a python list of the patches, if any, for the buildbot to use.

    build_tag is a (unique) string to be used to look up the buildbot results
    from among all the build records.
    """
    ce = command_executer.GetCommandExecuter()
    cbuildbot_path = os.path.join(chromeos_root, "chromite/cbuildbot")
    base_dir = os.getcwd()
    patch_arg = ""
    if patch_list:
      patch_arg = "-g "
      for p in patch_list:
        patch_arg = patch_arg + " " + repr(p)
    branch = "master"
    os.chdir(cbuildbot_path)

    # Launch buildbot with appropriate flags.
    build = buildbot_name
    description = build_tag
    command = ("./cbuildbot --remote --nochromesdk --notests %s %s"
               " --remote-description=%s"
               " --chrome_rev=tot" % (patch_arg, build, description))
    ce.RunCommand(command)
    os.chdir(base_dir)

    build_id = 0
    # Wait for  buildbot to finish running (check every 10 minutes)
    done = False
    running_time = 0
    while not done:
      done = True
      build_info = GetBuildInfo(base_dir)
      if not build_info:
        logger.GetLogger().LogFatal("Unable to get build logs for target %s"
                                    % build)

      data_dict = FindBuildRecordFromLog(description, build_info)
      if not data_dict:
        logger.GetLogger().LogFatal("Unable to find build record for trybot %s"
                                    % description)

      if "True" in data_dict["completed"]:
        build_id = data_dict["number"]
      else:
        done = False

      if not done:
        logger.GetLogger().LogOutput("{0} minutes passed.".format(
          running_time / 60))
        logger.GetLogger().LogOutput("Sleeping {0} seconds.".format(SLEEP_TIME))
        time.sleep(SLEEP_TIME)
        running_time += SLEEP_TIME
        if running_time > TIME_OUT:
            done = True

    trybot_image = ""
    # Buildbot has finished. Look for the log and the trybot image.
    if build_id:
      log_name = GetBuildData(build, build_id)
      if log_name:
        trybot_image = ParseReportLog(log_name, build)

    return trybot_image
