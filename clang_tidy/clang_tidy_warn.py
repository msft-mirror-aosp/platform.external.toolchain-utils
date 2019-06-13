#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Grep warnings messages and output HTML tables or warning data in protobuf.

Default is to output warnings in HTML tables grouped by warning severity.
Use option --byproject to output tables grouped by source file projects.
Use option --genproto to output warning data in protobuf format.
"""

# List of important data structures and functions in this script.
#
# To parse and keep warning message in the input file:
#   severity:                classification of message severity
#   warn_patterns:
#   warn_patterns[w]['category']     tool that issued the warning, not used now
#   warn_patterns[w]['description']  table heading
#   warn_patterns[w]['members']      matched warnings from input
#   warn_patterns[w]['option']       compiler flag to control the warning
#   warn_patterns[w]['patterns']     regular expressions to match warnings
#   warn_patterns[w]['projects'][p]  number of warnings of pattern w in p
#   warn_patterns[w]['severity']     severity tuple
#   project_list[p][0]               project name
#   project_list[p][1]               regular expression to match a project path
#   project_patterns[p]              re.compile(project_list[p][1])
#   project_names[p]                 project_list[p][0]
#   warning_messages     array of each warning message, without source url
#   warning_links        array of each warning code search link
#   warning_records      array of [idx to warn_patterns,
#                                  idx to project_names,
#                                  idx to warning_messages,
#                                  idx to warning_links]
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
#   SeverityColors:        list of colors for all severity levels
#   SeverityHeaders:       list of headers for all severity levels
#   SeverityColumnHeaders: list of column_headers for all severity levels
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
import multiprocessing
import os
import re
import signal
import struct
import sys

from clang_tidy_warn_patterns import warn_patterns, Severity
import warnings_pb2  # if missing, run compile_proto.sh to generate it


def project_name_and_pattern(name, pattern):
  return [name, '(^|.*/)' + pattern + '/.*: warning:']


def simple_project_pattern(pattern):
  return project_name_and_pattern(pattern, pattern)


# A list of [project_name, file_path_pattern].
project_list = [
    simple_project_pattern("android_webview"),
    simple_project_pattern("apps"),
    simple_project_pattern("ash/app_list"),
    simple_project_pattern("ash/public"),
    simple_project_pattern("ash/assistant"),
    simple_project_pattern("ash/display"),
    simple_project_pattern("ash/resources"),
    simple_project_pattern("ash/login"),
    simple_project_pattern("ash/system"),
    simple_project_pattern("ash/wm"),
    simple_project_pattern("ash/shelf"),
    simple_project_pattern("ash"),
    simple_project_pattern("base/trace_event"),
    simple_project_pattern("base/debug"),
    simple_project_pattern("base/third_party"),
    simple_project_pattern("base/files"),
    simple_project_pattern("base/test"),
    simple_project_pattern("base/util"),
    simple_project_pattern("base/task"),
    simple_project_pattern("base/metrics"),
    simple_project_pattern("base/strings"),
    simple_project_pattern("base/memory"),
    simple_project_pattern("base"),
    simple_project_pattern("build"),
    simple_project_pattern("build_overrides"),
    simple_project_pattern("buildtools"),
    simple_project_pattern("cc"),
    simple_project_pattern("chrome/services"),
    simple_project_pattern("chrome/app"),
    simple_project_pattern("chrome/renderer"),
    simple_project_pattern("chrome/test"),
    simple_project_pattern("chrome/common/safe_browsing"),
    simple_project_pattern("chrome/common/importer"),
    simple_project_pattern("chrome/common/media_router"),
    simple_project_pattern("chrome/common/extensions"),
    simple_project_pattern("chrome/common"),
    simple_project_pattern("chrome/browser/sync_file_system"),
    simple_project_pattern("chrome/browser/safe_browsing"),
    simple_project_pattern("chrome/browser/download"),
    simple_project_pattern("chrome/browser/ui"),
    simple_project_pattern("chrome/browser/supervised_user"),
    simple_project_pattern("chrome/browser/search"),
    simple_project_pattern("chrome/browser/browsing_data"),
    simple_project_pattern("chrome/browser/predictors"),
    simple_project_pattern("chrome/browser/net"),
    simple_project_pattern("chrome/browser/devtools"),
    simple_project_pattern("chrome/browser/resource_coordinator"),
    simple_project_pattern("chrome/browser/page_load_metrics"),
    simple_project_pattern("chrome/browser/extensions"),
    simple_project_pattern("chrome/browser/ssl"),
    simple_project_pattern("chrome/browser/printing"),
    simple_project_pattern("chrome/browser/profiles"),
    simple_project_pattern("chrome/browser/chromeos"),
    simple_project_pattern("chrome/browser/performance_manager"),
    simple_project_pattern("chrome/browser/metrics"),
    simple_project_pattern("chrome/browser/component_updater"),
    simple_project_pattern("chrome/browser/media"),
    simple_project_pattern("chrome/browser/notifications"),
    simple_project_pattern("chrome/browser/web_applications"),
    simple_project_pattern("chrome/browser/media_galleries"),
    simple_project_pattern("chrome/browser"),
    simple_project_pattern("chrome"),
    simple_project_pattern("chromecast"),
    simple_project_pattern("chromeos/services"),
    simple_project_pattern("chromeos/dbus"),
    simple_project_pattern("chromeos/assistant"),
    simple_project_pattern("chromeos/components"),
    simple_project_pattern("chromeos/settings"),
    simple_project_pattern("chromeos/constants"),
    simple_project_pattern("chromeos/network"),
    simple_project_pattern("chromeos"),
    simple_project_pattern("cloud_print"),
    simple_project_pattern("components/crash"),
    simple_project_pattern("components/subresource_filter"),
    simple_project_pattern("components/invalidation"),
    simple_project_pattern("components/autofill"),
    simple_project_pattern("components/onc"),
    simple_project_pattern("components/arc"),
    simple_project_pattern("components/safe_browsing"),
    simple_project_pattern("components/services"),
    simple_project_pattern("components/cast_channel"),
    simple_project_pattern("components/download"),
    simple_project_pattern("components/feed"),
    simple_project_pattern("components/offline_pages"),
    simple_project_pattern("components/bookmarks"),
    simple_project_pattern("components/cloud_devices"),
    simple_project_pattern("components/mirroring"),
    simple_project_pattern("components/spellcheck"),
    simple_project_pattern("components/viz"),
    simple_project_pattern("components/gcm_driver"),
    simple_project_pattern("components/ntp_snippets"),
    simple_project_pattern("components/translate"),
    simple_project_pattern("components/search_engines"),
    simple_project_pattern("components/background_task_scheduler"),
    simple_project_pattern("components/signin"),
    simple_project_pattern("components/chromeos_camera"),
    simple_project_pattern("components/reading_list"),
    simple_project_pattern("components/assist_ranker"),
    simple_project_pattern("components/payments"),
    simple_project_pattern("components/feedback"),
    simple_project_pattern("components/ui_devtools"),
    simple_project_pattern("components/password_manager"),
    simple_project_pattern("components/omnibox"),
    simple_project_pattern("components/content_settings"),
    simple_project_pattern("components/dom_distiller"),
    simple_project_pattern("components/nacl"),
    simple_project_pattern("components/metrics"),
    simple_project_pattern("components/policy"),
    simple_project_pattern("components/optimization_guide"),
    simple_project_pattern("components/exo"),
    simple_project_pattern("components/update_client"),
    simple_project_pattern("components/data_reduction_proxy"),
    simple_project_pattern("components/sync"),
    simple_project_pattern("components/drive"),
    simple_project_pattern("components/variations"),
    simple_project_pattern("components/history"),
    simple_project_pattern("components/webcrypto"),
    simple_project_pattern("components"),
    simple_project_pattern("content/public"),
    simple_project_pattern("content/renderer"),
    simple_project_pattern("content/test"),
    simple_project_pattern("content/common"),
    simple_project_pattern("content/browser"),
    simple_project_pattern("content/zygote"),
    simple_project_pattern("content"),
    simple_project_pattern("courgette"),
    simple_project_pattern("crypto"),
    simple_project_pattern("dbus"),
    simple_project_pattern("device/base"),
    simple_project_pattern("device/vr"),
    simple_project_pattern("device/gamepad"),
    simple_project_pattern("device/test"),
    simple_project_pattern("device/fido"),
    simple_project_pattern("device/bluetooth"),
    simple_project_pattern("device"),
    simple_project_pattern("docs"),
    simple_project_pattern("extensions/docs"),
    simple_project_pattern("extensions/components"),
    simple_project_pattern("extensions/buildflags"),
    simple_project_pattern("extensions/renderer"),
    simple_project_pattern("extensions/test"),
    simple_project_pattern("extensions/common"),
    simple_project_pattern("extensions/shell"),
    simple_project_pattern("extensions/browser"),
    simple_project_pattern("extensions/strings"),
    simple_project_pattern("extensions"),
    simple_project_pattern("fuchsia"),
    simple_project_pattern("gin"),
    simple_project_pattern("google_apis"),
    simple_project_pattern("google_update"),
    simple_project_pattern("gpu/perftests"),
    simple_project_pattern("gpu/GLES2"),
    simple_project_pattern("gpu/command_buffer"),
    simple_project_pattern("gpu/tools"),
    simple_project_pattern("gpu/gles2_conform_support"),
    simple_project_pattern("gpu/ipc"),
    simple_project_pattern("gpu/khronos_glcts_support"),
    simple_project_pattern("gpu"),
    simple_project_pattern("headless"),
    simple_project_pattern("infra"),
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
    simple_project_pattern("services/audio"),
    simple_project_pattern("services/content"),
    simple_project_pattern("services/data_decoder"),
    simple_project_pattern("services/device"),
    simple_project_pattern("services/file"),
    simple_project_pattern("services/identity"),
    simple_project_pattern("services/image_annotation"),
    simple_project_pattern("services/media_session"),
    simple_project_pattern("services/metrics"),
    simple_project_pattern("services/network"),
    simple_project_pattern("services/preferences"),
    simple_project_pattern("services/proxy_resolver"),
    simple_project_pattern("services/resource_coordinator"),
    simple_project_pattern("services/service_manager"),
    simple_project_pattern("services/shape_detection"),
    simple_project_pattern("services/strings"),
    simple_project_pattern("services/test"),
    simple_project_pattern("services/tracing"),
    simple_project_pattern("services/video_capture"),
    simple_project_pattern("services/viz"),
    simple_project_pattern("services/ws"),
    simple_project_pattern("services"),
    simple_project_pattern("skia/config"),
    simple_project_pattern("skia/ext"),
    simple_project_pattern("skia/public"),
    simple_project_pattern("skia/tools"),
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
    simple_project_pattern("third_party/blink/public/common"),
    simple_project_pattern("third_party/blink/public/default_100_percent"),
    simple_project_pattern("third_party/blink/public/default_200_percent"),
    simple_project_pattern("third_party/blink/public/platform"),
    simple_project_pattern("third_party/blink/public/mojom/ad_tagging"),
    simple_project_pattern("third_party/blink/public/mojom/app_banner"),
    simple_project_pattern("third_party/blink/public/mojom/appcache"),
    simple_project_pattern("third_party/blink/public/mojom/array_buffer"),
    simple_project_pattern(
        "third_party/blink/public/mojom/associated_interfaces"),
    simple_project_pattern("third_party/blink/public/mojom/autoplay"),
    simple_project_pattern("third_party/blink/public/mojom/background_fetch"),
    simple_project_pattern("third_party/blink/public/mojom/background_sync"),
    simple_project_pattern("third_party/blink/public/mojom/badging"),
    simple_project_pattern("third_party/blink/public/mojom/blob"),
    simple_project_pattern("third_party/blink/public/mojom/bluetooth"),
    simple_project_pattern("third_party/blink/public/mojom/broadcastchannel"),
    simple_project_pattern("third_party/blink/public/mojom/cache_storage"),
    simple_project_pattern("third_party/blink/public/mojom/choosers"),
    simple_project_pattern("third_party/blink/public/mojom/clipboard"),
    simple_project_pattern("third_party/blink/public/mojom/commit_result"),
    simple_project_pattern("third_party/blink/public/mojom/contacts"),
    simple_project_pattern("third_party/blink/public/mojom/cookie_store"),
    simple_project_pattern("third_party/blink/public/mojom/crash"),
    simple_project_pattern("third_party/blink/public/mojom/credentialmanager"),
    simple_project_pattern("third_party/blink/public/mojom/csp"),
    simple_project_pattern("third_party/blink/public/mojom/devtools"),
    simple_project_pattern("third_party/blink/public/mojom/document_metadata"),
    simple_project_pattern("third_party/blink/public/mojom/dom_storage"),
    simple_project_pattern("third_party/blink/public/mojom/dwrite_font_proxy"),
    simple_project_pattern("third_party/blink/public/mojom/feature_policy"),
    simple_project_pattern("third_party/blink/public/mojom/fetch"),
    simple_project_pattern("third_party/blink/public/mojom/file"),
    simple_project_pattern("third_party/blink/public/mojom/filesystem"),
    simple_project_pattern(
        "third_party/blink/public/mojom/font_unique_name_lookup"),
    simple_project_pattern("third_party/blink/public/mojom/frame"),
    simple_project_pattern("third_party/blink/public/mojom/frame_sinks"),
    simple_project_pattern("third_party/blink/public/mojom/geolocation"),
    simple_project_pattern("third_party/blink/public/mojom/hyphenation"),
    simple_project_pattern("third_party/blink/public/mojom/idle"),
    simple_project_pattern("third_party/blink/public/mojom/indexeddb"),
    simple_project_pattern("third_party/blink/public/mojom/input"),
    simple_project_pattern("third_party/blink/public/mojom/insecure_input"),
    simple_project_pattern("third_party/blink/public/mojom/installation"),
    simple_project_pattern("third_party/blink/public/mojom/installedapp"),
    simple_project_pattern("third_party/blink/public/mojom/keyboard_lock"),
    simple_project_pattern("third_party/blink/public/mojom/leak_detector"),
    simple_project_pattern("third_party/blink/public/mojom/loader"),
    simple_project_pattern("third_party/blink/public/mojom/locks"),
    simple_project_pattern("third_party/blink/public/mojom/manifest"),
    simple_project_pattern("third_party/blink/public/mojom/media_controls"),
    simple_project_pattern("third_party/blink/public/mojom/mediasession"),
    simple_project_pattern("third_party/blink/public/mojom/mediastream"),
    simple_project_pattern("third_party/blink/public/mojom/messaging"),
    simple_project_pattern("third_party/blink/public/mojom/mime"),
    simple_project_pattern("third_party/blink/public/mojom/native_file_system"),
    simple_project_pattern("third_party/blink/public/mojom/net"),
    simple_project_pattern("third_party/blink/public/mojom/notifications"),
    simple_project_pattern("third_party/blink/public/mojom/oom_intervention"),
    simple_project_pattern("third_party/blink/public/mojom/page"),
    simple_project_pattern("third_party/blink/public/mojom/payments"),
    simple_project_pattern("third_party/blink/public/mojom/permissions"),
    simple_project_pattern("third_party/blink/public/mojom/picture_in_picture"),
    simple_project_pattern("third_party/blink/public/mojom/plugins"),
    simple_project_pattern("third_party/blink/public/mojom/portal"),
    simple_project_pattern("third_party/blink/public/mojom/presentation"),
    simple_project_pattern("third_party/blink/public/mojom/push_messaging"),
    simple_project_pattern("third_party/blink/public/mojom/quota"),
    simple_project_pattern("third_party/blink/public/mojom/remote_objects"),
    simple_project_pattern("third_party/blink/public/mojom/reporting"),
    simple_project_pattern("third_party/blink/public/mojom/script"),
    simple_project_pattern("third_party/blink/public/mojom/selection_menu"),
    simple_project_pattern("third_party/blink/public/mojom/serial"),
    simple_project_pattern("third_party/blink/public/mojom/service_worker"),
    simple_project_pattern("third_party/blink/public/mojom/site_engagement"),
    simple_project_pattern("third_party/blink/public/mojom/sms"),
    simple_project_pattern("third_party/blink/public/mojom/speech"),
    simple_project_pattern("third_party/blink/public/mojom/ukm"),
    simple_project_pattern(
        "third_party/blink/public/mojom/unhandled_tap_notifier"),
    simple_project_pattern("third_party/blink/public/mojom/usb"),
    simple_project_pattern("third_party/blink/public/mojom/use_counter"),
    simple_project_pattern("third_party/blink/public/mojom/user_agent"),
    simple_project_pattern("third_party/blink/public/mojom/wake_lock"),
    simple_project_pattern("third_party/blink/public/mojom/web_client_hints"),
    simple_project_pattern("third_party/blink/public/mojom/web_feature"),
    simple_project_pattern("third_party/blink/public/mojom/webaudio"),
    simple_project_pattern("third_party/blink/public/mojom/webauthn"),
    simple_project_pattern("third_party/blink/public/mojom/webdatabase"),
    simple_project_pattern("third_party/blink/public/mojom/webshare"),
    simple_project_pattern("third_party/blink/public/mojom/window_features"),
    simple_project_pattern("third_party/blink/public/mojom/worker"),
    simple_project_pattern("third_party/blink/public/web"),
    simple_project_pattern("third_party/blink/renderer/bindings"),
    simple_project_pattern("third_party/blink/renderer/build"),
    simple_project_pattern("third_party/blink/renderer/controller"),
    simple_project_pattern("third_party/blink/renderer/core/accessibility"),
    simple_project_pattern("third_party/blink/renderer/core/animation"),
    simple_project_pattern("third_party/blink/renderer/core/aom"),
    simple_project_pattern("third_party/blink/renderer/core/clipboard"),
    simple_project_pattern("third_party/blink/renderer/core/content_capture"),
    simple_project_pattern("third_party/blink/renderer/core/context_features"),
    simple_project_pattern("third_party/blink/renderer/core/css"),
    simple_project_pattern("third_party/blink/renderer/core/display_lock"),
    simple_project_pattern("third_party/blink/renderer/core/dom"),
    simple_project_pattern("third_party/blink/renderer/core/editing"),
    simple_project_pattern("third_party/blink/renderer/core/events"),
    simple_project_pattern("third_party/blink/renderer/core/execution_context"),
    simple_project_pattern("third_party/blink/renderer/core/exported"),
    simple_project_pattern("third_party/blink/renderer/core/feature_policy"),
    simple_project_pattern("third_party/blink/renderer/core/fetch"),
    simple_project_pattern("third_party/blink/renderer/core/fileapi"),
    simple_project_pattern("third_party/blink/renderer/core/frame"),
    simple_project_pattern("third_party/blink/renderer/core/fullscreen"),
    simple_project_pattern("third_party/blink/renderer/core/geometry"),
    simple_project_pattern("third_party/blink/renderer/core/html"),
    simple_project_pattern("third_party/blink/renderer/core/imagebitmap"),
    simple_project_pattern("third_party/blink/renderer/core/input"),
    simple_project_pattern("third_party/blink/renderer/core/inspector"),
    simple_project_pattern(
        "third_party/blink/renderer/core/intersection_observer"),
    simple_project_pattern("third_party/blink/renderer/core/invisible_dom"),
    simple_project_pattern("third_party/blink/renderer/core/layout"),
    simple_project_pattern("third_party/blink/renderer/core/loader"),
    simple_project_pattern("third_party/blink/renderer/core/messaging"),
    simple_project_pattern("third_party/blink/renderer/core/mojo"),
    simple_project_pattern("third_party/blink/renderer/core/offscreencanvas"),
    simple_project_pattern("third_party/blink/renderer/core/origin_trials"),
    simple_project_pattern("third_party/blink/renderer/core/page"),
    simple_project_pattern("third_party/blink/renderer/core/paint"),
    simple_project_pattern("third_party/blink/renderer/core/probe"),
    simple_project_pattern("third_party/blink/renderer/core/resize_observer"),
    simple_project_pattern("third_party/blink/renderer/core/scheduler"),
    simple_project_pattern("third_party/blink/renderer/core/script"),
    simple_project_pattern("third_party/blink/renderer/core/scroll"),
    simple_project_pattern("third_party/blink/renderer/core/streams"),
    simple_project_pattern("third_party/blink/renderer/core/style"),
    simple_project_pattern("third_party/blink/renderer/core/svg"),
    simple_project_pattern("third_party/blink/renderer/core/testing"),
    simple_project_pattern("third_party/blink/renderer/core/timezone"),
    simple_project_pattern("third_party/blink/renderer/core/timing"),
    simple_project_pattern("third_party/blink/renderer/core/trustedtypes"),
    simple_project_pattern("third_party/blink/renderer/core/typed_arrays"),
    simple_project_pattern("third_party/blink/renderer/core/url"),
    simple_project_pattern("third_party/blink/renderer/core/win"),
    simple_project_pattern("third_party/blink/renderer/core/workers"),
    simple_project_pattern("third_party/blink/renderer/core/xml"),
    simple_project_pattern("third_party/blink/renderer/core/xmlhttprequest"),
    simple_project_pattern("third_party/blink/renderer/devtools"),
    simple_project_pattern("third_party/blink/renderer/modules"),
    simple_project_pattern("third_party/blink/renderer/platform"),
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
    simple_project_pattern("third_party/icu/android"),
    simple_project_pattern("third_party/icu/android_small"),
    simple_project_pattern("third_party/icu/cast"),
    simple_project_pattern("third_party/icu/chromeos"),
    simple_project_pattern("third_party/icu/common"),
    simple_project_pattern("third_party/icu/filters"),
    simple_project_pattern("third_party/icu/flutter"),
    simple_project_pattern("third_party/icu/fuzzers"),
    simple_project_pattern("third_party/icu/ios"),
    simple_project_pattern("third_party/icu/patches"),
    simple_project_pattern("third_party/icu/scripts"),
    simple_project_pattern("third_party/icu/source"),
    simple_project_pattern("third_party/icu/tzres"),
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
    simple_project_pattern("ui/accelerated_widget_mac"),
    simple_project_pattern("ui/accessibility"),
    simple_project_pattern("ui/android"),
    simple_project_pattern("ui/aura"),
    simple_project_pattern("ui/aura_extra"),
    simple_project_pattern("ui/base"),
    simple_project_pattern("ui/chromeos"),
    simple_project_pattern("ui/compositor"),
    simple_project_pattern("ui/compositor_extra"),
    simple_project_pattern("ui/content_accelerators"),
    simple_project_pattern("ui/display"),
    simple_project_pattern("ui/events"),
    simple_project_pattern("ui/file_manager"),
    simple_project_pattern("ui/gfx"),
    simple_project_pattern("ui/gl"),
    simple_project_pattern("ui/latency"),
    simple_project_pattern("ui/login"),
    simple_project_pattern("ui/message_center"),
    simple_project_pattern("ui/native_theme"),
    simple_project_pattern("ui/ozone"),
    simple_project_pattern("ui/platform_window"),
    simple_project_pattern("ui/resources"),
    simple_project_pattern("ui/shell_dialogs"),
    simple_project_pattern("ui/snapshot"),
    simple_project_pattern("ui/strings"),
    simple_project_pattern("ui/surface"),
    simple_project_pattern("ui/touch_selection"),
    simple_project_pattern("ui/views"),
    simple_project_pattern("ui/views_bridge_mac"),
    simple_project_pattern("ui/views_content_client"),
    simple_project_pattern("ui/web_dialogs"),
    simple_project_pattern("ui/webui"),
    simple_project_pattern("ui/wm"),
    simple_project_pattern("url"),
    simple_project_pattern("v8/benchmarks"),
    simple_project_pattern("v8/build_overrides"),
    simple_project_pattern("v8/custom_deps"),
    simple_project_pattern("v8/docs"),
    simple_project_pattern("v8/gni"),
    simple_project_pattern("v8/include"),
    simple_project_pattern("v8/infra"),
    simple_project_pattern("v8/samples"),
    simple_project_pattern("v8/src"),
    simple_project_pattern("v8/test"),
    simple_project_pattern("v8/testing"),
    simple_project_pattern("v8/third_party"),
    simple_project_pattern("v8/tools"),

    # keep out/obj and other patterns at the end.
    [
        'out/obj', '.*/(gen|obj[^/]*)/(include|EXECUTABLES|SHARED_LIBRARIES|'
        'STATIC_LIBRARIES|NATIVE_TESTS)/.*: warning:'
    ],
    ['other', '.*']  # all other unrecognized patterns
]

warning_messages = []
warning_records = []
warning_links = []


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

  warnings = {p: {s.value: 0 for s in Severity.levels} for p in project_names}
  for i in warn_patterns:
    s = i['severity'].value
    for p in i['projects']:
      warnings[p][s] += i['projects'][p]
  return warnings


def get_total_by_project(warnings):
  """Returns dict, project as key and # warnings for that project as value"""

  return {
      p: sum(warnings[p][s.value] for s in Severity.levels)
      for p in project_names
  }


def get_total_by_severity(warnings):
  """Returns dict, severity as key and # warnings of that severity as value"""

  return {
      s.value: sum(warnings[p][s.value] for p in project_names)
      for s in Severity.levels
  }


def emit_table_header(total_by_severity):
  """Returns list of HTML-formatted content for severity stats"""

  stats_header = ['Project']
  for s in Severity.levels:
    if total_by_severity[s.value]:
      stats_header.append("<span style='background-color:{}'>{}</span>".format(
          s.color, s.column_header))
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
      for s in Severity.levels:
        if total_by_severity[s.value]:
          one_row.append(warnings[p][s.value])
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
  for s in Severity.levels:
    if total_by_severity[s.value]:
      one_row.append(total_by_severity[s.value])
      total_all_severities += total_by_severity[s.value]
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


def classify_one_warning(warning, results):
  """Classify one warning line."""

  # Ignore the following warnings so that the html will load
  # TODO: check out the significance of these warnings
  ignored_warnings = [
      r'\[hicpp-no-array-decay\]$', r'\[hicpp-signed-bitwise\]$',
      r'\[hicpp-braces-around-statements\]$',
      r'\[hicpp-uppercase-literal-suffix\]$',
      r'\[bugprone-narrowing-conversions\]$', r'\[fuchsia-.*\]$'
  ]

  for warning_text in ignored_warnings:
    pattern = re.compile(warning_text)
    searched_res = pattern.search(warning['line'])
    if searched_res:
      return

  for i, w in enumerate(warn_patterns):
    for cpat in w['compiled_patterns']:
      if cpat.match(warning['line']):
        p = find_project_index(warning['line'])
        results.append([warning['line'], warning['link'], i, p])
        return
      else:
        # If we end up here, there was a problem parsing the log
        # probably caused by 'make -j' mixing the output from
        # 2 or more concurrent compiles
        pass


def classify_warnings_wrapper(input_tuple):
  """map doesn't work with two input arguments, needs wrapper function"""
  warnings, args = input_tuple
  return classify_warnings(warnings, args)


def classify_warnings(warnings, args):
  results = []
  for warning in warnings:
    classify_one_warning(warning, results)
  # After the main work, ignore all other signals to a child process,
  # to avoid bad warning/error messages from the exit clean-up process.
  if args.processes > 1:
    signal.signal(signal.SIGTERM, lambda *args: sys.exit(-signal.SIGTERM))
  return results


def parallel_classify_warnings(warning_data, args):
  """Classify all warning lines with num_cpu parallel processes."""
  compile_patterns()
  num_cpu = args.processes
  if num_cpu > 1:
    groups = [[] for _ in range(num_cpu)]
    i = 0
    for warning in warning_data:
      groups[i].append(warning)
      i = (i + 1) % num_cpu
    for i, group in enumerate(groups):
      groups[i] = (group, args)
    pool = multiprocessing.Pool(num_cpu)
    group_results = pool.map(classify_warnings_wrapper, groups)
  else:
    group_results = [classify_warnings(warnings_data, args)]

  for result in group_results:
    for line, link, pattern_idx, project_idx in result:
      pattern = warn_patterns[pattern_idx]
      pattern['members'].append(line)
      message_idx = len(warning_messages)
      warning_messages.append(line)
      link_idx = len(warning_links)
      warning_links.append(link)
      warning_records.append([pattern_idx, project_idx, message_idx, link_idx])
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


def remove_prefix(s, sub):
  """Remove everything before last occurence of substring sub in string s"""
  if sub in s:
    inc_sub = s.rfind(sub)
    return s[inc_sub:]
  return s


def generate_cs_link(warning_line):
  """Generate the code search link for a warning line."""
  raw_path = warning_line.split(':')[0]
  normalized_path = normalize_path(warning_line.split(':')[0])
  link_base = 'https://cs.chromium.org/'
  link_add = 'chromium'
  link_path = None

  # Basically just going through a few specific directory cases and specifying
  # the proper behavior for that case. This list of cases was accumulated
  # through trial and error manually going through the warnings.
  #
  # This code pattern of using case-specific "if"s instead of "elif"s looks
  # possibly accidental and mistaken but it is intentional because some paths
  # fall under several cases (e.g. third_party/lib/nghttp2_frame.c) and for
  # those we want the most specific case to be applied. If there is reliable
  # knowledge of exactly where these occur, this could be changed to "elif"s
  # but there is no reliable set of paths falling under multiple cases at the
  # moment.
  if '/src/third_party' in raw_path:
    link_path = remove_prefix(raw_path, '/src/third_party/')
  if '/chrome_root/src_internal/' in raw_path:
    link_path = remove_prefix(raw_path, '/chrome_root/src_internal/')
    link_path = link_path[len('/chrome_root'):]  # remove chrome_root
  if '/chrome_root/src/' in raw_path:
    link_path = remove_prefix(raw_path, '/chrome_root/src/')
    link_path = link_path[len('/chrome_root'):]  # remove chrome_root
  if '/libassistant/' in raw_path:
    link_add = 'eureka_internal/chromium/src'
    link_base = 'https://cs.corp.google.com/'  # internal data
    link_path = remove_prefix(normalized_path, '/libassistant/')
  if raw_path.startswith('gen/'):
    link_path = '/src/out/Debug/gen/' + normalized_path
  if '/gen/' in raw_path:
    return '%s?q=file:%s' % (link_base, remove_prefix(normalized_path, '/gen/'))

  if not link_path:  # can't find specific link, send a query
    return '%s?q=file:%s' % (link_base, normalized_path)

  line_number = int(warning_line.split(':')[1])
  link = '%s%s%s?l=%d' % (link_base, link_add, link_path, line_number)
  return link


def normalize_path(path):
  """Normalize file path relative to src/ or src-internal/ directory."""
  path = os.path.normpath(path)
  # Remove known prefix of root path and normalize the suffix.
  idx = path.find('chrome_root/')
  if idx >= 0:
    # remove chrome_root/, we want path relative to that
    return path[idx + len('chrome_root/'):]
  else:
    return path


def normalize_warning_line(line):
  """Normalize file path relative to src directory in a warning line."""
  # replace fancy quotes with plain ol' quotes
  line = line.replace('‘', "'")
  line = line.strip()
  first_column = line.find(':')
  return normalize_path(line[:first_column]) + line[first_column:]


def parse_input_file(infile):
  """Parse input file, collect parameters and warning lines."""
  # pylint:disable=global-statement
  global platform_version

  # handle only warning messages with a file path
  warning_pattern = re.compile('^[^ ]*/[^ ]*: warning: .*')

  # Collect all warnings into the warning_lines set.
  warning_data = []
  for line in infile:

    if warning_pattern.match(line):
      warning = {}
      warning['link'] = generate_cs_link(line)
      line = normalize_warning_line(line)
      warning['line'] = line
      warning_data.append(warning)
    elif platform_version == 'unknown':
      m = re.match(r'.+Package:.+chromeos-base/chromeos-chrome-', line)
      if m is not None:
        platform_version = line.split('chrome-')[1].split('_')[0]
  return warning_data


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
    if name == "severity":
      print('{},'.format(w[name].value))
    else:
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

  function addURLToLine(line, link) {
      let line_split = line.split(":");
      let path = line_split.slice(0,3).join(":");
      let msg = line_split.slice(3).join(":");
      let html_link = `<a target="_blank" href="${link}">${path}</a>${msg}`;
      return html_link;
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
                  addURLToLine(WarningMessages[messages[i][2]], WarningLinks[messages[i][3]]) + "</td></tr>";
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


def emit_js_data(args):
  """Dump dynamic HTML page's static JavaScript data."""
  emit_const_string('FlagURL', args.url if args.url else '')
  emit_const_string('FlagSeparator', args.separator if args.separator else '')
  emit_const_string_array('SeverityColors', [s.color for s in Severity.levels])
  emit_const_string_array('SeverityHeaders',
                          [s.header for s in Severity.levels])
  emit_const_string_array('SeverityColumnHeaders',
                          [s.column_header for s in Severity.levels])
  emit_const_string_array('ProjectNames', project_names)
  emit_const_int_array('WarnPatternsSeverity',
                       [w['severity'].value for w in warn_patterns])
  emit_const_html_string_array('WarnPatternsDescription',
                               [w['description'] for w in warn_patterns])
  emit_const_html_string_array('WarnPatternsOption',
                               [w['option'] for w in warn_patterns])
  emit_const_html_string_array('WarningMessages', warning_messages)
  emit_const_object_array('Warnings', warning_records)
  emit_const_html_string_array('WarningLinks', warning_links)


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


def dump_html(args):
  """Dump the html output to stdout."""
  dump_html_prologue('Warnings for ' + platform_version + ' - ' +
                     target_product + ' - ' + target_variant)
  dump_stats()
  print('<br><div id="stats_table"></div><br>')
  print('\n<script>')
  emit_js_data(args)
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


def dump_protobuf(write_file):
  """Dump warnings in protobuf format to file given"""
  warnings = generate_protobufs()
  len_struct = struct.Struct('I')  # struct of one integer
  # write all protobufs to file (length delimited for now)
  for warning in warnings:
    warning_string = warning.SerializeToString()
    packed_len = len_struct.pack(len(warning_string))
    write_file.write(packed_len)
    write_file.write(warning_string)


def parse_compiler_output(compiler_output):
  # Parse compiler output for relevant info
  split_output = compiler_output.split(':', 3)  # 3 = max splits
  if len(split_output) < 3:
    # lacks path:line_number:col_number warning: <warning> format
    raise ValueError('Invalid compiler output %s' % compiler_output)
  file_path = split_output[0]
  line_number = int(split_output[1])
  col_number = int(split_output[2].split(' ')[0])
  warning_message = split_output[3]
  return file_path, line_number, col_number, warning_message


def generate_protobufs():
  """Convert warning_records to protobufs"""
  for warning_record in warning_records:
    pattern_idx, _, message_idx, _ = warning_record
    warn_pattern = warn_patterns[pattern_idx]
    compiler_output = warning_messages[message_idx]

    # create warning protobuf
    warning = warnings_pb2.Warning()
    warning.severity = warn_pattern['severity'].proto_value
    warning.warning_text = warn_pattern['description']

    parsed_output = parse_compiler_output(compiler_output)
    file_path, line_number, col_number, warning_message = parsed_output
    warning.file_path = file_path
    warning.line_number = line_number
    warning.col_number = col_number
    warning.matching_compiler_output = warning_message
    yield warning


# helper function to parse the inputting arguments
def create_parser():
  parser = argparse.ArgumentParser(description='Convert a build log into HTML')
  parser.add_argument(
      '--protopath',
      help='Save protobuffer warning file to the passed absolute path',
      default=None)
  parser.add_argument(
      '--genproto',
      help='Generate a protobuf file with number of various warnings',
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
  return parser


def main():
  # parse the input arguments for generating html and proto files
  parser = create_parser()
  args = parser.parse_args()

  warning_lines_and_links = parse_input_file(open(args.buildlog, 'r'))
  parallel_classify_warnings(warning_lines_and_links, args)
  # If a user pases a proto path, save the fileoutput to the path
  # If the user also passed genproto, write the output to stdout
  # If the user did not pass genproto flag dump the html report to stdout.
  if args.protopath:
    with open(args.protopath, 'wb') as f:
      dump_protobuf(f)
  if args.genproto:
    dump_protobuf(sys.stdout)
  else:
    dump_html(args)


# Run main function if warn.py is the main program.
if __name__ == '__main__':
  main()
