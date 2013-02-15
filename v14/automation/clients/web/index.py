#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

DEBUG = True

import xmlrpclib
import sys
import time
import getpass
import cgi

if DEBUG:
  import cgitb
  cgitb.enable()
  sys.stderr = sys.stdout

sys.path.append("../../../../chromeos-toolchain")
sys.path.append("../../common")
from utils import utils
import machine
import job_group
import report_generator

global server

print "Content-Type: text/html\n"
print


def print_page_header(page_title):
  print """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
<head>
<style type="text/css">
table
{
border-collapse:collapse;
}
table, td, th
{
border:1px solid black;
}
</style>
<script type="text/javascript">
function displayRow(id){
  var row = document.getElementById("group_"+id);
  if (row.style.display == '')  row.style.display = 'none';
    else row.style.display = '';
  }
</script>
<title>%s</title>
</head>
<body>

""" % page_title

def print_footer():
  print """</body> 
</html>"""

def print_header(text):
  print "<h1>%s</h1>" % text

def print_table_header(columns):
  print "<table>"
  print "<tr>"
  for column in columns:
    print "<th>% s </th>" % str(column)
  print "</tr>"

def print_table_footer():
  print "</table>"

def format_linebreaks(text):
  ret = text
  ret = ret.replace("\n", "<br>")
  return ret

def print_table_cell(text):
  text = format_linebreaks(str(text))
  print "<td>%s</td>" % text

def print_group_row(group):
  print "<tr>"
  print_table_cell(group.GetID())
  print_table_cell(group.GetDescription())
  print_table_cell(time.ctime(group.GetTimeSubmitted()))
  print_table_cell(group.GetStatus())
  print_table_cell(get_report_link(group))
  print_table_cell(get_display_button(group.GetID()))
  print "</tr>"

def get_display_button(id):
  return "<button onclick='displayRow(%s)' >Show/Hide Jobs</button>" % id

def get_link(link, text):
  return "<a href='%s'>%s</a>" % (link, text)

def print_job_row(job):
  print "<tr>"
  print_table_cell(job.GetID())
  print_table_cell(utils.FormatCommands(job.GetCommand()))
  machines = ""
  if job.GetMachines():
    machines = "<b>%s</b>" % job.GetMachines()[0].name
    for machine in job.GetMachines()[1:]:
      machines += " %s" % machine.name
  print_table_cell(machines)
  print_table_cell(job.GetWorkDir())
  deps = ""
  for child in job.GetChildren():
    deps += str(child.GetID()) + " "
  print_table_cell(deps)
  full_status = "%s\n%s" % (job.GetStatus(), job.GetTotalTime())
  print_table_cell(full_status)
  log_link = "index.py?log=%s" % job.GetID()
  out_link = log_link + "&type=out"
  err_link = log_link + "&type=err"
  cmd_link = log_link + "&type=cmd"
  print_table_cell("%s %s %s" %
                   (get_link(out_link, "[out]"), get_link(err_link, "[err]"),
                   get_link(cmd_link, "[cmd]")))
  print "</tr>"

def get_test_summary(group):
  if (group.GetStatus() != job_group.STATUS_SUCCEEDED and
      group.GetStatus() != job_group.STATUS_FAILED):
      return ""

  try:
    report = open(group.GetTestReport(), 'rb')
    report.readline()
    report.readline()
    num_passes = report.readline().split(":")[1].strip()
    num_failures = report.readline().split(":")[1].strip()
    num_regressions = report.readline().split(":")[1].strip()
    report.close()
    return "Passes: %s Failures: %s Regressions: %s" % (num_passes,
                                                      num_failures,
                                                      num_regressions)
  except StandardError:
    return "Report not found"
    
def get_report_link(group):
  return get_link("index.py?report=%s" % group.GetID(), get_test_summary(group))

print_page_header("Automated build.")

server = xmlrpclib.Server("http://localhost:8000")
groups = utils.Deserialize(server.GetAllJobGroups())


form = cgi.FieldStorage()

if "report" in form:
  try:
    current_id = int(form["report"].value)
    job_group = utils.Deserialize(server.GetJobGroup(current_id))
    if job_group is not None:
      report = open(job_group.GetTestReport(), 'rb')

      print "<pre>"
      for line in report:
        print line[:-1]
      print "</pre>"
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
        report = open(job.GetLogOut(), 'rb')
      elif type == "cmd":
        report = open(job.GetLogCmd(), 'rb')
      elif type == "err":
        report = open(job.GetLogErr(), 'rb')
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
  print_header("Automated build.")
  print_table_header(["ID", "Description", "Time Submitted", "Status", "Tests", "Show/Hide Jobs"])
  for group in groups[::-1]:
    print_group_row(group)
    print "<tr id='group_%s' style='display: none;'><td colspan=5 style='padding-left: 10px;'>" % group.GetID()
    print_table_header(["ID", "Command", "Machines",
                        "Job Directory", "Dependencies", "Status", "Logs"])
    for job in group.GetJobs():
      print_job_row(job)
    print_table_footer()
    print "</td></tr>"
  print_table_footer()

#    for machine in job.GetMachines():
#      print machine


print_footer()
