============
Installation
============

Dependencies
------------

This project relies on `libsndfile <http://www.mega-nerd.com/libsndfile>`_
(via `PyAudio <https://github.com/bastibe/PyAudio>`_) to decode music files,
and `PortAudio <http://www.portaudio.com>`_ (via `PySoundCard <https://github.com/bastibe/PySoundCard>`_)
to play the decoded file. Both of these packages are available in most OS package repositories.
For example, to install on OS X using `MacPorts <http://www.macports.org>`_::

    $ sudo port install libsndfile portaudio

To install on ``FreeBSD`` using ports::

    $ sudo portmaster audio/libsndfile audio/portaudio

Python Package
--------------

At the command line::

    $ easy_install gunny

Or, if you have `virtualenvwrapper <http://virtualenvwrapper.readthedocs.org/en/latest>`_ installed::

    $ mkvirtualenv gunny
    $ pip install gunny
