from collections import deque

from twisted.internet import defer
from twisted.internet.task import cooperate
from twisted.python import log

from pysoundcard import Stream, continue_flag, complete_flag
from pysoundfile import SoundFile


(PLAYER_STOPPED, PLAYER_PAUSED, PLAYER_PLAYING) = range(3)


class Player(object):
    BUFFER_SIZE = 0.25  # in seconds

    def __init__(self):
        """
        """

        self.track = None  # the currently playing SoundFile
        self.buffer_size = 0  # the number of PCM frames to process
        self.state = PLAYER_STOPPED
        self.progress = [0, 1]  # an Array of current/total frames
        self.task = None
        #self.stream = Stream(callback=self.stream_callback)
        self.stream = Stream()
        self.queue = defer.DeferredQueue()
        self.played = deque()

    def enqueue(self, track):
        #self.queue.put(track)
        self.track = track

    def close(self):
        self.stop_playing()

    def pause(self):
        if (self.state == PLAYER_PLAYING):
            self.task.pause()
            self.stream.stop()
            self.state = PLAYER_PAUSED

    def play(self):
        log.msg('Play: %r, %d' % (self.track, len(self.queue)))
        if self.track is None and self.queue:
            self.fObj = self.queue.popleft()
            self.track = SoundFile(self.fObj, virtual_io=True)
        if (self.track is not None):
            if (self.state == PLAYER_STOPPED):
                self.start_playing()
            elif (self.state == PLAYER_PAUSED):
                self.stream.start()
                self.task.resume()
                self.state = PLAYER_PLAYING
            elif (self.state == PLAYER_PLAYING):
                pass

    def toggle_play_pause(self):
        if (self.state == PLAYER_PLAYING):
            self.pause()
        elif ((self.state == PLAYER_PAUSED) or
              (self.state == PLAYER_STOPPED)):
            self.play()

    def start_playing(self):
        self.buffer_size = min(int(round(self.BUFFER_SIZE *
                                         self.track.sample_rate)),
                               2048)
        log.msg('buf size: %s' % self.buffer_size)
        #reopen stream if necessary based on file's parameters
        if self.stream.sample_rate != self.track.sample_rate or \
           self.stream.block_length != self.buffer_size:
            self.stream = Stream(sample_rate=self.track.sample_rate,
                                 block_length=self.buffer_size)
                                 #callback=self.stream_callback)
        self.state = PLAYER_PLAYING
        self.stream.start()
        #self.set_progress(0, self.track.frames)
        self.task = cooperate(self)

    def stop_playing(self):
        if self.task is not None:
            self.task.stop()
            self.task = None
        if self.state > PLAYER_STOPPED:
            self.state = PLAYER_STOPPED
            if self.stream.is_active():
                self.stream.stop()
        self.set_progress(0, 1)
        if self.track is not None:
            self.track = None
            self.fObj.close()
            self.played.append(self.fObj)
            self.fObj = None

    def stream_callback(self, in_data, frame_count, time_info, status):
        # This method doesn't seem to play nice with Twisted.
        # It seems to behave as a large blocking thread;
        # i.e., not releasing back to Twisted after each iteration
        out_data = self.track.read(frame_count)
        self.progress[0] += len(out_data)
        if self.progress[0] < self.track.frames:
            if len(out_data) >= frame_count:
                return (out_data, continue_flag)
            else:
                return (out_data, complete_flag)
        else:
            return (out_data, complete_flag)

    def output_chunk(self):
        frame = self.track.read(self.buffer_size)
        frame_len = len(frame)
        if (frame_len > 0):
            self.progress[0] += frame_len
            self.stream.write(frame)
            return frame_len
        else:
            self.stop_playing()

    def set_progress(self, current, total):
        self.progress[0] = current
        self.progress[1] = total

    def __iter__(self):
        #log.msg('__iter__')
        return self

    def next(self):
        #log.msg('next state: %s' % self.state)
        if self.state == PLAYER_PLAYING:
            return self.output_chunk()
        else:
            raise StopIteration
