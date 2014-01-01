
from zope.interface import implements

from twisted.application.internet import UNIXClient
from twisted.plugin import IPlugin
from twisted.python import log
from twisted.python import usage
from twisted.application.service import IServiceMaker

from autobahn.wamp import WampClientFactory

from gunny.reveille.coxswain import ReveilleClientProtocol
from gunny.reveille.service import CoxswainService


class EnqueueOptions(usage.Options):
    optParameters = [
        ['file', 'f', None, None],
    ]

    def __init__(self):
        usage.Options.__init__(self)
        self['files'] = []

    def opt_file(self, fname):
        self['files'].append(fname)

    opt_f = opt_file


class ToggleOptions(usage.Options):
    optParameters = []


class Options(usage.Options):
    subCommands = [
        ['enqueue', None, EnqueueOptions, "Queue File(s)"],
        ['toggle', None, ToggleOptions, "Toggle play/pause"],
    ]
    optParameters = [
        ["host", "h", '127.0.0.1', "The host to connect to."],
        ["port", "p", 9876, "The port number to connect to.", int],
    ]

    def parseArgs(self):
        pass


class CoxswainMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "coxswaind"
    description = "Play tracks from server."
    options = Options

    def makeService(self, options):
        """
        Construct a UNIXClient from a factory defined in myproject.
        """
        #log.startLogging(sys.stderr)
        return UNIXClient('/tmp/rcp.sock')


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.

coxswain = CoxswainMaker()
