#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

DEBUG = True

import xmlrpclib
import sys
import time
import cgi

if DEBUG:
  import cgitb
  cgitb.enable()
  sys.stderr = sys.stdout

sys.path.append("../../..")

from utils import utils
from utils import html_tools
from automation.common import machine
import automation.common.job

global server

def PrintAutomationHeader():
  print html_tools.GetHeader("Automated Build")
  home_link = html_tools.GetLink("index.py", "Job Groups")
  results_link = html_tools.GetLink("index.py?results=1", "Results")
  print html_tools.GetParagraph(home_link + " | " + results_link)

def PrintJobGroupView(group):
  PrintAutomationHeader()
  print html_tools.GetHeader("Job Group %s (%s)" % (group.id, group.label), 2)
  print html_tools.GetTableHeader(["ID", "Label", "Time Submitted", "Status"])
  PrintGroupRow(group, False)
  print html_tools.GetTableFooter()
  print html_tools.GetHeader("Jobs", 2)
  print html_tools.GetTableHeader(["ID", "Label", "Command", "Machines",
                                     "Job Directory", "Dependencies", "Status", "Logs", "Test Report"])
  for job in group.jobs:
    PrintJobRow(job)
  print html_tools.GetTableFooter()


def PrintResultsView(groups, label):
  PrintAutomationHeader()
  print html_tools.GetHeader("Results (%s)" % label, 2)
  tests = []
  for group in groups:
    if group.label == label:
      for job in group.jobs:
        if not job.label in tests:
          tests.append(job.label)

  print html_tools.GetTableHeader(["Group ID", "Time Submitted"] + tests)

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

def GetJobsLink(id, text):
  return html_tools.GetLink("index.py?job_group=%s" % id, text)

def PrintJobRow(job):
  print "<tr>"
  print html_tools.GetTableCell(job.id)
  print html_tools.GetTableCell(job.label)
  print html_tools.GetTableCell(utils.FormatCommands(job.command))
  machines = ""
  if job.machines:
    machines = job.machines[0].name
    for machine in job.machines[1:]:
      machines += " %s" % machine.name
  print html_tools.GetTableCell(machines)
  print html_tools.GetTableCell(job.work_dir)
  deps = ""
  for child in job.GetChildren():
    deps += str(child.id) + " "
  print html_tools.GetTableCell(deps)
  full_status = "%s\n%s" % (job.status, job.GetTotalTime())
  print html_tools.GetTableCell(full_status)
  log_link = "index.py?log=%s" % job.id
  out_link = log_link + "&type=out"
  err_link = log_link + "&type=err"
  cmd_link = log_link + "&type=cmd"
  print html_tools.GetTableCell("%s %s %s" %
                   (html_tools.GetLink(out_link, "[out]"), html_tools.GetLink(err_link, "[err]"),
                   html_tools.GetLink(cmd_link, "[cmd]")))
  print html_tools.GetTableCell(GetTestSummary(job))
  print "</tr>"

def GetTestSummary(job):
  if job.status == automation.common.job.STATUS_RUNNING:
    return "Running job..."
  if job.status == automation.common.job.STATUS_NOT_EXECUTED:
    return "Not executed."

  try:
    report = open(job.GetTestReportSummaryFile(), 'rb')
    stats = {}
    for line in report:
      (name, val) = line.split(":")
      stats[name.lower().strip()] = val.lower().strip()
    report.close()
    text = "Passes: %s Failures: %s Regressions: %s" % (stats["tests passing"],
                                                        stats["tests failing"],
                                                        stats["regressions"])
    return html_tools.GetLink("index.py?report=%s" % job.id, text)

  except IOError:
    return "Summary not found"
  except KeyError:
    return "Summary corrupt"


print html_tools.GetContentType()

print html_tools.GetPageHeader("Automated build.")

server = xmlrpclib.Server("http://localhost:8000")
groups = utils.Deserialize(server.GetAllJobGroups())


form = cgi.FieldStorage()

if "results" in form:
  PrintResultsView(groups, "nightly_client")
elif "job_group" in form:
  current_id = int(form["job_group"].value)
  job_group = utils.Deserialize(server.GetJobGroup(current_id))
  PrintJobGroupView(job_group)
elif "report" in form:
  try:
    current_id = int(form["report"].value)
    job = utils.Deserialize(server.GetJob(current_id))
    if job is not None:
      report = open(job.GetTestReportFile(), 'rb')
      print report.read()
      report.close()
  except StandardError, e:
    print e
elif "log" in form:
  try:
    current_id = int(form["log"].value)
    type = str(form["type"].value)
    job = utils.Deserialize(server.GetJob(current_id))
    if job is not None:
      if type == "out":
        report = open(job.log_out_filename, 'rb')
      elif type == "cmd":
        report = open(job.log_cmd_filename, 'rb')
      elif type == "err":
        report = open(job.log_err_filename, 'rb')
      else:
        print "Invalid log type"
      print "<pre>"
      for line in report:
        print line[:-1]
      print "</pre>"
      report.close()
  except StandardError, e:
    print e
else:
  PrintAutomationHeader()
  print html_tools.GetHeader("Job Groups", 2)
  print html_tools.GetTableHeader(["ID", "Label", "Time Submitted", "Status", "Details"])
  for group in groups[::-1]:
    PrintGroupRow(group)
  print html_tools.GetTableFooter()


print html_tools.GetFooter()
