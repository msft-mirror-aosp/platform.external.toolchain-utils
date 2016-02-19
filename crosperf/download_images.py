# Copyright (c) 2014, 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import os

import test_flag

from utils import command_executer


class MissingImage(Exception):
  """Raised when the requested image does not exist in gs://"""


class ImageDownloader(object):

  def __init__(self, logger_to_use=None, log_level='verbose', cmd_exec=None):
    self._logger = logger_to_use
    self.log_level = log_level
    self._ce = cmd_exec or command_executer.GetCommandExecuter(
        self._logger,
        log_level=self.log_level)

  def GetBuildID(self, chromeos_root, xbuddy_label):
    # Get the translation of the xbuddy_label into the real Google Storage
    # image name.
    command = ('cd ~/trunk/src/third_party/toolchain-utils/crosperf; '
               "python translate_xbuddy.py '%s'" % xbuddy_label)
    retval, build_id_tuple_str, _ = self._ce.ChrootRunCommandWOutput(
        chromeos_root, command)
    if not build_id_tuple_str:
      raise MissingImage("Unable to find image for '%s'" % xbuddy_label)

    build_id_tuple = ast.literal_eval(build_id_tuple_str)
    build_id = build_id_tuple[0]

    return build_id

  def DownloadImage(self, chromeos_root, build_id, image_name):
    if self.log_level == 'average':
      self._logger.LogOutput('Preparing to download %s image to local '
                             'directory.' % build_id)

    # Make sure the directory for downloading the image exists.
    download_path = os.path.join(chromeos_root, 'chroot/tmp', build_id)
    image_path = os.path.join(download_path, 'chromiumos_test_image.bin')
    if not os.path.exists(download_path):
      os.makedirs(download_path)

    # Check to see if the image has already been downloaded.  If not,
    # download the image.
    if not os.path.exists(image_path):
      command = 'gsutil cp %s /tmp/%s' % (image_name, build_id)

      if self.log_level != 'verbose':
        self._logger.LogOutput('CMD: %s' % command)
      status = self._ce.ChrootRunCommand(chromeos_root, command)
      if status != 0 or not os.path.exists(image_path):
        raise MissingImage('Cannot download image: %s.' % image_name)

    return image_path

  def UncompressImage(self, chromeos_root, build_id):
    # Check to see if the file has already been uncompresssed, etc.
    if os.path.exists(os.path.join(chromeos_root, 'chroot/tmp', build_id,
                                   'chromiumos_test_image.bin')):
      return

    # Uncompress and untar the downloaded image.
    command = ('cd /tmp/%s ;unxz chromiumos_test_image.tar.xz; '
               'tar -xvf chromiumos_test_image.tar' % build_id)
    if self.log_level != 'verbose':
      self._logger.LogOutput('CMD: %s' % command)
      print('(Uncompressing and un-tarring may take a couple of minutes...'
            'please be patient.)')
    retval = self._ce.ChrootRunCommand(chromeos_root, command)
    if retval != 0:
      raise MissingImage('Cannot uncompress image: %s.' % build_id)

  def Run(self, chromeos_root, xbuddy_label):
    build_id = self.GetBuildID(chromeos_root, xbuddy_label)
    image_name = ('gs://chromeos-image-archive/%s/chromiumos_test_image.tar.xz'
                  % build_id)

    # Verify that image exists for build_id, before attempting to
    # download it.
    status = 0
    if not test_flag.GetTestMode():
      cmd = 'gsutil ls %s' % image_name
      status = self._ce.ChrootRunCommand(chromeos_root, cmd)
    if status != 0:
      raise MissingImage('Cannot find official image: %s.' % image_name)

    image_path = self.DownloadImage(chromeos_root, build_id, image_name)
    self.UncompressImage(chromeos_root, build_id)

    if self.log_level != 'quiet':
      self._logger.LogOutput('Using image from %s.' % image_path)

    return image_path
