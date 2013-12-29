import sys

from zope.interface import implements

from twisted.plugin import IPlugin
from twisted.python import log
from twisted.python import usage
from twisted.application.service import IServiceMaker

from gunny.reveille.client import ReveilleCommandFactory
from gunny.reveille.client import ReveilleCommandProtocol
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


class CoxswainMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "coxswaind"
    description = "Play tracks from server."
    options = Options

    def makeService(self, options):
        """
        Construct a TCPServer from a factory defined in myproject.
        """
        #log.startLogging(sys.stderr)
        url = "ws://%s:%s/ws" % (options["host"], options["port"])
        log.msg('URL: %s' % url)
        factory = ReveilleCommandFactory(ReveilleCommandProtocol(), url)
        return factory.startFactory()


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.

coxswaind = CoxswainMaker()
