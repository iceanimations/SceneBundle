import unittest
import os
import zipfile
import shutil
import pymel.core as pc

currentdir = os.path.dirname(__file__)

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

    @classmethod
    def setUpClass(self):
        if not os.path.exists(self.tmpdir):
            mkdir(self.tmpdir)

        if os.path.exists(self.srcdir):
            shutil.rmtree(self.srcdir)

        if not os.path.exists(os.path.join(currentdir, 'mayaproj.zip')):
            raise IOError, 'Cannot find zip file'

        with zipfile.ZipFile(os.path.join(currentdir, 'mayaproj.zip'), 'r') as z:
            z.extractall(self.tmpdir)

        if not os.path.exists(self.srcdir):
            raise IOError, "Cannot find the directory for testing"

    @classmethod
    def tearDownClass(self):
        pc.newFile(f=1)
        self.bm.removeBundle()
        shutil.rmtree(self.srcdir)

