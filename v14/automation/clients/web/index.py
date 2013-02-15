#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import cgi
import cgitb
import pickle
import sys
import time
import xmlrpclib

from automation.common import job as job_const
from utils import html_tools
from utils import utils

DEBUG = True

if DEBUG:
  cgitb.enable()
  sys.stderr = sys.stdout

server = None


def PrintAutomationHeader():
  print html_tools.GetHeader("Automated Build")
  home_link = html_tools.GetLink("index.py", "Job Groups")
  results_link = html_tools.GetLink("index.py?results=1", "Results")
  print html_tools.GetParagraph("%s | %s" % (home_link, results_link))


def PrintJobGroupView(group):
  PrintAutomationHeader()
  print html_tools.GetHeader("Job Group %s (%s)" % (group.id, group.label), 2)
  print html_tools.GetTableHeader(["ID", "Label", "Time Submitted", "Status"])
  PrintGroupRow(group, False)
  print html_tools.GetTableFooter()
  print html_tools.GetHeader("Jobs", 2)
  print html_tools.GetTableHeader(["ID", "Label", "Command", "Machines",
                                   "Job Directory", "Dependencies", "Status",
                                   "Logs", "Test Report"])
  for job in group.jobs:
    PrintJobRow(job)
  print html_tools.GetTableFooter()


def PrintResultsView(groups, label):
  PrintAutomationHeader()
  print html_tools.GetHeader("Results (%s)" % label, 2)

  tests = ["Group ID", "Time Submitted"]

  for group in groups:
    if group.label == label:
      for job in group.jobs:
        if not job.label in tests:
          tests.append(job.label)

  print html_tools.GetTableHeader(tests)

  for group in groups:
    if group.label == label:
      PrintResultRow(group, tests)

  print html_tools.GetTableFooter()


def PrintResultRow(group, tests):
  print "<tr>"
  print html_tools.GetTableCell(GetJobsLink(group.id, group.id))
  print html_tools.GetTableCell(time.ctime(group.time_submitted))

  for test in tests:
    found = False
    for job in group.jobs:
      if job.label == test:
        print html_tools.GetTableCell(GetTestSummary(job))
        found = True
    if not found:
      print html_tools.GetTableCell("")

  print "</tr>"


def PrintGroupRow(group, details=True):
  print "<tr>"
  print html_tools.GetTableCell(group.id)
  print html_tools.GetTableCell(group.label)
  print html_tools.GetTableCell(time.ctime(group.time_submitted))
  print html_tools.GetTableCell(group.status)
  if details:
    print html_tools.GetTableCell(GetJobsLink(group.id, "Details..."))
  print "</tr>"


def GetJobsLink(id_, text):
  return html_tools.GetLink("index.py?job_group=%s" % id_, text)


def PrintJobRow(job):
  print "<tr>"
  print html_tools.GetTableCell(job.id)
  print html_tools.GetTableCell(job.label)
  print html_tools.GetTableCell(utils.FormatCommands(job.command))
  machines = " ".join([machine.name for machine in job.machines])
  print html_tools.GetTableCell(machines)
  print html_tools.GetTableCell(job.work_dir)
  deps = " ".join(["%d" % child.id for child in job.children])
  print html_tools.GetTableCell(deps)
  print html_tools.GetTableCell("%s\n%s" % (job.status, job.GetTotalTime()))
  log_link = "index.py?log=%s" % job.id
  out_link = "%s&type=out" % log_link
  err_link = "%s&type=err" % log_link
  cmd_link = "%s&type=cmd" % log_link
  print html_tools.GetTableCell("%s %s %s" %
                                (html_tools.GetLink(out_link, "[out]"),
                                 html_tools.GetLink(err_link, "[err]"),
                                 html_tools.GetLink(cmd_link, "[cmd]")))
  print html_tools.GetTableCell(GetTestSummary(job))
  print "</tr>"


def GetTestSummary(job):
  if job.status == job_const.STATUS_RUNNING:
    return "Running job..."
  if job.status == job_const.STATUS_NOT_EXECUTED:
    return "Not executed."

  try:
    stats = {}

    with open(job.test_report_summary_filename, "rb") as report:
      for line in report:
        name, val = [word.lower().strip() for word in line.split(":")]
        stats[name] = val

    text = "Passes: %s Failures: %s Regressions: %s" % (stats["tests passing"],
                                                        stats["tests failing"],
                                                        stats["regressions"])
    return html_tools.GetLink("index.py?report=%d" % job.id, text)
  except IOError:
    return "Summary not found"
  except KeyError:
    return "Summary corrupt"
  except ValueError:
    return "Summary corrupt"


def Main():
  print html_tools.GetContentType()
  print html_tools.GetPageHeader("Automated build.")

  global server

  server = xmlrpclib.Server("http://localhost:8000")
  groups = pickle.loads(server.GetAllJobGroups())

  form = cgi.FieldStorage()

  if "results" in form:
    PrintResultsView(groups, "nightly_client")
  elif "job_group" in form:
    current_id = int(form["job_group"].value)
    job_group = pickle.loads(server.GetJobGroup(current_id))
    PrintJobGroupView(job_group)
  elif "report" in form:
    current_id = int(form["report"].value)
    job = pickle.loads(server.GetJob(current_id))
    if job:
      try:
        with open(job.test_report_filename, "rb") as report:
          print report.read()
      except IOError as ex:
        print ex
  elif "log" in form:
    current_id = int(form["log"].value)
    output_type = str(form["type"].value)
    job = pickle.dumps(server.GetJob(current_id))
    if job:
      filename = None
      if output_type == "out":
        filename = job.log_out_filename
      elif output_type == "cmd":
        filename = job.log_cmd_filename
      elif output_type == "err":
        filename = job.log_err_filename
      else:
        print "Invalid log type"
      print "<pre>"
      try:
        with open(filename, "rb") as report:
          print report.read()
      except IOError as ex:
        print ex
      print "</pre>"
  else:
    PrintAutomationHeader()
    print html_tools.GetHeader("Job Groups", 2)
    print html_tools.GetTableHeader(["ID", "Label", "Time Submitted", "Status",
                                     "Details"])
    for group in reversed(groups):
      PrintGroupRow(group)
    print html_tools.GetTableFooter()

  print html_tools.GetFooter()


if __name__ == "__main__":
  Main()
