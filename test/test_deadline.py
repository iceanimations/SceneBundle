import unittest
import functools


def printargs(funcName, *args, **kwargs):
    print funcName, ':'
    print args
    print kwargs

from src import _deadline as dl
dl.dl.deadlineCommand = functools.partial(printargs, 'deadlineCommand')

DeadlineBundleSubmitter = dl.DeadlineBundleSubmitter
class TestDeadlineBundleSubmitter(unittest.TestCase):

    def testDeadlineSubmission(self):
        dsm = DeadlineBundleSubmitter('name', 'pro', 'ep', 'seq', 'shot')
        jobs = dsm.createJobs()
        self.assertEqual(len(jobs), 1)

if __name__ == "__main__":
    unittest.main()

