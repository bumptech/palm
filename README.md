PALM - Protobufs Are Lightweight Messages
=========================================

This is a lightweight, fast library for using Google's protobufs in Python.

How fast?

Google pure-python version:

    In [23]: %timeit t.ParseFromString(e)
    10000 loops, best of 3: 54.8 us per loop

    In [24]: %timeit t.SerializeToString()
    10000 loops, best of 3: 65.3 us per loop

Palm:

    In [25]: t = Test(e)

    In [26]: %timeit Test(e)
    100000 loops, best of 3: 3.54 us per loop

    In [27]: %timeit t.dumps()
    1000000 loops, best of 3: 1.64 us per loop

Status
------

It is currently beta quality.  It is used in production, but its
production use is young.

Pull requests welcome!

Authors
-------

    Jamie Turner <jamie@bu.mp>  @jamwt
    Will Moss <wmoss@bu.mp> @wbmoss
    Christian Wyglendowski <christian@bu.mp> @dowskimania
