def GetContentType():
  return "Content-Type: text/html\n\n"

def GetPageHeader(page_title):
  return """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
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

def GetListHeader():
  return "<ul>"

def GetListItem(text):
  return "<li>%s</li>" % text

def GetListFooter():
  return "</ul>"

def GetParagraph(text):
  return "<p>%s</p>" % text

def GetFooter():
  return """</body> 
</html>"""

def GetHeader(text, h=1):
  return "<h%s>%s</h%s>" % (str(h), text, str(h))

def GetTableHeader(columns):
  res = "<table>"
  res += "<tr>"
  for column in columns:
    res += "<th>%s</th>" % str(column)
  res += "</tr>"
  return res

def GetTableFooter():
  return "</table>"

def FormatLineBreaks(text):
  ret = text
  ret = ret.replace("\n", "<br>")
  return ret

def GetTableCell(text):
  text = FormatLineBreaks(str(text))
  return "<td>%s</td>" % text
  
def GetTableRow(columns):
  res = "<tr>"
  for column in columns:
    res += GetTableCell(column)
  res += "<tr/>"
  return res
  
def GetLink(link, text):
  return "<a href='%s'>%s</a>" % (link, text)