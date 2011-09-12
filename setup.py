from setuptools import setup, Extension, find_packages
from Cython.Distutils import build_ext

sourcefiles = ["palm/palm.pyx", "palm/palmcore.c"]

setup(
        name="palm",
        version="0.1b",
        cmdclass = {'build_ext' : build_ext},
        packages=["palm", "palm.palmc",],
        ext_modules = [Extension("palm.palm", sourcefiles, extra_compile_args=['-g'])],
        install_requires=["simpleparse >=2.1"],
        entry_points='''
        [console_scripts]
        palmc = palm.palmc.main:run
        '''
        )
