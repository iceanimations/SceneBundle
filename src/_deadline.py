import os
import os.path as op

import ideadline as dl
reload(dl)

#import ideadline.maya as dlm
#reload(dlm)

rs_pools = {'rs'+(str(idx)):r'd:\shared\lb\rs'+(str(idx)) for idx in
        range(10) }

def mkdir(path):
    if not op.exists(op.dirname(path)):
        mkdir(op.dirname(path))
    os.mkdir(path)

for value in rs_pools.values():
    try:
        mkdir(value)
    except:
        pass

def createJobs(pool=None):
    submitter = dlm.DeadlineMayaSubmitter()
    if pool:
        submitter.pool=pool
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
    frames = {}
    for pool in pools:
        pooljobs = dl.filterItems(jobs,[("PoolOverride", pool)])
        frames[pool]= sum([getFramesPendingInJob(job) for job in pooljobs])
    return frames

if __name__ == '__main__':
    print getFramesPendingOnPools(dl.pools())
