PALM - Protobufs Are Lightweight Messages
=========================================

This is a lightweight, fast library for using Google's protobufs in Python.

How fast?

    Palm, 10,000 decodes: 0.224280118942
    Palm, 10,000 encodes: 0.0757548809052

    ------------------------------------------------------------------------

    PB, 10,000 decodes: 5.67175507545
    PB, 10,000 encodes: 3.88449811935

(See the benchmark script in tests/bench/bench.py)

Status
------

Palm is stable enough for production use, having logged millions
of uptime-hours over the last few years.

Development
-----------

Fork on Github: https://github.com/bumptech/palm

Run tests with nose:

```
pip install protobuf pytest nose
nosetests test/test.py
```

Authors
-------

    Jamie Turner <jamie@bu.mp>  @jamwt
    Will Moss <wmoss@bu.mp> @wbmoss
    Christian Wyglendowski <christian@bu.mp> @dowskimania
    .. and, generally, the http://bu.mp server team
