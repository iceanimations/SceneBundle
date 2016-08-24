import unittest
import logging
import sys
import os

import site
site.addsitedir(os.path.abspath('..'))
site.addsitedir(r'R:\Python_Scripts\plugins\utilities')
from sceneBundle.src._bundle import BundleMaker, BaseBundleHandler

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

    def testCreateBundle(self):
        self.bm.name = 'test'
        self.bm.filename = r'd:\shared\test.ma'
        self.bm.path = r'd:\shared'
        self.bm.deadline = False
        self.bm.archive = False
        self.bm.delete = False
        self.bm.createBundle()

if __name__ == "__main__":
    unittest.main()
