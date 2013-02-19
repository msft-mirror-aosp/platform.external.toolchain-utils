#!/usr/bin/python2.4
# Copyright 2010 Google Inc. All Rights Reserved.
"""Code to transport profile data between a user's phone and the GWP servers.
    Pages:
    "/": the main page for the app, left blank so that users cannot access
         the file upload but left in the code for debuggin purposes
    "/upload": Updates the datastore with a new file. the upload depends on
               the for which is templated on the main page ("/")
               input includes:
                    build_num: the build number of the kernel
                    kernel_ver: the version of the kernel
                    phone_id: the imei number of the phone if in debug mode or
                          a random number if not in debug mode
                    proc_name: name of the processor on the phone.
                    profile_data: the zipped file containing profile data
                                  and other files from the phone
    "/serve": Lists all of the files in the datastore. each line is a new entry
              in the datastore. The format is key~date~build~ver~imei, where
              key is the entries key in the datastore), date is the file upload
              time and date, build is the build number, ver is the kernel
              version, and imei is the imei number of the phone.(Authentication
              Required)
    "/serve/([^/]+)?": For downloading a file of profile data, ([^/]+)? means
                       any character sequence so the to download the file go to
                       '/serve/$key' where $key is the datastore key of the file
                       you want to download.(Authentication Required)
    "/del/([^/]+)?": For deleting an entry in the datastore. To use go to
                     '/del/$key' where $key is the datastore key of the entry
                     you want to be deleted form the datastore. (Authentication
                     Required)
    TODO: Add more extensive logging"""

import cgi
import logging
import md5
import urllib

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

MAX_FILE_ENTRIES_DISP = 100

logging.getLogger().setLevel(logging.DEBUG)


class FileEntry(db.Model):
  ufile = db.BlobProperty()                       #The profile data of the phone
  date = db.DateTimeProperty(auto_now_add=True)   #date it was uploaded
  fmd5 = db.ByteStringProperty()                  #fmd5 for error testing
  build = db.StringProperty()                     #build number fo the phone
  ver = db.StringProperty()                       #kernel version of the phone
  proc_info = db.StringProperty()                 #Processor information
  phone_id = db.StringProperty()                  #imei num. of the phone if in
                                                  #debug mode else random number


class MainPage(webapp.RequestHandler):
  """Main page only used as the form template, not actually displayed."""

  def get(self, response=""):
    if response is not "" and Authenticate(self):
      self.response.out.write("<html><body>")
      self.response.out.write("""<br>
        <form action="/upload" enctype="multipart/form-data" method="post">
          <div><label>File:</label></div>
          <div><input type="file" name="profile_data"/></div>
          <div><label>Build:</label></div>
          <div><input type="text" name="build_num"/></div>
          <div><label>Version Number:</label></div>
          <div><input type="text" name="kernel_ver"/></div>
          <div><label>IMEI Number:</label></div>
          <div><input type="text" name="phone_id"/></div>
          <div><input type="submit" value="Upload"></div>
        </form>
      </body>
      </html>""")


class Upload(webapp.RequestHandler):
  """Handler for uploading data to the datastore, accessible by anyone."""

  def post(self):
    """Takes input based on the main page's form."""
    getfile = FileEntry()

    getfile.build = self.request.get("build_num")
    getfile.ver = self.request.get("kernel_ver")
    getfile.phone_id = self.request.get("phone_id")
    getfile.proc_info = self.request.get("proc_info")
    f = self.request.get("profile_data")
    getfile.ufile = db.Blob(f)

    m = md5.new(f)
    getfile.fmd5 = m.hexdigest()

    getfile.put()
    self.response.out.write(getfile.key())
    #self.redirect('/')


class ServeHandler(webapp.RequestHandler):
  """Given the entry's key in the database, output the profile data file. Only 
      accessible from @google.com accounts."""

  def get(self, resource):
    auth = Authenticate(self)
    if auth is True:
      fkey = str(urllib.unquote(resource))
      reqent = db.get(fkey)
      self.response.out.write(reqent.ufile)


class ListAll (webapp.RequestHandler):
  """Displays all files uploaded. Only accessible by @google.com accounts."""

  def get (self):
    """Dispalys all information in FileEntry for, ~ delimited."""
    auth = Authenticate(self)
    if auth is True:
      query_str = ("SELECT * FROM FileEntry ORDER BY date ASC LIMIT "
                   + str(MAX_FILE_ENTRIES_DISP))
      query = db.GqlQuery(query_str)
      for item in query:
        self.response.out.write(
            "%s<div>%s<div>%s<div>%s<div>%s<div>%s<div>%s</br>"
            %(cgi.escape(str(item.key())), item.date, cgi.escape(item.build),
              cgi.escape(item.ver), cgi.escape(str(item.proc_info)),
              item.phone_id, item.fmd5))


class DelEntries(webapp.RequestHandler):
  """Deletes entries. Only accessible from @google.com accounts."""

  def get(self, resource):
    """A specific entry is deleted, when the key is given."""
    auth = Authenticate(self)
    if auth is True:
      fkey = str(urllib.unquote(resource))
      reqent = db.get(fkey)
      if reqent is not None:
        db.delete(fkey)


def Authenticate (webpage):
  """Some urls are only accessible if logged in with a @google.com account."""
  user = users.get_current_user()
  if user is None:
    webpage.redirect(users.create_login_url(webpage.request.uri))
  elif user.email().endswith("@google.com"):
    return True
  else:
    webpage.response.out.write("Not Authenticated")
    return False


def main():
  application = webapp.WSGIApplication([
      ("/", MainPage),
      ("/upload", Upload),
      ("/serve/([^/]+)?", ServeHandler),
      ("/serve", ListAll),
      ("/del/([^/]+)?", DelEntries),
      #("/([^/]+)?", MainPage)
  ], debug=False)

  run_wsgi_app(application)


if __name__ == "__main__":
  main()
