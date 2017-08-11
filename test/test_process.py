import shutil
import os
import unittest

from src._process import BundleMakerProcess, OnError
from _testbase import TestBase, TestBundleHandler

currentdir = os.path.dirname(__file__)

class TestBundleProcess(TestBase):
    bp = BundleMakerProcess()
    zipfileName = 'mayaproj2.zip'

    @classmethod
    def setUpClass(self):
        super(TestBundleProcess, self).setUpClass()
        self.handler = TestBundleHandler()
        self.bp.setProgressHandler(self.handler)
        self.bp.name = self.bundledir
        self.name = self.bundledir
        self.bp.filename = os.path.join( self.tmpdir, 'mayaproj', 'scenes',
                'mayaproj.ma' )
        self.bp.path = self.tmpdir
        self.bp.deadline = False
        self.bp.archive = False
        self.bp.delete = False
        self.bp.keepReferences = True
        self.bp.onError = OnError.LOG

        self.rootPath = os.path.join(self.tmpdir, self.name)
        if os.path.exists(self.rootPath):
            shutil.rmtree(self.rootPath)

        self.bp.createBundle()

    @classmethod
    def tearDownClass(self):
        self.bp.killProcess()
        super(TestBundleProcess, self).tearDownClass()
        shutil.rmtree( os.path.join( self.bp.path, self.bp.name ) )

    def testRootPath(self):
        self.assertTrue(os.path.exists(self.rootPath))

    def testTextures(self):
        images = []
        images.append ( r"sourceimages\0\Form_1001.png" )
        images.append ( r"sourceimages\0\Form_1002.png" )
        # images.append ( r"sourceimages\0\image.1001.jpg" )
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

    def testParsing(self):
        self.assertEqual(self.bp.status.counts,
                {'setMaximum': 14, 'setValue': 14, 'setProcess': 14,
                    'setStatus': 18, 'done': 1, 'error': 1} )

if __name__ == "__main__":
    unittest.main()
