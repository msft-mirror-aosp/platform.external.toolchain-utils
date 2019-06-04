#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Grep warnings messages and output HTML tables or warning counts in CSV.

Default is to output warnings in HTML tables grouped by warning severity.
Use option --byproject to output tables grouped by source file projects.
Use option --gencsv to output warning counts in CSV format.
"""

# FIXME: This was imported from Android at
# ${android_root}/build/make/tools/warn.py, so it has some Android-specific
# bits. Java-specific warnings have been removed but other details such as
# the project list still have Android-specific parts.

# List of important data structures and functions in this script.
#
# To parse and keep warning message in the input file:
#   severity:                classification of message severity
#   severity.range           [0, 1, ... last_severity_level]
#   severity.colors          for header background
#   severity.column_headers  for the warning count table
#   severity.headers         for warning message tables
#   warn_patterns:
#   warn_patterns[w]['category']     tool that issued the warning, not used now
#   warn_patterns[w]['description']  table heading
#   warn_patterns[w]['members']      matched warnings from input
#   warn_patterns[w]['option']       compiler flag to control the warning
#   warn_patterns[w]['patterns']     regular expressions to match warnings
#   warn_patterns[w]['projects'][p]  number of warnings of pattern w in p
#   warn_patterns[w]['severity']     severity level
#   project_list[p][0]               project name
#   project_list[p][1]               regular expression to match a project path
#   project_patterns[p]              re.compile(project_list[p][1])
#   project_names[p]                 project_list[p][0]
#   warning_messages     array of each warning message, without source url
#   warning_records      array of [idx to warn_patterns,
#                                  idx to project_names,
#                                  idx to warning_messages]
#   android_root
#   platform_version
#   target_product
#   target_variant
#   compile_patterns, parse_input_file
#
# To emit html page of warning messages:
#   flags: --byproject, --url, --separator
# Old stuff for static html components:
#   html_script_style:  static html scripts and styles
#   htmlbig:
#   dump_stats, dump_html_prologue, dump_html_epilogue:
#   emit_buttons:
#   dump_fixed
#   sort_warnings:
#   emit_stats_by_project:
#   all_patterns,
#   findproject, classify_warning
#   dump_html
#
# New dynamic HTML page's static JavaScript data:
#   Some data are copied from Python to JavaScript, to generate HTML elements.
#   FlagURL                args.url
#   FlagSeparator          args.separator
#   SeverityColors:        severity.colors
#   SeverityHeaders:       severity.headers
#   SeverityColumnHeaders: severity.column_headers
#   ProjectNames:          project_names, or project_list[*][0]
#   WarnPatternsSeverity:     warn_patterns[*]['severity']
#   WarnPatternsDescription:  warn_patterns[*]['description']
#   WarnPatternsOption:       warn_patterns[*]['option']
#   WarningMessages:          warning_messages
#   Warnings:                 warning_records
#   StatsHeader:           warning count table header row
#   StatsRows:             array of warning count table rows
#
# New dynamic HTML page's dynamic JavaScript data:
#
# New dynamic HTML related function to emit data:
#   escape_string, strip_escape_string, emit_warning_arrays
#   emit_js_data():

from __future__ import print_function

import argparse
import cgi
import csv
import multiprocessing
import os
import re
import signal
import sys

from clang_tidy_warn_patterns import warn_patterns, Severity

# TODO: move the parser code into a function
parser = argparse.ArgumentParser(description='Convert a build log into HTML')
parser.add_argument(
    '--csvpath',
    help='Save CSV warning file to the passed absolute path',
    default=None)
parser.add_argument(
    '--gencsv',
    help='Generate a CSV file with number of various warnings',
    action='store_true',
    default=False)
parser.add_argument(
    '--byproject',
    help='Separate warnings in HTML output by project names',
    action='store_true',
    default=False)
parser.add_argument(
    '--url',
    help='Root URL of an Android source code tree prefixed '
    'before files in warnings')
parser.add_argument(
    '--separator',
    help='Separator between the end of a URL and the line '
    'number argument. e.g. #')
parser.add_argument(
    '--processes',
    type=int,
    default=multiprocessing.cpu_count(),
    help='Number of parallel processes to process warnings')
parser.add_argument(
    dest='buildlog', metavar='build.log', help='Path to build.log file')

if len(sys.argv) > 1:
  args = parser.parse_args()
else:
  args = None


class Severity(object):
  """Severity levels and attributes."""
  # numbered by dump order
  FIXMENOW = 0
  HIGH = 1
  MEDIUM = 2
  LOW = 3
  ANALYZER = 4
  TIDY = 5
  HARMLESS = 6
  UNKNOWN = 7
  SKIP = 8
  range = range(SKIP + 1)
  attributes = [
      # pylint:disable=bad-whitespace
      ['fuchsia', 'FixNow', 'Critical warnings, fix me now'],
      ['red', 'High', 'High severity warnings'],
      ['orange', 'Medium', 'Medium severity warnings'],
      ['yellow', 'Low', 'Low severity warnings'],
      ['hotpink', 'Analyzer', 'Clang-Analyzer warnings'],
      ['peachpuff', 'Tidy', 'Clang-Tidy warnings'],
      ['limegreen', 'Harmless', 'Harmless warnings'],
      ['lightblue', 'Unknown', 'Unknown warnings'],
      ['grey', 'Unhandled', 'Unhandled warnings']
  ]
  colors = [a[0] for a in attributes]
  column_headers = [a[1] for a in attributes]
  headers = [a[2] for a in attributes]


def project_name_and_pattern(name, pattern):
  return [name, '(^|.*/)' + pattern + '/.*: warning:']


def simple_project_pattern(pattern):
  return project_name_and_pattern(pattern, pattern)


# A list of [project_name, file_path_pattern].
# project_name should not contain comma, to be used in CSV output.
project_list = [
    simple_project_pattern('android_webview'),
    simple_project_pattern('apps'),
    simple_project_pattern('ash'),
    simple_project_pattern('base'),
    simple_project_pattern('build'),
    simple_project_pattern('build_overrides'),
    simple_project_pattern('buildtools'),
    simple_project_pattern('cc'),
    simple_project_pattern('chrome'),
    simple_project_pattern('chromecast'),
    simple_project_pattern('chromeos'),
    simple_project_pattern('cloud_print'),
    simple_project_pattern('components'),
    simple_project_pattern('content'),
    simple_project_pattern('courgette'),
    simple_project_pattern('crypto'),
    simple_project_pattern('dbus'),
    simple_project_pattern('device'),
    simple_project_pattern('docs'),
    simple_project_pattern('extensions'),
    simple_project_pattern('fuchsia'),
    simple_project_pattern('gin'),
    simple_project_pattern('google_apis'),
    simple_project_pattern('google_update'),
    simple_project_pattern('gpu'),
    simple_project_pattern('headless'),
    simple_project_pattern('infra'),
    simple_project_pattern("ipc"),
    simple_project_pattern("jingle"),
    simple_project_pattern("media"),
    simple_project_pattern("mojo"),
    simple_project_pattern("native_client"),
    simple_project_pattern("ative_client_sdk"),
    simple_project_pattern("net"),
    simple_project_pattern("out"),
    simple_project_pattern("pdf"),
    simple_project_pattern("ppapi"),
    simple_project_pattern("printing"),
    simple_project_pattern("remoting"),
    simple_project_pattern("rlz"),
    simple_project_pattern("sandbox"),
    simple_project_pattern("services"),
    simple_project_pattern("skia"),
    simple_project_pattern("sql"),
    simple_project_pattern("storage"),
    simple_project_pattern("styleguide"),
    simple_project_pattern("testing"),
    simple_project_pattern("third_party/Python-Markdown"),
    simple_project_pattern("third_party/SPIRV-Tools"),
    simple_project_pattern("third_party/abseil-cpp"),
    simple_project_pattern("third_party/accessibility-audit"),
    simple_project_pattern("third_party/accessibility_test_framework"),
    simple_project_pattern("third_party/adobe"),
    simple_project_pattern("third_party/afl"),
    simple_project_pattern("third_party/android_build_tools"),
    simple_project_pattern("third_party/android_crazy_linker"),
    simple_project_pattern("third_party/android_data_chart"),
    simple_project_pattern("third_party/android_deps"),
    simple_project_pattern("third_party/android_media"),
    simple_project_pattern("third_party/android_ndk"),
    simple_project_pattern("third_party/android_opengl"),
    simple_project_pattern("third_party/android_platform"),
    simple_project_pattern("third_party/android_protobuf"),
    simple_project_pattern("third_party/android_sdk"),
    simple_project_pattern("third_party/android_support_test_runner"),
    simple_project_pattern("third_party/android_swipe_refresh"),
    simple_project_pattern("third_party/android_system_sdk"),
    simple_project_pattern("third_party/android_tools"),
    simple_project_pattern("third_party/angle"),
    simple_project_pattern("third_party/apache-mac"),
    simple_project_pattern("third_party/apache-portable-runtime"),
    simple_project_pattern("third_party/apache-win32"),
    simple_project_pattern("third_party/apk-patch-size-estimator"),
    simple_project_pattern("third_party/apple_apsl"),
    simple_project_pattern("third_party/arcore-android-sdk"),
    simple_project_pattern("third_party/ashmem"),
    simple_project_pattern("third_party/auto"),
    simple_project_pattern("third_party/axe-core"),
    simple_project_pattern("third_party/bazel"),
    simple_project_pattern("third_party/binutils"),
    simple_project_pattern("third_party/bison"),
    simple_project_pattern("third_party/blanketjs"),
    simple_project_pattern("third_party/blink/common"),
    simple_project_pattern("third_party/blink/manual_tests"),
    simple_project_pattern("third_party/blink/perf_tests"),
    simple_project_pattern("third_party/blink/public"),
    simple_project_pattern("third_party/blink/renderer"),
    simple_project_pattern("third_party/blink/tools"),
    simple_project_pattern("third_party/blink/web_tests"),
    simple_project_pattern("third_party/boringssl"),
    simple_project_pattern("third_party/bouncycastle"),
    simple_project_pattern("third_party/breakpad"),
    simple_project_pattern("third_party/brotli"),
    simple_project_pattern("third_party/bspatch"),
    simple_project_pattern("third_party/byte_buddy"),
    simple_project_pattern("third_party/cacheinvalidation"),
    simple_project_pattern("third_party/catapult"),
    simple_project_pattern("third_party/cct_dynamic_module"),
    simple_project_pattern("third_party/ced"),
    simple_project_pattern("third_party/chaijs"),
    simple_project_pattern("third_party/checkstyle"),
    simple_project_pattern("third_party/chromevox"),
    simple_project_pattern("third_party/chromite"),
    simple_project_pattern("third_party/cld_3"),
    simple_project_pattern("third_party/closure_compiler"),
    simple_project_pattern("third_party/colorama"),
    simple_project_pattern("third_party/crashpad"),
    simple_project_pattern("third_party/crc32c"),
    simple_project_pattern("third_party/cros_system_api"),
    simple_project_pattern("third_party/custom_tabs_client"),
    simple_project_pattern("third_party/d3"),
    simple_project_pattern("third_party/dav1d"),
    simple_project_pattern("third_party/dawn"),
    simple_project_pattern("third_party/decklink"),
    simple_project_pattern("third_party/depot_tools"),
    simple_project_pattern("third_party/devscripts"),
    simple_project_pattern("third_party/devtools-node-modules"),
    simple_project_pattern("third_party/dom_distiller_js"),
    simple_project_pattern("third_party/elfutils"),
    simple_project_pattern("third_party/emoji-segmenter"),
    simple_project_pattern("third_party/errorprone"),
    simple_project_pattern("third_party/espresso"),
    simple_project_pattern("third_party/expat"),
    simple_project_pattern("third_party/feed"),
    simple_project_pattern("third_party/ffmpeg"),
    simple_project_pattern("third_party/flac"),
    simple_project_pattern("third_party/flatbuffers"),
    simple_project_pattern("third_party/flot"),
    simple_project_pattern("third_party/fontconfig"),
    simple_project_pattern("third_party/freetype"),
    simple_project_pattern("third_party/fuchsia-sdk"),
    simple_project_pattern("third_party/gestures"),
    simple_project_pattern("third_party/gif_player"),
    simple_project_pattern("third_party/glfw"),
    simple_project_pattern("third_party/glslang"),
    simple_project_pattern("third_party/gnu_binutils"),
    simple_project_pattern("third_party/google-truth"),
    simple_project_pattern("third_party/google_android_play_core"),
    simple_project_pattern("third_party/google_appengine_cloudstorage"),
    simple_project_pattern("third_party/google_input_tools"),
    simple_project_pattern("third_party/google_toolbox_for_mac"),
    simple_project_pattern("third_party/google_trust_services"),
    simple_project_pattern("third_party/googletest"),
    simple_project_pattern("third_party/gperf"),
    simple_project_pattern("third_party/gradle_wrapper"),
    simple_project_pattern("third_party/grpc"),
    simple_project_pattern("third_party/gson"),
    simple_project_pattern("third_party/guava"),
    simple_project_pattern("third_party/gvr-android-keyboard"),
    simple_project_pattern("third_party/gvr-android-sdk"),
    simple_project_pattern("third_party/hamcrest"),
    simple_project_pattern("third_party/harfbuzz-ng"),
    simple_project_pattern("third_party/hunspell"),
    simple_project_pattern("third_party/hunspell_dictionaries"),
    simple_project_pattern("third_party/iaccessible2"),
    simple_project_pattern("third_party/iccjpeg"),
    simple_project_pattern("third_party/icu"),
    simple_project_pattern("third_party/icu4j"),
    simple_project_pattern("third_party/ijar"),
    simple_project_pattern("third_party/ink"),
    simple_project_pattern("third_party/inspector_protocol"),
    simple_project_pattern("third_party/instrumented_libraries"),
    simple_project_pattern("third_party/intellij"),
    simple_project_pattern("third_party/isimpledom"),
    simple_project_pattern("third_party/jacoco"),
    simple_project_pattern("third_party/jinja2"),
    simple_project_pattern("third_party/jsoncpp"),
    simple_project_pattern("third_party/jsr-305"),
    simple_project_pattern("third_party/jstemplate"),
    simple_project_pattern("third_party/junit"),
    simple_project_pattern("third_party/khronos"),
    simple_project_pattern("third_party/lcov"),
    simple_project_pattern("third_party/leveldatabase"),
    simple_project_pattern("third_party/libFuzzer"),
    simple_project_pattern("third_party/libXNVCtrl"),
    simple_project_pattern("third_party/libaddressinput"),
    simple_project_pattern("third_party/libaom"),
    simple_project_pattern("third_party/libcxx-pretty-printers"),
    simple_project_pattern("third_party/libdrm"),
    simple_project_pattern("third_party/libevdev"),
    simple_project_pattern("third_party/libjingle_xmpp"),
    simple_project_pattern("third_party/libjpeg"),
    simple_project_pattern("third_party/libjpeg_turbo"),
    simple_project_pattern("third_party/liblouis"),
    simple_project_pattern("third_party/libovr"),
    simple_project_pattern("third_party/libphonenumber"),
    simple_project_pattern("third_party/libpng"),
    simple_project_pattern("third_party/libprotobuf-mutator"),
    simple_project_pattern("third_party/libsecret"),
    simple_project_pattern("third_party/libsrtp"),
    simple_project_pattern("third_party/libsync"),
    simple_project_pattern("third_party/libudev"),
    simple_project_pattern("third_party/libusb"),
    simple_project_pattern("third_party/libvpx"),
    simple_project_pattern("third_party/libwebm"),
    simple_project_pattern("third_party/libwebp"),
    simple_project_pattern("third_party/libxml"),
    simple_project_pattern("third_party/libxslt"),
    simple_project_pattern("third_party/libyuv"),
    simple_project_pattern("third_party/lighttpd"),
    simple_project_pattern("third_party/logilab"),
    simple_project_pattern("third_party/lss"),
    simple_project_pattern("third_party/lzma_sdk"),
    simple_project_pattern("third_party/mach_override"),
    simple_project_pattern("third_party/markdown"),
    simple_project_pattern("third_party/markupsafe"),
    simple_project_pattern("third_party/material_design_icons"),
    simple_project_pattern("third_party/mesa_headers"),
    simple_project_pattern("third_party/metrics_proto"),
    simple_project_pattern("third_party/microsoft_webauthn"),
    simple_project_pattern("third_party/mingw-w64"),
    simple_project_pattern("third_party/minigbm"),
    simple_project_pattern("third_party/minizip"),
    simple_project_pattern("third_party/mocha"),
    simple_project_pattern("third_party/mockito"),
    simple_project_pattern("third_party/modp_b64"),
    simple_project_pattern("third_party/motemplate"),
    simple_project_pattern("third_party/mozilla"),
    simple_project_pattern("third_party/nacl_sdk_binaries"),
    simple_project_pattern("third_party/nasm"),
    simple_project_pattern("third_party/netty-tcnative"),
    simple_project_pattern("third_party/netty4"),
    simple_project_pattern("third_party/node"),
    simple_project_pattern("third_party/nvml"),
    simple_project_pattern("third_party/objenesis"),
    simple_project_pattern("third_party/ocmock"),
    simple_project_pattern("third_party/openh264"),
    simple_project_pattern("third_party/openscreen"),
    simple_project_pattern("third_party/openvr"),
    simple_project_pattern("third_party/opus"),
    simple_project_pattern("third_party/ots"),
    simple_project_pattern("third_party/ow2_asm"),
    simple_project_pattern("third_party/pdfium"),
    simple_project_pattern("third_party/pefile"),
    simple_project_pattern("third_party/perfetto"),
    simple_project_pattern("third_party/perl"),
    simple_project_pattern("third_party/pexpect"),
    simple_project_pattern("third_party/pffft"),
    simple_project_pattern("third_party/ply"),
    simple_project_pattern("third_party/polymer"),
    simple_project_pattern("third_party/proguard"),
    simple_project_pattern("third_party/protobuf"),
    simple_project_pattern("third_party/protoc_javalite"),
    simple_project_pattern("third_party/pycoverage"),
    simple_project_pattern("third_party/pyelftools"),
    simple_project_pattern("third_party/pyjson5"),
    simple_project_pattern("third_party/pylint"),
    simple_project_pattern("third_party/pymock"),
    simple_project_pattern("third_party/pystache"),
    simple_project_pattern("third_party/pywebsocket"),
    simple_project_pattern("third_party/qcms"),
    simple_project_pattern("third_party/quic_trace"),
    simple_project_pattern("third_party/qunit"),
    simple_project_pattern("third_party/r8"),
    simple_project_pattern("third_party/re2"),
    simple_project_pattern("third_party/requests"),
    simple_project_pattern("third_party/rnnoise"),
    simple_project_pattern("third_party/robolectric"),
    simple_project_pattern("third_party/s2cellid"),
    simple_project_pattern("third_party/sfntly"),
    simple_project_pattern("third_party/shaderc"),
    simple_project_pattern("third_party/simplejson"),
    simple_project_pattern("third_party/sinonjs"),
    simple_project_pattern("third_party/skia"),
    simple_project_pattern("third_party/smhasher"),
    simple_project_pattern("third_party/snappy"),
    simple_project_pattern("third_party/speech-dispatcher"),
    simple_project_pattern("third_party/spirv-cross"),
    simple_project_pattern("third_party/spirv-headers"),
    simple_project_pattern("third_party/sqlite"),
    simple_project_pattern("third_party/sqlite4java"),
    simple_project_pattern("third_party/sudden_motion_sensor"),
    simple_project_pattern("third_party/swiftshader"),
    simple_project_pattern("third_party/tcmalloc"),
    simple_project_pattern("third_party/test_fonts"),
    simple_project_pattern("third_party/tlslite"),
    simple_project_pattern("third_party/ub-uiautomator"),
    simple_project_pattern("third_party/unrar"),
    simple_project_pattern("third_party/usb_ids"),
    simple_project_pattern("third_party/usrsctp"),
    simple_project_pattern("third_party/v4l-utils"),
    simple_project_pattern("third_party/vulkan"),
    simple_project_pattern("third_party/wayland"),
    simple_project_pattern("third_party/wayland-protocols"),
    simple_project_pattern("third_party/wds"),
    simple_project_pattern("third_party/web-animations-js"),
    simple_project_pattern("third_party/webdriver"),
    simple_project_pattern("third_party/webgl"),
    simple_project_pattern("third_party/webrtc"),
    simple_project_pattern("third_party/webrtc_overrides"),
    simple_project_pattern("third_party/webxr_test_pages"),
    simple_project_pattern("third_party/widevine"),
    simple_project_pattern("third_party/win_build_output"),
    simple_project_pattern("third_party/woff2"),
    simple_project_pattern("third_party/wtl"),
    simple_project_pattern("third_party/xdg-utils"),
    simple_project_pattern("third_party/xstream"),
    simple_project_pattern("third_party/yasm"),
    simple_project_pattern("third_party/zlib"),
    simple_project_pattern("tools"),
    simple_project_pattern("ui"),
    simple_project_pattern("url"),
    simple_project_pattern("v8"),
    # keep out/obj and other patterns at the end.
    [
        'out/obj', '.*/(gen|obj[^/]*)/(include|EXECUTABLES|SHARED_LIBRARIES|'
        'STATIC_LIBRARIES|NATIVE_TESTS)/.*: warning:'
    ],
    ['other', '.*']  # all other unrecognized patterns
]

warning_messages = []
warning_records = []


def initialize_arrays():
  """Complete global arrays before they are used."""
  names = [p[0] for p in project_list]
  patterns = [re.compile(p[1]) for p in project_list]
  for w in warn_patterns:
    w['members'] = []
    if 'option' not in w:
      w['option'] = ''
    # Each warning pattern has a 'projects' dictionary, that
    # maps a project name to number of warnings in that project.
    w['projects'] = {}
  return names, patterns


project_names, project_patterns = initialize_arrays()

android_root = ''
platform_version = 'unknown'
target_product = 'unknown'
target_variant = 'unknown'

##### Data and functions to dump html file. ##################################

html_head_scripts = """\
  <script type="text/javascript">
  function expand(id) {
    var e = document.getElementById(id);
    var f = document.getElementById(id + "_mark");
    if (e.style.display == 'block') {
       e.style.display = 'none';
       f.innerHTML = '&#x2295';
    }
    else {
       e.style.display = 'block';
       f.innerHTML = '&#x2296';
    }
  };
  function expandCollapse(show) {
    for (var id = 1; ; id++) {
      var e = document.getElementById(id + "");
      var f = document.getElementById(id + "_mark");
      if (!e || !f) break;
      e.style.display = (show ? 'block' : 'none');
      f.innerHTML = (show ? '&#x2296' : '&#x2295');
    }
  };
  </script>
  <style type="text/css">
  th,td{border-collapse:collapse; border:1px solid black;}
  .button{color:blue;font-size:110%;font-weight:bolder;}
  .bt{color:black;background-color:transparent;border:none;outline:none;
      font-size:140%;font-weight:bolder;}
  .c0{background-color:#e0e0e0;}
  .c1{background-color:#d0d0d0;}
  .t1{border-collapse:collapse; width:100%; border:1px solid black;}
  </style>
  <script src="https://www.gstatic.com/charts/loader.js"></script>
"""


def html_big(param):
  return '<font size="+2">' + param + '</font>'


def dump_html_prologue(title):
  print('<html>\n<head>')
  print('<title>' + title + '</title>')
  print(html_head_scripts)
  emit_stats_by_project()
  print('</head>\n<body>')
  print(html_big(title))
  print('<p>')


def dump_html_epilogue():
  print('</body>\n</head>\n</html>')


def sort_warnings():
  for i in warn_patterns:
    i['members'] = sorted(set(i['members']))


def create_warnings():
  """Creates warnings s.t. warnings[p][s] is as specified in above docs

  Returns 2D warnings array where warnings[p][s] is # of warnings
  in project name p of severity level s
  """

  warnings = {p: {s: 0 for s in Severity.range} for p in project_names}
  for i in warn_patterns:
    s = i['severity']
    for p in i['projects']:
      warnings[p][s] += i['projects'][p]
  return warnings


def get_total_by_project(warnings):
  """Returns dict, project as key and # warnings for that project as value"""

  return {p: sum(warnings[p][s] for s in Severity.range) for p in project_names}


def get_total_by_severity(warnings):
  """Returns dict, severity as key and # warnings of that severity as value"""

  return {s: sum(warnings[p][s] for p in project_names) for s in Severity.range}


def emit_table_header(total_by_severity):
  """Returns list of HTML-formatted content for severity stats"""

  stats_header = ['Project']
  for s in Severity.range:
    if total_by_severity[s]:
      stats_header.append("<span style='background-color:{}'>{}</span>".format(
          Severity.colors[s], Severity.column_headers[s]))
  stats_header.append('TOTAL')
  return stats_header


def emit_row_counts_per_project(warnings, total_by_project, total_by_severity):
  """Returns total project warnings and row of stats for each project

  Returns total_all_projects, the total number of warnings over all projects
  and stats_rows, a 2d list where each row is [Project Name,
  <severity counts>, total # warnings for this project]
  """

  total_all_projects = 0
  stats_rows = []
  for p in project_names:
    if total_by_project[p]:
      one_row = [p]
      for s in Severity.range:
        if total_by_severity[s]:
          one_row.append(warnings[p][s])
      one_row.append(total_by_project[p])
      stats_rows.append(one_row)
      total_all_projects += total_by_project[p]
  return total_all_projects, stats_rows


def emit_row_counts_per_severity(total_by_severity, stats_header, stats_rows,
                                 total_all_projects):
  """Emits stats_header and stats_rows as specified above

  Specifications found in docstrings for emit_table_header and
  emit_row_counts_per_project above
  """

  total_all_severities = 0
  one_row = ['<b>TOTAL</b>']
  for s in Severity.range:
    if total_by_severity[s]:
      one_row.append(total_by_severity[s])
      total_all_severities += total_by_severity[s]
  one_row.append(total_all_projects)
  stats_rows.append(one_row)
  print('<script>')
  emit_const_string_array('StatsHeader', stats_header)
  emit_const_object_array('StatsRows', stats_rows)
  print(draw_table_javascript)
  print('</script>')


def emit_stats_by_project():
  """Dump a google chart table of warnings per project and severity."""

  warnings = create_warnings()
  total_by_project = get_total_by_project(warnings)
  total_by_severity = get_total_by_severity(warnings)
  stats_header = emit_table_header(total_by_severity)
  total_all_projects, stats_rows = \
    emit_row_counts_per_project(warnings, total_by_project, total_by_severity)
  emit_row_counts_per_severity(total_by_severity, stats_header, stats_rows,
                               total_all_projects)


def dump_stats():
  """Dump some stats about total number of warnings and such."""

  known = 0
  skipped = 0
  unknown = 0
  sort_warnings()
  for i in warn_patterns:
    if i['severity'] == Severity.UNKNOWN:
      unknown += len(i['members'])
    elif i['severity'] == Severity.SKIP:
      skipped += len(i['members'])
    else:
      known += len(i['members'])
  print('Number of classified warnings: <b>' + str(known) + '</b><br>')
  print('Number of skipped warnings: <b>' + str(skipped) + '</b><br>')
  print('Number of unclassified warnings: <b>' + str(unknown) + '</b><br>')
  total = unknown + known + skipped
  extra_msg = ''
  if total < 1000:
    extra_msg = ' (low count may indicate incremental build)'
  print('Total number of warnings: <b>' + str(total) + '</b>' + extra_msg)


# New base table of warnings, [severity, warn_id, project, warning_message]
# Need buttons to show warnings in different grouping options.
# (1) Current, group by severity, id for each warning pattern
#     sort by severity, warn_id, warning_message
# (2) Current --byproject, group by severity,
#     id for each warning pattern + project name
#     sort by severity, warn_id, project, warning_message
# (3) New, group by project + severity,
#     id for each warning pattern
#     sort by project, severity, warn_id, warning_message
def emit_buttons():
  print('<button class="button" onclick="expandCollapse(1);">'
        'Expand all warnings</button>\n'
        '<button class="button" onclick="expandCollapse(0);">'
        'Collapse all warnings</button>\n'
        '<button class="button" onclick="groupBySeverity();">'
        'Group warnings by severity</button>\n'
        '<button class="button" onclick="groupByProject();">'
        'Group warnings by project</button><br>')


def all_patterns(category):
  patterns = ''
  for i in category['patterns']:
    patterns += i
    patterns += ' / '
  return patterns


def dump_fixed():
  """Show which warnings no longer occur."""
  anchor = 'fixed_warnings'
  mark = anchor + '_mark'
  print('\n<br><p style="background-color:lightblue"><b>'
        '<button id="' + mark + '" '
        'class="bt" onclick="expand(\'' + anchor + '\');">'
        '&#x2295</button> Fixed warnings. '
        'No more occurrences. Please consider turning these into '
        'errors if possible, before they are reintroduced in to the build'
        ':</b></p>')
  print('<blockquote>')
  fixed_patterns = []
  for i in warn_patterns:
    if not i['members']:
      fixed_patterns.append(i['description'] + ' (' + all_patterns(i) + ')')
    if i['option']:
      fixed_patterns.append(' ' + i['option'])
  fixed_patterns.sort()
  print('<div id="' + anchor + '" style="display:none;"><table>')
  cur_row_class = 0
  for text in fixed_patterns:
    cur_row_class = 1 - cur_row_class
    # remove last '\n'
    t = text[:-1] if text[-1] == '\n' else text
    print('<tr><td class="c' + str(cur_row_class) + '">' + t + '</td></tr>')
  print('</table></div>')
  print('</blockquote>')


def find_project_index(line):
  for i, p in enumerate(project_patterns):
    if p.match(line):
      return i
  return -1


def classify_one_warning(line, results):
  """Classify one warning line."""
  for i, w in enumerate(warn_patterns):
    for cpat in w['compiled_patterns']:
      if cpat.match(line):
        p = find_project_index(line)
        results.append([line, i, p])
        return
      else:
        # If we end up here, there was a problem parsing the log
        # probably caused by 'make -j' mixing the output from
        # 2 or more concurrent compiles
        pass


def classify_warnings(lines):
  results = []
  for line in lines:
    classify_one_warning(line, results)
  # After the main work, ignore all other signals to a child process,
  # to avoid bad warning/error messages from the exit clean-up process.
  if args.processes > 1:
    signal.signal(signal.SIGTERM, lambda *args: sys.exit(-signal.SIGTERM))
  return results


def parallel_classify_warnings(warning_lines):
  """Classify all warning lines with num_cpu parallel processes."""
  compile_patterns()
  num_cpu = args.processes
  if num_cpu > 1:
    groups = [[] for x in range(num_cpu)]
    i = 0
    for x in warning_lines:
      groups[i].append(x)
      i = (i + 1) % num_cpu
    pool = multiprocessing.Pool(num_cpu)
    group_results = pool.map(classify_warnings, groups)
  else:
    group_results = [classify_warnings(warning_lines)]

  for result in group_results:
    for line, pattern_idx, project_idx in result:
      pattern = warn_patterns[pattern_idx]
      pattern['members'].append(line)
      message_idx = len(warning_messages)
      warning_messages.append(line)
      warning_records.append([pattern_idx, project_idx, message_idx])
      pname = '???' if project_idx < 0 else project_names[project_idx]
      # Count warnings by project.
      if pname in pattern['projects']:
        pattern['projects'][pname] += 1
      else:
        pattern['projects'][pname] = 1


def compile_patterns():
  """Precompiling every pattern speeds up parsing by about 30x."""
  for i in warn_patterns:
    i['compiled_patterns'] = []
    for pat in i['patterns']:
      i['compiled_patterns'].append(re.compile(pat))


def find_android_root(path):
  """Set and return android_root path if it is found."""
  global android_root  # pylint:disable=global-statement
  parts = path.split('/')
  for idx in reversed(range(2, len(parts))):
    root_path = '/'.join(parts[:idx])
    # Android root directory should contain this script.
    if os.path.exists(root_path + '/build/make/tools/warn.py'):
      android_root = root_path
      return root_path
  return ''


def remove_android_root_prefix(path):
  """Remove android_root prefix from path if it is found."""
  if path.startswith(android_root):
    return path[1 + len(android_root):]
  else:
    return path


def normalize_path(path):
  """Normalize file path relative to android_root."""
  # If path is not an absolute path, just normalize it.
  path = os.path.normpath(path)
  if path[0] != '/':
    return path
  # Remove known prefix of root path and normalize the suffix.
  if android_root or find_android_root(path):
    return remove_android_root_prefix(path)
  else:
    return path


def normalize_warning_line(line):
  """Normalize file path relative to android_root in a warning line."""
  # replace fancy quotes with plain ol' quotes
  line = line.replace('‘', "'")
  line = line.replace('’', "'")
  line = line.strip()
  first_column = line.find(':')
  if first_column > 0:
    return normalize_path(line[:first_column]) + line[first_column:]
  else:
    return line


def parse_input_file(infile):
  """Parse input file, collect parameters and warning lines."""
  # pylint:disable=global-statement
  global android_root
  global platform_version
  global target_product
  global target_variant
  line_counter = 0

  # handle only warning messages with a file path
  warning_pattern = re.compile('^[^ ]*/[^ ]*: warning: .*')

  # Collect all warnings into the warning_lines set.
  warning_lines = set()
  for line in infile:
    if warning_pattern.match(line):
      line = normalize_warning_line(line)
      warning_lines.add(line)
    elif line_counter < 100:
      # save a little bit of time by only doing this for the first few lines
      line_counter += 1
      m = re.search('(?<=^PLATFORM_VERSION=).*', line)
      if m is not None:
        platform_version = m.group(0)
      m = re.search('(?<=^TARGET_PRODUCT=).*', line)
      if m is not None:
        target_product = m.group(0)
      m = re.search('(?<=^TARGET_BUILD_VARIANT=).*', line)
      if m is not None:
        target_variant = m.group(0)
      m = re.search('.* TOP=([^ ]*) .*', line)
      if m is not None:
        android_root = m.group(1)
  return warning_lines


# Return s with escaped backslash and quotation characters.
def escape_string(s):
  return s.replace('\\', '\\\\').replace('"', '\\"')


# Return s without trailing '\n' and escape the quotation characters.
def strip_escape_string(s):
  if not s:
    return s
  s = s[:-1] if s[-1] == '\n' else s
  return escape_string(s)


def emit_warning_array(name):
  print('var warning_{} = ['.format(name))
  for w in warn_patterns:
    print('{},'.format(w[name]))
  print('];')


def emit_warning_arrays():
  emit_warning_array('severity')
  print('var warning_description = [')
  for w in warn_patterns:
    if w['members']:
      print('"{}",'.format(escape_string(w['description'])))
    else:
      print('"",')  # no such warning
  print('];')


scripts_for_warning_groups = """
  function compareMessages(x1, x2) { // of the same warning type
    return (WarningMessages[x1[2]] <= WarningMessages[x2[2]]) ? -1 : 1;
  }
  function byMessageCount(x1, x2) {
    return x2[2] - x1[2];  // reversed order
  }
  function bySeverityMessageCount(x1, x2) {
    // orer by severity first
    if (x1[1] != x2[1])
      return  x1[1] - x2[1];
    return byMessageCount(x1, x2);
  }
  const ParseLinePattern = /^([^ :]+):(\\d+):(.+)/;
  function addURL(line) {
    if (FlagURL == "") return line;
    if (FlagSeparator == "") {
      return line.replace(ParseLinePattern,
        "<a target='_blank' href='" + FlagURL + "/$1'>$1</a>:$2:$3");
    }
    return line.replace(ParseLinePattern,
      "<a target='_blank' href='" + FlagURL + "/$1" + FlagSeparator +
        "$2'>$1:$2</a>:$3");
  }
  function createArrayOfDictionaries(n) {
    var result = [];
    for (var i=0; i<n; i++) result.push({});
    return result;
  }
  function groupWarningsBySeverity() {
    // groups is an array of dictionaries,
    // each dictionary maps from warning type to array of warning messages.
    var groups = createArrayOfDictionaries(SeverityColors.length);
    for (var i=0; i<Warnings.length; i++) {
      var w = Warnings[i][0];
      var s = WarnPatternsSeverity[w];
      var k = w.toString();
      if (!(k in groups[s]))
        groups[s][k] = [];
      groups[s][k].push(Warnings[i]);
    }
    return groups;
  }
  function groupWarningsByProject() {
    var groups = createArrayOfDictionaries(ProjectNames.length);
    for (var i=0; i<Warnings.length; i++) {
      var w = Warnings[i][0];
      var p = Warnings[i][1];
      var k = w.toString();
      if (!(k in groups[p]))
        groups[p][k] = [];
      groups[p][k].push(Warnings[i]);
    }
    return groups;
  }
  var GlobalAnchor = 0;
  function createWarningSection(header, color, group) {
    var result = "";
    var groupKeys = [];
    var totalMessages = 0;
    for (var k in group) {
       totalMessages += group[k].length;
       groupKeys.push([k, WarnPatternsSeverity[parseInt(k)], group[k].length]);
    }
    groupKeys.sort(bySeverityMessageCount);
    for (var idx=0; idx<groupKeys.length; idx++) {
      var k = groupKeys[idx][0];
      var messages = group[k];
      var w = parseInt(k);
      var wcolor = SeverityColors[WarnPatternsSeverity[w]];
      var description = WarnPatternsDescription[w];
      if (description.length == 0)
          description = "???";
      GlobalAnchor += 1;
      result += "<table class='t1'><tr bgcolor='" + wcolor + "'><td>" +
                "<button class='bt' id='" + GlobalAnchor + "_mark" +
                "' onclick='expand(\\"" + GlobalAnchor + "\\");'>" +
                "&#x2295</button> " +
                description + " (" + messages.length + ")</td></tr></table>";
      result += "<div id='" + GlobalAnchor +
                "' style='display:none;'><table class='t1'>";
      var c = 0;
      messages.sort(compareMessages);
      for (var i=0; i<messages.length; i++) {
        result += "<tr><td class='c" + c + "'>" +
                  addURL(WarningMessages[messages[i][2]]) + "</td></tr>";
        c = 1 - c;
      }
      result += "</table></div>";
    }
    if (result.length > 0) {
      return "<br><span style='background-color:" + color + "'><b>" +
             header + ": " + totalMessages +
             "</b></span><blockquote><table class='t1'>" +
             result + "</table></blockquote>";

    }
    return "";  // empty section
  }
  function generateSectionsBySeverity() {
    var result = "";
    var groups = groupWarningsBySeverity();
    for (s=0; s<SeverityColors.length; s++) {
      result += createWarningSection(SeverityHeaders[s], SeverityColors[s],
                                     groups[s]);
    }
    return result;
  }
  function generateSectionsByProject() {
    var result = "";
    var groups = groupWarningsByProject();
    for (i=0; i<groups.length; i++) {
      result += createWarningSection(ProjectNames[i], 'lightgrey', groups[i]);
    }
    return result;
  }
  function groupWarnings(generator) {
    GlobalAnchor = 0;
    var e = document.getElementById("warning_groups");
    e.innerHTML = generator();
  }
  function groupBySeverity() {
    groupWarnings(generateSectionsBySeverity);
  }
  function groupByProject() {
    groupWarnings(generateSectionsByProject);
  }
"""


# Emit a JavaScript const string
def emit_const_string(name, value):
  print('const ' + name + ' = "' + escape_string(value) + '";')


# Emit a JavaScript const integer array.
def emit_const_int_array(name, array):
  print('const ' + name + ' = [')
  for n in array:
    print(str(n) + ',')
  print('];')


# Emit a JavaScript const string array.
def emit_const_string_array(name, array):
  print('const ' + name + ' = [')
  for s in array:
    print('"' + strip_escape_string(s) + '",')
  print('];')


# Emit a JavaScript const string array for HTML.
def emit_const_html_string_array(name, array):
  print('const ' + name + ' = [')
  for s in array:
    print('"' + cgi.escape(strip_escape_string(s)) + '",')
  print('];')


# Emit a JavaScript const object array.
def emit_const_object_array(name, array):
  print('const ' + name + ' = [')
  for x in array:
    print(str(x) + ',')
  print('];')


def emit_js_data():
  """Dump dynamic HTML page's static JavaScript data."""
  emit_const_string('FlagURL', args.url if args.url else '')
  emit_const_string('FlagSeparator', args.separator if args.separator else '')
  emit_const_string_array('SeverityColors', Severity.colors)
  emit_const_string_array('SeverityHeaders', Severity.headers)
  emit_const_string_array('SeverityColumnHeaders', Severity.column_headers)
  emit_const_string_array('ProjectNames', project_names)
  emit_const_int_array('WarnPatternsSeverity',
                       [w['severity'] for w in warn_patterns])
  emit_const_html_string_array('WarnPatternsDescription',
                               [w['description'] for w in warn_patterns])
  emit_const_html_string_array('WarnPatternsOption',
                               [w['option'] for w in warn_patterns])
  emit_const_html_string_array('WarningMessages', warning_messages)
  emit_const_object_array('Warnings', warning_records)


draw_table_javascript = """
google.charts.load('current', {'packages':['table']});
google.charts.setOnLoadCallback(drawTable);
function drawTable() {
  var data = new google.visualization.DataTable();
  data.addColumn('string', StatsHeader[0]);
  for (var i=1; i<StatsHeader.length; i++) {
    data.addColumn('number', StatsHeader[i]);
  }
  data.addRows(StatsRows);
  for (var i=0; i<StatsRows.length; i++) {
    for (var j=0; j<StatsHeader.length; j++) {
      data.setProperty(i, j, 'style', 'border:1px solid black;');
    }
  }
  var table = new google.visualization.Table(
      document.getElementById('stats_table'));
  table.draw(data, {allowHtml: true, alternatingRowStyle: true});
}
"""


def dump_html():
  """Dump the html output to stdout."""
  dump_html_prologue('Warnings for ' + platform_version + ' - ' +
                     target_product + ' - ' + target_variant)
  dump_stats()
  print('<br><div id="stats_table"></div><br>')
  print('\n<script>')
  emit_js_data()
  print(scripts_for_warning_groups)
  print('</script>')
  emit_buttons()
  # Warning messages are grouped by severities or project names.
  print('<br><div id="warning_groups"></div>')
  if args.byproject:
    print('<script>groupByProject();</script>')
  else:
    print('<script>groupBySeverity();</script>')
  dump_fixed()
  dump_html_epilogue()


##### Functions to count warnings and dump csv file. #########################


def description_for_csv(category):
  if not category['description']:
    return '?'
  return category['description']


def count_severity(writer, sev, kind):
  """Count warnings of given severity."""
  total = 0
  for i in warn_patterns:
    if i['severity'] == sev and i['members']:
      n = len(i['members'])
      total += n
      warning = kind + ': ' + description_for_csv(i)
      writer.writerow([n, '', warning])
      # print number of warnings for each project, ordered by project name.
      projects = i['projects'].keys()
      projects.sort()
      for p in projects:
        writer.writerow([i['projects'][p], p, warning])
  writer.writerow([total, '', kind + ' warnings'])

  return total


# dump number of warnings in csv format to stdout
def dump_csv(writer):
  """Dump number of warnings in csv format to stdout."""
  sort_warnings()
  total = 0
  for s in Severity.range:
    total += count_severity(writer, s, Severity.column_headers[s])
  writer.writerow([total, '', 'All warnings'])


def main():
  warning_lines = parse_input_file(open(args.buildlog, 'r'))
  parallel_classify_warnings(warning_lines)
  # If a user pases a csv path, save the fileoutput to the path
  # If the user also passed gencsv write the output to stdout
  # If the user did not pass gencsv flag dump the html report to stdout.
  if args.csvpath:
    with open(args.csvpath, 'w') as f:
      dump_csv(csv.writer(f, lineterminator='\n'))
  if args.gencsv:
    dump_csv(csv.writer(sys.stdout, lineterminator='\n'))
  else:
    dump_html()


# Run main function if warn.py is the main program.
if __name__ == '__main__':
  main()
