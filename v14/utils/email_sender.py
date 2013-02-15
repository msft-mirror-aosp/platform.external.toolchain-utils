#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from email.mime.text import MIMEText
import os
import smtplib


class EmailSender(object):
  def SendEmailToUser(self, subject, text_to_send):
    # Email summary to the current user.
    msg = MIMEText(text_to_send)

    # me == the sender's email address
    # you == the recipient's email address
    me = os.path.basename(__file__)
    you = os.getlogin()
    msg["Subject"] = "[%s] %s" % (os.path.basename(__file__), subject)
    msg["From"] = me
    msg["To"] = you

    # Send the message via our own SMTP server, but don't include the
    # envelope header.
    s = smtplib.SMTP("localhost")
    s.sendmail(me, [you], msg.as_string())
    s.quit()
