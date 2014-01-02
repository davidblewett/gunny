============
Installation
============

Dependencies
------------

This project relies on `libsndfile <http://www.mega-nerd.com/libsndfile>`_
(via `PyAudio <https://github.com/bastibe/PyAudio>`_) to decode music files,
`PortAudio <http://www.portaudio.com>`_ (via `PySoundCard <https://github.com/bastibe/PySoundCard>`_)
to play the decoded file and `PostgreSQL <http://www.postgresql.org>`_ to index the files.
These packages are available in most OS package repositories.

For example, to install on OS X using `MacPorts <http://www.macports.org>`_::

    $ sudo port install libsndfile portaudio postgresql93-server

To install on ``FreeBSD`` using ports::

    $ sudo portmaster audio/libsndfile audio/portaudio databases/postgresql93-server

To setup the database (``FreeBSD``-specific)::

    $ sudo service postgresql initdb
    $ sudo service postgresql start
    $ createuser -U pgsql gunny
    $ createuser -U pgsql -P gunny
    Enter password for new role:
    Enter it again:

Generate config file from template:

    $ cox config generate /path/to/location/reveille.ini

Update `/path/to/location/reveille.ini` and set the password in `sqlalchemy.url`.


Python Package
--------------

At the command line::

    $ easy_install gunny

Or, if you have `virtualenvwrapper <http://virtualenvwrapper.readthedocs.org/en/latest>`_ installed::

    $ mkvirtualenv gunny
    $ pip install gunny
