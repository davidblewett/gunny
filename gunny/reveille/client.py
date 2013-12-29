from io import BufferedRandom
from io import BytesIO
import os
import sys

from zope.interface import implements

from twisted.application.internet import UNIXServer
from twisted.internet import stdio, reactor, defer, interfaces
from twisted.internet.defer import inlineCallbacks
from twisted.protocols import basic
from twisted.python import log

from autobahn.wamp import WampClientFactory
from autobahn.wamp import WampClientProtocol
from autobahn.wamp import exportRpc
from autobahn.websocket import WebSocketClientFactory
from autobahn.websocket import WebSocketClientProtocol
from autobahn.websocket import connectWS

from gunny.player import Player


# FIXME: refactor to buffer based on seek points
# Not a hard limit; more of a high-water mark
BUFFER_SIZE = 32 * 1024


class WebSocketDecoder(BufferedRandom):
    """
    A Twisted IConsumer in a WebSockets message frame.
    """
    implements(interfaces.IConsumer)

    producer = None
    streaming = None
    write_pos = 0
    closed = False
    _length = 0

    def __init__(self, proto, path, buf=None):
        if buf is None:
            buf = BufferedRandom(BytesIO())
        self._buffer = buf
        self.proto = proto
        self.path = path

    def registerProducer(self, producer, streaming):
        log.msg('registerProducer: %s, %s' % (producer, streaming))
        self.producer = producer
        self.streaming = streaming
        if not self.streaming:
            self.producer.resumeProducing(self.path)

    def unregisterProducer(self):
        log.msg('unregisterProducer')
        self.producer = None
        self.streaming = None

    def write(self, data):
        #log.msg('write: %d' % len(data))
        curr_pos = self.tell()
        self.seek(0, os.SEEK_END)
        num_bytes = self._buffer.write(data)
        self.write_pos += num_bytes
        self.seek(curr_pos, os.SEEK_SET)
        self.checkBuffer(curr_pos)
        return num_bytes

    def read(self, n=-1):
        data = self._buffer.read(n)
        self.checkBuffer()
        return data

    def seek(self, pos, whence=0):
        return self._buffer.seek(pos, whence)

    def tell(self):
        pos = self._buffer.tell()
        #log.msg('tell: %d' % pos)
        return pos

    def readinto(self, buf):
        data = self.read(len(buf))
        dlen = len(data)
        buf[:dlen] = data
        return dlen

    def checkBuffer(self, pos=None):
        if pos is None:
            pos = self.tell()
        #log.msg('checkBuffer: %d' % pos)
        if self.write_pos - pos < self.proto.buffer_size:
            log.msg('Buffer short: resume %d' % (self.write_pos - pos))
            self.producer.resumeProducing(self.path)

    def close(self):
        self.write_pos = 0
        self._buffer.truncate(0)
        self.closed = True

    def __len__(self):
        return self._length

    def __unicode__(self):
        return u'<WebSocketDecoder "%s">' % self.path


(WSCP_PATH, WSCP_SIZE, WSCP_DATA) = range(3)


class WscpClientProtocol(WebSocketClientProtocol):
    """
    WebSockets client that streams files from the server
    """
    implements(interfaces.IPushProducer)

    open_deferred = None
    buffer_filled = None
    frame_num = WSCP_PATH
    path = None

    def __init__(self, buffer_size=BUFFER_SIZE):
        self.open_deferred = defer.Deferred()
        self.buffer_size = buffer_size
        self.file_decoders = {}

    def sendCommand(self, command, *args):
        log.msg('Sending %s: %r' % (command, args))
        cmd = [command]
        cmd.extend(args)
        self.sendMessage('|'.join(cmd))

    def resumeProducing(self, path):
        self.sendCommand('RESUME', path)

    def stopProducing(self, path):
        self.sendCommand('STOP', path)

    def getFile(self, path):
        self.buffer_filled = defer.Deferred()
        self.file_decoders[path] = WebSocketDecoder(self, path)
        self.sendCommand('GET', path)
        return self.buffer_filled

    def seek(self, pos, whence=0):
        self.sendCommand('SEEK', str(pos), str(whence))

    def onOpen(self):
        self.open_deferred.callback(self)
        self.open_deferred = None

    def onMessageBegin(self, opcode):
        log.msg('onMessageBegin')
        WebSocketClientProtocol.onMessageBegin(self, opcode)

    def onMessageFrameBegin(self, length, reserved):
        #log.msg('onMessageFrameBegin: %s' % length)
        WebSocketClientProtocol.onMessageFrameBegin(self, length, reserved)
        if self.frame_num == WSCP_DATA and self.buffer_filled is not None:
            self.file_decoders[self.path].registerProducer(self, True)

    def onMessageFrameData(self, data):
        #log.msg('Received chunk: %d / %d / %d' % (len(data), self.file_decoders[path].write_pos, self.file_decoders[path].length))
        if self.frame_num == WSCP_PATH:
            #log.msg('Frame path: %s' % (data, ))
            self.path = data
        elif self.frame_num == WSCP_SIZE:
            #log.msg('File total size: %s' % (data, ))
            self.file_decoders[self.path]._length = long(data)
        elif self.frame_num == WSCP_DATA and self.file_decoders[self.path] is not None:
            log.msg('Received chunk %s: %d' % (self.path, len(data),))
            curr_pos = self.file_decoders[self.path].tell()
            self.file_decoders[self.path].write(data)
            buffered_bytes = self.file_decoders[self.path].write_pos - curr_pos
            log.msg('Buffered: %d/%d' % (buffered_bytes,
                                         self.buffer_size))
            if self.buffer_filled is not None and \
               buffered_bytes >= self.buffer_size:
                # We wait for first block before returning the decoder
                self.buffer_filled.callback(self.file_decoders[self.path])
                self.buffer_filled = None

    def onMessageFrameEnd(self):
        self.frame_num += 1

    def onMessageEnd(self):
        self.frame_num = WSCP_PATH


class WscpClientFactory(WebSocketClientFactory):

    protocol = WscpClientProtocol

    def __init__(self, control_channel, **kwargs):
        self.control_channel = control_channel
        WebSocketClientFactory.__init__(self, **kwargs)

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        p.open_deferred.addCallback(self.control_channel.onWscpOpen)
        return p


class ReveilleClientProtocol(WampClientProtocol):

    subprotocolFactory = WscpClientFactory
    wscp = None
    open_deferred = None

    def __init__(self):
        self.open_deferred = defer.Deferred()

    def onOpen(self):
        self.open_deferred.callback(self)
        self.open_deferred = None

    def onSessionOpen(self):
        log.msg('onSessionOpen')
        self.onClientAdd()

    def connectionLost(self, reason):
        if self.wscp is not None:
            self.wscp.failConnection()
        WampClientProtocol.connectionLost(self, reason)

    def onClientAdd(self):
        log.msg('onClientAdd')
        # FIXME: parse existing connection URL and change path
        factory = self.subprotocolFactory(
            self,
            #url="ws://192.168.1.2:9876/stream",
            url="ws://127.0.0.1:9876/stream",
            protocols=['wscp'],
            debug=self.debug,
            debugCodePaths=self.debugCodePaths
        )
        connect_d = connectWS(factory)
        return connect_d

    def onWscpOpen(self, wcsp):
        self.wcsp = wcsp
        self.player = Player()
        #self.enqueue('01.flac')

    @inlineCallbacks
    @exportRpc
    def enqueue(self, path):
        log.msg('enqueue: %s' % path)
        fObj = yield self.wcsp.getFile(path)
        self.player.enqueue(fObj)

    @exportRpc
    def play(self):
        log.msg('play')
        self.player.play()

    @exportRpc
    def playPause(self):
        log.msg('playPause')
        self.player.toggle_play_pause()

    @exportRpc
    def stopPlaying(self):
        log.msg('stopPlaying')
        self.player.stop_playing()

    @exportRpc
    def nextTrack(self):
        log.msg('nextTrack')
        self.stopPlaying()
        self.player.play()

    @inlineCallbacks
    @exportRpc
    def previousTrack(self):
        log.msg('previousTrack')
        prev = self.player.played.pop()
        self.stopPlaying()
        fObj = yield self.enqueue(prev.path)
        self.play()

    @exportRpc
    def resumeProducing(self, path):
        if self.wscp is not None:
            self.wscp.resumeProducing(path)

    @exportRpc
    def stopProducing(self, path):
        if self.wscp is not None:
            self.wscp.stopProducing(path)


class ReveilleClientFactory(WampClientFactory):

    protocol = ReveilleClientProtocol

    def __init__(self, command_channel, *args, **kwargs):
        self.command_channel = command_channel
        WampClientFactory.__init__(self, *args, **kwargs)

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        p.open_deferred.addCallback(self.command_channel.onReveilleOpen)
        return p


class ReveilleCommandProtocol(basic.LineReceiver):
    delimiter = '\n'  # unix terminal style newlines. remove this line
                      # for use with Telnet

    def __init__(self, factory_class=ReveilleClientFactory, **kwargs):
        self.factory_class = factory_class

    def onReveilleOpen(self, reveille):
        self.reveille = reveille

    def connectionMade(self):
        self.sendLine("Reveille command console. Type 'help' for help.")

    def lineReceived(self, line):
        # Ignore blank lines
        if not line: return

        # Parse the command
        commandParts = line.split()
        command = commandParts[0].lower()
        args = commandParts[1:]

        # Dispatch the command to the appropriate method.  Note that all you
        # need to do to implement a new command is add another do_* method.
        try:
            method = getattr(self, 'do_' + command)
        except AttributeError, e:
            self.sendLine('Error: no such command.')
        else:
            try:
                method(*args)
            except Exception, e:
                self.sendLine('Error: ' + str(e))

    def do_help(self, command=None):
        """help [command]: List commands, or show help on the given command"""
        if command:
            self.sendLine(getattr(self, 'do_' + command).__doc__)
        else:
            commands = [cmd[3:] for cmd in dir(self) if cmd.startswith('do_')]
            self.sendLine("Valid commands: " + " ".join(commands))

    def do_quit(self):
        """quit: Quit this session"""
        self.sendLine('Goodbye.')
        self.transport.loseConnection()

    def do_enqueue(self, file_name):
        """playTrack <file_name>: play selected file"""
        self.reveille.enqueue(file_name)
        #self.sendLine("Success: got %i bytes." % len(pageData))

    def do_play(self):
        self.reveille.play()

    def do_toggle(self):
        self.reveille.playPause()

    def do_stop(self):
        self.reveille.stopPlaying()

    def do_prev(self):
        self.reveille.previousTrack()

    def do_next(self):
        self.reveille.nextTrack()

    def connectionLost(self, reason):
        # stop the reactor, only because this is meant to be run in Stdio.
        reactor.stop()


class ReveilleCommandFactory(ReveilleClientFactory):

    protocol = ReveilleCommandProtocol

    def buildProtocol(self, addr):
        proto = ReveilleClientFactory.buildProtocol(self, addr)
        factory = proto.factory_class(self,
            #"ws://192.168.1.2:9876/reveille",
            "ws://127.0.0.1:9876/reveille",
            #debug=debug,
            #debugCodePaths=debug,
        )
        connectWS(factory)

    def startFactory(self):
        return UNIXServer('/tmp/rcp.sock', self)


if __name__ == '__main__':
    log.startLogging(sys.stderr)
    stdio.StandardIO(ReveilleCommandProtocol())
    #factory = WampClientFactory(
    #    #"ws://192.168.1.2:9876/reveille",
    #    "ws://127.0.0.1:9876/reveille",
    #    #debug=debug,
    #    #debugCodePaths=debug,
    #)
    #factory.protocol = ReveilleClientProtocol
    #connectWS(factory)

    reactor.run()
