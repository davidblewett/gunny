from collections import deque
import os
from io import BufferedRandom
from io import BytesIO

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

    def registerProducer(self, producer, streaming):
        #log.msg('registerProducer: %s, %s' % (producer, streaming))
        self.producer = producer
        self.streaming = streaming
        if not self.streaming:
            self.producer.resumeProducing()

    def unregisterProducer(self):
        #log.msg('unregisterProducer')
        self.producer = None
        self.streaming = None

    def write(self, data):
        curr_pos = self.tell()
        self.seek(0, os.SEEK_END)
        num_bytes = BufferedRandom.write(self, data)
        self.write_pos += num_bytes
        self.seek(curr_pos, os.SEEK_SET)
        if self.write_pos - curr_pos < BUFFER_SIZE:
            #log.msg('Buffer short: resume')
            self.producer.resumeProducing()
        return num_bytes

    def read(self, n=-1):
        data = BufferedRandom.read(self, n)
        curr_pos = self.tell()
        curr_buf = self.write_pos - curr_pos
        if curr_buf < BUFFER_SIZE:
            #log.msg('Buffer short: resume %d' % curr_buf)
            self.producer.resumeProducing()
        return data


def chunks(s, n):
    """Produce `n`-character chunks from `s`.
    http://stackoverflow.com/a/7111143
    """
    for start in range(0, len(s), n):
        yield s[start:start+n]


class WebSocketStreamingDecoder(object):
    """
    A Twisted IConsumer in a WebSockets message frame.
    """
    implements(interfaces.IConsumer)

    producer = None
    streaming = None
    remaining = 0
    write_deferred = None

    def __init__(self, proto, length):
        self.proto = proto
        self.length = length
        self.buflist = deque()
        self.buflist.append(bytearray())
        self.write_pos = 0
        self.read_pos = 0

    def __len__(self):
        #log.msg('__len__: %d' % self.length)
        return self.length

    def seek(self, offset, whence=os.SEEK_SET):
        # Seeking not supported for now
        if whence == os.SEEK_SET:
            if offset > self.write_pos:
                raise ValueError("Can't seek past end of stream")
            self.read_pos = offset
        elif whence == os.SEEK_CUR:
            if self.read_pos + offset > self.write_pos:
                raise ValueError("Can't seek past end of stream")
            self.read_pos = self.read_pos + offset
        elif whence == os.SEEK_END:
            if self.write_pos < self.length:
                raise ValueError("Can't seek past end of stream")
            self.read_pos = self.length - offset
        return self.read_pos

    def tell(self):
        return self.read_pos

    def registerProducer(self, producer, streaming):
        #log.msg('registerProducer: %s, %s' % (producer, streaming))
        self.producer = producer
        self.streaming = streaming
        if not self.streaming:
            self.producer.resumeProducing()

    def unregisterProducer(self):
        #log.msg('unregisterProducer')
        self.producer = None
        self.streaming = None

    #@inlineCallbacks
    def write(self, data):
        last_block_len = len(self.buflist[-1])
        if last_block_len < BLOCK_SIZE:
            chunk_pos = BLOCK_SIZE - last_block_len
            self.buflist[-1].extend(data[:chunk_pos])
            self.write_pos += len(data[:chunk_pos])
            data = data[chunk_pos:]

        for chunk in chunks(data, BLOCK_SIZE):
            self.buflist.append(bytearray(chunk))
            self.write_pos += len(chunk)

        if self.write_deferred is not None and \
           self.curr_size >= self.remaining:
            remaining_data = self._packBuffer(self.remaining)
            self.write_deferred.callback(remaining_data)
            self.write_deferred = None
        if len(self.buflist) >= self.proto.buffer_blocks:
            #log.msg('Buffer full: pausing')
            self.producer.pauseProducing()
        elif not self.streaming:
            self.producer.resumeProducing()
        return len(data)

    def _waitForData(self, n):
        self.remaining += n
        self.write_deferred = defer.Deferred()
        return self.write_deferred

    #@inlineCallbacks
    def _packBuffer(self, n):
        # Allocate a buffer big enough to hold the
        # entire requested size
        ret_val = bytearray(n)
        curr_pos = 0
        while self.buflist and curr_pos < n:
            data = self.buflist.popleft()
            dlen = len(data)
            remaining = n - curr_pos
            if dlen <= remaining:
                # Easy case: chunk fits in remaining
                ret_val[curr_pos:dlen] = data
                curr_pos += dlen
            elif dlen > remaining:
                # Last chunk doesn't fit
                ret_val[curr_pos:remaining] = data[:remaining]
                curr_pos += remaining
                self.buflist.appendleft(data[remaining:])
        # If we didn't accumulate enough data, defer until filled
        if curr_pos < n:
            pass
            #log.msg("Didn't accumulate enough data for read")
        #    data = yield self._waitForData(n-curr_pos)
        #    dlen = len(data)
        #    ret_val[curr_pos:dlen] = data
        #    curr_pos += dlen
        #assert curr_pos == n
        #defer.returnValue(ret_val)
        return ret_val

    #@inlineCallbacks
    def read(self, n=-1):
        if n <= 0:
            ret_val = bytearray().join(self.buflist)
            self.buflist = deque()
        elif n == BLOCK_SIZE:
            ret_val = self.buflist.popleft()
        elif n < BLOCK_SIZE:
            ret_val = self.buflist[0][:n]
        elif n > BLOCK_SIZE:
            ret_val = self._packBuffer(n)
        self.read_pos += len(ret_val)
        if len(self.buflist) < self.proto.buffer_blocks:
            #log.msg('Buffer short: resume')
            self.producer.resumeProducing()
        #defer.returnValue(ret_val)
        #log.msg('read: %d. %d/%d' % (len(ret_val),
        #                             len(self.buflist),
        #                             self.proto.buffer_blocks))
        return ret_val

    def readinto(self, buf):
        data = self.read(len(buf))
        dlen = len(data)
        buf[:dlen] = data
        return dlen

    def close(self):
        if self.producer is not None:
            self.producer.stopProducing()
        self.buflist = deque()

    @property
    def curr_size(self):
        return sum(map(len, self.buflist))


class WscpClientProtocol(WebSocketClientProtocol):
    """
    WebSockets client that streams a file from the server
    """
    implements(interfaces.IPushProducer)

    open_deferred = None
    buffer_filled = None
    paused = False
    consumer = None
    resume_count = 0

    def __init__(self, buffer_blocks=BUFFER_BLOCKS):
        self.open_deferred = defer.Deferred()
        self.buffer_blocks = buffer_blocks

    def pauseProducing(self):
        #log.msg('Sending PAUSE')
        self.sendMessage('PAUSE')
        self.paused = True

    def resumeProducing(self):
        self.resume_count += 1
        #log.msg('Sending RESUME: %d' % self.resume_count)
        self.sendMessage('RESUME')
        self.paused = False

    def stopProducing(self):
        ##log.msg('Sending STOP')
        self.sendMessage('STOP')

    def getFile(self, path):
        #log.msg('getFile: %s' % path)
        self.sendMessage('%s|%s' % ('GET', path))
        self.buffer_filled = defer.Deferred()
        return self.buffer_filled

    def onOpen(self):
        self.open_deferred.callback(self)
        self.open_deferred = None

    def onMessage(self, message, binary):
        #log.msg('onMessage: %s' % message)
        pass

    def onMessageBegin(self, opcode):
        #log.msg('onMessageBegin')
        WebSocketClientProtocol.onMessageBegin(self, opcode)

    def onMessageFrameBegin(self, length, reserved):
        #log.msg('onMessageFrameBegin: %s' % length)
        WebSocketClientProtocol.onMessageFrameBegin(self, length, reserved)
        if self.buffer_filled is not None:
            #self.consumer = WebSocketStreamingDecoder(self, length)
            self.consumer = WebSocketDecoder(BytesIO())
            self.consumer._length = length
            self.consumer.registerProducer(self, True)

    def onMessageFrameData(self, data):
        ##log.msg('Received chunk: %d / %d / %d' % (len(data), self.consumer.write_pos, self.consumer.length))
        #log.msg('Received chunk: %d' % (len(data),))
        self.resume_count -= 1
        if self.consumer is not None:
            curr_pos = self.consumer.tell()
            self.consumer.write(data)
            #log.msg('Buffered: %d/%d' % (self.consumer.write_pos - curr_pos, BUFFER_SIZE))
            if self.buffer_filled is not None and \
               self.consumer.write_pos - curr_pos >= BUFFER_SIZE:
                # We wait for first block before returning the consumer
                self.buffer_filled.callback(self.consumer)
                self.buffer_filled = None

    def onMessageFrameEnd(self):
        if self.consumer is not None:
            #log.msg('Received file, length: %d' % self.consumer.write_pos)
            self.consumer = None

    def onMessageEnd(self):
        pass


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
        #log.msg('onSessionOpen')
        self.onClientAdd()

    def connectionLost(self, reason):
        if self.wscp is not None:
            self.wscp.failConnection()
        WampClientProtocol.connectionLost(self, reason)

    def onClientAdd(self):
        #log.msg('onClientAdd')
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

    @inlineCallbacks
    @exportRpc
    def enqueue(self, path):
        log.msg('enqueue: %s' % path)
        fObj = yield self.wcsp.getFile(path)
        self.player.enqueue(fObj)

    @exportRpc
    def playPause(self):
        #log.msg('playPause')
        self.player.toggle_play_pause()

    @exportRpc
    def stopPlaying(self):
        #log.msg('playPause')
        self.player.stop_playing()

    @exportRpc
    def pauseProducing(self):
        if self.wscp is not None:
            self.wscp.pauseProducing()

    @exportRpc
    def resumeProducing(self):
        if self.wscp is not None:
            self.wscp.resumeProducing()

    @exportRpc
    def stopProducing(self):
        if self.wscp is not None:
            self.wscp.stopProducing()


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
        factory = factory_class(self,
            #"ws://192.168.1.2:9876/reveille",
            "ws://127.0.0.1:9876/reveille",
            #debug=debug,
            #debugCodePaths=debug,
        )
        connectWS(factory)

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

    def do_toggle(self):
        self.reveille.playPause()

    def do_stop(self):
        self.reveille.stopPlaying()

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
    stdio.StandardIO(ReveilleCommandProtocol())
    reactor.run()
