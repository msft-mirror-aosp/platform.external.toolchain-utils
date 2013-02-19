#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import math


class Table(object):
  class Cell(object):
    """The cell class of table."""

    def __init__(self, value, colspan=1, hidden=False,
                 header=False, color="", color_theme=""):
      self.value = value
      self.colspan = colspan
      self.hidden = hidden
      self.header = header
      self.color = color
      self.color_theme = color_theme

    def Color(self):
      """Add color to number or add a color bar."""
      if not self.color_theme:
        self.value = "<FONT COLOR=#"+self.color+">"+self.value+"</FONT>"
        return None
      if self.color_theme == "background":

        """The color is represented as RGB code, and each color uses two hex
           digits. The following code computes the background color code from
           the original color code(full green 00FF00 or full red FF0000 to
           dark 000000) to full green 00FF00 or full red FF0000  to white
           FFFFFF. If first decides whether we should use green or red by
           checking the first two digit of the color code. If it is 00, we
           want green backgound. So the color code should be ??FF??, where
           the ?? is computed by 255 - green number in the original code."""

        if self.color[:2] == "00":
          ss = 255 - int(self.color[2:4], 16)
          s1 = ("%x" % ss).upper()
          bar_color = s1+"FF"+s1
        else:
          ss = 255 - int(self.color[:2], 16)
          s1 = ("%x" % ss).upper()
          bar_color = "FF"+s1*2
        self.value = ("<FONT style=\"BACKGROUND-COLOR:#"+bar_color
                      +"\" color=#"+bar_color+">--</FONT>")

  def __init__(self, table_id):
    self.table_id = table_id
    self.rows = []

  def AddRow(self, row):
    self.rows.append(row)

  def ToHTML(self):
    res = "<table id='%s'>\n" % self.table_id
    for row in self.rows:
      res += "<tr>"
      for cell in row:
        if cell.header:
          tag = "th"
        else:
          tag = "td"
        cell_class = ""
        if cell.hidden:
          cell_class = "class='hidden'"
        res += "<%s colspan='%s' %s>%s</%s>" % (tag, cell.colspan, cell_class,
                                                cell.value, tag)
      res += "</tr>\n"
    res += "</table>"
    return res

  def ToText(self, max_column_width=None):
    col_spacing = 2
    max_widths = []
    for row in self.rows:
      column = 0
      for cell in row:
        text_width = len(str(cell.value))
        per_column_width = int(math.ceil(float(text_width) / cell.colspan))
        if max_column_width:
          per_column_width = min(max_column_width, per_column_width)
        for i in range(column, column + cell.colspan):
          while i >= len(max_widths):
            max_widths.append(0)
          max_widths[i] = max(per_column_width, max_widths[i])
        column += cell.colspan

    res = ""
    for row in self.rows:
      column = 0
      for cell in row:
        val = str(cell.value)
        if max_column_width:
          if len(val) > max_column_width:
            val = val[:2] + ".." + val[len(val) - (max_column_width - 4):]
        res += val
        space_to_use = (sum(max_widths[column:column + cell.colspan]) +
                        (cell.colspan * col_spacing))
        whitespace_length = space_to_use - len(val)
        res += " " * whitespace_length
        # Add space b/w columns
        column += cell.colspan
      res += "\n"
    return res

  def ToTSV(self):
    res = ""
    column = 0
    for row in self.rows:
      for cell in row:
        res += str(cell.value).replace("\t", "    ")
        for _ in range(column, column + cell.colspan):
          res += "\t"
      res += "\n"
    return res

  def AddColor(self):
    for row in self.rows:
      for cell in row:
        if cell.color:
          cell.Color()
