# Copyright 2012 Google Inc. All Rights Reserved.

"""Tests for misc."""

__author__ = 'asharif@google.com (Ahmad Sharif)'

# System modules
import unittest

# Local modules
import tabulator


class TabulatorTest(unittest.TestCase):
  def testResult(self):
    table = ["k1", ["1", "3"], ["55"]]
    result = tabulator.Result()
    cell = tabulator.Cell()
    result.Compute(cell, table[2], table[1])
    expected = " ".join([str(float(v)) for v in table[2]])
    self.assertTrue(cell.value == expected)

    result = tabulator.AmeanResult()
    cell = tabulator.Cell()
    result.Compute(cell, table[2], table[1])
    self.assertTrue(cell.value == float(table[2][0]))

  def testStringMean(self):
    smr = tabulator.StringMeanResult()
    cell = tabulator.Cell()
    value = "PASS"
    values = [value for _ in range(3)]
    smr.Compute(cell, values, None)
    self.assertTrue(cell.value == value)
    values.append("FAIL")
    smr.Compute(cell, values, None)
    self.assertTrue(cell.value == "?")

  def testStorageFormat(self):
    sf = tabulator.StorageFormat()
    cell = tabulator.Cell()
    base = 1024.0
    cell.value = base
    sf.Compute(cell)
    self.assertTrue(cell.string_value == "1.0K")
    cell.value = base**2
    sf.Compute(cell)
    self.assertTrue(cell.string_value == "1.0M")
    cell.value = base**3
    sf.Compute(cell)
    self.assertTrue(cell.string_value == "1.0G")

  def testLerp(self):
    c1 = tabulator.Color(0, 0, 0, 0)
    c2 = tabulator.Color(255, 0, 0, 0)
    c3 = tabulator.Color.Lerp(0.5, c1, c2)
    self.assertTrue(c3.r == 127.5)
    self.assertTrue(c3.g == 0)
    self.assertTrue(c3.b == 0)
    self.assertTrue(c3.a == 0)
    c3.Round()
    self.assertTrue(c3.r == 127)

  def testTableGenerator(self):
    runs = [[{"k1": "10", "k2": "12"},
             {"k1": "13", "k2": "14", "k3": "15"}],
            [{"k1": "50", "k2": "51", "k3": "52", "k4": "53"},]]
    labels = ["vanilla", "modified"]
    tg = tabulator.TableGenerator(runs, labels)
    table = tg.GetTable()
    header = table.pop(0)

    self.assertTrue(header == ["keys", "vanilla", "modified"])
    row = table.pop(0)
    self.assertTrue(row == ["k1", ["10", "13"], ["50"]])
    row = table.pop(0)
    self.assertTrue(row == ["k2", ["12", "14"], ["51"]])
    row = table.pop(0)
    self.assertTrue(row == ["k3", [None, "15"], ["52"]])
    row = table.pop(0)
    self.assertTrue(row == ["k4", [None, None], ["53"]])

    table = tg.GetTable()
    columns = [
        tabulator.Column(tabulator.AmeanResult(),
                         tabulator.Format()),
        tabulator.Column(tabulator.AmeanRatioResult(),
                         tabulator.PercentFormat()),
        ]
    tf = tabulator.TableFormatter(table, columns)
    table = tf.GetCellTable()
    self.assertTrue(table)


if __name__ == '__main__':
  unittest.main()
