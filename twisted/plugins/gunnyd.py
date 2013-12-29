import sys

from zope.interface import implements

from twisted.application import internet
from twisted.application.service import IServiceMaker
from twisted.plugin import IPlugin
from twisted.python import log
from twisted.python import usage
from twisted.web.server import Site
from twisted.web.static import File

from autobahn.resource import HTTPChannelHixie76Aware
from autobahn.resource import WebSocketResource
from autobahn.wamp import WampClientFactory, WampClientProtocol

from gunny.reveille.server import ReveilleServerFactory
from gunny.reveille.server import WscpServerFactory
from gunny.reveille.service import PlayerService


class Options(usage.Options):
    optParameters = [
        ["port", "p", 9876, "The port number to listen on."],
    ]


class GunnyMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "gunnyd"
    description = "Serve up tracks."
    options = Options

    def makeService(self, options):
        """
        Construct a TCPServer from a factory defined in myproject.
        """

        ws_factory = ReveilleServerFactory("ws://localhost:%d" % options["port"])
        ws_factory.setProtocolOptions(allowHixie76=True)
        ## need to start manually, see https://github.com/tavendo/AutobahnPython/issues/133
        ws_factory.startFactory()
        #listenWS(ws_factory)

        ## Twisted Web resource for our WAMP factory
        ws_resource = WebSocketResource(ws_factory)

        stream_factory = WscpServerFactory("ws://localhost:%d" % options["port"],
                                           #'/data/music_archive',
                                           '/Users/davidb/src')
        stream_factory.setProtocolOptions(allowHixie76=True)
        ## need to start manually, see https://github.com/tavendo/AutobahnPython/issues/133
        stream_factory.startFactory()
        #listenWS(stream_factory)

        ## Twisted Web resource for our WAMP factory
        stream_resource = WebSocketResource(stream_factory)

        ## we server static files under "/" ..
        root = File(".")

        ## and our WAMP server under "/reveille"
        root.putChild("reveille", ws_resource)

        ## and our WebSocket server under "/stream"
        root.putChild("stream", stream_resource)

        ## both under one Twisted Web Site
        site = Site(root)
        site.protocol = HTTPChannelHixie76Aware  # needed if Hixie76 is to be supported
        return internet.TCPServer(int(options["port"]), site)


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.

gunnyd = GunnyMaker()
