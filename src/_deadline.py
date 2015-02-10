import math
import os
import random
import time
import re

import ideadline as dl
reload(dl)

import ideadline.maya as dlm
reload(dlm)
import imaya

variables = ['bundle_base', 'poolidx', 'project', 'episode', 'sequence', 'shot']
num_pools = 3
bundle_base = r'\\hp-001\drive%(poolidx)d'
output_loc = r'\\ice-lac\Storage\Projects\external\%(project)s\02_production\%(episode)s\%(sequence)s\%(shot)s'
bundle_loc = r'%(bundle_base)s\%(project)s\%(episode)s\%(sequence)s\%(shot)s'
job_priority = 25
chunk_size = 50
submitAsSuspended = False
configfilepath = os.path.dirname(__file__)

random.seed(time.time())

renderer_pools = {
    'redshift': { 'rs'+str(idx): [bundle_base%{'poolidx':idx}]
            for idx in range(1, num_pools+1) },
    'arnold': {'hp':[bundle_base%{'poolidx':idx} for idx in range(1,
        num_pools+1)]},
    'default': {'none':[bundle_base%{'poolidx':idx} for idx in range(1,
    num_pools+1)]}
}

all_pools = {}
for key, value in renderer_pools.items():
    all_pools.update( value )

def getPreferredPool():
    renderer = imaya.currentRenderer()
    mypools = renderer_pools.get(renderer, renderer_pools['default'])

    if renderer == 'redshift':
        validPools = getValidPools(mypools)
        if validPools:
            poolframes = getFramesPendingOnPools(validPools)
            return min(poolframes.keys(), key=lambda x:poolframes[x])

    elif renderer == 'arnold':
        validPools = getValidPools(mypools)
        if validPools:
            return random.choice(validPools)

    return random.choice(mypools.keys())

def createJobs(pool=None, outputPath=None, projectPath=None, sceneFile=None,
        jobName=None):
    submitter = dlm.DeadlineMayaSubmitter()
    basepath = detectBasepathFromProjectPath(projectPath)
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

    submitter.submitAsSuspended = submitAsSuspended
    submitter.priority = job_priority
    submitter.chunkSize = chunk_size
    jobs = submitter.createJobs()

    for job in jobs[:]:
        if re.match('.*depth.*', job.pluginInfo["RenderLayer"], re.I):
            jobs.remove(job)
            continue
        renderer = job.pluginInfo.get('Renderer', '')
        mypools = renderer_pools.get(renderer, renderer_pools['default'])
        if pool not in mypools:
            newpool = getPreferredPoolByBasepath(basepath, mypools)
            job.jobInfo['Pool']=newpool

    return jobs

def getPreferredPoolByBasepath(basepath, mypools=all_pools):
    for pool, path in mypools.items():
        if basepath in path:
            return pool
    try:
        return random.choice(mypools.keys())
    except:
        return random.choice(renderer_pools['default'].keys())

def detectBasepathFromProjectPath(projectPath, mypools=all_pools):
    for pool, paths in mypools.items():
        for path in paths:
            if path in projectPath:
                return path
    return projectPath

def getBundleBase(pool):
    base = all_pools[pool]
    if not base:
        raise Exception, 'No basepaths for pool %s'%pool
    return random.choice(base)

def getValidPools(mypools=all_pools):
    validPools = []
    for pool in dl.pools():
        bases = mypools.get(pool)
        if bases:
            for base in bases:
                if base and os.path.exists(base) and os.path.isdir(base):
                    validPools.append(pool)
                    break
    return validPools

def getFramesPendingInJob(job):
    totalFrames = len(job["Frames"].split(","))
    ratio = 1-float(job["CompletedChunks"])/int(job["TaskCount"])
    return int(math.ceil(totalFrames * ratio))

def getFramesPendingOnPools(pools,
        statuses = ["Queued", "Active"]):
    jobs = dl.getJobs()
    jobs = dl.filterItems(jobs,
            [("Status", status) for status in statuses] )
    frames = dict()
    for pool in pools:
        pooljobs = dl.filterItems(jobs,[("PoolOverride", pool)])
        frames[pool]= sum([getFramesPendingInJob(job) for job in pooljobs])
    return frames


if __name__ == '__main__':
    print getFramesPendingOnPools(dl.pools())
