#import os
#import os.path as op


from collections import OrderedDict

import ideadline as dl
reload(dl)

import ideadline.maya as dlm
reload(dlm)

variables = ['bundle_base', 'poolidx', 'project', 'episode', 'sequence', 'shot']
num_pools = 3
bundle_base = r'\\hp-001\drive%(poolidx)d'
output_loc = r'\\ice-lac\Storage\Projects\external\%(project)s\02_production\%(episode)s\%(sequence)s\%(shot)s'
bundle_loc = r'%(bundle_base)s\%(project)s\%(episode)s\%(sequence)s\%(shot)s'


rs_pools = OrderedDict([('rs'+str(idx), bundle_base%{'poolidx':idx})
        for idx in range(1, num_pools+1) ])


def getPreferredPool():
    poolframes = getFramesPendingOnPools(getRedshiftPools())
    return min(enumerate(poolframes.keys()), key=lambda x:poolframes[x[1]])


def createJobs(pool=None, outputPath=None, projectPath=None, sceneFile=None,
        jobName=None):
    submitter = dlm.DeadlineMayaSubmitter()
    if pool:
        submitter.pool=pool
    if outputPath:
        submitter.outputPath = outputPath
    if projectPath:
        submitter.projectPath = projectPath
    if sceneFile:
        submitter.sceneFile = sceneFile
    if jobName:
        submitter.jobName = jobName
    return submitter.createJobs()


def getRedshiftPools():
    return [pool for pool in dl.pools() if pool in rs_pools]


def getFramesPendingInJob(job):
    totalFrames = len(job["Frames"].split(","))
    doneRatio = float(job["QueuedChunks"])/int(job["TaskCount"])
    return int(totalFrames * doneRatio)


def getFramesPendingOnPools(pools,
        statuses = ["Queued", "Active", "Suspended"]):
    jobs = dl.getJobs()
    jobs = dl.filterItems(jobs,
            [("Status", status) for status in statuses] )
    frames = OrderedDict()
    for pool in pools:
        pooljobs = dl.filterItems(jobs,[("PoolOverride", pool)])
        frames[pool]= sum([getFramesPendingInJob(job) for job in pooljobs])
    return frames


if __name__ == '__main__':
    print getFramesPendingOnPools(dl.pools())
