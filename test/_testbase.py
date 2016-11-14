import unittest
import os
import zipfile
import shutil
import logging
import sys

from src._bundle import BaseBundleHandler, _ProgressLogHandler

currentdir = os.path.dirname(__file__)

def normpath(path):
    return os.path.normpath( os.path.abspath( os.path.expandvars(
        os.path.expanduser( path ) ) ) )

def mkdir(path):
    '''make a directory recursively from parent to child'''
    if os.path.exists(path):
        return False
    else:
        parent = os.path.dirname(path)
        if not os.path.exists(parent):
            mkdir(parent)
        os.mkdir(path)
        return True

class _TestBase(unittest.TestCase):
    '''Base class for Inheritance'''
    tmpdir = r'd:\temp'
    name = 'bundle'
    srcdir = os.path.join(tmpdir, 'mayaproj')
    bundledir = os.path.join(tmpdir, name)
    zipfileName = 'mayaproj.zip'

    @classmethod
    def setUpClass(self):
        if not os.path.exists(self.tmpdir):
            mkdir(self.tmpdir)

        if os.path.exists(self.srcdir):
            shutil.rmtree(self.srcdir)

        if not os.path.exists(os.path.join(currentdir, self.zipfileName)):
            raise IOError, 'Cannot find zip file'

        with zipfile.ZipFile(os.path.join(currentdir, self.zipfileName), 'r') as z:
            z.extractall(self.tmpdir)

        if not os.path.exists(self.srcdir):
            raise IOError, "Cannot find the directory for testing"

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.srcdir)

class _TestBundleHandler(BaseBundleHandler):
    process = ''
    maxx = 0
    value = 0
    logger = 'TESTBUNDLE'

    def __init__(self):
        self.logger = logging.getLogger(self.logger)
        self.handler = logging.StreamHandler(sys.stdout)
        self.handler.setFormatter(_ProgressLogHandler.formatter)
        self.logger.addHandler(self.handler)

    @property
    def processName(self):
        return self.process + ': ' if self.process else ''

    def setProcess(self, process):
        self.process = process

    def setStatus(self, msg):
        logging.info(self.processName + msg)

    def setMaximum(self, maxx):
        self.maxx = maxx

    def setValue(self, value):
        if self.maxx:
            logging.info( self.processName +
                    '%d of %d Done' % (self.value, self.maxx) )
        self.value = value

    def error(self, msg, exc_info=False):
        logging.error(self.processName + msg, exc_info=exc_info)

    def warning(self, msg):
        logging.warning(self.processName + msg)

    def done(self):
        pass

