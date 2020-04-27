#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Checks for new reverts in LLVM on a nightly basis.

If any reverts are found that were previously unknown, this fires off an email.
All LLVM SHAs to monitor are autodetected.
"""

# pylint: disable=cros-logging-import

from __future__ import print_function

import argparse
import io
import json
import logging
import os
import pprint
import sys
import typing as t

import cros_utils.email_sender as email_sender
import cros_utils.tiny_render as tiny_render
import get_llvm_hash
import revert_checker

State = t.Any

# FIXME(gbiv): we probably want to have Android compat here, too. Should be
# easy to nab their testing version automatically with:
# git merge-base m/llvm-toolchain aosp/upstream-master


def _parse_llvm_ebuild_for_shas(
    ebuild_file: io.TextIOWrapper) -> t.List[t.Tuple[str]]:

  def parse_ebuild_assignment(line: str) -> str:
    no_comments = line.split('#')[0]
    no_assign = no_comments.split('=', 1)[1].strip()
    assert no_assign.startswith('"') and no_assign.endswith('"'), no_assign
    return no_assign[1:-1]

  llvm_hash, llvm_next_hash = None, None
  for line in ebuild_file:
    if line.startswith('LLVM_HASH='):
      llvm_hash = parse_ebuild_assignment(line)
      if llvm_next_hash:
        break
    if line.startswith('LLVM_NEXT_HASH'):
      llvm_next_hash = parse_ebuild_assignment(line)
      if llvm_hash:
        break
  if not llvm_next_hash or not llvm_hash:
    raise ValueError('Failed to detect SHAs for llvm/llvm_next. Got: '
                     'llvm=%s; llvm_next=%s' % (llvm_hash, llvm_next_hash))
  return [('llvm', llvm_hash), ('llvm-next', llvm_next_hash)]


def _find_interesting_shas(chromeos_base: str) -> t.List[t.Tuple[str]]:
  llvm_dir = os.path.join(chromeos_base,
                          'src/third_party/chromiumos-overlay/sys-devel/llvm')
  candidate_ebuilds = [
      os.path.join(llvm_dir, x)
      for x in os.listdir(llvm_dir)
      if '_pre' in x and not os.path.islink(os.path.join(llvm_dir, x))
  ]

  if len(candidate_ebuilds) != 1:
    raise ValueError('Expected exactly one llvm ebuild candidate; got %s' %
                     pprint.pformat(candidate_ebuilds))

  with open(candidate_ebuilds[0], encoding='utf-8') as f:
    return _parse_llvm_ebuild_for_shas(f)


_Email = t.NamedTuple('_Email', [
    ('subject', str),
    ('body', tiny_render.Piece),
])


def _generate_revert_email(
    friendly_name: str, sha: str,
    prettify_sha: t.Callable[[str], tiny_render.Piece],
    new_reverts: t.List[revert_checker.Revert]) -> _Email:
  email_pieces = [
      'It looks like there may be %s across %s (' % (
          'a new revert' if len(new_reverts) == 1 else 'new reverts',
          friendly_name,
      ),
      prettify_sha(sha),
      ').',
      tiny_render.line_break,
      tiny_render.line_break,
      'That is:' if len(new_reverts) == 1 else 'These are:',
  ]

  revert_listing = []
  for revert in sorted(new_reverts, key=lambda r: r.sha):
    revert_listing.append([
        prettify_sha(revert.sha),
        ' (appears to revert ',
        prettify_sha(revert.reverted_sha),
        ')',
    ])

  email_pieces.append(tiny_render.UnorderedList(items=revert_listing))
  email_pieces += [
      tiny_render.line_break,
      'PTAL and consider reverting them locally.',
  ]
  return _Email(
      subject='[revert-checker] new %s discovered across %s' % (
          'revert' if len(new_reverts) == 1 else 'reverts',
          friendly_name,
      ),
      body=email_pieces,
  )


def _send_revert_email(email: _Email) -> None:
  email_sender.EmailSender().SendX20Email(
      subject=email.subject,
      identifier='revert-checker',
      well_known_recipients=[],
      direct_recipients=['gbiv@google.com'],
      text_body=tiny_render.render_text_pieces(email.body),
      html_body=tiny_render.render_html_pieces(email.body),
  )


def _write_state(state_file: str, new_state: State) -> None:
  try:
    tmp_file = state_file + '.new'
    with open(tmp_file, 'w', encoding='utf-8') as f:
      json.dump(new_state, f, sort_keys=True, indent=2, separators=(',', ': '))
    os.rename(tmp_file, state_file)
  except:
    try:
      os.remove(tmp_file)
    except FileNotFoundError:
      pass
    raise


def _read_state(state_file: str) -> State:
  try:
    with open(state_file) as f:
      return json.load(f)
  except FileNotFoundError:
    logging.info('No state file found at %r; starting with an empty slate',
                 state_file)
    return {}


def main(argv: t.List[str]) -> None:
  parser = argparse.ArgumentParser(
      description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument(
      '--state_file', required=True, help='File to store persistent state in.')
  parser.add_argument(
      '--llvm_dir', required=True, help='Up-to-date LLVM directory to use.')
  parser.add_argument(
      '--chromeos_dir', required=True, help='Up-to-date CrOS directory to use.')
  parser.add_argument(
      '--dry_run',
      action='store_true',
      help='Print email contents, rather than sending them.')
  parser.add_argument('--debug', action='store_true')
  opts = parser.parse_args(argv)

  logging.basicConfig(
      format='%(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: %(message)s',
      level=logging.DEBUG if opts.debug else logging.INFO,
  )

  state_file = opts.state_file
  dry_run = opts.dry_run
  llvm_dir = opts.llvm_dir

  state = _read_state(state_file)

  interesting_shas = _find_interesting_shas(opts.chromeos_dir)
  logging.info('Interesting SHAs were %r', interesting_shas)

  def prettify_sha(sha: str) -> tiny_render.Piece:
    rev = get_llvm_hash.GetVersionFrom(llvm_dir, sha)

    # 12 is arbitrary, but should be unambiguous enough.
    short_sha = sha[:12]
    return tiny_render.Switch(
        text='r%s (%s)' % (rev, short_sha),
        html=tiny_render.Link(
            href='https://reviews.llvm.org/rG' + sha, inner='r' + str(rev)),
    )

  new_state: State = {}
  revert_emails_to_send: t.List[t.Tuple[str, t.List[revert_checker
                                                    .Revert]]] = []
  for friendly_name, sha in interesting_shas:
    logging.info('Finding reverts across %s (%s)', friendly_name, sha)
    all_reverts = revert_checker.find_reverts(
        llvm_dir, sha, root='origin/master')
    logging.info('Detected the following revert(s) across %s:\n%s',
                 friendly_name, pprint.pformat(all_reverts))

    new_state[sha] = [r.sha for r in all_reverts]

    if sha not in state:
      logging.info('SHA %s is new to me', sha)
      existing_reverts = set()
    else:
      existing_reverts = set(state[sha])

    new_reverts = [r for r in all_reverts if r.sha not in existing_reverts]
    if not new_reverts:
      logging.info('...All of which have been reported.')
      continue

    revert_emails_to_send.append(
        _generate_revert_email(friendly_name, sha, prettify_sha, new_reverts))

  # We want to be as free of obvious side-effects as possible in case something
  # above breaks. Hence, send the email as late as possible.
  for email in revert_emails_to_send:
    if dry_run:
      logging.info('Would send email:\nSubject: %s\nBody:\n%s\n', email.subject,
                   tiny_render.render_text_pieces(email.body))
    else:
      logging.info('Sending email with subject %r...', email.subject)
      _send_revert_email(email)
      logging.info('Email sent.')

  _write_state(state_file, new_state)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
