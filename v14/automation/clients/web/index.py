#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import BaseHTTPServer
import cStringIO as StringIO
import logging
import pickle
import re
import socket
import time
import traceback
import xmlrpclib

from automation.common import job as job_const
from utils import html_tools


def PrintAutomationHeader(out):
  out.write(html_tools.GetHeader('Automated Build'))
  out.write(html_tools.GetParagraph('%s | %s' % (
      html_tools.GetLink('/', 'Job Groups'),
      html_tools.GetLink('/results', 'Results'))))


def PrintGroupRow(out, group, details=True):
  out.write('<tr>')
  out.write(html_tools.GetTableCell(group.id))
  out.write(html_tools.GetTableCell(group.label))
  out.write(html_tools.GetTableCell(time.ctime(group.time_submitted)))
  out.write(html_tools.GetTableCell(group.status))

  if details:
    out.write(html_tools.GetTableCell(GetJobsLink(group.id, 'Details...')))
  out.write('</tr>')


def GetJobsLink(job_group_id, text):
  return html_tools.GetLink('/job-group/%d' % job_group_id, text)


def GetTestSummary(job):
  if job.status == job_const.STATUS_RUNNING:
    return 'Running job...'
  if job.status == job_const.STATUS_NOT_EXECUTED:
    return 'Not executed.'

  try:
    stats = {}

    with open(job.test_report_summary_filename, 'rb') as report:
      for line in report:
        name, val = [word.lower().strip() for word in line.split(':')]
        stats[name] = val

    text = 'Passes: %s Failures: %s Regressions: %s' % (stats['tests passing'],
                                                        stats['tests failing'],
                                                        stats['regressions'])
    return html_tools.GetLink('/job/%d/report' % job.id, text)
  except IOError:
    return 'Summary not found'
  except KeyError:
    return 'Summary corrupt'
  except ValueError:
    return 'Summary corrupt'


class BasePageHandler(object):
  def __init__(self):
    self._server = xmlrpclib.Server('http://localhost:8000')


class JobGroupPageHandler(BasePageHandler):
  def __init__(self, job_group_id):
    BasePageHandler.__init__(self)
    self._job_group_id = int(job_group_id)

  def __call__(self, out):
    group = pickle.loads(self._server.GetJobGroup(self._job_group_id))

    PrintAutomationHeader(out)

    out.write(html_tools.GetHeader(
        'Job Group %s (%s)' % (group.id, group.label), 2))
    out.write(html_tools.GetTableHeader(
        ['ID', 'Label', 'Time Submitted', 'Status']))

    PrintGroupRow(out, group, False)

    out.write(html_tools.GetTableFooter())
    out.write(html_tools.GetHeader('Jobs', 2))
    out.write(html_tools.GetTableHeader(
        ['ID', 'Label', 'Command', 'Machines', 'Job Directory', 'Dependencies',
         'Status', 'Logs', 'Test Report']))

    for job in group.jobs:
      self.PrintJobRow(out, job)

    out.write(html_tools.GetTableFooter())

  def PrintJobRow(self, out, job):
    out.write('<tr>')
    out.write(html_tools.GetTableCell(job.id))
    out.write(html_tools.GetTableCell(job.label))
    out.write(html_tools.GetTableCell(job.PrettyFormatCommand()))
    machines = ' '.join([machine.name for machine in job.machines])
    out.write(html_tools.GetTableCell(machines))
    out.write(html_tools.GetTableCell(job.work_dir))
    deps = ' '.join([str(child.id) for child in job.children])
    out.write(html_tools.GetTableCell(deps))
    out.write(html_tools.GetTableCell('%s\n%s' % (job.status,
                                                  job.GetTotalTime())))
    log_link = '/job/%s/log/' % job.id
    out_link = log_link + 'out'
    err_link = log_link + 'err'
    cmd_link = log_link + 'cmd'
    out.write(html_tools.GetTableCell(
        '%s %s %s' % (html_tools.GetLink(out_link, '[out]'),
                      html_tools.GetLink(err_link, '[err]'),
                      html_tools.GetLink(cmd_link, '[cmd]'))))
    out.write(html_tools.GetTableCell(GetTestSummary(job)))
    out.write('</tr>')


class ResultsPageHandler(BasePageHandler):
  def __call__(self, out):
    groups = pickle.loads(self._server.GetAllJobGroups())
    label = 'nightly_client'

    PrintAutomationHeader(out)

    out.write(html_tools.GetHeader('Results (%s)' % label, 2))

    tests = ['Group ID', 'Time Submitted']

    for group in groups:
      if group.label == label:
        for job in group.jobs:
          if not job.label in tests:
            tests.append(job.label)

    out.write(html_tools.GetTableHeader(tests))

    for group in groups:
      if group.label == label:
        self.PrintResultRow(out, group, tests)

    out.write(html_tools.GetTableFooter())

  def PrintResultRow(self, out, group, tests):
    out.write('<tr>')
    out.write(html_tools.GetTableCell(GetJobsLink(group.id, group.id)))
    out.write(html_tools.GetTableCell(time.ctime(group.time_submitted)))

    for test in tests:
      found = False
      for job in group.jobs:
        if job.label == test:
          out.write(html_tools.GetTableCell(GetTestSummary(job)))
          found = True
      if not found:
        out.write(html_tools.GetTableCell(''))

    out.write('</tr>')


class ReportPageHandler(BasePageHandler):
  def __init__(self, job_id):
    BasePageHandler.__init__(self)

    self._job_id = int(job_id)

  def __call__(self):
    job = pickle.loads(self._server.GetJob(self._job_id))

    assert job, 'No job with number %d.' % self._job_id

    with open(job.test_report_filename, 'rb') as report:
      self.write(report.read())


class LogPageHandler(BasePageHandler):
  def __init__(self, job_id, log_type):
    BasePageHandler.__init__(self)

    self._job_id = int(job_id)
    self._log_type = str(log_type)

    assert self._log_type in ['out', 'cmd', 'err']

  def __call__(self, out):
    job = pickle.loads(self._server.GetJob(self._job_id))

    assert job, 'No job with number %d.' % self._job_id

    filename = getattr(job, 'log_%s_filename' %  self._log_type)
    out.write('<pre>')
    with open(filename, 'rb') as report:
      out.write(report.read())
    out.write('</pre>')


class DefaultPageHandler(BasePageHandler):
  def __call__(self, out):
    PrintAutomationHeader(out)
    out.write(html_tools.GetHeader('Job Groups', 2))
    out.write(html_tools.GetTableHeader(
        ['ID', 'Label', 'Time Submitted', 'Status', 'Details']))

    groups = pickle.loads(self._server.GetAllJobGroups())

    for group in reversed(groups):
      PrintGroupRow(out, group)
    out.write(html_tools.GetTableFooter())


class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  handlers = [
      ('/job-group/(?P<job_group_id>\d+)', JobGroupPageHandler),
      ('/job/(?P<job_id>\d+)/log/(?P<log_type>\w+)', LogPageHandler),
      ('/jon/(?P<job_id>\d+)/report', ReportPageHandler),
      ('/results', ResultsPageHandler),
      ('/', DefaultPageHandler)]

  def do_GET(self):
    # url = urlparse.urlparse(self.path)
    # params = url.query.split('&') if url.query else []
    # params = dict(param.split('=') for param in params)

    handler = None

    logging.debug('Trying to match "%s"', self.path)

    for path_re, handler_cls in self.handlers:
      try:
        match = re.match(path_re, self.path)
      except re.error as ex:
        logging.debug('Error in "%s" regexp (%s)', path_re, ex)

      if match:
        handler = handler_cls(**match.groupdict())
        break
      else:
        logging.debug('Regexp "%s" not matched', path_re)

    output = StringIO.StringIO()
    output.write(html_tools.GetPageHeader('Automated build.'))
    try:
      handler(output)
    except:
      output.write(traceback.format_exc().replace('\n', '<br/>'))
    output.write(html_tools.GetFooter())
    response = output.getvalue()
    output.close()

    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()
    self.wfile.write(response)

  def log_message(self, _format, *args):
    logging.info(_format, *args)

if __name__ == '__main__':
  HOST_NAME = socket.gethostname()
  PORT_NUMBER = 8080

  FORMAT = '%(asctime)-15s %(levelname)s %(message)s'

  logging.basicConfig(format=FORMAT, level=logging.DEBUG)

  httpd = BaseHTTPServer.HTTPServer((HOST_NAME, PORT_NUMBER), RequestHandler)
  logging.info('Server Starts - %s:%s', HOST_NAME, PORT_NUMBER)
  try:
    httpd.serve_forever()
  finally:
    httpd.server_close()
  logging.info('Server Stops - %s:%s', HOST_NAME, PORT_NUMBER)
