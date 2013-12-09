import sys

from zope.interface import implements

from twisted.plugin import IPlugin
from twisted.python import log
from twisted.python import usage
from twisted.application.service import IServiceMaker

from autobahn.wamp import WampClientFactory, WampClientProtocol
from autobahn.websocket import connectWS

from gunny.reveille.client import ReveilleClientProtocol
from gunny.reveille.service import PlayerService


class Options(usage.Options):
    optFlags = [
        ['nodaemon','n',  "don't daemonize, don't use default umask of 0077"],
    ]
    optParameters = [
        ["host", "h", '127.0.0.1', "The host to connect to."],
        ["port", "p", 9876, "The port number to connect to."],
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
        factory = WampClientFactory(url)
        factory.protocol = ReveilleClientProtocol
        import pdb; pdb.set_trace()  # NOQA
        #return connectWS(factory)
        return PlayerService(factory)


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.

coxswaind = CoxswainMaker()
