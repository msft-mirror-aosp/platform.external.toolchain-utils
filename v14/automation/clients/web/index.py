#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import xmlrpclib
import sys
import time
sys.path.append("../../../../chromeos-toolchain")
sys.path.append("../../common")

from utils import utils
import machine

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
  var row = document.getElementById("job_group_"+id);
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

def print_table_cell(text):
  print "<td>%s</td>" % str(text)

def print_job_group_row(job_group):
  print "<tr>"
  print_table_cell(job_group.GetID())
  print_table_cell(job_group.GetDescription())
  print_table_cell(time.ctime(job_group.GetTimeSubmitted()))
  print_table_cell(job_group.GetStatus())
  print_table_cell(get_display_button(job_group.GetID()))
  print "</tr>"

def get_display_button(id):
  return "<button onclick='displayRow(%s)' >Show/Hide Jobs</button>" % id

def print_job_row(job):
  print "<tr>"
  print_table_cell(job.GetID())
  print_table_cell(job.GetCommand()[0:20])
  machines = ""
  if job.GetMachines():
    machines = "<b>%s</b>" % job.GetMachines()[0].name
    for i in job.GetMachines()[1:]:
      machines += " %s" % job.GetMachines()[i + 1].name
  print_table_cell(machines)
  print_table_cell(job.GetJobDir())
  deps = ""
  for child in job.GetChildren():
    deps += str(child.GetID()) + " "
  print_table_cell(deps)
  print_table_cell(job.GetStatus())
  print "</tr>"

print_page_header("Automated build.")
print_header("Automated build.")

server = xmlrpclib.Server("http://localhost:8000")
job_groups = utils.Deserialize(server.GetAllJobGroups())


print_table_header(["ID", "Description", "Time Submitted", "Status", "Show/Hide Jobs"])
for job_group in job_groups[::-1]:
  print_job_group_row(job_group)
  print "<tr id='job_group_%s' style='display: none;'><td colspan=5 style='padding-left: 10px;'>" % job_group.GetID()
  print_table_header(["ID", "Command", "Machines",
                      "Job Directory", "Dependencies", "Status"])
  for job in job_group.GetJobs():
    print_job_row(job)
  print_table_footer()
  print "</td></tr>"
print_table_footer()

#    for machine in job.GetMachines():
#      print machine


print_footer()