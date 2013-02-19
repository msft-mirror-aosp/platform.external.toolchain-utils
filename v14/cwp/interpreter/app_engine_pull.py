#!/usr/bin/python2.4
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Client to pull and opreport on samples from App Engine Server.

Samples are on the server, so this script first authenticates with a proper
@google.com account, then downloads a sample, unzips, and calls opreport on
the raw data.

  _Authenticate(): gets login information and returns an authorization token.
  _DownloadSamples(): downloads, unzips, opreport, and create est pbs.
  _IsFileNameValid(): check that .zip files won't overwrite crucial files.
  _GetServePage(): pulls /serve page from app engine server.
  _DownloadSampleFromServer(): downloads a local copy of a zipped sample.
  _DeleteSampleFromServer(): visits /del/$key to delete file from ae server.
  _SetupAndCallOpreport(): modifies samples and calls opreport.
  _GetImagePath(): get the dir to symbols folder.
  _ChecksForOpreport(): gets path for opreport and checks env variables.
  _ParseOpreport(): parses output of opreport.
  _ParseLine(): parses one line of opreport output.
  _RecordEstsToFile(): writes serialized pbs to a file to be processed later.
  _MakeDatabase(): creates sqlite db to be used for awp server.
  _ProcessLogAppend(): process an event stack trace pbs file to append to db.

TODO: Save downloaded samples in unique folders, and by specifying a flag, be
able to recreate db with those older samples.

Would be nice to create the server from another file and use this as more of
a library.

Add a flag, and a way to skip over anything related to oprofiled.
"""


__author__ = ("rharagutchi@google.com (Rodrigo Haragutchi)")


import cookielib
import getpass
import md5
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib
import urllib2
import zipfile

import profile_db_writer_append
from SymbolizeData import CreateESTs
from SymbolizeData import GetEncodedESTs

from google3.file.base import pywrapfile
from google3.file.base import pywraprecordio
from google3.file.base import recordio
from google3.monitoring.stacktrace.event_stack_trace_pb import EventStackTrace
from google3.perftools.gwp.database import dbwrapper
from google3.perftools.gwp.database import make_database
from google3.perftools.gwp.database import profile_db_writer
from google3.perftools.gwp.symbolization import symbolized_log
from google3.pyglib import app
from google3.pyglib import flags

#flags
FLAGS = flags.FLAGS
flags.DEFINE_string("symbols_dir", None,
                    "Dir holding symbols")
flags.DEFINE_string("server", "http://server1test.appspot.com/",
                    "URL that AWP server is running on")
flags.DEFINE_string("app_name", "server1test",
                    "Name of application on App Engine")
flags.DEFINE_string("output_dir", None,
                    "Dir to output temp files (which will be deleted "
                    "eventually) and database")
flags.DEFINE_string("profile_server_dir", None,
                    "Dir to instance of //perftools/gwp/database/"
                    "profile_server binary")
flags.DEFINE_boolean("forever", True, "Keep update db "
                     "and restarting awp server")
flags.DEFINE_integer("server_update_interval", 1800, "Time interval in between "
                     "restarts of the awp server")
flags.DEFINE_integer("ae_poll_interval", 60, "Time interval in between polls "
                     "of app engine server to check for new data")


def _ValidateArgs(fl):
  """Check for required arguments."""
  if not fl.symbols_dir:
    print "Must specify --symbols_dir"
    sys.exit(1)
  if not fl.output_dir:
    print "Must specify --output_dir"
    sys.exit(1)
  if not fl.profile_server_dir:
    print "Must specify --profile_server_dir"
    sys.exit(1)
  if not os.path.exists(fl.symbols_dir):
    print "Specified symbols_dir does not exist"
    sys.exit(1)
  if not os.path.exists(fl.output_dir):
    print "Specified output_dir does not exist"
    sys.exit(1)
  if not fl.profile_server_dir.endswith("profile_server"):
    print "Must point to a profile_server binary"
    sys.exit(1)
  if not os.path.exists(fl.profile_server_dir):
    print fl.profile_server_dir
    print "Specified profile_server binary does not exist"
    sys.exit(1)
  else:
    os.chdir(fl.output_dir)


def _Authenticate(server_name, app_name):
  """Gets credentials from user and attempts to retrieve an authorization token.

  Args:
    server_name: (string) url that the app engine code is living on
    app_name: (string) name of the app on app engine

  Returns:
    authtoken: (string) the authorization token that can be used to grab other
              pages that have been secured with login

  """
  if server_name.endswith("/"):
    server_name = server_name.rstrip("/")
  # grab username and password from user, must be @google.com
  username = raw_input("Email (must be an @google account): ")
  password = getpass.getpass("Password: ")

  # we use a cookie to authenticate with Google App Engine
  cookiejar = cookielib.LWPCookieJar()
  opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))
  urllib2.install_opener(opener)

  # get an AuthToken from Google accounts
  auth_uri = "https://www.google.com/accounts/ClientLogin"
  authreq_data = urllib.urlencode({"Email": username,
                                   "Passwd": password,
                                   "service": "ah",
                                   "source": app_name,
                                   "accountType": "HOSTED_OR_GOOGLE"})
  auth_req = urllib2.Request(auth_uri, data=authreq_data)
  # write over password for security purposes
  password = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
  try:
    auth_resp = urllib2.urlopen(auth_req)
  except urllib2.URLError:
    print "Error Logging In"
    return None
  auth_resp_body = auth_resp.read()
  # auth response includes several fields,
  # we're interested in the bit after Auth=
  auth_resp_dict = dict(x.split("=")
                        for x in auth_resp_body.split("\n") if x)
  authtoken = auth_resp_dict["Auth"]
  return authtoken


def _DownloadSamples(server_name, authtoken):
  """Download each sample, unzip and generate opreport.

  Args:
    server_name: (string) url that the app engine code is living on
    authtoken: (string) authorization token

  Returns:
    sample_count: (int) number of samples in the /serve page

  Notes:
    On the serve page, we are given all the information for the sample as well
    as the sample's key in the following format:
    key<div>date/time<div>build number<div>kernel version<div>id<div>md5</br>
    So we parse first by </br> then by <div> to get individual information.
  """
  if server_name.endswith("/"):
    server_name = server_name.rstrip("/")

  serve_page_string = _GetServePage(server_name, authtoken)
  if serve_page_string is None:
    print "Error getting Serve Page!"
    return 0
  sample_list = serve_page_string.split("</br>")
  sample_count = 0
  for sample in sample_list:
    if sample == "":
      return sample_count
    sample_info = sample.split("<div>")  # each item is separated by a '<div>'
    # e.g. (all one line) agtzZXJ2ZXIxdGVzdHIRCxIJRmlsZUVudHJ5GLzpBAw<div>
    # 2010-07-30 01:03:38.045936<div>passion-userdebug 2.2 FRF75 41082 test-keys
    # <div>2.6.32.9-27155-gfca96c3<div>924717304<div>
    # 2f0186df6f3bdac1469adb434ab214ca</br>
    sample_key = sample_info[0]
    # sample_info[1] is the time
    sample_build_num = sample_info[2]
    sample_kernel_vr = sample_info[3]
    sample_proc_info = sample_info[4]
    sample_phone_id = sample_info[5]
    sample_md5 = sample_info[6]
    _DownloadSampleFromServer(server_name, authtoken, sample_key)
    fh = open("sample.zip", "rb")
    if not sample_md5 == (md5.new(fh.read()).hexdigest()):
      # md5 was not the same, bad data. skip over
      print "md5 sum was not correct"
      sys.exit(1)
      continue
    try:
      z = zipfile.ZipFile(fh)
    except zipfile.error:
      print "Error opening downloaded zip file"
      # os.remove("sample.zip")
      _DeleteSampleFromServer(server_name, authtoken, sample_key)
      continue
    sample_number = "0"
    (arch_path, oprofile_event_dir) = _ChecksForOpreport()
     # in order to extract, we need to make the directories
    for name in z.namelist():
      directories = name.split("/")
      directory_name = ""
      for item in directories[1:len(directories)-1]:
        directory_name += item + "/"
        # each sample has a number value after it (e.g. sample35),
        # which we need for later
        if item.startswith("sample"):
          sample_number = item[len("sample")+1:]
      try:
        os.makedirs(directory_name)  # create directories
      except OSError:
        # check to make sure file is valid
        if _IsFileNameValid(item[1:]):
          outfile = open(name[1:], "wb")
          outfile.write(z.read(name))
          outfile.close()
      # extract and write the file in the .zip file
      outfile = open(name[1:], "wb")
      outfile.write(z.read(name))
      outfile.close()
    fh.close()
    image_path = _GetImagePath()
    _SetupAndCallOpreport(sample_number, image_path, arch_path,
                          oprofile_event_dir)
    parsed_report = _ParseOpreport()
    if parsed_report is None:
      shutil.rmtree("mnt")  # remove created directories
      os.remove("sample.zip")  # remove deleted .zip file
      os.remove("opreport_output")  # remove output from opreport
      _DeleteSampleFromServer(server_name, authtoken, sample_key)
      continue
    binaries = {}
    ests = CreateESTs(binaries, parsed_report, sample_build_num, 
                      sample_kernel_vr, sample_proc_info)
    
    encoded_ests_list = GetEncodedESTs(ests)    
    _RecordEstsToFile("slog%d" % (sample_count,), encoded_ests_list)
    sample_count += 1

    shutil.rmtree("mnt")  # remove created directories
    os.remove("sample.zip")  # remove deleted .zip file
    os.remove("opreport_output")  # remove output from opreport
    _DeleteSampleFromServer(server_name, authtoken, sample_key)

  return sample_count


def _IsFileNameValid(name):
  """Checks that the file we're about to write doesn't overwrite important data.

  Args:
    name: (string) The file name

  Returns:
    True if name is valid, False otherwise

  """
  if (name.find("..") != -1) or (name.startswith("/")):  # bad things
    error = "File has bad file names, check "
    error += "%ssample.zip" % FLAGS.output_dir
    print error
    return False
  return True


def _GetServePage(server_name, authtoken):
  """Opens the /serve page and returns the page's source file.

  Args:
    server_name: (string) url that the app engine code is living on
    authtoken: (string) authorization token

  Returns:
    read: (string) the serve's page text (including html tags)

  """
  serv_uri = server_name + "/serve"
  serv_args = {"continue": serv_uri, "auth": authtoken}
  full_serv_uri = server_name+"/_ah/login?%s" % (urllib.urlencode(serv_args))
  serv_req = urllib2.Request(full_serv_uri)
  while True:
    try:
      serv_resp = urllib2.urlopen(serv_req)
      break
    except urllib2.URLError:
      pass
  read = serv_resp.read()
  return read


def _DownloadSampleFromServer(server_name, authtoken, sample_key):
  """Opens a page with the sample key and downloads the .zip to current dir.

  Args:
    server_name: (string) url that the app engine code is living on
    authtoken: (string) authorization token
    sample_key: (string) key given by app engine that designates a file

  Returns:
    None

  """
  serv_uri = server_name + "/serve/" + sample_key
  serv_args = {"continue": serv_uri, "auth": authtoken}
  full_serv_uri = server_name+"/_ah/login?%s" % (urllib.urlencode(serv_args))
  serv_req = urllib2.Request(full_serv_uri)
  while True:
    try:
      serv_resp = urllib2.urlopen(serv_req)
      break
    except urllib2.URLError:
      pass
  f = open("sample.zip", "w+")
  f.write(serv_resp.read())
  f.close()


def _DeleteSampleFromServer(server_name, authtoken, sample_key):
  """Opens page with the sample key and signals app engine to delete that file.

    Args:
      server_name: (string) url that the app engine code is living on
      authtoken: (string) authorization token
      sample_key: (string) key given by app engine that designates a file

    Returns:
      None

  """
  serv_uri = server_name + "/del/" + sample_key
  serv_args = {}
  serv_args["continue"] = serv_uri
  serv_args["auth"] = authtoken
  full_serv_uri = server_name+"/_ah/login?%s" % (urllib.urlencode(serv_args))
  serv_req = urllib2.Request(full_serv_uri)
  while True:
    try:
      serv_resp = urllib2.urlopen(serv_req)
      break
    except urllib2.URLError:
      pass


def _SetupAndCallOpreport(sample_number, image_path, arch_path,
                          oprofile_event_dir):
  """Changes ABI of samples from ARM to x86_64 then calls opreport.

  Args:
    sample_number: (string) all samples coming from the phone are in individual
                  directories with sample + "number" (e.g. sample35)
    image_path: (string) path to dir that contains the symbols used by opreport
    arch_path: (string) architecture of the machine running script
    oprofile_event_dir: (string) directory to oprofile event directory

  Returns:
    None

  Note: All this code came from opimport_pull found in the Android source tree
  """
  # enter the destination directory
  os.chdir("mnt/sdcard/sentinel")
  stream = os.popen("find samples"+sample_number+" -type f -name \*all")

  # now all the sample files are on the host, we need to invoke opimport one 
  # at a time to convert the content from the ARM abi to x86 ABI

  # break the full filename into:
  # 1: leading dir: "raw_samples"
  # 2: intermediate dirs: "/blah/blah/blah"
  # 3: filename: e.g. "CPU_CYCLES.150000.0.all.all.all"
  pattern = re.compile("(^samples"+sample_number+")(.*)/(.*)$")
  for line in stream:
    match = pattern.search(line)
    # leading_dir = match.group(1)
    middle_part = match.group(2)
    file_name = match.group(3)

    directory = "samples" + middle_part

    # if multiple events are collected the directory could have been setup
    if not os.path.exists(directory):
      os.makedirs(directory)

    cmd = oprofile_event_dir + arch_path + "/bin/opimport -a "
    cmd += oprofile_event_dir + "/abi/arm_abi -o samples" + middle_part
    cmd += "/" + file_name + " " + line
    os.system(cmd)

  stream.close()
  os.chdir("../../..")  # go back up to original dir
  # short summary of profiling results
  # os.system(oprofile_event_dir + arch_path + "/bin/opreport --session-dir=.")
  # long summary
  cmd = oprofile_event_dir + arch_path + "/bin/opreport "
  cmd += "--long-filenames --session-dir=mnt/sdcard/sentinel --image-path="
  cmd += image_path + " --symbols --details --debug-info "
  cmd += "> opreport_output"
  os.system(cmd)


def _GetImagePath():
  """Gets the path for the symbols.

  Args:
    None

  Returns:
    A string, path to symbols in Android source tree

  Note: Currently set up for local testing only
  """
  # TODO(rharagutchi): need to look up symbols dir dynamically
  return FLAGS.symbols_dir


def _ChecksForOpreport():
  """Checks for architecture and oprofile environment variable.

  Args:
    None

  Returns:
    A tuple, path to correct oprofile according to arch and oprofile's event dir

  Note:
    This code was taken from the opimport_pull script that can be found in
    the Android source tree at /external/oprofile/opimport_pull

  """
   # identify 32-bit vs 64-bit platform
  stream = os.popen("uname -m")
  arch_name = stream.readline().rstrip("\n")
  stream.close()

  # default path is prebuilt/linux-x86/oprofile
  # for 64-bit OS, use prebuilt/linux-x86_64/oprofile instead
  if arch_name == "x86_64":
    arch_path = "/../../linux-x86_64/oprofile"
  else:
    arch_path = ""

  try:
    oprofile_event_dir = os.environ["OPROFILE_EVENTS_DIR"]
  except KeyError:
    string = "OPROFILE_EVENTS_DIR not set. Run \". envsetup.sh\" first. "
    string += "From Android source tree, it can be found in build/. "
    string += "Next, run \"lunch 1\" from inside the source tree."
    print string
    sys.exit(1)

  return (arch_path, oprofile_event_dir)


def _ParseOpreport():
  """Parses Opreport to get relavant information to return.

  Args:
    None

  Returns:
    A tuple:
      image(2): (string) the app and image name which is the same
      address_dict: (dictionary) maps an address to a tuple (a list of
                    number of samples, src file, and src line)
      function: (string) name of the function for specific line
      event_types: (list) list of event types that were used to get profile
                   information

  """
  report_file = open("opreport_output", "r+")
  report = report_file.read()
  report_file.close()
  report_lines = report.split("\n")
  event_types = []
  first_line = 1
  # The first line of the report is not needed
  # and get all the events
  for line in report_lines[1:]:
    if line.startswith("Counted"):
      line_words = line.split(" ")
      event_types.append(line_words[1])
      first_line += 1
  parsed_report = []
  detail_line = False
  image = function = ""
  # first_line points to the column names line, data starts on next one
  # end of file was getting counted as new line, go to 2nd to last line
  for line in report_lines[first_line+1:len(report_lines)-1]:
    if not line.startswith(" "):
      detail_line = True
    else:
      detail_line = False
    address_dict, rest_of_line = _ParseLine(len(event_types), line, detail_line)
    if detail_line:
      # check if "app name" column is missing (bad profile data)
      if len(rest_of_line.split(" ")) < 2:
        return None
      image, function = rest_of_line.split(None, 1)
      continue
    # we return image twice because in our opreports, the "app name" and "image
    # name" were the same
    parsed_report.append((image, image, address_dict, function, event_types))
  return parsed_report


def _ParseLine(num_events, line, detail_line):
  """Parses one line of the opreport output.

  Args:
    num_events: (int) the number of events for the profile session
    line: (string) one line of the opreport
    detail_line: (bool) whether or not the line is a detail line

  Returns:
    A tuple:
      address_dict: (dictionary) maps an address to list of number of samples,
                    the src file, and the src line
      rest_of_line: (string) rest of the line that contains image and symbol
                    name

  """
  vma, rest_of_line = line.split(None, 1)
  samples = []
  address_dict = {}
  for i in range(num_events):
    s, _, rest_of_line = rest_of_line.split(None, 2)
    samples.append(s)
  if rest_of_line.startswith("(no location information)"):  # no src file/line
    address_dict[vma] = (samples, "", "")
    return address_dict, rest_of_line.lstrip("(no location information)")
  else:
    # src, rest_of_line = rest_of_line.split(None, 1)
    if detail_line:
      src, rest_of_line = rest_of_line.split(None, 1)
    else:
      src = rest_of_line.split(":")
    src_file = src[0]
    src_line = src[1]
    address_dict[vma] = (samples, src_file, src_line)
    return address_dict, rest_of_line


# Following values are from //perftools/gwp/symbolization/combine_profiles.py
# _RecordEstsToFile is a modified, simplified version of combine_profiles.py's
# SequentialSymbolization function.
_COMPRESSION_BLOCKSIZE = 1048576
_COMPRESSION_WINDOWSIZE = 20


def _RecordEstsToFile(log_path, encoded_ests):
  """Writes list of encoded event stack trace pb to file.

  Args:
    log_path: (string) path to dir that log files will be written to
    encoded_ests: (list) list of encoded event stack trace protocol buffers

  Returns:
    None

  """
  slog_writer = pywraprecordio.RecordWriter(
      pywrapfile.File_Open(log_path, "w"),
      1048576,
      pywraprecordio.RecordWriter.AUTO,
      0)
  slog_writer.EnableCWCompression(_COMPRESSION_BLOCKSIZE,
                                  _COMPRESSION_WINDOWSIZE,
                                  True,  # Compress whole window
                                  False)
  for encoded_rec in encoded_ests:
    if not slog_writer.WriteRecord(encoded_rec):
      print "Error writing"


def _MakeDatabase(sample_count):
  """Create sqlite database to be used to run server.

  Args:
    sample_count: (int) number of samples that were downloaded

  Returns:
    None

  """
  logs = []
  for i in range(sample_count):
    logs.append("slog%d" % (i,))
  # Write db to local file first.  Move to final path when complete.
  # (building to nfs slow, and gfs not possible, since SQLite does not know
  # gfs.)
  if os.path.exists("awp.sqlite"):
    writer = dbwrapper.CreateDBWrapper("dbwrapper_sqlite",
                                       "awp.sqlite")
    db = profile_db_writer_append.ProfileDatabaseWriter(writer)
    # db = sqlite.connect(awp.sqlite)
    # db._created=True
    for current_log in logs:
      print "Processing profile log %s" % (current_log)
      # Process the profile-log.
      records = recordio.RecordReader(current_log)
      _ProcessLogAppend(records, db)
      os.remove(current_log)
    db.Close(optimize_database=True)
  else:
    (db_fd, db_temp_file) = tempfile.mkstemp(suffix="gwp_profile_db")
    # We never use the file descriptor opened by mkstemp, so we close it
    # right away to avoid a space leak.
    os.close(db_fd)
    writer = dbwrapper.CreateDBWrapper("dbwrapper_sqlite",
                                       db_temp_file)
    writer.CreateDatabase()
    db = profile_db_writer.ProfileDatabaseWriter(writer)

    for current_log in logs:
      print "Processing profile log %s" % (current_log)

      # Process the profile-log.
      records = recordio.RecordReader(current_log)
      make_database.ProcessLog(records, db)
      os.remove(current_log)
    db.Close(optimize_database=True)
    make_database.MoveFile(db_temp_file, "awp.sqlite")
  print "Finished updating DB"


def _ProcessLogAppend(records, db):
  """Process all the records in one symbolized log.

  Each record in the log is read in and then written to a db.  Currently, no
  special processing is done in between.

  Args:
    records: handle of recordio file containing EventStackTrace PBs.
    db: a ProfileDBWriter.profile_database_writer object.
  """
  for record in records:
    # Read from log, and write to db.
    est = EventStackTrace(record)
    resource, row = symbolized_log.ProtoToDict(est, True)
    make_database.ZeroLineNumbers(row["callstack"])
    if resource:
      db.WriteFullRow(resource, row)


def main(argv):
  _ValidateArgs(FLAGS)
  authtoken = _Authenticate(FLAGS.server, FLAGS.app_name)
  if authtoken is None:
    sys.exit(1)

  ps_cmd = [FLAGS.profile_server_dir, "--noallow_callgraphs",
            "--allow_eye3_views", "--db_type=sqlite",
            "--default_timerange=\"(Week,=,LastWeek)\"",
            "--enable_analytic_tracking",
            "--noenable_source_annotator",
            "--eye3_view_prefix=http://0.eye3.gse.google-wide-"
            "profiling.mg.borg.google.com/codeprof",
            "--gfs_client_security_level=integrity",
            "--gfs_user=google-wide-profiling",
            "--old_server=http://0.gwp.profile_server_old.google-"
            "wide-profiling.mg.borg.google.com/", "--port=8080",
            "--profile_db="+FLAGS.output_dir+"awp.sqlite",
            "--query_cache_size=8000",
            "--logtostderr"]
  
  server_pid = 0
  
  if not FLAGS.forever:
    sample_count = _DownloadSamples(FLAGS.server, authtoken)
    if sample_count > 0:  # if sample count is 0, there are no files on server
      _MakeDatabase(sample_count)
    if os.path.exists("awp.sqlite"):
      p = subprocess.Popen(ps_cmd)
    else:
      print "no awp.sqlite was found"
      sys.exit(1)
  else:
    while True:
      next_update = time.time() + FLAGS.server_update_interval
      if(os.path.exists("%sawp.sqlite" % FLAGS.output_dir)):
        if server_pid != 0:
          os.system("kill %d" % server_pid)
        p = subprocess.Popen(ps_cmd)
        server_pid = p.pid
        print "Started AWP server (pid = %d)" % server_pid
      while time.time() < next_update:
        print "minutes until next server update: %f" % ((next_update - time.time())/60)
        print "xxxxChecking App Engine Serverxxxx\n"
        sample_count = _DownloadSamples(FLAGS.server, authtoken)
        if sample_count > 0:  # if sample count is 0, there are no files on server
          _MakeDatabase(sample_count)
        time.sleep(FLAGS.ae_poll_interval)

if __name__ == "__main__":
  app.run()

