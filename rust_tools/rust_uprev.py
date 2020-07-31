#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool to automatically generate a new Rust uprev CL.

This tool is intended to automatically generate a CL to uprev Rust to a
newer version in Chrome OS. It's based on
src/third_party/chromiumos-overlay/dev-lang/rust/UPGRADE.md. When using
the tool, the progress can be saved to a JSON file, so the user can resume
the process after a failing step is fixed. Example usage:

1. (inside chroot) $ ./rust_tools/rust_uprev.py --rust_version 1.45.0 \
                   --state_file /tmp/state-file.json
2. Step "compile rust" failed due to the patches can't apply to new version
3. Manually fix the patches
4. Execute the command in step 1 again.
5. Iterate 1-4 for each failed step until the tool passes.

See `--help` for all available options.
"""

# pylint: disable=cros-logging-import

import argparse
import pathlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, NamedTuple, Optional, T, Tuple

from llvm_tools import chroot, git


def get_command_output(command: List[str]) -> str:
  return subprocess.check_output(command, encoding='utf-8').strip()


class RustVersion(NamedTuple):
  """NamedTuple represents a Rust version"""
  major: int
  minor: int
  patch: int

  def __str__(self):
    return f'{self.major}.{self.minor}.{self.patch}'

  @staticmethod
  def parse_from_ebuild(ebuild_name: str) -> 'RustVersion':
    input_re = re.compile(r'^rust-'
                          r'(?P<major>\d+)\.'
                          r'(?P<minor>\d+)\.'
                          r'(?P<patch>\d+)'
                          r'\.ebuild$')
    m = input_re.match(ebuild_name)
    assert m, f'failed to parse {ebuild_name!r}'
    return RustVersion(
        int(m.group('major')), int(m.group('minor')), int(m.group('patch')))

  @staticmethod
  def parse(x: str) -> 'RustVersion':
    input_re = re.compile(r'^(?:rust-)?'
                          r'(?P<major>\d+)\.'
                          r'(?P<minor>\d+)\.'
                          r'(?P<patch>\d+)'
                          r'(?:.ebuild)?$')
    m = input_re.match(x)
    assert m, f'failed to parse {x!r}'
    return RustVersion(
        int(m.group('major')), int(m.group('minor')), int(m.group('patch')))


def parse_stage0_file(new_version: RustVersion) -> Tuple[str, str, str]:
  # Find stage0 date, rustc and cargo
  stage0_file = get_command_output([
      'curl', '-f', 'https://raw.githubusercontent.com/rust-lang/rust/'
      f'{new_version}/src/stage0.txt'
  ])
  regexp = re.compile(r'date:\s*(?P<date>\d+-\d+-\d+)\s+'
                      r'rustc:\s*(?P<rustc>\d+\.\d+\.\d+)\s+'
                      r'cargo:\s*(?P<cargo>\d+\.\d+\.\d+)')
  m = regexp.search(stage0_file)
  assert m, 'failed to parse stage0.txt file'
  stage0_date, stage0_rustc, stage0_cargo = m.groups()
  logging.info('Found stage0 file has date: %s, rustc: %s, cargo: %s',
               stage0_date, stage0_rustc, stage0_cargo)
  return stage0_date, stage0_rustc, stage0_cargo


def prepare_uprev_from_json(json_input: Any
                           ) -> Tuple[str, RustVersion, RustVersion]:
  a, b, c = json_input
  return a, RustVersion(*b), RustVersion(*c)


def prepare_uprev(rust_version: RustVersion,
                  reset: bool) -> Tuple[str, RustVersion, RustVersion]:
  ebuild_path = get_command_output(['equery', 'w', 'rust'])
  rust_path, ebuild_name = os.path.split(ebuild_path)
  if reset:
    subprocess.check_call(['git', 'reset', '--hard'], cwd=rust_path)
    ebuild_path = get_command_output(['equery', 'w', 'rust'])
    _, ebuild_name = os.path.split(ebuild_path)

  current_version = RustVersion.parse(ebuild_name)
  if rust_version <= current_version:
    logging.info('Requested version %s is not newer than existing version %s.',
                 rust_version, current_version)
    return '', None, None

  logging.info('Current Rust version is %s', current_version)
  other_ebuilds = [
      x for x in os.listdir(rust_path) if '.ebuild' in x and x != ebuild_name
  ]
  if len(other_ebuilds) != 1:
    raise Exception('Expect exactly 1 previous version ebuild, '
                    f'but actually found {other_ebuilds}')
  # TODO(tcwang): Only support uprev from the older ebuild; need support to
  # pick either version of the Rust to uprev from
  old_version = RustVersion.parse(other_ebuilds[0])
  # Prepare a repo branch for uprev
  branch_name = f'rust-to-{rust_version}'
  git.CreateBranch(rust_path, branch_name)
  logging.info('Create a new repo branch %s', branch_name)
  return rust_path, current_version, old_version


def copy_patches(rust_path: str, old_version: RustVersion,
                 current_version: RustVersion,
                 new_version: RustVersion) -> None:
  patch_path = os.path.join(rust_path, 'files')
  for f in os.listdir(patch_path):
    if f'rust-{current_version}' not in f:
      continue
    logging.info('Rename patch %s to new version', f)
    new_name = f.replace(str(current_version), str(new_version))
    shutil.copyfile(
        os.path.join(patch_path, f),
        os.path.join(patch_path, new_name),
    )

  subprocess.check_call(['git', 'add', f'files/rust-{new_version}-*.patch'],
                        cwd=rust_path)

  subprocess.check_call(['git', 'rm', f'files/rust-{old_version}-*.patch'],
                        cwd=rust_path)


def rename_ebuild(rust_path: str, old_version: RustVersion,
                  current_version: RustVersion,
                  new_version: RustVersion) -> str:
  shutil.copyfile(
      os.path.join(rust_path, f'rust-{current_version}.ebuild'),
      os.path.join(rust_path, f'rust-{new_version}.ebuild'))
  subprocess.check_call(['git', 'add', f'rust-{new_version}.ebuild'],
                        cwd=rust_path)
  subprocess.check_call(['git', 'rm', f'rust-{old_version}.ebuild'],
                        cwd=rust_path)
  return os.path.join(rust_path, f'rust-{new_version}.ebuild')


def update_ebuild(ebuild_file: str, stage0_info: Tuple[str, str, str]) -> None:
  stage0_date, stage0_rustc, stage0_cargo = stage0_info
  with open(ebuild_file, encoding='utf-8') as f:
    contents = f.read()
  # Update STAGE0_DATE in the ebuild
  stage0_date_re = re.compile(r'STAGE0_DATE="(\d+-\d+-\d+)"')
  if not stage0_date_re.search(contents):
    raise RuntimeError('STAGE0_DATE not found in rust ebuild')
  new_contents = stage0_date_re.sub(f'STAGE0_DATE="{stage0_date}"', contents)

  # Update STAGE0_VERSION in the ebuild
  stage0_rustc_re = re.compile(r'STAGE0_VERSION="[^"]*"')
  if not stage0_rustc_re.search(new_contents):
    raise RuntimeError('STAGE0_VERSION not found in rust ebuild')
  new_contents = stage0_rustc_re.sub(f'STAGE0_VERSION="{stage0_rustc}"',
                                     new_contents)

  # Update STAGE0_VERSION_CARGO in the ebuild
  stage0_cargo_re = re.compile(r'STAGE0_VERSION_CARGO="[^"]*"')
  if not stage0_cargo_re.search(new_contents):
    raise RuntimeError('STAGE0_VERSION_CARGO not found in rust ebuild')
  new_contents = stage0_cargo_re.sub(f'STAGE0_VERSION_CARGO="{stage0_cargo}"',
                                     new_contents)
  with open(ebuild_file, 'w', encoding='utf-8') as f:
    f.write(new_contents)
  logging.info(
      'Rust ebuild file has STAGE0_DATE, STAGE0_VERSION, STAGE0_VERSION_CARGO '
      'updated to %s, %s, %s respectively', stage0_date, stage0_rustc,
      stage0_cargo)
  return ebuild_file


def flip_mirror_in_ebuild(ebuild_file: str, add: bool) -> None:
  restrict_re = re.compile(
      r'(?P<before>RESTRICT=")(?P<values>"[^"]*"|.*)(?P<after>")')
  with open(ebuild_file, encoding='utf-8') as f:
    contents = f.read()
  m = restrict_re.search(contents)
  assert m, 'failed to find RESTRICT variable in Rust ebuild'
  values = m.group('values')
  if add:
    if 'mirror' in values:
      return
    values += ' mirror'
  else:
    if 'mirror' not in values:
      return
    values = values.replace(' mirror', '')
  new_contents = restrict_re.sub(r'\g<before>%s\g<after>' % values, contents)
  with open(ebuild_file, 'w', encoding='utf-8') as f:
    f.write(new_contents)


def rust_ebuild_command(command: str, sudo: bool = False) -> None:
  ebuild_path_inchroot = get_command_output(['equery', 'w', 'rust'])
  cmd = ['ebuild', ebuild_path_inchroot, command]
  if sudo:
    cmd = ['sudo'] + cmd
  subprocess.check_call(cmd, stderr=subprocess.STDOUT)


def update_manifest(ebuild_file: str) -> None:
  logging.info('Added "mirror" to RESTRICT to Rust ebuild')
  flip_mirror_in_ebuild(ebuild_file, add=True)
  rust_ebuild_command('manifest')
  logging.info('Removed "mirror" to RESTRICT from Rust ebuild')
  flip_mirror_in_ebuild(ebuild_file, add=False)


def upgrade_rust_packages(ebuild_file: str, old_version: RustVersion,
                          current_version: RustVersion,
                          new_version: RustVersion) -> None:
  package_file = os.path.join(
      os.path.dirname(ebuild_file),
      '../../profiles/targets/chromeos/package.provided')
  with open(package_file, encoding='utf-8') as f:
    contents = f.read()
  old_str = f'dev-lang/rust-{old_version}'
  current_str = f'dev-lang/rust-{current_version}'
  new_str = f'dev-lang/rust-{new_version}'
  if old_str not in contents or current_str not in contents:
    raise Exception(f'Expect {old_str} and {current_str} to be in '
                    'profiles/targets/chromeos/package.provided')
  # Replace the two strings (old_str, current_str) with (current_str, new_str),
  # so they are still ordered by rust versions
  new_contents = contents.replace(current_str,
                                  new_str).replace(old_str, current_str)
  with open(package_file, 'w', encoding='utf-8') as f:
    f.write(new_contents)
  logging.info('package.provided has been updated from %s, %s to %s, %s',
               old_str, current_str, current_str, new_str)


def update_virtual_rust(ebuild_file: str, old_version: RustVersion,
                        new_version: RustVersion) -> None:
  virtual_rust_dir = os.path.join(
      os.path.dirname(ebuild_file), '../../virtual/rust')
  assert os.path.exists(virtual_rust_dir)
  subprocess.check_call(
      ['git', 'mv', f'rust-{old_version}.ebuild', f'rust-{new_version}.ebuild'],
      cwd=virtual_rust_dir)


def upload_to_localmirror(tempdir: str, rust_version: RustVersion) -> None:
  tarfile_name = f'rustc-{rust_version}-src.tar.gz'
  rust_src = f'https://static.rust-lang.org/dist/{tarfile_name}'
  logging.info('Downloading Rust from %s', rust_src)
  gsutil_location = f'gs://chromeos-localmirror/distfiles/{tarfile_name}'

  local_file = os.path.join(tempdir, tarfile_name)
  subprocess.check_call(['curl', '-f', '-o', local_file, rust_src])
  # Since we are using `-n` to skip an item if it already exists, there's no
  # need to check if the file exists on GS bucket or not.
  subprocess.check_call(
      ['gsutil', 'cp', '-n', '-a', 'public-read', local_file, gsutil_location])


def perform_step(state_file: pathlib.Path,
                 tmp_state_file: pathlib.Path,
                 completed_steps: Dict[str, Any],
                 step_name: str,
                 step_fn: Callable[[], T],
                 result_from_json: Optional[Callable[[Any], T]] = None,
                 result_to_json: Optional[Callable[[T], Any]] = None) -> T:
  if step_name in completed_steps:
    logging.info('Skipping previously completed step %s', step_name)
    if result_from_json:
      return result_from_json(completed_steps[step_name])
    return completed_steps[step_name]

  logging.info('Running step %s', step_name)
  val = step_fn()
  logging.info('Step %s complete', step_name)
  if result_to_json:
    completed_steps[step_name] = result_to_json(val)
  else:
    completed_steps[step_name] = val

  with tmp_state_file.open('w', encoding='utf-8') as f:
    json.dump(completed_steps, f, indent=4)
  tmp_state_file.rename(state_file)
  return val


def main():
  if not chroot.InChroot():
    raise RuntimeError('This script must be executed inside chroot')

  logging.basicConfig(level=logging.INFO)

  parser = argparse.ArgumentParser(
      description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--rust_version',
      type=RustVersion.parse,
      required=True,
      help='Rust version to upgrade to, in the form a.b.c',
  )
  parser.add_argument(
      '--state_file',
      required=True,
      help='A state file to hold previous completed steps. If the file '
      'exists, it needs to be used together with --continue or --restart. '
      'If not exist (do not use --continue in this case), we will create a '
      'file for you.',
  )
  parser.add_argument(
      '--skip_compile',
      action='store_true',
      help='Skip compiling rust to test the tool. Only for testing',
  )
  parser.add_argument(
      '--restart',
      action='store_true',
      help='Restart from the first step. Ignore the completed steps in '
      'the state file',
  )
  parser.add_argument(
      '--continue',
      dest='cont',
      action='store_true',
      help='Continue the steps from the state file',
  )

  args = parser.parse_args()

  rust_version = args.rust_version
  state_file = pathlib.Path(args.state_file)
  tmp_state_file = pathlib.Path(args.state_file + '.tmp')

  if args.cont and args.restart:
    parser.error('Please select either --continue or --restart')

  if os.path.exists(state_file):
    if not args.cont and not args.restart:
      parser.error('State file exists, so you should either --continue '
                   'or --restart')
  if args.cont and not os.path.exists(state_file):
    parser.error('Indicate --continue but the state file does not exist')

  if args.restart and os.path.exists(state_file):
    os.remove(state_file)

  try:
    with state_file.open(encoding='utf-8') as f:
      completed_steps = json.load(f)
  except FileNotFoundError:
    completed_steps = {}

  def run_step(
      step_name: str,
      step_fn: Callable[[], T],
      result_from_json: Optional[Callable[[Any], T]] = None,
      result_to_json: Optional[Callable[[T], Any]] = None,
  ) -> T:
    return perform_step(state_file, tmp_state_file, completed_steps, step_name,
                        step_fn, result_from_json, result_to_json)

  stage0_info = run_step(
      'parse stage0 file', lambda: parse_stage0_file(rust_version))
  rust_path, current_version, old_version = run_step(
      'prepare uprev',
      lambda: prepare_uprev(rust_version, args.restart),
      result_from_json=prepare_uprev_from_json,
  )
  if current_version is None:
    return

  current_version = RustVersion(*current_version)
  old_version = RustVersion(*old_version)

  run_step(
      'copy patches', lambda: copy_patches(rust_path, old_version,
                                           current_version, rust_version))
  ebuild_file = run_step(
      'rename ebuild', lambda: rename_ebuild(rust_path, old_version,
                                             current_version, rust_version))
  run_step('update ebuild', lambda: update_ebuild(ebuild_file, stage0_info))
  with tempfile.TemporaryDirectory(dir='/tmp') as tempdir:
    run_step('upload_to_localmirror', lambda: upload_to_localmirror(
        tempdir, rust_version))
  run_step('update manifest', lambda: update_manifest(ebuild_file))
  if not args.skip_compile:
    run_step('compile rust', lambda: rust_ebuild_command('compile'))
    run_step('merge rust', lambda: rust_ebuild_command('merge', sudo=True))
  run_step(
      'upgrade rust packages', lambda: upgrade_rust_packages(
          ebuild_file, old_version, current_version, rust_version))
  run_step('upgrade virtual/rust', lambda: update_virtual_rust(
      ebuild_file, old_version, rust_version))


if __name__ == '__main__':
  sys.exit(main())
