#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.
#

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


class HtmlFactory(object):

  @staticmethod
  def GetTestSummary(job):
    if job.status == job_const.STATUS_RUNNING:
      return '<tt>Running job...</tt>'
    if job.status == job_const.STATUS_NOT_EXECUTED:
      return '<tt>Not executed</tt>'

    try:
      stats = {}

      with open(job.test_report_summary_filename, 'rb') as report:
        for line in report:
          name, val = [word.lower().strip() for word in line.split(':')]
          stats[name] = val

      text = ' '.join(['Passes: %s' % stats['tests passing'],
                       'Failures: %s' % stats['tests failing'],
                       'Regressions: %s' % stats['regressions']])

      return html_tools.GetLink('/job/%d/report' % job.id, text)
    except IOError:
      return '<tt>Summary not found</tt>'
    except KeyError:
      return '<tt>Summary corrupt</tt>'
    except ValueError:
      return '<tt>Summary corrupt</tt>'

  @staticmethod
  def GetJobInfo(job):
    machines = ['<tt>%s</tt>' % machine.hostname for machine in job.machines]
    parents = [html_tools.GetLink('/job/%d' % child.id, '[%d]' % child.id)
               for child in job.children] or ['None']

    children = [html_tools.GetLink('/job/%d' % parent.id, '[%d]' % parent.id)
                for parent in job.parents] or ['None']

    rows = [
        ['Label', '<tt>%s</tt>' % job.label],
        ['JobGroup', html_tools.GetLink(
            '/job-group/%d' % job.group.id, '[%d]' % job.group.id)],
        ['Parents', ' '.join(parents)],
        ['Children', ' '.join(children)],
        ['Total Time', '<tt>%s</tt>' % job.GetTotalTime()],
        ['Machines', ', '.join(machines)],
        ['Directory', '<tt>%s</tt>' % job.work_dir],
        ['Command', '<pre>%s</pre>' % job.PrettyFormatCommand()]]

    return html_tools.GetTable(['Attribute', 'Value'], rows)

  @staticmethod
  def GetJobTimeline(job):
    rows = []

    for event in job.status_events:
      rows.append(['<tt>%s</tt>' % event.old_status.split('_', 1)[1],
                   '<tt>%s</tt>' % event.new_status.split('_', 1)[1],
                   '<tt>%s</tt>' % time.ctime(event.event_time)])

    return html_tools.GetTable(
        ['From Status', 'To Status', 'Transition Time'], rows)

  @staticmethod
  def GetJobListReport(jobs):
    headers = ['Job ID', 'Label', 'Machines', 'Status', 'Total Time',
               'Test Report']
    rows = []

    for job in jobs:
      machines = ['<tt>%s</tt>' % machine.hostname for machine in job.machines]

      rows.append([html_tools.GetLink('/job/%d' % job.id, '[%d]' % job.id),
                   '<tt>%s</tt>' % job.label,
                   '<br/>'.join(machines),
                   '<tt>%s</tt>' % job.status.split('_', 1)[1],
                   '<tt>%s</tt>' % job.GetTotalTime(),
                   HtmlFactory.GetTestSummary(job)])

    return html_tools.GetTable(headers, rows)

  @staticmethod
  def GetJobGroupInfo(group):
    rows = [
        ['Label', '<tt>%s</tt>' % group.label],
        ['Time submitted', '<tt>%s</tt>' % time.ctime(group.time_submitted)],
        ['Status', '<tt>%s</tt>' % group.status.split('_', 1)[1]],
        ['Directory', '<tt>%s</tt>' % group.home_dir],
        ['Cleanup on completion', '<tt>%s</tt>' % group.cleanup_on_completion],
        ['Cleanup on failure', '<tt>%s</tt>' % group.cleanup_on_failure]]

    return html_tools.GetTable(['Attribute', 'Value'], rows)

  @staticmethod
  def GetJobGroupListReport(groups):
    headers = ['Group ID', 'Label', 'Time Submitted', 'Status']
    rows = []

    for group in groups:
      rows.append([
          html_tools.GetLink('/job-group/%d' % group.id, '[%d]' % group.id),
          '<tt>%s</tt>' % group.label,
          '<tt>%s</tt>' % time.ctime(group.time_submitted),
          '<tt>%s</tt>' % group.status.split('_', 1)[1]])

    return html_tools.GetTable(headers, rows)


class BasePageHandler(object):
  def __init__(self):
    self._server = xmlrpclib.Server('http://localhost:8000')

  def Render(self):
    try:
      output = StringIO.StringIO()

      self._PrintHeader(output, error=False)
      self._Render(output)
      self._PrintFooter(output)

      handled_with_success = True
    except:
      output = StringIO.StringIO()

      self._PrintHeader(output, error=True)
      self._PrintTraceback(output)
      self._PrintFooter(output)

      handled_with_success = False

    response = output.getvalue()
    output.close()

    return response, handled_with_success

  def _PrintTraceback(self, out):
    out.write('<pre>')
    out.write(traceback.format_exc().replace('\n', '<br/>'))
    out.write('</pre>')

  def _PrintHeader(self, out, error=False):
    out.write(html_tools.GetPageHeader('Monitor'))

    if not error:
      out.write(html_tools.GetHeader('Automation Monitor'))
      out.write(html_tools.GetParagraph('%s | %s | %s' % (
          html_tools.GetLink('/', 'Job Groups'),
          html_tools.GetLink('/results', 'Results'),
          html_tools.GetLink('/filter', 'Filter'))))
    else:
      out.write(html_tools.GetHeader('Server error:'))

  def _PrintFooter(self, out):
    out.write(html_tools.GetFooter())


class JobPageHandler(BasePageHandler):
  def __init__(self, job_id):
    BasePageHandler.__init__(self)

    self._job_id = int(job_id)

  def _Render(self, out):
    job = pickle.loads(self._server.GetJob(self._job_id))

    out.write(html_tools.GetHeader('Job %d' % job.id, 2))

    log_link = '/job/%s/log/' % job.id

    out.write(html_tools.GetParagraph('%s | %s | %s | %s' % (
        html_tools.GetLink('/job/%d/report' % job.id, 'Report'),
        html_tools.GetLink(log_link + 'out', 'Output Log'),
        html_tools.GetLink(log_link + 'err', 'Error Log'),
        html_tools.GetLink(log_link + 'cmd', 'Commands Log'))))

    out.write(HtmlFactory.GetJobInfo(job))

    out.write(html_tools.GetHeader("Timeline of status events:", 3))
    out.write(HtmlFactory.GetJobTimeline(job))


class JobGroupPageHandler(BasePageHandler):
  def __init__(self, job_group_id):
    BasePageHandler.__init__(self)

    self._job_group_id = int(job_group_id)

  def _Render(self, out):
    group = pickle.loads(self._server.GetJobGroup(self._job_group_id))

    out.write(html_tools.GetHeader('Job Group %d' % group.id, 2))
    out.write(HtmlFactory.GetJobGroupInfo(group))

    out.write(html_tools.GetHeader('Jobs', 2))
    out.write(HtmlFactory.GetJobListReport(group.jobs))


class ResultsPageHandler(BasePageHandler):
  def _Render(self, out):
    groups = pickle.loads(self._server.GetAllJobGroups())

    unique_labels = sorted(set(group.label for group in groups))

    for label in unique_labels:
      out.write(html_tools.GetHeader('Results for <tt>%s</tt>' % label, 2))

      filtered = [group for group in groups if group.label == label]

      for group in filtered:
        headers = ['Group ID', 'Time Submitted']
        headers.extend(job.label for job in group.jobs)

        row = [
            html_tools.GetLink('/job-group/%d' % group.id, '[%d]' % group.id),
            time.ctime(group.time_submitted)]
        row.extend([HtmlFactory.GetTestSummary(job) for job in group.jobs])

        out.write(html_tools.GetTable(headers, [row]))
        out.write('<br/>')


class ReportPageHandler(BasePageHandler):
  def __init__(self, job_id):
    BasePageHandler.__init__(self)

    self._job_id = int(job_id)

  def _Render(self, out):
    job = pickle.loads(self._server.GetJob(self._job_id))

    assert job, 'No job with number %d.' % self._job_id

    out.write(html_tools.GetHeader('Job %d' % job.id, 2))
    out.write(html_tools.GetHeader('Job report', 3))

    try:
      with open(job.test_report_filename, 'rb') as report:
        out.write(report.read())
    except IOError as ex:
      out.write('<b>Error:</b> Could not access: <tt>%s</tt> file.' %
                ex.filename)


class LogPageHandler(BasePageHandler):
  def __init__(self, job_id, log_type):
    BasePageHandler.__init__(self)

    self._job_id = int(job_id)
    self._log_type = str(log_type)

    assert self._log_type in ['out', 'cmd', 'err']

  def _Render(self, out):
    job = pickle.loads(self._server.GetJob(self._job_id))

    assert job, 'No job with number %d.' % self._job_id

    filename = getattr(job, 'log_%s_filename' %  self._log_type)

    out.write(html_tools.GetHeader('Job %d' % job.id, 2))

    names = {'out': 'Output', 'cmd': 'Commands', 'err': 'Error'}

    out.write(html_tools.GetHeader('%s Log' % names[self._log_type], 3))

    out.write('<pre>')
    with open(filename, 'rb') as report:
      out.write(report.read())
    out.write('</pre>')


class FilterPageHandler(BasePageHandler):
  def __init__(self, filter_by=None, value=None):
    BasePageHandler.__init__(self)

    self._filter_by = filter_by
    self._value = value

  def PrintFilterChoices(self, out):
    out.write(html_tools.GetHeader('Filter by:', 3))

    if self._filter_by == 'client_name':
      by_client_name = '<b>Client Name</b>'
    else:
      by_client_name = html_tools.GetLink('/filter/client_name', 'Client Name')

    out.write(html_tools.GetList([by_client_name]))

  def PrintFilterByClientName(self, out):
    groups = pickle.loads(self._server.GetAllJobGroups())

    if not self._value:
      out.write(html_tools.GetHeader('Filter by client name:', 3))

      client_names = []

      for label in sorted(set(group.label for group in groups)):
        client_names.append(html_tools.GetLink(
            '/filter/client_name/%s' % label, label))

      out.write(html_tools.GetList(client_names))
    else:
      filtered = [group for group in groups if group.label == self._value]

      out.write(html_tools.GetHeader(
          'Job groups with client name <tt>%s</tt>:' % self._value, 3))
      out.write(HtmlFactory.GetJobGroupListReport(filtered))

  def _Render(self, out):
    self.PrintFilterChoices(out)

    if self._filter_by == 'client_name':
      self.PrintFilterByClientName(out)
    elif self._filter_by:
      out.write(
          html_tools.GetHeader('Unknown filter: "%s"' % self._filter_by, 3))


class DefaultPageHandler(BasePageHandler):
  def _Render(self, out):
    groups = reversed(pickle.loads(self._server.GetAllJobGroups()))

    out.write(html_tools.GetHeader('Job Groups', 2))
    out.write(HtmlFactory.GetJobGroupListReport(groups))


class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  handlers = [
      ('/job-group/(?P<job_group_id>\d+)', JobGroupPageHandler),
      ('/job/(?P<job_id>\d+)/log/(?P<log_type>\w+)', LogPageHandler),
      ('/job/(?P<job_id>\d+)/report', ReportPageHandler),
      ('/job/(?P<job_id>\d+)', JobPageHandler),
      ('/filter(/(?P<filter_by>\w+)(/(?P<value>\w+))?)?', FilterPageHandler),
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

    response, handled_with_success = handler.Render()

    status_code = (handled_with_success and 200) or 500

    self.send_response(status_code)
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
