import unittest
import logging
import sys
import os
import shutil

import pymel.core as pc

import site
site.addsitedir(os.path.abspath('..'))
site.addsitedir(r'R:\Python_Scripts\plugins\utilities')
from src._bundle import BundleMaker, BaseBundleHandler

import zipfile

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

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
class BundleHandler(BaseBundleHandler):
    process = ''
    maxx = 0
    value = 0

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

class TestBundle(unittest.TestCase):
    handler = BundleHandler()
    bm = BundleMaker(handler)
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

        self.bm.name = self.name
        self.bm.filename = r'd:\temp\mayaproj\scenes\mayaproj.ma'
        self.bm.path = self.tmpdir
        self.bm.deadline = False
        self.bm.archive = False
        self.bm.delete = False

        rootPath = os.path.join(self.bm.path, self.bm.name)
        if os.path.exists(rootPath):
            shutil.rmtree(rootPath)

        self.bm.openFile()
        self.bm.createBundle()

    @classmethod
    def tearDownClass(self):
        pc.newFile(f=1)
        self.bm.removeBundle()
        shutil.rmtree(self.srcdir)

    def testRootPath(self):
        rootPath = self.bm.rootPath
        constructed = normpath(os.path.join( self.bm.path, self.bm.name ))
        self.assertEqual(rootPath, constructed)

    def testTextures(self):
        images = []
        images.append ( r"D:\temp\bundle\sourceimages\1\Form_1001.png" )
        images.append ( r"D:\temp\bundle\sourceimages\1\Form_1002.png" )
        images.append ( r"D:\temp\bundle\sourceimages\0\image.1001.jpg" )
        for image in images:
            self.assertTrue(os.path.exists(image))

    def testCaches(self):
        caches = []
        caches.append(r"D:\temp\bundle\data\air_hornShape.xml")
        caches.append(r"D:\temp\bundle\data\air_hornShape.mcx")
        for cache in caches:
            self.assertTrue(os.path.exists(cache))

    def testRsProxies(self):
        proxies = [r"D:\temp\bundle\proxies\bundle\data\air_horn_shaded_v001.rs"]
        for proxy in proxies:
            self.assertTrue(os.path.exists(proxy))

    def testMayaFile(self):
        mayafile = r"D:\temp\mayaproj\scenes\mayaproj.ma" 
        self.assertTrue(os.path.exists(mayafile))

    def testReferences(self):
        ref_file = r"D:\temp\mayaproj\scenes\refs\air_horn_shaded.ma"
        self.assertTrue(os.path.exists(ref_file))


if __name__ == "__main__":
    unittest.main()
