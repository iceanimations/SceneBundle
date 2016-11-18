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

class TestBase(unittest.TestCase):
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

class TestBundleHandler(BaseBundleHandler):
    process = ''
    maxx = 0
    value = 0
    logger = 'TESTBUNDLE'

    def __init__(self):
        self.logger = logging.getLogger(self.logger)
        self.handler = logging.StreamHandler(sys.stdout)
        self.handler.setFormatter(_ProgressLogHandler.formatter)
        self.logger.addHandler(self.handler)
        self.counts = {}

    def count(self, name):
        self.counts[name] = self.counts.get(name, 0) + 1

    def setProcess(self, process):
        self.process = process
        self.logger.info('Process : %s' %(self.process))
        self.count('setProcess')

    def setStatus(self, msg):
        self.status = msg
        self.logger.info('Status : %s : %s' %(self.process, msg))
        self.count('setStatus')

    def setMaximum(self, maxx):
        self.maxx = maxx
        self.count('setMaximum')

    def setValue(self, value):
        if self.maxx:
            self.logger.info('Progress : %s : %s of %s' % (self.process,
                self.value, self.maxx))
        self.value = value
        self.count('setValue')

    def error(self, msg, exc_info=False):
        self.err = msg
        self.logger.error('%s : %s' %(self.process, msg))
        self.count('error')

    def warning(self, msg):
        self.warn = msg
        self.logger.warning('%s : %s' %(self.process, msg))
        self.count('warning')

    def done(self):
        self.logger.info('DONE')
        self.count('done')

