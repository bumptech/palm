from setuptools import setup, Extension

sourcefiles = ["palm/palm.c", "palm/palmcore.c"]

setup(
        name="palm",
        version="0.1.6post2",
        packages=["palm", "palm.palmc", ],
        ext_modules=[Extension("palm.palm", sources=sourcefiles)],
        install_requires=["simpleparse >=2.1",
                          "protobuf>=2.4.1,<=2.4.999"],
        zip_safe=False, # This fixes some crazy circular import junk.
        entry_points='''
        [console_scripts]
        palmc = palm.palmc.main:run
        ''',
        url="https://github.com/bumptech/palm",
        description="Fast Protocol Buffer library for Python",
        long_description='''
palm - Protobufs Are Lightweight Messages
=========================================

palm is a library for using Google's protocol buffers in Python.  It has
a fast core written in C with a thin Cython binding to Python.  The goal of
palm was to make improvements to the Google reference implementation, namely:

 * Make the library significantly faster
 * Clean up the API

While the palm developers feel that the second goal has been achieved, the
first goal undoubtely has: palm is 40-60x faster than the pure-python
protobuf-2.3 library.

Palm was developed for use at bu.mp .
'''
        )
