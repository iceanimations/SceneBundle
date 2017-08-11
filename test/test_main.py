import os
import site
import unittest

from src._main import bundleMain
from ._testbase import TestBase, normpath

import pymel.core as pc

from src._bundle import BundleMaker

site.addsitedir(os.path.abspath('.'))
site.addsitedir(os.path.dirname(__file__))
site.addsitedir(r'R:\Python_Scripts\plugins\utilities')

currentdir = os.path.dirname(__file__)


class TestMain(TestBase):
    bm = BundleMaker()
    zipfileName = 'mayaproj2.zip'

    @classmethod
    def setUpClass(self):
        super(TestMain, self).setUpClass()
        self.name = self.bundledir
        args = [
            os.path.join(self.tmpdir, 'mayaproj', 'scenes', 'mayaproj.ma'),
            '-n', self.name, '-tp', self.tmpdir, '-r'
        ]
        self.bm.open = True
        self.bm.name = self.name
        self.bm.path = self.tmpdir
        self.bm.rootPath = normpath(os.path.join(self.bm.path, self.bm.name))

        bundleMain(bm=self.bm, args=args)

    @classmethod
    def tearDownClass(self):
        pc.newFile(f=1)
        super(TestMain, self).tearDownClass()
        self.bm.removeBundle()

    def testRootPath(self):
        rootPath = self.bm.rootPath
        constructed = normpath(os.path.join(self.bm.path, self.bm.name))
        self.assertEqual(rootPath, constructed)
        self.assertTrue(os.path.exists(rootPath))

    def testTextures(self):
        images = []
        images.append(r"sourceimages\0\Form_1001.png")
        images.append(r"sourceimages\0\Form_1002.png")
        # images.append ( r"sourceimages\0\image.1001.jpg" )
        for image in images:
            self.assertTrue(
                os.path.exists(os.path.join(self.tmpdir, self.name, image)))

    def testCaches(self):
        caches = []
        caches.append(r"data\air_hornShape.xml")
        caches.append(r"data\air_hornShape.mcx")
        for cache in caches:
            self.assertTrue(
                os.path.exists(os.path.join(self.tmpdir, self.name, cache)))

    def testRsProxies(self):
        proxies = [r"proxies\0\air_horn_shaded_v001.rs"]
        for proxy in proxies:
            self.assertTrue(
                os.path.exists(os.path.join(self.tmpdir, self.name, proxy)))

    def testMayaFile(self):
        mayafile = os.path.join(self.tmpdir, self.name, r"scenes",
                                self.name + '.ma')
        self.assertTrue(os.path.exists(mayafile))

    def testReferences(self):
        ref_file = os.path.join(self.tmpdir, self.name,
                                r"scenes\refs\air_horn_shaded.ma")
        self.assertTrue(os.path.exists(ref_file))


if __name__ == "__main__":
    unittest.main()
