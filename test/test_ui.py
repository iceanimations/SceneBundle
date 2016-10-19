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
from PyQt4.QtGui import QApplication, qApp
from PyQt4.QtTest import QTest
from PyQt4.QtCore import Qt

from _testbase import _TestBase

import maya.cmds as mc

app = QApplication(sys.argv)

import src._ui as ui
BundleMakerUI = ui.BundleMakerUI

currentdir = os.path.dirname(__file__)
class TestBundleMakerUI(_TestBase):
    tmpdir = r'd:\temp'
    name = 'bundle'
    srcdir = os.path.join(tmpdir, 'mayaproj')
    bundledir = os.path.join(tmpdir, name)

    @classmethod
    def setUpClass(self):
        super(TestBundleMakerUI, self).setUpClass()

        rootPath = os.path.join(self.tmpdir, self.name)
        if os.path.exists(rootPath):
            shutil.rmtree(rootPath)

        self.gui = BundleMakerUI()
        self.gui.show()
        qApp.processEvents()
        time.sleep(1)

        self.gui.bundleMaker.filename = os.path.join(self.tmpdir, 'mayaproj',
                'scenes', 'mayaproj.ma')
        self.gui.bundleMaker.openFile()

        QTest.mouseClick(self.gui.currentSceneButton, Qt.LeftButton)
        QTest.mouseDClick(self.gui.pathBox, Qt.LeftButton)
        QTest.mouseClick(self.gui.pathBox, Qt.LeftButton)
        QTest.keyClicks(self.gui.pathBox, self.tmpdir)
        QTest.mouseClick(self.gui.keepBundleButton, Qt.LeftButton)
        QTest.mouseClick(self.gui.deadlineCheck, Qt.LeftButton)
        QTest.mouseClick(self.gui.keepReferencesButton, Qt.LeftButton)
        QTest.keyClicks(self.gui.nameBox, self.name)

        qApp.processEvents()
        time.sleep(1)
        QTest.mouseClick(self.gui.bundleButton, Qt.LeftButton)

    def testCreateBundle(self):
        pass

    @classmethod
    def tearDownClass(self):
        mc.file(new=1, f=1)
        super(TestBundleMakerUI, self).tearDownClass()


if __name__ == "__main__":
    unittest.main()
