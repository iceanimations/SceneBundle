import logging
import sys
import os
import shutil
import unittest

import pymel.core as pc

import site
site.addsitedir(os.path.abspath('..'))
site.addsitedir(r'R:\Python_Scripts\plugins\utilities')
from src._bundle import BundleMaker, BaseBundleHandler

from _testbase import _TestBase

currentdir = os.path.dirname(__file__)

def normpath(path):
    return os.path.normpath( os.path.abspath( os.path.expandvars(
        os.path.expanduser( path ) ) ) )

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

class TestBundle(_TestBase):
    handler = BundleHandler()
    bm = BundleMaker(handler)

    @classmethod
    def setUpClass(self):
        super(TestBundle, self).setUpClass()
        self.bm.name = self.name
        self.bm.filename = os.path.join(self.tmpdir,
                'mayaproj', 'scenes', 'mayaproj.ma')
        self.bm.path = self.tmpdir
        self.bm.deadline = False
        self.bm.archive = False
        self.bm.delete = False
        self.bm.keepReferences = True

        rootPath = os.path.join(self.bm.path, self.bm.name)
        if os.path.exists(rootPath):
            shutil.rmtree(rootPath)

        self.bm.openFile()
        self.bm.createBundle()

    @classmethod
    def tearDownClass(self):
        pc.newFile(f=1)
        super(TestBundle, self).tearDownClass()
        self.bm.removeBundle()

    def testRootPath(self):
        rootPath = self.bm.rootPath
        constructed = normpath(os.path.join( self.bm.path, self.bm.name ))
        self.assertEqual(rootPath, constructed)

    def testTextures(self):
        images = []
        images.append ( r"sourceimages\1\Form_1001.png" )
        images.append ( r"sourceimages\1\Form_1002.png" )
        images.append ( r"sourceimages\0\image.1001.jpg" )
        for image in images:
            self.assertTrue( os.path.exists(os.path.join(self.tmpdir,
                self.name, image)))

    def testCaches(self):
        caches = []
        caches.append(r"data\air_hornShape.xml")
        caches.append(r"data\air_hornShape.mcx")
        for cache in caches:
            self.assertTrue(os.path.exists(os.path.join(self.tmpdir, self.name,
                cache)))

    def testRsProxies(self):
        proxies = [r"proxies\bundle\data\air_horn_shaded_v001.rs"]
        for proxy in proxies:
            self.assertTrue(os.path.exists(os.path.join(self.tmpdir, self.name,
                proxy)))

    def testMayaFile(self):
        mayafile = os.path.join( self.tmpdir, self.name, r"scenes\bundle.ma" )
        self.assertTrue(os.path.exists(mayafile))

    def testReferences(self):
        ref_file = os.path.join(self.tmpdir, self.name,
                r"scenes\refs\air_horn_shaded.ma")
        self.assertTrue(os.path.exists(ref_file))

if __name__ == "__main__":
    unittest.main()
