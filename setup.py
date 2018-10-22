import os
import re
from setuptools import setup


def get_version(pkg):
    """Scrap __version__  from __init__.py"""
    vfilename = os.path.join(os.getcwd(), pkg, '__init__.py')
    vfile = open(vfilename).read()
    m = re.search(r'__version__ = (\S+)\n', vfile)
    if m is None or len(m.groups()) != 1:
        raise Exception("Cannot determine __version__ from init file: '%s'!" % vfilename)
    version = m.group(1).strip('\'\"')
    return version

setup(
    name='pyADioc',
    version=get_version('pyADioc'),
    description='Simulated AreaDectector IOC',
    long_description='Simulated AreaDetector IOC using pcaspy for testing with the LCLS DAQ',
    author='Daniel Damiani',
    author_email='ddamiani@slac.stanford.edu',
    packages=['pyADioc'],
    install_requires=[
        'numpy',
        'pcaspy',
    ],
    entry_points={
        'console_scripts': [
            'pycamioc = pyADioc.ioc:main',
        ]
    },
    classifiers=[
        'Development Status :: 1 - Planning'
        'Environment :: Other Environment',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
    ],
)
