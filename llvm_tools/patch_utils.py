# Copyright 2022 The ChromiumOS Authors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides patch utilities for PATCHES.json file handling."""

import collections
import contextlib
import dataclasses
import io
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union


CHECKED_FILE_RE = re.compile(r'^checking file\s+(.*)$')
HUNK_FAILED_RE = re.compile(r'^Hunk #(\d+) FAILED at.*')
HUNK_HEADER_RE = re.compile(r'^@@\s+-(\d+),(\d+)\s+\+(\d+),(\d+)\s+@@')
HUNK_END_RE = re.compile(r'^--\s*$')
PATCH_SUBFILE_HEADER_RE = re.compile(r'^\+\+\+ [ab]/(.*)$')


@contextlib.contextmanager
def atomic_write(fp: Union[Path, str], mode='w', *args, **kwargs):
  """Write to a filepath atomically.

  This works by a temp file swap, created with a .tmp suffix in
  the same directory briefly until being renamed to the desired
  filepath.

  Args:
    fp: Filepath to open.
    mode: File mode; can be 'w', 'wb'. Default 'w'.
    *args: Passed to Path.open as nargs.
    **kwargs: Passed to Path.open as kwargs.

  Raises:
    ValueError when the mode is invalid.
  """
  if isinstance(fp, str):
    fp = Path(fp)
  if mode not in ('w', 'wb'):
    raise ValueError(f'mode {mode} not accepted')
  temp_fp = fp.with_suffix(fp.suffix + '.tmp')
  try:
    with temp_fp.open(mode, *args, **kwargs) as f:
      yield f
  except:
    if temp_fp.is_file():
      temp_fp.unlink()
    raise
  temp_fp.rename(fp)


@dataclasses.dataclass
class Hunk:
  """Represents a patch Hunk."""
  hunk_id: int
  """Hunk ID for the current file."""
  orig_start: int
  orig_hunk_len: int
  patch_start: int
  patch_hunk_len: int
  patch_hunk_lineno_begin: int
  patch_hunk_lineno_end: Optional[int]


def parse_patch_stream(patch_stream: io.TextIOBase) -> Dict[str, List[Hunk]]:
  """Parse a patch file-like into Hunks.

  Args:
    patch_stream: A IO stream formatted like a git patch file.

  Returns:
    A dictionary mapping filenames to lists of Hunks present
    in the patch stream.
  """

  current_filepath = None
  current_hunk_id = 0
  current_hunk = None
  out = collections.defaultdict(list)
  for lineno, line in enumerate(patch_stream.readlines()):
    subfile_header = PATCH_SUBFILE_HEADER_RE.match(line)
    if subfile_header:
      current_filepath = subfile_header.group(1)
      if not current_filepath:
        raise RuntimeError('Could not get file header in patch stream')
      # Need to reset the hunk id, as it's per-file.
      current_hunk_id = 0
      continue
    hunk_header = HUNK_HEADER_RE.match(line)
    if hunk_header:
      if not current_filepath:
        raise RuntimeError('Parsed hunk before file header in patch stream')
      if current_hunk:
        # Already parsing a hunk
        current_hunk.patch_hunk_lineno_end = lineno
      current_hunk_id += 1
      current_hunk = Hunk(hunk_id=current_hunk_id,
                          orig_start=int(hunk_header.group(1)),
                          orig_hunk_len=int(hunk_header.group(2)),
                          patch_start=int(hunk_header.group(3)),
                          patch_hunk_len=int(hunk_header.group(4)),
                          patch_hunk_lineno_begin=lineno + 1,
                          patch_hunk_lineno_end=None)
      out[current_filepath].append(current_hunk)
      continue
    if current_hunk and HUNK_END_RE.match(line):
      current_hunk.patch_hunk_lineno_end = lineno
  return out


def parse_failed_patch_output(text: str) -> Dict[str, List[int]]:
  current_file = None
  failed_hunks = collections.defaultdict(list)
  for eline in text.split('\n'):
    checked_file_match = CHECKED_FILE_RE.match(eline)
    if checked_file_match:
      current_file = checked_file_match.group(1)
      continue
    failed_match = HUNK_FAILED_RE.match(eline)
    if failed_match:
      if not current_file:
        raise ValueError('Input stream was not parsable')
      hunk_id = int(failed_match.group(1))
      failed_hunks[current_file].append(hunk_id)
  return failed_hunks


@dataclasses.dataclass(frozen=True)
class PatchResult:
  """Result of a patch application."""
  succeeded: bool
  failed_hunks: Dict[str, List[Hunk]] = dataclasses.field(default_factory=dict)

  def __bool__(self):
    return self.succeeded


@dataclasses.dataclass
class PatchEntry:
  """Object mapping of an entry of PATCHES.json."""
  workdir: Path
  metadata: Dict[str, Any]
  platforms: List[str]
  rel_patch_path: str
  version_range: Dict[str, int]
  _parsed_hunks = None

  def __post_init__(self):
    if not self.workdir.is_dir():
      raise ValueError(f'workdir {self.workdir} is not a directory')

  @classmethod
  def from_dict(cls, workdir: Path, data: Dict[str, Any]):
    """Instatiate from a dictionary.

    Dictionary must have at least the following keys:

      {
        'metadata': {
          'title': '<title>'
        },
        'platforms': ['<platform>'],
        'rel_patch_path': '<relative patch path to workdir>',
        'version_range': {
          'from': <int>,
          'until': <int>,
        },
      }

    Returns:
      A new PatchEntry.
    """
    return cls(workdir, data['metadata'], data['platforms'],
               data['rel_patch_path'], data['version_range'])

  def to_dict(self) -> Dict[str, Any]:
    return {
        'metadata': self.metadata,
        'platforms': self.platforms,
        'rel_patch_path': self.rel_patch_path,
        'version_range': self.version_range,
    }

  def parsed_hunks(self) -> Dict[str, List[Hunk]]:
    # Minor caching here because IO is slow.
    if not self._parsed_hunks:
      with self.patch_path().open(encoding='utf-8') as f:
        self._parsed_hunks = parse_patch_stream(f)
    return self._parsed_hunks

  def patch_path(self) -> Path:
    return self.workdir / self.rel_patch_path

  def can_patch_version(self, svn_version: int) -> bool:
    """Is this patch meant to apply to `svn_version`?"""
    # Sometimes the key is there, but it's set to None.
    from_v = self.version_range.get('from') or 0
    until_v = self.version_range.get('until')
    if until_v is None:
      until_v = sys.maxsize
    return from_v <= svn_version < until_v

  def is_old(self, svn_version: int) -> bool:
    """Is this patch old compared to `svn_version`?"""
    until_v = self.version_range.get('until')
    # Sometimes the key is there, but it's set to None.
    if until_v is None:
      until_v = sys.maxsize
    return svn_version >= until_v

  def apply(self,
            root_dir: Path,
            extra_args: Optional[List[str]] = None) -> PatchResult:
    """Apply a patch to a given directory."""
    if not extra_args:
      extra_args = []
    # Cmd to apply a patch in the src unpack path.
    cmd = [
        'patch', '-d',
        root_dir.absolute(), '-f', '-p1', '--no-backup-if-mismatch', '-i',
        self.patch_path().absolute()
    ] + extra_args
    try:
      subprocess.run(cmd, encoding='utf-8', check=True, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
      parsed_hunks = self.parsed_hunks()
      failed_hunks_id_dict = parse_failed_patch_output(e.stdout)
      failed_hunks = {}
      for path, failed_hunk_ids in failed_hunks_id_dict.items():
        hunks_for_file = parsed_hunks[path]
        failed_hunks[path] = [
            hunk for hunk in hunks_for_file if hunk.hunk_id in failed_hunk_ids
        ]
      return PatchResult(succeeded=False, failed_hunks=failed_hunks)
    return PatchResult(succeeded=True)

  def test_apply(self, root_dir: Path) -> PatchResult:
    """Dry run applying a patch to a given directory."""
    return self.apply(root_dir, ['--dry-run'])

  def title(self) -> str:
    return self.metadata['title']
