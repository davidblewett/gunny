=============
Design
=============

The design of the Reveille music protocol encompasses 3 pieces of functionality:

1. Music file cataloging and serving (``flakd``)
    * On any device where you have music stored (desktop, NAS, etc)
2. Central catalog and dispatch of music requests (``gunnyd``)
3. Music search and playback (``coxswaind``)
    * One on any device you want to play music from (laptop, netbook, etc)

There can be multiple instances of daemons #1 and #3 that are dispatched by
a single instance of #2::

     ┌───────┐             ┌───────────┐
     | flakd ├─────────────┤ coxswaind │
     └───────┘             └───────────┘
        | ╲              ╱       |
        |   ╲          ╱         |
        |    ┌────────┐      ┌───────┐
        |    | gunnyd ├──────┤ flakd |
        |    └────────┘      └───────┘
        |              ╲         |
        |                ╲       |
        |                  ┌───────────┐
        └──────────────────┤ coxswaind |
                           └───────────┘

flakd
-----

The ``flakd`` daemon scans a given set of directories for music
files and submits the metadata to the ``gunnyd`` daemon for indexing.
It waits for requests for the contents of specific music files
from the ``coxswaind`` daemon.


gunnyd
------

The ``gunnyd`` daemon is the central hub responsible for cataloging
music files from the ``flakd`` daemon, dispatching music search
requests and pub/sub events from the ``coxswaind`` daemon
(such as playback begin/pause/end).

coxswaind
---------

The ``coxswaind`` daemon is the one most users will interact with
the most. It is responsible for submitting search requests to the
``gunnyd`` daemon, submitting requests for file data to the ``flakd``
daemon and actually playing back music files to the local soundcard.
It runs in the background, and the user submits commands to it via
the ``coxswain`` CLI script.
