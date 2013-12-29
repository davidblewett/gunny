========
Usage
========

The ``gunnyd`` daemon provides a central point to access your music collection::

    (gunny)
    dhmo% twistd -n --pidfile=gunnyd.pid gunnyd
    2013-12-08 23:08:23-0500 [-] Log opened.
    2013-12-08 23:08:23-0500 [-] twistd 13.2.0 (/Users/davidb/.virtualenvs/gunny/bin/python 2.7.5) starting up.
    2013-12-08 23:08:23-0500 [-] reactor class: twisted.internet.selectreactor.SelectReactor.
    2013-12-08 23:08:23-0500 [-] Site starting on 9876
    2013-12-08 23:08:23-0500 [-] Starting factory <twisted.web.server.Site instance at 0x10d9f5b00>

The ``flakd`` daemon catalogs your music collection and streams audio data to clients::

    (gunny)
    dhmo% twistd -n --pidfile=flakd.pid flakd
    2013-12-08 23:08:23-0500 [-] Log opened.
    2013-12-08 23:08:23-0500 [-] twistd 13.2.0 (/Users/davidb/.virtualenvs/gunny/bin/python 2.7.5) starting up.
    2013-12-08 23:08:23-0500 [-] reactor class: twisted.internet.selectreactor.SelectReactor.
    2013-12-08 23:08:23-0500 [-] Site starting on 9875
    2013-12-08 23:08:23-0500 [-] Starting factory <twisted.web.server.Site instance at 0x10d9f5b00>

The ``coxswaind`` daemon runs where you would like the music to play::

    (gunny)
    dhmo% twistd -n --pidfile=coxswaind.pid coxswaind
    2013-12-29 15:48:33-0500 [-] Log opened.
    2013-12-29 15:48:33-0500 [-] twistd 13.2.0 (/Users/davidb/.virtualenvs/gunny/bin/python 2.7.5) starting up.
    2013-12-29 15:48:33-0500 [-] reactor class: twisted.internet.selectreactor.SelectReactor.
    2013-12-29 15:48:33-0500 [-] ReveilleCommandFactory starting on '/tmp/rcp.sock'
    2013-12-29 15:48:33-0500 [-] Starting factory <gunny.reveille.client.ReveilleCommandFactory instance at 0x10441d998>

Submit commands to ``coxswaind`` via the ``coxswain`` script::

    (gunny)
    dhmo% coxswain shell
    Reveille command console. Type 'help' for help.
    enqueue 01.flac
    play
    pause
    quit
    Goodbye.
