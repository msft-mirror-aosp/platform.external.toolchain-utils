#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from email import Encoders
from email.MIMEBase import MIMEBase
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import getpass
import os
import smtplib
import sys


class EmailSender(object):
  class Attachment(object):
    def __init__(self, name, content):
      self.name = name
      self.content = content

  def SendEmail(self,
                email_to,
                subject,
                text_to_send,
                email_cc=None,
                email_bcc=None,
                email_from=None,
                msg_type="plain",
                attachments=None):
    # Email summary to the current user.
    msg = MIMEMultipart()

    if not email_from:
      email_from = os.path.basename(__file__)

    msg["To"] = ",".join(email_to)
    msg["Subject"] = subject

    if email_from:
      msg["From"] = email_from
    if email_cc:
      msg["CC"] = ",".join(email_cc)
      email_to += email_cc
    if email_bcc:
      msg["BCC"] = ",".join(email_bcc)
      email_to += email_bcc

    msg.attach(MIMEText(text_to_send, msg_type))
    if attachments:
      for attachment in attachments:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.content)
        Encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment; filename=\"%s\"" %
                        attachment.name)
        msg.attach(part)

    # Send the message via our own SMTP server, but don't include the
    # envelope header.
    s = smtplib.SMTP("localhost")
    s.sendmail(email_from, email_to, msg.as_string())
    s.quit()
