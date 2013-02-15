import sys
import optparse
import xmlrpclib
from utils import utils
from automation.common import job
from automation.common import job_group


def Main(argv):
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-s",
                    "--server",
                    dest="server",
                    default="localhost",
                    help="The server address (default is localhost)."
                    )
  parser.add_option("-p",
                    "--port",
                    dest="port",
                    default="8000",
                    help="The port of the server."
                    )
  options = parser.parse_args(argv)[0]
  server = "http://" +  options.server + ":" + options.port
  server = xmlrpclib.Server(server)
  job_groups = utils.Deserialize(server.GetAllJobGroups())
  for job_group in job_groups[::-1]:
    print str(job_group)


if __name__ == "__main__":
  Main(sys.argv)

