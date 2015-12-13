# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module to handle the report format."""
from __future__ import print_function

import datetime
import json
import os

from cros_utils.tabulator import AmeanResult
from cros_utils.tabulator import Cell
from cros_utils.tabulator import CoeffVarFormat
from cros_utils.tabulator import CoeffVarResult
from cros_utils.tabulator import Column
from cros_utils.tabulator import Format
from cros_utils.tabulator import GmeanRatioResult
from cros_utils.tabulator import LiteralResult
from cros_utils.tabulator import MaxResult
from cros_utils.tabulator import MinResult
from cros_utils.tabulator import PValueFormat
from cros_utils.tabulator import PValueResult
from cros_utils.tabulator import RatioFormat
from cros_utils.tabulator import RawResult
from cros_utils.tabulator import StdResult
from cros_utils.tabulator import TableFormatter
from cros_utils.tabulator import TableGenerator
from cros_utils.tabulator import TablePrinter
from update_telemetry_defaults import TelemetryDefaults

from column_chart import ColumnChart
from results_organizer import ResultOrganizer
from perf_table import PerfTable


def ParseChromeosImage(chromeos_image):
  """Parse the chromeos_image string for the image and version.

  The chromeos_image string will probably be in one of two formats:
  1: <path-to-chroot>/src/build/images/<board>/<ChromeOS-version>.<datetime>/ \
     chromiumos_test_image.bin
  2: <path-to-chroot>/chroot/tmp/<buildbot-build>/<ChromeOS-version>/ \
      chromiumos_test_image.bin

  We parse these strings to find the 'chromeos_version' to store in the
  json archive (without the .datatime bit in the first case); and also
  the 'chromeos_image', which would be all of the first case, but only the
  part after '/chroot/tmp' in the second case.

  Args:
      chromeos_image: string containing the path to the chromeos_image that
      crosperf used for the test.

  Returns:
      version, image: The results of parsing the input string, as explained
      above.
  """
  version = ''
  real_file = os.path.realpath(os.path.expanduser(chromeos_image))
  pieces = real_file.split('/')
  # Find the Chromeos Version, e.g. R45-2345.0.0.....
  # chromeos_image should have been something like:
  # <path>/<board-trybot-release>/<chromeos-version>/chromiumos_test_image.bin"
  num_pieces = len(pieces)
  if pieces[num_pieces-1] == "chromiumos_test_image.bin":
    version = pieces[num_pieces-2]
    # Find last '.' in the version and chop it off (removing the .datatime
    # piece from local builds).
    loc = version.rfind('.')
    version = version[:loc]
  # Find the chromeos image.  If it's somewhere in .../chroot/tmp/..., then
  # it's an official image that got downloaded, so chop off the download path
  # to make the official image name more clear.
  loc = real_file.find('/chroot/tmp')
  if loc != -1:
    loc += len('/chroot/tmp')
    real_file = real_file[loc:]
  image = real_file
  return version, image

class ResultsReport(object):
  """Class to handle the report format."""
  MAX_COLOR_CODE = 255
  PERF_ROWS = 5

  def __init__(self, experiment):
    self.experiment = experiment
    self.benchmark_runs = experiment.benchmark_runs
    self.labels = experiment.labels
    self.benchmarks = experiment.benchmarks
    self.baseline = self.labels[0]

  def _SortByLabel(self, runs):
    labels = {}
    for benchmark_run in runs:
      if benchmark_run.label_name not in labels:
        labels[benchmark_run.label_name] = []
      labels[benchmark_run.label_name].append(benchmark_run)
    return labels

  def GetFullTables(self, perf=False):
    columns = [Column(RawResult(),
                      Format()),
               Column(MinResult(),
                      Format()),
               Column(MaxResult(),
                      Format()),
               Column(AmeanResult(),
                      Format()),
               Column(StdResult(),
                      Format(), "StdDev"),
               Column(CoeffVarResult(),
                      CoeffVarFormat(), "StdDev/Mean"),
               Column(GmeanRatioResult(),
                      RatioFormat(), "GmeanSpeedup"),
               Column(PValueResult(),
                      PValueFormat(), "p-value")
              ]
    if not perf:
      return self._GetTables(self.labels, self.benchmark_runs, columns,
                             "full")
    return self._GetPerfTables(self.labels, columns, "full")

  def GetSummaryTables(self, perf=False):
    columns = [Column(AmeanResult(),
                      Format()),
               Column(StdResult(),
                      Format(), "StdDev"),
               Column(CoeffVarResult(),
                      CoeffVarFormat(), "StdDev/Mean"),
               Column(GmeanRatioResult(),
                      RatioFormat(), "GmeanSpeedup"),
               Column(PValueResult(),
                      PValueFormat(), "p-value")
              ]
    if not perf:
      return self._GetTables(self.labels, self.benchmark_runs, columns,
                             "summary")
    return self._GetPerfTables(self.labels, columns, "summary")

  def _ParseColumn(self, columns, iteration):
    new_column = []
    for column in columns:
      if column.result.__class__.__name__ != "RawResult":
      #TODO(asharif): tabulator should support full table natively.
        new_column.append(column)
      else:
        for i in range(iteration):
          cc = Column(LiteralResult(i), Format(), str(i+1))
          new_column.append(cc)
    return new_column

  def _AreAllRunsEmpty(self, runs):
    for label in runs:
      for dictionary in label:
        if dictionary:
          return False
    return True

  def _GetTableHeader(self, benchmark):
    benchmark_info = ("Benchmark:  {0};  Iterations: {1}"
                      .format(benchmark.name, benchmark.iterations))
    cell = Cell()
    cell.string_value = benchmark_info
    cell.header = True
    return  [[cell]]

  def _GetTables(self, labels, benchmark_runs, columns, table_type):
    tables = []
    ro = ResultOrganizer(benchmark_runs, labels, self.benchmarks)
    result = ro.result
    label_name = ro.labels
    for item in result:
      benchmark = None
      runs = result[item]
      for benchmark in self.benchmarks:
        if benchmark.name == item:
          break
      ben_table = self._GetTableHeader(benchmark)

      if  self._AreAllRunsEmpty(runs):
        cell = Cell()
        cell.string_value = ("This benchmark contains no result."
                             " Is the benchmark name valid?")
        cell_table = [[cell]]
      else:
        tg = TableGenerator(runs, label_name)
        table = tg.GetTable()
        parsed_columns = self._ParseColumn(columns, benchmark.iterations)
        tf = TableFormatter(table, parsed_columns)
        cell_table = tf.GetCellTable(table_type)
      tables.append(ben_table)
      tables.append(cell_table)
    return tables

  def _GetPerfTables(self, labels, columns, table_type):
    tables = []
    label_names = [label.name for label in labels]
    p_table = PerfTable(self.experiment, label_names)

    if not p_table.perf_data:
      return tables

    for benchmark in p_table.perf_data:
      ben = None
      for ben in self.benchmarks:
        if ben.name == benchmark:
          break

      ben_table = self._GetTableHeader(ben)
      tables.append(ben_table)
      benchmark_data = p_table.perf_data[benchmark]
      row_info = p_table.row_info[benchmark]
      table = []
      for event in benchmark_data:
        tg = TableGenerator(benchmark_data[event], label_names,
                            sort=TableGenerator.SORT_BY_VALUES_DESC)
        table = tg.GetTable(max(self.PERF_ROWS, row_info[event]))
        parsed_columns = self._ParseColumn(columns, ben.iterations)
        tf = TableFormatter(table, parsed_columns)
        tf.GenerateCellTable()
        tf.AddColumnName()
        tf.AddLabelName()
        tf.AddHeader(str(event))
        table = tf.GetCellTable(table_type, headers=False)
        tables.append(table)
    return tables

  def PrintTables(self, tables, out_to):
    output = ""
    if not tables:
      return output
    for table in tables:
      if out_to == "HTML":
        tp = TablePrinter(table, TablePrinter.HTML)
      elif out_to == "PLAIN":
        tp = TablePrinter(table, TablePrinter.PLAIN)
      elif out_to == "CONSOLE":
        tp = TablePrinter(table, TablePrinter.CONSOLE)
      elif out_to == "TSV":
        tp = TablePrinter(table, TablePrinter.TSV)
      elif out_to == "EMAIL":
        tp = TablePrinter(table, TablePrinter.EMAIL)
      else:
        pass
      output += tp.Print()
    return output


class TextResultsReport(ResultsReport):
  """Class to generate text result report."""
  TEXT = """
===========================================
Results report for: '%s'
===========================================

-------------------------------------------
Summary
-------------------------------------------
%s


Number re-images: %s

-------------------------------------------
Benchmark Run Status
-------------------------------------------
%s


-------------------------------------------
Perf Data
-------------------------------------------
%s



Experiment File
-------------------------------------------
%s


CPUInfo
-------------------------------------------
%s
===========================================
"""

  def __init__(self, experiment, email=False):
    super(TextResultsReport, self).__init__(experiment)
    self.email = email

  def GetStatusTable(self):
    """Generate the status table by the tabulator."""
    table = [["", ""]]
    columns = [Column(LiteralResult(iteration=0), Format(), "Status"),
               Column(LiteralResult(iteration=1), Format(), "Failing Reason")]

    for benchmark_run in self.benchmark_runs:
      status = [benchmark_run.name, [benchmark_run.timeline.GetLastEvent(),
                                     benchmark_run.failure_reason]]
      table.append(status)
    tf = TableFormatter(table, columns)
    cell_table = tf.GetCellTable("status")
    return [cell_table]

  def GetReport(self):
    """Generate the report for email and console."""
    status_table = self.GetStatusTable()
    summary_table = self.GetSummaryTables()
    perf_table = self.GetSummaryTables(perf=True)
    if not perf_table:
      perf_table = None
    if not self.email:
      return self.TEXT % (self.experiment.name,
                          self.PrintTables(summary_table, "CONSOLE"),
                          self.experiment.machine_manager.num_reimages,
                          self.PrintTables(status_table, "CONSOLE"),
                          self.PrintTables(perf_table, "CONSOLE"),
                          self.experiment.experiment_file,
                          self.experiment.machine_manager.GetAllCPUInfo(
                              self.experiment.labels))

    return self.TEXT % (self.experiment.name,
                        self.PrintTables(summary_table, "EMAIL"),
                        self.experiment.machine_manager.num_reimages,
                        self.PrintTables(status_table, "EMAIL"),
                        self.PrintTables(perf_table, "EMAIL"),
                        self.experiment.experiment_file,
                        self.experiment.machine_manager.GetAllCPUInfo(
                            self.experiment.labels))


class HTMLResultsReport(ResultsReport):
  """Class to generate html result report."""

  HTML = """
<html>
  <head>
    <style type="text/css">

body {
  font-family: "Lucida Sans Unicode", "Lucida Grande", Sans-Serif;
  font-size: 12px;
}

pre {
  margin: 10px;
  color: #039;
  font-size: 14px;
}

.chart {
  display: inline;
}

.hidden {
  visibility: hidden;
}

.results-section {
  border: 1px solid #b9c9fe;
  margin: 10px;
}

.results-section-title {
  background-color: #b9c9fe;
  color: #039;
  padding: 7px;
  font-size: 14px;
  width: 200px;
}

.results-section-content {
  margin: 10px;
  padding: 10px;
  overflow:auto;
}

#box-table-a {
  font-size: 12px;
  width: 480px;
  text-align: left;
  border-collapse: collapse;
}

#box-table-a th {
  padding: 6px;
  background: #b9c9fe;
  border-right: 1px solid #fff;
  border-bottom: 1px solid #fff;
  color: #039;
  text-align: center;
}

#box-table-a td {
  padding: 4px;
  background: #e8edff;
  border-bottom: 1px solid #fff;
  border-right: 1px solid #fff;
  color: #669;
  border-top: 1px solid transparent;
}

#box-table-a tr:hover td {
  background: #d0dafd;
  color: #339;
}

    </style>
    <script type='text/javascript' src='https://www.google.com/jsapi'></script>
    <script type='text/javascript'>
      google.load('visualization', '1', {packages:['corechart']});
      google.setOnLoadCallback(init);
      function init() {
        switchTab('summary', 'html');
        %s
        switchTab('full', 'html');
        drawTable();
      }
      function drawTable() {
        %s
      }
      function switchTab(table, tab) {
        document.getElementById(table + '-html').style.display = 'none';
        document.getElementById(table + '-text').style.display = 'none';
        document.getElementById(table + '-tsv').style.display = 'none';
        document.getElementById(table + '-' + tab).style.display = 'block';
      }
    </script>
  </head>

  <body>
    <div class='results-section'>
      <div class='results-section-title'>Summary Table</div>
      <div class='results-section-content'>
        <div id='summary-html'>%s</div>
        <div id='summary-text'><pre>%s</pre></div>
        <div id='summary-tsv'><pre>%s</pre></div>
      </div>
      %s
    </div>
    %s
    <div class='results-section'>
      <div class='results-section-title'>Charts</div>
      <div class='results-section-content'>%s</div>
    </div>
    <div class='results-section'>
      <div class='results-section-title'>Full Table</div>
      <div class='results-section-content'>
        <div id='full-html'>%s</div>
        <div id='full-text'><pre>%s</pre></div>
        <div id='full-tsv'><pre>%s</pre></div>
      </div>
      %s
    </div>
    <div class='results-section'>
      <div class='results-section-title'>Experiment File</div>
      <div class='results-section-content'>
        <pre>%s</pre>
    </div>
    </div>
  </body>
</html>
"""

  PERF_HTML = """
    <div class='results-section'>
      <div class='results-section-title'>Perf Table</div>
      <div class='results-section-content'>
        <div id='perf-html'>%s</div>
        <div id='perf-text'><pre>%s</pre></div>
        <div id='perf-tsv'><pre>%s</pre></div>
      </div>
      %s
    </div>
"""

  def __init__(self, experiment):
    super(HTMLResultsReport, self).__init__(experiment)

  def _GetTabMenuHTML(self, table):
    return """
<div class='tab-menu'>
  <a href="javascript:switchTab('%s', 'html')">HTML</a>
  <a href="javascript:switchTab('%s', 'text')">Text</a>
  <a href="javascript:switchTab('%s', 'tsv')">TSV</a>
</div>""" % (table, table, table)

  def GetReport(self):
    chart_javascript = ""
    charts = self._GetCharts(self.labels, self.benchmark_runs)
    for chart in charts:
      chart_javascript += chart.GetJavascript()
    chart_divs = ""
    for chart in charts:
      chart_divs += chart.GetDiv()

    summary_table = self.GetSummaryTables()
    full_table = self.GetFullTables()
    perf_table = self.GetSummaryTables(perf=True)
    if perf_table:
      perf_html = self.PERF_HTML % (
          self.PrintTables(perf_table, "HTML"),
          self.PrintTables(perf_table, "PLAIN"),
          self.PrintTables(perf_table, "TSV"),
          self._GetTabMenuHTML("perf")
          )
      perf_init = "switchTab('perf', 'html');"
    else:
      perf_html = ""
      perf_init = ""

    return self.HTML % (perf_init,
                        chart_javascript,
                        self.PrintTables(summary_table, "HTML"),
                        self.PrintTables(summary_table, "PLAIN"),
                        self.PrintTables(summary_table, "TSV"),
                        self._GetTabMenuHTML("summary"),
                        perf_html,
                        chart_divs,
                        self.PrintTables(full_table, "HTML"),
                        self.PrintTables(full_table, "PLAIN"),
                        self.PrintTables(full_table, "TSV"),
                        self._GetTabMenuHTML("full"),
                        self.experiment.experiment_file)

  def _GetCharts(self, labels, benchmark_runs):
    charts = []
    ro = ResultOrganizer(benchmark_runs, labels)
    result = ro.result
    for item in result:
      runs = result[item]
      tg = TableGenerator(runs, ro.labels)
      table = tg.GetTable()
      columns = [Column(AmeanResult(),
                        Format()),
                 Column(MinResult(),
                        Format()),
                 Column(MaxResult(),
                        Format())
                ]
      tf = TableFormatter(table, columns)
      data_table = tf.GetCellTable("full")

      for i in range(2, len(data_table)):
        cur_row_data = data_table[i]
        test_key = cur_row_data[0].string_value
        title = "{0}: {1}".format(item, test_key.replace("/", ""))
        chart = ColumnChart(title, 300, 200)
        chart.AddColumn("Label", "string")
        chart.AddColumn("Average", "number")
        chart.AddColumn("Min", "number")
        chart.AddColumn("Max", "number")
        chart.AddSeries("Min", "line", "black")
        chart.AddSeries("Max", "line", "black")
        cur_index = 1
        for label in ro.labels:
          chart.AddRow([label, cur_row_data[cur_index].value,
                        cur_row_data[cur_index + 1].value,
                        cur_row_data[cur_index + 2].value])
          if isinstance(cur_row_data[cur_index].value, str):
            chart = None
            break
          cur_index += 3
        if chart:
          charts.append(chart)
    return charts

class JSONResultsReport(ResultsReport):
  """class to generate JASON report."""
  def __init__(self, experiment, date=None, time=None):
    super(JSONResultsReport, self).__init__(experiment)
    self.ro = ResultOrganizer(experiment.benchmark_runs,
                              experiment.labels,
                              experiment.benchmarks,
                              json_report=True)
    self.date = date
    self.time = time
    self.defaults = TelemetryDefaults()
    if not self.date:
      timestamp = datetime.datetime.strftime(datetime.datetime.now(),
                                             "%Y-%m-%d %H:%M:%S")
      date, time = timestamp.split(" ")
      self.date = date
      self.time = time

  def GetReport(self, results_dir):
    self.defaults.ReadDefaultsFile()
    final_results = []
    board = self.experiment.labels[0].board
    for test, test_results in self.ro.result.iteritems():
      for i, label in enumerate(self.ro.labels):
        label_results = test_results[i]
        for j, iter_results in enumerate(label_results):
          json_results = dict()
          json_results['date'] = self.date
          json_results['time'] = self.time
          json_results['board'] = board
          json_results['label'] = label
          common_checksum = ''
          common_string = ''
          compiler_string = 'gcc'
          for l in self.experiment.labels:
            if l.name == label:
              ver, img = ParseChromeosImage(l.chromeos_image)
              json_results['chromeos_image'] = img
              json_results['chromeos_version'] = ver
              json_results['chrome_version'] = l.chrome_version
              json_results['compiler'] = l.compiler
              # If any of the labels used the LLVM compiler, we will add
              # ".llvm" to the json report filename. (Otherwise we use .gcc).
              if 'llvm' in l.compiler:
                compiler_string = 'llvm'
              common_checksum = \
                self.experiment.machine_manager.machine_checksum[l.name]
              common_string = \
                self.experiment.machine_manager.machine_checksum_string[l.name]
              break
          json_results['test_name'] = test
          if not iter_results or iter_results['retval'] != 0:
            json_results['pass'] = False
          else:
            json_results['pass'] = True
            # Get overall results.
            if test in self.defaults.GetDefault():
              default_result_fields = self.defaults.GetDefault()[test]
              value = []
              for f in default_result_fields:
                v = iter_results[f]
                if type(v) == list:
                  v = v[0]
                item = (f, float(v))
                value.append(item)
              json_results['overall_result'] = value
            # Get detailed results.
            detail_results = dict()
            for k in iter_results.keys():
              if k != 'retval':
                v = iter_results[k]
                if type(v) == list:
                  v = v[0]
                if v != 'PASS':
                  if k.find('machine') == -1:
                    detail_results[k] = float(v)
                  else:
                    json_results[k] = v
            if 'machine_checksum' not in json_results.keys():
              json_results['machine_checksum'] = common_checksum
            if 'machine_string' not in json_results.keys():
              json_results['machine_string'] = common_string
            json_results['detailed_results'] = detail_results
          final_results.append(json_results)

    filename = "report_%s_%s_%s.%s.json" % (board, self.date,
                                            self.time.replace(':', '.'),
                                            compiler_string)
    fullname = os.path.join(results_dir, filename)
    with open(fullname, "w") as fp:
      json.dump(final_results, fp, indent=2)
