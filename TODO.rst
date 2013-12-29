====
ToDo
====

Initial Public Release
----------------------

* Refactor SoundFile use to be able to close/re-open
  * Close frees streamed data
  * Open restarts initial stream
* Refactor WscpServerProtocol / WscpClientProtocol
  to be able to handle multiple file transfers
  * See twisted.conch.ssh.filetransfer
  * Refactor message framing so that one chunk of a
    file is a message with 2 frames: path, offset, data
* Player track queue
* Prev/next skip
* coxswain CLI
* Pull in flak indexing logic
* Files served by flakd
* Refactor API to use database-backed calls
  * Use file_id vs. path
* Seek inside a track
  * If seeking past stream end point, pause playback
    until caught up
