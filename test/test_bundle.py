import os
import shutil
import unittest

import pymel.core as pc

from src._bundle import BundleMaker
from _testbase import TestBase, normpath, TestBundleHandler

currentdir = os.path.dirname(__file__)

class TestBundle(TestBase):
    handler = TestBundleHandler()
    bm = BundleMaker()

    @classmethod
    def setUpClass(self):
        super(TestBundle, self).setUpClass()
        self.name = self.bundledir
        self.bm.name = self.name
        self.bm.filename = os.path.join( self.tmpdir, 'mayaproj', 'scenes',
                'mayaproj.ma' )
        self.bm.path = self.tmpdir
        self.bm.deadline = False
        self.bm.archive = False
        self.bm.delete = False
        self.bm.keepReferences = True

        rootPath = os.path.join(self.bm.path, self.bm.name)
        if os.path.exists(rootPath):
            shutil.rmtree(rootPath)

        self.bm.open = False
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
            self.assertTrue( os.path.exists( os.path.join( self.tmpdir,
                self.name, image ) ) )

    def testCaches(self):
        caches = []
        caches.append( r"data\air_hornShape.xml" )
        caches.append( r"data\air_hornShape.mcx" )
        for cache in caches:
            self.assertTrue( os.path.exists( os.path.join( self.tmpdir,
                self.name, cache ) ) )

    def testRsProxies(self):
        proxies = [ r"proxies\0\air_horn_shaded_v001.rs" ]
        for proxy in proxies:
            self.assertTrue( os.path.exists( os.path.join( self.tmpdir,
                self.name, proxy ) ) )

    def testMayaFile(self):
        mayafile = os.path.join( self.tmpdir, self.name, r"scenes\bundle.ma" )
        self.assertTrue( os.path.exists(mayafile) )

    def testReferences(self):
        ref_file = os.path.join( self.tmpdir, self.name,
                r"scenes\refs\air_horn_shaded.ma" )
        self.assertTrue( os.path.exists(ref_file) )

if __name__ == "__main__":
    unittest.main()
