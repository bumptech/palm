from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

sourcefiles = ["palm/palm.pyx", "palm/palmcore.c"]

setup(
        cmdclass = {'build_ext' : build_ext},
        ext_modules = [Extension("palm", sourcefiles, extra_compile_args=['-g'])]
        )
