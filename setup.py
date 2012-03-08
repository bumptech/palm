from setuptools import setup, Extension

sourcefiles = ["palm/palm.c", "palm/palmcore.c"]

setup(
        name="palm",
        version="0.1.1",
        packages=["palm", "palm.palmc", ],
        ext_modules=[Extension("palm.palm", sources=sourcefiles)],
        install_requires=["simpleparse >=2.1"],
        zip_safe=False, # This fixes some crazy circular import junk.
        entry_points='''
        [console_scripts]
        palmc = palm.palmc.main:run
        '''
        )
