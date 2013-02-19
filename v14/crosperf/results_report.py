#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import math
from column_chart import ColumnChart
from results_columns import *
from results_sorter import ResultSorter
from results_organizer import ResultOrganizer
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

  def GetFullTables(self):
    columns = [Column(NonEmptyCountResult(),
                      Format(),
                      "Completed"),
               Column(RawResult(),
                      Format()),
               Column(MinResult(),
                      Format()),
               Column(MaxResult(),
                      Format()),
               Column(AmeanResult(),
                      Format()),
               Column(StdResult(),
                      Format())
              ]
    return self._GetTables(self.labels, self.benchmark_runs, columns)

  def GetSummaryTables(self):
    columns = [Column(AmeanResult(),
                      Format()),
               Column(GmeanRatioResult(),
                      RatioFormat(),"GmeanSpeedup"),
               Column(GmeanRatioResult(),
                      ColorBoxFormat(), " "),
               Column(StatsSignificant(),
                      Format(), "p-value")
              ]
    return self._GetTables(self.labels, self.benchmark_runs, columns)

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

  def _GetTables(self, labels, benchmark_runs, columns):
    tables = []
    ro = ResultOrganizer(benchmark_runs, labels)
    result = ro.result
    label_name = ro.labels
    for item in result:
      runs = result[item]
      for benchmark in self.benchmarks:
        if benchmark.name == item:
          break
      benchmark_info = ("Benchmark:  {0};  Iterations: {1}"
                         .format(benchmark.name, benchmark.iterations))
      cell = Cell()
      cell.string_value = benchmark_info
      ben_table = [[cell]]

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
        cell_table = tf.GetCellTable()
      tables.append(ben_table)
      tables.append(cell_table)
    return tables

  def PrintTables(self, tables, out_to):
    output = ""
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

  def __init__(self, experiment, email=False):
    super(TextResultsReport, self).__init__(experiment)
    self.email = email

  def GetStatusTable(self):
    status_table = Table("status")
    for benchmark_run in self.benchmark_runs:
      status_table.AddRow([Table.Cell(benchmark_run.name),
                           Table.Cell(benchmark_run.status),
                           Table.Cell(benchmark_run.failure_reason)])
    return status_table

  def GetReport(self):
    summary_table = self.GetSummaryTables()
    full_table = self.GetFullTables()
    if not self.email:
      return self.TEXT % (self.experiment.name,
                          self.GetStatusTable().ToText(),
                          self.experiment.machine_manager.num_reimages,
                          self.PrintTables(summary_table, "CONSOLE"),
                          self.PrintTables(full_table, "CONSOLE"),
                          #self.GetFullTable().ToText(80),
                          self.experiment.experiment_file)

    #summary_table = self.GetSummaryTables()
    #full_table = self.GetFullTable()
    #full_table.AddColor()
    return self.TEXT % (self.experiment.name,
                        self.GetStatusTable().ToText(),
                        self.experiment.machine_manager.num_reimages,
                        self.PrintTables(summary_table, "HTML"),
                        self.PrintTables(full_table, "HTML"),
                        #full_table.ToText(80),
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
    charts = self._GetCharts(self.labels, self.benchmark_runs)
    for chart in charts:
      chart_javascript += chart.GetJavascript()
    chart_divs = ""
    for chart in charts:
      chart_divs += chart.GetDiv()

    summary_table = self.GetSummaryTables()
    full_table = self.GetFullTables()
    return self.HTML % (chart_javascript,
                        self.PrintTables(summary_table, "HTML"),
                        self.PrintTables(summary_table, "PLAIN"),
                        self.PrintTables(summary_table, "TSV"),
                        self._GetTabMenuHTML("summary"),
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
      data_table = tf.GetCellTable()

      for i in range(2, len(data_table)):
        cur_row_data = data_table[i]
        autotest_key = cur_row_data[0].string_value
        title = "{0}: {1}".format(item, autotest_key.replace("/", ""))
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
