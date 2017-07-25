import unittest
import os
import zipfile
import shutil
import logging
import sys

from src._base import BaseBundleHandler, bundleFormatter

import site
sys.path.insert(0, r'd:\talha.ahmed\workspace\pyenv_maya\tactic')
# site.addsitedir(os.path.abspath('..'))
site.addsitedir(r'R:\Python_Scripts\plugins\utilities')
site.addsitedir(r'R:\Python_Scripts\plugins')


currentdir = os.path.dirname(__file__)


def normpath(path):
    return os.path.normpath(
        os.path.abspath(os.path.expandvars(os.path.expanduser(path))))


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


def setUp(tmpdir, srcdir, bundledir, zipfileName):
    if not os.path.exists(tmpdir):
        mkdir(tmpdir)
    if os.path.exists(srcdir):
        shutil.rmtree(srcdir)
    if not os.path.exists(os.path.join(currentdir, zipfileName)):
        raise IOError('Cannot find zip file')
    unpack_dir = os.path.join(tmpdir, 'mayaproj')
    if not os.path.exists(unpack_dir):
        with zipfile.ZipFile(os.path.join(currentdir, zipfileName), 'r') as z:
            z.extractall(tmpdir)
    if unpack_dir != srcdir:
        shutil.copytree(unpack_dir, srcdir)
    rootPath = os.path.join(tmpdir, bundledir)
    if os.path.exists(rootPath):
        shutil.rmtree(rootPath)
    if not os.path.exists(srcdir):
        raise IOError("Cannot find the directory for testing")


def tearDown(srcdir):
    shutil.rmtree(srcdir)


class TestBase(unittest.TestCase):
    '''Base class for Inheritance'''
    tmpdir = r'd:\temp'
    srcdir = 'mayaproj'
    bundledir = 'bundle'
    zipfileName = 'mayaproj.zip'

    @classmethod
    def setUpClass(self):
        setUp(self.tmpdir,
              os.path.join(self.tmpdir, self.srcdir),
              os.path.join(self.tmpdir, self.bundledir), self.zipfileName)

    @classmethod
    def tearDownClass(self):
        tearDown(os.path.join(self.tmpdir, self.srcdir))


class TestBundleHandler(BaseBundleHandler):
    process = ''
    maxx = 0
    value = 0
    logger = 'TESTBUNDLE'

    def __init__(self):
        self.logger = logging.getLogger(self.logger)
        self.handler = logging.StreamHandler(sys.stdout)
        self.handler.setFormatter(bundleFormatter)
        self.handler.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        self.counts = {}

    def count(self, name):
        self.counts[name] = self.counts.get(name, 0) + 1

    def setProcess(self, process):
        self.process = process
        self.logger.info('Process : %s' % (self.process))
        self.count('setProcess')

    def setStatus(self, msg):
        self.status = msg
        self.logger.info('Status : %s : %s' % (self.process, msg))
        self.count('setStatus')

    def setMaximum(self, maxx):
        self.maxx = maxx
        self.count('setMaximum')

    def setValue(self, value):
        if self.maxx:
            self.logger.info('Progress : %s : %s of %s' %
                             (self.process, self.value, self.maxx))
        self.value = value
        self.count('setValue')

    def error(self, msg, exc_info=False):
        self.err = msg
        self.logger.error('%s : %s' % (self.process, msg))
        self.count('error')

    def warning(self, msg):
        self.warn = msg
        self.logger.warning('%s : %s' % (self.process, msg))
        self.count('warning')

    def done(self):
        self.logger.info('DONE')
        self.count('done')
