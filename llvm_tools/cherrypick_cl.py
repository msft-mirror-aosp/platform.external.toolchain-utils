#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=cros-logging-import

"""Adds a cherrypick to LLVM's PATCHES.json."""

from __future__ import print_function

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys

import get_llvm_hash
import git_llvm_rev


def add_cherrypick(patches_json_path: str, patches_dir: str,
                   relative_patches_dir: str, start_version: git_llvm_rev.Rev,
                   llvm_dir: str, rev: git_llvm_rev.Rev, sha: str):
  with open(patches_json_path, encoding='utf-8') as f:
    patches_json = json.load(f)

  file_name = sha + '.patch'
  rel_patch_path = os.path.join(relative_patches_dir, file_name)

  for p in patches_json:
    rel_path = p['rel_patch_path']
    if rel_path == rel_patch_path:
      raise ValueError('Patch at %r already exists in PATCHES.json' % rel_path)
    if sha in rel_path:
      logging.warning(
          'Similarly-named patch already exists in PATCHES.json: %r', rel_path)

  with open(os.path.join(patches_dir, file_name), 'wb') as f:
    subprocess.check_call(['git', 'show', sha], stdout=f, cwd=llvm_dir)

  commit_subject = subprocess.check_output(
      ['git', 'log', '-n1', '--format=%s', sha], cwd=llvm_dir, encoding='utf-8')

  patches_json.append({
      'comment': commit_subject.strip(),
      'rel_patch_path': rel_patch_path,
      'start_version': start_version.number,
      'end_version': rev.number,
  })

  temp_file = patches_json_path + '.tmp'
  with open(temp_file, 'w', encoding='utf-8') as f:
    json.dump(patches_json, f, indent=4, separators=(',', ': '))
  os.rename(temp_file, patches_json_path)


def parse_ebuild_for_assignment(llvm_path: str, var_name: str) -> str:
  # '_pre' filters the LLVM 9.0 ebuild, which we never want to target, from
  # this list.
  candidates = [
      x for x in os.listdir(llvm_path)
      if x.endswith('.ebuild') and x.startswith('llvm') and '_pre' in x
  ]

  if not candidates:
    raise ValueError('No LLVM ebuilds found under %r' % llvm_path)

  ebuild = os.path.join(llvm_path, max(candidates))
  with open(ebuild, encoding='utf-8') as f:
    var_name_eq = var_name + '='
    for orig_line in f:
      if not orig_line.startswith(var_name_eq):
        continue

      # We shouldn't see much variety here, so do the simplest thing possible.
      line = orig_line[len(var_name_eq):]
      # Remove comments
      line = line.split('#')[0]
      # Remove quotes
      line = shlex.split(line)
      if len(line) != 1:
        raise ValueError('Expected exactly one quoted value in %r' % orig_line)
      return line[0].strip()

  raise ValueError('No %s= line found in %r' % (var_name, ebuild))


# Resolves a git ref (or similar) to a LLVM SHA.
def resolve_llvm_ref(llvm_dir: str, sha: str) -> str:
  return subprocess.check_output(
      ['git', 'rev-parse', sha],
      encoding='utf-8',
      cwd=llvm_dir,
  ).strip()


def main():
  logging.basicConfig(
      format='%(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: %(message)s',
      level=logging.INFO,
  )

  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      '--llvm', help='Path to sys-devel/llvm. Will autodetect if not provided.')
  parser.add_argument(
      '--start_sha',
      default='llvm-next',
      help='LLVM SHA that the patch should start applying at. You can specify '
      '"llvm" or "llvm-next", as well. Defaults to %(default)s.')
  parser.add_argument(
      '--sha', help='LLVM git SHA. Either this or --sha must be specified.')
  args = parser.parse_args()

  if args.llvm:
    llvm = args.llvm
  else:
    my_dir = os.path.dirname(os.path.realpath(__file__))
    llvm = os.path.join(
        my_dir, '../../../third_party/chromiumos-overlay/sys-devel/llvm')
    if not os.path.isdir(llvm):
      raise ValueError("Couldn't autodetect llvm")

  llvm = os.path.realpath(llvm)

  patches_json_path = os.path.join(llvm, 'files/PATCHES.json')
  relative_patches_dir = 'cherry'
  patches_dir = os.path.join(llvm, 'files', relative_patches_dir)

  llvm_config = git_llvm_rev.LLVMConfig(
      remote='origin', dir=get_llvm_hash.GetAndUpdateLLVMProjectInLLVMTools())

  start_sha = args.start_sha
  if start_sha == 'llvm':
    start_sha = parse_ebuild_for_assignment(llvm, 'LLVM_HASH')
    logging.info('Autodetected llvm hash == %s', start_sha)
  elif start_sha == 'llvm-next':
    start_sha = parse_ebuild_for_assignment(llvm, 'LLVM_NEXT_HASH')
    logging.info('Autodetected llvm-next hash == %s', start_sha)

  start_sha = resolve_llvm_ref(llvm_config.dir, start_sha)
  start_rev = git_llvm_rev.translate_sha_to_rev(llvm_config, start_sha)
  sha = resolve_llvm_ref(llvm_config.dir, args.sha)
  rev = git_llvm_rev.translate_sha_to_rev(llvm_config, sha)

  logging.info('Will cherrypick %s (%s), with start == %s', rev, sha, start_sha)
  add_cherrypick(patches_json_path, patches_dir, relative_patches_dir,
                 start_rev, llvm_config.dir, rev, sha)
  logging.info('Complete.')


if __name__ == '__main__':
  sys.exit(main())
