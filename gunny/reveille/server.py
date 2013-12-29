import os
import sys

from zope.interface import implements

from twisted.internet import reactor, defer, interfaces
from twisted.internet.defer import inlineCallbacks
from twisted.protocols import ftp
from twisted.python import log, filepath
from twisted.web.server import Site
from twisted.web.static import File

from autobahn.resource import WebSocketResource
from autobahn.resource import HTTPChannelHixie76Aware
from autobahn.wamp import exportRpc
from autobahn.wamp import WampServerFactory
from autobahn.wamp import WebSocketServerFactory
from autobahn.wamp import WampServerProtocol
from autobahn.wamp import WebSocketServerProtocol
from autobahn.websocket import listenWS
from autobahn.websocket import WebSocketProtocol


class ReveilleServerProtocol(WampServerProtocol):
    """
    Demonstrates creating a server with Autobahn WebSockets that provides
    a persistent key-value store which can we access via RPCs.
    """

    #def onSessionOpen(self):
        ## register the key-value store, which resides on the factory within
        ## this connection
        #self.registerForRpc(self.factory.keyvalue, "http://reveille.ws/simple/keyvalue#")


class WebSocketStreamingEncoder(object):
    """
    A Twisted IConsumer in a WebSockets message frame.
    """
    implements(interfaces.IConsumer)

    producer = None
    streaming = None
    write_pos = 0

    def __init__(self, proto, path):
        self.proto = proto
        self.path = path
        self.reactor = proto.transport.reactor
        self.size = proto.file_path.getsize()

    def registerProducer(self, producer, streaming):
        log.msg('registerProducer: %s, %s' % (producer, streaming))
        self.producer = producer
        self.streaming = streaming
        if not self.streaming:
            # NOTE: we use callLater to avoid possibly exceeding
            #       maximum recursion depth
            self.reactor.callLater(0, self.producer.resumeProducing)

    def unregisterProducer(self):
        log.msg('unregisterProducer')
        self.proto.endMessage()
        self.producer = None
        self.streaming = None

    def write(self, data):
        # FIXME: refactor this to use callbacks
        self.proto.beginMessage(binary=True)
        log.msg('beginMessageFrame: %d' % len(self.path))
        self.proto.beginMessageFrame(len(self.path))
        log.msg('sendMessageFrameData: %s' % self.path)
        self.proto.sendMessageFrameData(self.path)
        log.msg('beginMessageFrame: %d' % len(str(self.size)))
        self.proto.beginMessageFrame(len(str(self.size)))
        log.msg('sendMessageFrameData: %s' % str(self.size))
        self.proto.sendMessageFrameData(str(self.size))
        log.msg('beginMessageFrame: %d' % len(data))
        self.proto.beginMessageFrame(len(data))
        self.proto.sendMessageFrameData(data)
        self.proto.endMessage()
        self.write_pos += len(data)
        log.msg('Sent frame bytes for %s: %d/%d/%d' % (self.path,
                                                       len(data),
                                                       self.write_pos,
                                                       self.size))

    def __len__(self):
        return self.size


class WscpServerProtocol(WebSocketServerProtocol):
    """
    Streaming WebSockets server that transmits the contents of a local file
    """

    def __init__(self):
        self.file_encoders = {}

    def _path(self, path):
        combined_path = reduce(filepath.FilePath.child, path,
                               self.factory.filesystemRoot)
        log.msg(combined_path)
        return combined_path

    #def onConnect(self, connectionRequest):
    #    WebSocketServerProtocol.onConnect(self, connectionRequest)

    def sendFile(self, path):
        log.msg('sendFile')
        cwd = '/'.split(self.factory.filesystemRoot.path)[1:]
        segs = ftp.toSegments(cwd, path)
        self.file_path = self._path(segs)
        if self.file_path.isdir():
            # Normally, we would only check for EISDIR in open, but win32
            # returns EACCES in this case, so we check before
            log.msg('cant send dir')
            return defer.fail(ftp.IsADirectoryError(path))
        try:
            f = self.file_path.open('rb')
        except (IOError, OSError), e:
            log.msg('Error: %s' % e)
            return ftp.errnoToFailure(e.errno, path)
        except:
            log.msg('Bare except fail')
            return defer.fail()
        else:
            log.msg('Returning file reader')
            return defer.succeed(ftp._FileReader(f))

    def onMessage(self, message, binary):
        # Since the data channel is completely independent
        # from the control channel server-side, we have to
        # roll a simple RPC mechanism
        log.msg('onMessage: %r' % message)
        args = message.split('|')
        if args[0].upper() == 'GET':
            return self.onFileGet(args[1])
        elif args[0].upper() == 'RESUME':
            return self.onResumeProducing(args[1])
        elif args[0].upper() == 'STOP':
            return self.onStopProducing(args[1])

    def onResumeProducing(self, path):
        log.msg('Resuming production: %s' % path)
        if self.file_encoders[path] is not None:
            self.file_encoders[path].producer.resumeProducing()

    def onStopProducing(self, path):
        log.msg('Stopping production: %s.' % path)
        if self.file_encoders[path] is not None:
            self.file_encoders[path].producer.stopProducing()
            del self.file_encoders[path]

    @inlineCallbacks
    def onFileGet(self, path):
        log.msg('Sending file: %s' % path)
        file_reader = yield self.sendFile(path)
        log.msg('file_reader: %s' % file_reader)
        self.file_encoders[path] = WebSocketStreamingEncoder(self, path)
        last_sent = yield file_reader.send(self.file_encoders[path])
        log.msg('last_sent: %r' % last_sent)
        defer.returnValue(last_sent)


class MuxingServerProtocol(WebSocketServerProtocol):
    """
    Switch protocol handler based on subprotocol
    """

    protocol = None

    def onConnect(self, connectionRequest):
        if 'wscp' in connectionRequest.protocols:
            # Prefer wscp over wamp
            self.protocol = WscpServerProtocol
        else:
            self.protocol = ReveilleServerProtocol
        self.service.onConnect(connectionRequest)

    def onOpen(self):
        if self.service:
            self.service.onOpen()

    def onMessage(self, msg, isBinary):
        if self.service:
            self.service.onMessage(msg, isBinary)

    def onClose(self, wasClean, code, reason):
        if self.service:
            self.service.onClose(wasClean, code, reason)


class ReveilleServerFactory(WampServerFactory):

    protocol = ReveilleServerProtocol

    def __init__(self, url, debugWamp=False):
        WampServerFactory.__init__(self, url, debugWamp=debugWamp)

        ## the key-value store resides on the factory object, since it is to
        ## be shared among all client connections
        #self.keyvalue = Reveille("keyvalue.dat")


class WscpServerFactory(WebSocketServerFactory):

    protocol = WscpServerProtocol

    def __init__(self, url, fsRoot, debugWamp=False):
        self.filesystemRoot = filepath.FilePath(fsRoot)
        WebSocketServerFactory.__init__(self, url)


if __name__ == '__main__':

    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        log.startLogging(sys.stdout)
        debug = True
    else:
        debug = False

    port = 9876

    ws_factory = ReveilleServerFactory("ws://localhost:%d" % port,
                                       debugWamp=debug)
    ws_factory.setProtocolOptions(allowHixie76=True)
    ## need to start manually, see https://github.com/tavendo/AutobahnPython/issues/133
    ws_factory.startFactory()
    #listenWS(ws_factory)

    ## Twisted Web resource for our WAMP factory
    ws_resource = WebSocketResource(ws_factory)

    stream_factory = WscpServerFactory("ws://localhost:%d" % port,
                                       #'/data/music_archive',
                                       '/Users/davidb/src',
                                       debugWamp=debug)
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
    reactor.listenTCP(port, site)

    reactor.run()
