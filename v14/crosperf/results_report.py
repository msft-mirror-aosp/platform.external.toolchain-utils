#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import math
from column_chart import ColumnChart
from results_columns import *
from results_sorter import ResultSorter
from table import Table
from utils.tabulator import *

class ResultsReport(object):
  DELTA_COLUMN_NAME = "Change"
  CHANGE_COLOR_NAME = ""
  STATS_DIFF_NAME = "p value"
  MAX_COLOR_CODE = 255

  def __init__(self, experiment):
    self.experiment = experiment
    self.benchmark_runs = experiment.benchmark_runs
    self.labels = experiment.labels
    self.benchmarks = experiment.benchmarks
    self.baseline = self.labels[0]

  def _ShouldSkipColumn(self, column):
    if column.name in [self.DELTA_COLUMN_NAME, self.CHANGE_COLOR_NAME,
                       self.STATS_DIFF_NAME]:
      return True
    return False

  def _GetColorCode(self, number, power_factor=4):
    number = round(number, 2)
    if number < 1:
      color = int(math.pow((1-number), 1.0/power_factor)
                  * self.MAX_COLOR_CODE)
      color_string = ("%x" % color).upper()
      if len(color_string) < 2:
        color_string = "0"+color_string
      color_string += "0000"
    if number >= 1:
      number = 2 - 1/number
      color = int(math.pow((number - 1), 1.0/power_factor)
                  * self.MAX_COLOR_CODE)
      cc = ("%x" % color).upper()
      if len(cc) < 2:
        cc = "0" + cc
      color_string = "00"+cc+"00"
    return color_string

  def _IsLowerBetter(self, column, autotest_key):
    if ((autotest_key.find("milliseconds") == 0
         or autotest_key.find("ms_") == 0
         or autotest_key.find("seconds") == 0
         or autotest_key.find("KB_") == 0)
        and column.name == self.DELTA_COLUMN_NAME):
      return True
    return False

  def _SortByLabel(self, runs):
    labels = {}
    for benchmark_run in runs:
      if benchmark_run.label_name not in labels:
        labels[benchmark_run.label_name] = []
      labels[benchmark_run.label_name].append(benchmark_run)
    return labels

  def GetFullTable(self):
    full_columns = []
    max_iterations = 0
    for benchmark in self.benchmarks:
      if benchmark.iterations > max_iterations:
        max_iterations = benchmark.iterations

    for i in range(1, max_iterations + 1):
      full_columns.append(IterationColumn(str(i), i))

    full_columns.append(IterationsCompleteColumn("Completed"))
    full_columns.append(MinColumn("Min"))
    full_columns.append(MaxColumn("Max"))
    full_columns.append(MeanColumn("Avg"))
    full_columns.append(StandardDeviationColumn("Std Dev"))
    full_columns.append(RatioColumn(self.DELTA_COLUMN_NAME))
    return self._GetTable(self.labels, self.benchmarks, self.benchmark_runs,
                          full_columns)

  def GetSummaryTable(self):
    summary_columns = [MeanColumn("Average"),
                       RatioColumn(self.DELTA_COLUMN_NAME),
                       ColorColumn(self.CHANGE_COLOR_NAME),
                       SignificantDiffColumn(self.STATS_DIFF_NAME)]
    return self._GetTable(self.labels, self.benchmarks, self.benchmark_runs,
                          summary_columns)

  def _GetTable(self, labels, benchmarks, benchmark_runs, columns):
    table = Table("box-table-a")
    label_headings = [Table.Cell("", hidden=True, colspan=2, header=True)]
    for label in labels:
      colspan = len(columns)
      for col in columns:
        if self._ShouldSkipColumn(col):
          colspan -= 1
      label_headings.append(Table.Cell(label.name, colspan=colspan,
                                       header=True))

    table.AddRow(label_headings)

    column_headings = [Table.Cell("Autotest Key", header=True),
                       Table.Cell("Iterations", header=True)]
    for label in labels:
      for column in columns:
        if (label.name == self.baseline.name and
            self._ShouldSkipColumn(column)):
          continue
        column_headings.append(Table.Cell(column.name, header=True))

    table.AddRow(column_headings)

    sorter = ResultSorter(benchmark_runs)

    for benchmark in benchmarks:
      table.AddRow([Table.Cell(benchmark.name)])
      autotest_keys = sorter.GetAutotestKeys(benchmark.name)
      for autotest_key in sorted(autotest_keys):
        row = [Table.Cell(autotest_key),
               Table.Cell(benchmark.iterations)]
        for label in labels:
          row_color = ""
          for column in columns:
            if (label.name == self.baseline.name and
                self._ShouldSkipColumn(column)):
              continue
            results = sorter.GetResults(benchmark.name,
                                        autotest_key, label.name)
            baseline_results = sorter.GetResults(benchmark.name,
                                                 autotest_key,
                                                 self.baseline.name)
            value = column.Compute(results, baseline_results)
            if isinstance(value, float):
              if self._IsLowerBetter(column, autotest_key):
                value = 1/value
              value_string = "%.2f" % value
              if column.name == self.DELTA_COLUMN_NAME:
                row_color = self._GetColorCode(value)
            else:
              value_string = value
            if column.name == self.DELTA_COLUMN_NAME:
              row.append(Table.Cell(value_string, color=row_color))
            elif column.name == self.CHANGE_COLOR_NAME:
              row.append(Table.Cell(value_string, color=row_color,
                                    color_theme="background"))
            else:
              row.append(Table.Cell(value_string))
        table.AddRow(row)

    return table


class TextResultsReport(ResultsReport):
  TEXT = """
===========================================
Results report for: '%s'
===========================================

-------------------------------------------
Benchmark Run Status
-------------------------------------------
%s

Number re-images: %s

-------------------------------------------
Summary
-------------------------------------------
%s

-------------------------------------------
Full Table
-------------------------------------------
%s

-------------------------------------------
Experiment File
-------------------------------------------
%s
===========================================
"""

  def __init__(self, experiment, color=False):
    super(TextResultsReport, self).__init__(experiment)
    self.color = color

  def GetStatusTable(self):
    status_table = Table("status")
    for benchmark_run in self.benchmark_runs:
      status_table.AddRow([Table.Cell(benchmark_run.name),
                           Table.Cell(benchmark_run.status),
                           Table.Cell(benchmark_run.failure_reason)])
    return status_table

  def GetReport(self):
    if not self.color:
      return self.TEXT % (self.experiment.name,
                          self.GetStatusTable().ToText(),
                          self.experiment.machine_manager.num_reimages,
                          self.GetSummaryTable().ToText(80),
                          self.GetFullTable().ToText(80),
                          self.experiment.experiment_file)

    summary_table = self.GetSummaryTable()
    full_table = self.GetFullTable()
    summary_table.AddColor()
    full_table.AddColor()
    return self.TEXT % (self.experiment.name,
                        self.GetStatusTable().ToText(),
                        self.experiment.machine_manager.num_reimages,
                        summary_table.ToText(120),
                        full_table.ToText(80),
                        self.experiment.experiment_file)


class HTMLResultsReport(ResultsReport):
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
    charts = self._GetCharts(self.labels, self.benchmarks, self.benchmark_runs)
    for chart in charts:
      chart_javascript += chart.GetJavascript()
    chart_divs = ""
    for chart in charts:
      chart_divs += chart.GetDiv()

    summary_table = self.GetSummaryTable()
    summary_table.AddColor()
    full_table = self.GetFullTable()
    full_table.AddColor()
    return self.HTML % (chart_javascript,
                        summary_table.ToHTML(),
                        summary_table.ToText(),
                        summary_table.ToTSV(),
                        self._GetTabMenuHTML("summary"),
                        chart_divs,
                        full_table.ToHTML(),
                        full_table.ToText(),
                        full_table.ToTSV(),
                        self._GetTabMenuHTML("full"),
                        self.experiment.experiment_file)

  def _GetCharts(self, labels, benchmarks, benchmark_runs):
    charts = []
    sorter = ResultSorter(benchmark_runs)

    for benchmark in benchmarks:
      autotest_keys = sorter.GetAutotestKeys(benchmark.name)

      for autotest_key in autotest_keys:
        title = "%s: %s" % (benchmark.name, autotest_key.replace("/", " "))
        chart = ColumnChart(title, 300, 200)
        chart.AddColumn("Label", "string")
        chart.AddColumn("Average", "number")
        chart.AddColumn("Min", "number")
        chart.AddColumn("Max", "number")
        chart.AddSeries("Min", "line", "black")
        chart.AddSeries("Max", "line", "black")

        for label in labels:
          res = sorter.GetResults(benchmark.name, autotest_key, label.name)
          avg_val = MeanColumn("").Compute(res, None)
          min_val = MinColumn("").Compute(res, None)
          max_val = MaxColumn("").Compute(res, None)
          chart.AddRow([label.name, avg_val, min_val, max_val])
          if isinstance(avg_val, str):
            chart = None
            break

        if chart:
          charts.append(chart)
    return charts
