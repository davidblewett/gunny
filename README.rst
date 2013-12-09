===============================
gunny
===============================

.. image:: https://badge.fury.io/py/gunny.png
    :target: http://badge.fury.io/py/gunny
    
.. image:: https://travis-ci.org/davidblewett/gunny.png?branch=master
        :target: https://travis-ci.org/davidblewett/gunny

.. image:: https://pypip.in/d/gunny/badge.png
        :target: https://crate.io/packages/gunny?version=latest


Gunny is the control package for the Reveille music protocol.
The gunnyd daemon streams audio data to clients.
It provides a central point to access your music collection::

    dhmo% twistd -n --pidfile=gunnyd.pid gunnyd
    2013-12-08 23:08:23-0500 [-] Log opened.
    2013-12-08 23:08:23-0500 [-] twistd 13.2.0 (/Users/davidb/.virtualenvs/gunny/bin/python 2.7.5) starting up.
    2013-12-08 23:08:23-0500 [-] reactor class: twisted.internet.selectreactor.SelectReactor.
    2013-12-08 23:08:23-0500 [-] Site starting on 9876
    2013-12-08 23:08:23-0500 [-] Starting factory <twisted.web.server.Site instance at 0x10d9f5b00>

The coxswaind daemon runs where you would like the music to play::

    (gunny)
    Sun Dec  8, 23:08 | /Users/davidb/src/gunny
    dhmo% python gunny/reveille/client.py
    Reveille command console. Type 'help' for help.
    enqueue 01.flac
    toggle
    toggle
    quit
    Goodbye.

* Free software: BSD license
* Documentation: http://gunny.rtfd.org.

Features
--------

* Uses Twisted for the server, client and player components
* Uses the PySoundFile Python binding for libsndfile to decode audio files
* Uses the PySoundCard Python binding for PortAudio to play audio files
