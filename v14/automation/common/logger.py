#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import gzip
import logging
import logging.handlers
import time
import traceback


def SetUpRootLogger(filename=None, level=None):
  console_handler = logging.StreamHandler()
  console_handler.setFormatter(CustomFormatter(AnsiColorCoder()))
  logging.root.addHandler(console_handler)

  if filename:
    file_handler = logging.handlers.RotatingFileHandler(
        filename, maxBytes=10*1024*1024, backupCount=9, delay=True)
    file_handler.setFormatter(CustomFormatter(NullColorCoder()))
    logging.root.addHandler(file_handler)

  if level:
    logging.root.setLevel(level)


class NullColorCoder(object):
  def __call__(self, *args):
    return ''


class AnsiColorCoder(object):
  CODES = {'reset': (0, ),
           'bold': (1, 22),
           'italics': (3, 23),
           'underline': (4, 24),
           'inverse': (7, 27),
           'strikethrough': (9, 29),
           'black': (30, 40),
           'red': (31, 41),
           'green': (32, 42),
           'yellow': (33, 43),
           'blue': (34, 44),
           'magenta': (35, 45),
           'cyan': (36, 46),
           'white': (37, 47)}

  def __call__(self, *args):
    codes = []

    for arg in args:
      if arg.startswith('bg-') or arg.startswith('no-'):
        codes.append(self.CODES[arg[3:]][1])
      else:
        codes.append(self.CODES[arg][0])

    return '\033[%sm' % ';'.join(map(str, codes))


class CustomFormatter(logging.Formatter):
  COLORS = {'DEBUG': ('white',),
            'INFO': ('green',),
            'WARN': ('yellow', 'bold'),
            'ERROR': ('red', 'bold'),
            'CRIT': ('red', 'inverse', 'bold')}

  def __init__(self, coder):
    logging.Formatter.__init__(self, fmt=(
            '%(asctime)s %(levelname)s ' + coder('cyan') +
            '[%(threadName)s:%(name)s]' + coder('reset') + ' %(message)s'))

    self._coder = coder

  def formatTime(self, record):
    ct = self.converter(record.created)
    t = time.strftime("%Y-%m-%d %H:%M:%S", ct)
    return "%s.%02d" % (t, record.msecs / 10)

  def format(self, record):
    if record.levelname in ['WARNING', 'CRITICAL']:
      levelname = record.levelname[:4]
    else:
      levelname = record.levelname

    fmt = record.__dict__.copy()
    fmt.update({
        'levelname': '%s%s%s' % (self._coder(*self.COLORS[levelname]),
                                 levelname, self._coder('reset')),
        'asctime': self.formatTime(record)})

    s = []

    for line in record.getMessage().splitlines():
      try:
        fmt['message'] = (
            '%s%s:%s %s' % (self._coder('black', 'bold'), record.prefix,
                            self._coder('reset'), line))
      except AttributeError:
        fmt['message'] = line

      s.append(self._fmt % fmt)

    return '\n'.join(s)


class CompressedFileHandler(logging.FileHandler):
  def _open(self):
    return gzip.open(self.baseFilename + '.gz', self.mode, 9)


def HandleUncaughtExceptions(fun):
  """Catches all exceptions that would go outside decorated fun scope."""

  def _Interceptor(*args, **kwargs):
    try:
      return fun(*args, **kwargs)
    except StandardError as ex:
      logging.error("Uncaught exception:")
      logging.error(ex)

  return _Interceptor
