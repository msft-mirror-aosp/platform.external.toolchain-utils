#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from email import Encoders
from email.MIMEBase import MIMEBase
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import getpass
import smtplib
import sys


class EmailSender(object):
  class Attachment(object):
    def __init__(self, name, content):
      self.name = name
      self.content = content

  def SendEmailToUser(self, subject, text_to_send, msg_type="plain",
                      attachments=None):
    # Email summary to the current user.
    msg = MIMEMultipart()

    # me == the sender's email address
    # you == the recipient's email address
    me = sys.argv[0]
    you = getpass.getuser()
    msg["Subject"] = "[%s] %s" % (me, subject)
    msg["From"] = me
    msg["To"] = you

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
    s.sendmail(me, [you], msg.as_string())
    s.quit()
