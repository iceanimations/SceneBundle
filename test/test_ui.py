import os
import unittest
import sys
import time
import shutil

# sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_common")
sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_common\utilities")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
# sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_maya")
# sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_maya\tactic")
# sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_maya\tactic\app")
# sys.path.insert(0, r"D:\talha.ahmed\workspace\pyenv_maya\maya2015\PyQt")

from uiContainer import setPyQt4
setPyQt4()

from PyQt4.QtGui import QApplication, qApp
from PyQt4.QtTest import QTest
from PyQt4.QtCore import Qt, QObject, QTimer

from _testbase import TestBase, TestBundleHandler, setUp, tearDown

import maya.cmds as mc
import src._ui as ui

app = QApplication(sys.argv)
BundleMakerUI = ui.BundleMakerUI
currentdir = os.path.dirname(__file__)


class DiagHelper(QObject):
    key = None
    func = None
    time = None
    keyword = None

    def __init__(self, key=None, func=None, time=1000, keyword=None):
        super(DiagHelper, self).__init__()
        self.key = key
        self.func = func
        self.time = time
        self.keyword = keyword

    def recognize(self, obj):
        if self.keyword is None:
            return True
        text = ''
        try:
            text = obj.text()
        except AttributeError:
            pass
        if self.keyword.lower() in text.lower():
            return True
        return False

    def dismissDialog(self, *args):
        activeWidget = qApp.activeModalWidget()
        if self.recognize(activeWidget):
            QTest.keyClick(qApp.activeModalWidget(), self.key)
            self.timer.stop()

    def activate(self, time=None, func=None):
        if func is None:
            if self.func is None:
                func = self.dismissDialog
            else:
                func = self.func
        if time is not None:
            self.time = time
        self.timer = QTimer(self)
        self.timer.timeout.connect(func)
        self.timer.start(self.time)


class TestBundleMakerUI_CurrentScene(TestBase):
    tmpdir = r'd:\temp'
    name = 'bundle'
    srcdir = 'mayaproj'
    bundledir = name
    zipfileName = 'mayaproj2.zip'

    def __init__(self, *args):
        TestBase.__init__(self, *args)

    @classmethod
    def setUpClass(self):
        super(TestBundleMakerUI_CurrentScene, self).setUpClass()
        self.handler = TestBundleHandler()
        self.rootPath = os.path.join(self.tmpdir, self.bundledir)

        self.gui = BundleMakerUI()
        self.gui.show()
        qApp.processEvents()
        time.sleep(0.5)

        self.gui.bundler.progressHandler = self.handler
        self.gui.bundler.filename = os.path.join(self.tmpdir, self.srcdir,
                                                 'scenes', 'mayaproj.ma')
        self.gui.bundler.open = False
        self.gui.bundler.openFile()

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

        dh1 = DiagHelper(
            key=Qt.Key_Enter, time=1000, keyword='CollectTextures')
        dh1.activate()

        dh2 = DiagHelper(
            key=Qt.Key_Escape, time=2000, keyword='latestErrorLog')
        dh2.activate()

        QTest.mouseClick(self.gui.bundleButton, Qt.LeftButton)
        time.sleep(1)

    @classmethod
    def tearDownClass(self):
        mc.file(new=1, f=1)
        super(TestBundleMakerUI_CurrentScene, self).tearDownClass()
        shutil.rmtree(self.rootPath)

    def testRootPath(self):
        self.assertTrue(os.path.exists(self.rootPath))

    def testTextures(self):
        images = []
        images.append(r"sourceimages\1\Form_1001.png")
        images.append(r"sourceimages\1\Form_1002.png")
        images = [
            os.path.join(self.tmpdir, self.bundledir, image)
            for image in images
        ]
        self.assertTrue((any(os.path.exists(image)) for image in images))

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
        mayafile = os.path.join(self.tmpdir, self.name, r"scenes\bundle.ma")
        self.assertTrue(os.path.exists(mayafile))

    def testReferences(self):
        ref_file = os.path.join(self.tmpdir, self.name,
                                r"scenes\refs\air_horn_shaded.ma")
        self.assertTrue(os.path.exists(ref_file))


class TestBundleMakerUI_List(TestBase):
    srcdir = ('mayaproj1', 'mayaproj2', 'mayaproj3')
    name = ('bundle1', 'bundle2', 'bundle3')
    bundledir = name
    zipfileName = ('mayaproj2.zip', 'mayaproj2.zip', 'mayaproj2.zip')

    @classmethod
    def setUpClass(self):
        self.rootPaths = []
        paths = []
        for srcdir, bundledir, zipfileName in zip(self.srcdir, self.bundledir,
                                                  self.zipfileName):
            setUp(self.tmpdir,
                  os.path.join(self.tmpdir, srcdir),
                  os.path.join(self.tmpdir, bundledir), zipfileName)
            self.rootPaths.append(os.path.join(self.tmpdir, bundledir))
            filename = os.path.join(self.tmpdir, srcdir, 'scenes',
                                    'mayaproj.ma')
            paths.append(' | '.join([bundledir, filename, '', '', '', '']))
        self.rootPaths = tuple(self.rootPaths)

        self.handler = TestBundleHandler()
        self.gui = BundleMakerUI()
        self.gui.setPaths(paths)
        self.gui.show()

        def stop_decorator(func):
            def stop():
                func()
                self.gui.deleteLater()
                qApp.exit()

            return stop

        self.gui.stopPolling = stop_decorator(self.gui.stopPolling)

        QTest.mouseClick(self.gui.keepBundleButton, Qt.LeftButton)
        QTest.mouseClick(self.gui.deadlineCheck, Qt.LeftButton)
        QTest.mouseClick(self.gui.keepReferencesButton, Qt.LeftButton)
        QTest.mouseClick(self.gui.bgButton, Qt.LeftButton)

        dh2 = DiagHelper(key=Qt.Key_Enter, time=2000, keyword='latestErrorLog')
        dh2.activate()

        qApp.processEvents()
        QTest.mouseClick(self.gui.bundleButton, Qt.LeftButton)
        time.sleep(1)
        qApp.exec_()

    def testRootPaths(self):
        for rootPath in self.rootPaths:
            self.assertTrue(os.path.exists(rootPath))

    def testTextures(self):
        for bundledir in self.bundledir:
            images = []
            images.append(r"sourceimages\1\Form_1001.png")
            images.append(r"sourceimages\1\Form_1002.png")
            images = [
                os.path.join(self.tmpdir, bundledir, image) for image in images
            ]
            self.assertTrue((any(os.path.exists(image)) for image in images))

    def testCaches(self):
        for bundledir in self.bundledir:
            caches = []
            caches.append(r"data\air_hornShape.xml")
            caches.append(r"data\air_hornShape.mcx")
            for cache in caches:
                self.assertTrue(
                    os.path.exists(
                        os.path.join(self.tmpdir, bundledir, cache)))

    def testRsProxies(self):
        for bundledir in self.bundledir:
            proxies = [r"proxies\0\air_horn_shaded_v001.rs"]
            for proxy in proxies:
                path = os.path.join(self.tmpdir, bundledir, proxy)
                self.assertTrue(os.path.exists(path))

    def testMayaFile(self):
        for bundledir in self.bundledir:
            mayafile = os.path.join(self.tmpdir, bundledir, "scenes",
                                    bundledir + ".ma")
            self.assertTrue(os.path.exists(mayafile))

    def testReferences(self):
        for bundledir in self.bundledir:
            ref_file = os.path.join(self.tmpdir, bundledir,
                                    r"scenes\refs\air_horn_shaded.ma")
            self.assertTrue(os.path.exists(ref_file))

    @classmethod
    def tearDownClass(self):
        if hasattr(self.gui.bundler, 'stop'):
            self.gui.bundler.stop()
        for srcdir, bundledir in zip(self.srcdir, self.bundledir):
            tearDown(os.path.join(self.tmpdir, srcdir))
            tearDown(os.path.join(self.tmpdir, bundledir))
        tearDown(os.path.join(self.tmpdir, 'mayaproj'))


if __name__ == "__main__":
    unittest.main()
