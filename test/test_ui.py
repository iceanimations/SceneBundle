import os
import unittest
import sys
import time
import shutil

sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_common")
sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_common\utilities")
sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_maya")
sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_maya\tactic")
sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_maya\tactic\app")
sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_maya\maya2015\PyQt")

from uiContainer import uic
reload(uic)
from PyQt4.QtGui import QApplication, qApp
from PyQt4.QtTest import QTest
from PyQt4.QtCore import Qt, QTimer, QObject, pyqtSlot

from _testbase import _TestBase, normpath, _TestBundleHandler

import maya.cmds as mc

app = QApplication(sys.argv)

import src._ui as ui
BundleMakerUI = ui.BundleMakerUI

currentdir = os.path.dirname(__file__)
class TestBundleMakerUI(_TestBase, QObject):
    tmpdir = r'd:\temp'
    name = 'bundle'
    srcdir = os.path.join(tmpdir, 'mayaproj')
    bundledir = os.path.join(tmpdir, name)
    zipfileName = 'mayaproj2.zip'

    def __init__(self, *args):
        QObject.__init__(self)
        _TestBase.__init__(self, *args)

    @classmethod
    def setUpClass(self):
        self.rootPath = os.path.join(self.tmpdir, self.name)
        if os.path.exists(self.rootPath):
            shutil.rmtree(self.rootPath)

        super(TestBundleMakerUI, self).setUpClass()
        self.handler = _TestBundleHandler()

        self.gui = BundleMakerUI()
        self.gui.show()
        qApp.processEvents()
        time.sleep(0.5)

        self.gui.bundleMaker.progressHandler=self.handler
        self.gui.bundleMaker.filename = os.path.join(self.tmpdir, 'mayaproj',
                'scenes', 'mayaproj.ma')
        self.gui.bundleMaker.openFile()

        QTest.mouseClick(self.gui.currentSceneButton, Qt.LeftButton)
        QTest.mouseDClick(self.gui.pathBox, Qt.LeftButton)
        QTest.mouseClick(self.gui.pathBox, Qt.LeftButton)
        QTest.keyClicks(self.gui.pathBox, self.tmpdir)
        QTest.mouseClick(self.gui.keepBundleButton, Qt.LeftButton)
        QTest.mouseClick(self.gui.deadlineCheck, Qt.LeftButton)
        QTest.mouseDClick(self.gui.nameBox, Qt.LeftButton)
        QTest.keyClicks(self.gui.nameBox, self.name)
        qApp.processEvents()
        time.sleep(0.5)
        QTest.mouseClick(self.gui.keepReferencesButton, Qt.LeftButton)
        qApp.processEvents()
        time.sleep(1)

        # self.timer = QTimer()
        # # self.timer.timeout.connect(self.acceptDialog)
        # self.timer.setSingleShot(True)
        # self.timer.start(3000)
        QTest.mouseClick(self.gui.bundleButton, Qt.LeftButton)
        time.sleep(1)

    @classmethod
    def tearDownClass(self):
        mc.file(new=1, f=1)
        super(TestBundleMakerUI, self).tearDownClass()

    def testRootPath(self):
        rootPath = self.rootPath
        constructed = normpath(os.path.join( self.tmpdir, self.name ))
        self.assertEqual(rootPath, constructed)

    def testTextures(self):
        images = []
        images.append ( r"sourceimages\1\Form_1001.png" )
        images.append ( r"sourceimages\1\Form_1002.png" )
        images = [os.path.join(self.tmpdir, self.name, image) for image in
                images]
        self.assertTrue( ( any(os.path.exists(image)) for image in images ) )

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
