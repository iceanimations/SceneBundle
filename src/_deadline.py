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

config = {}

configfile = os.path.join(os.path.dirname(os.path.dirname(__file__)),
        'config', '_deadline.yml')
try:
    import yaml
    with open(configfile) as f:
        config = yaml.load(f)
except Exception as e:
    print "Error not read config file (%s) ... using defaults"%str(e)

if not config:
    config['priority'] = 25
    config['chunkSize'] = 50
    config['submitAsSuspended'] = False
    config['submitEachRenderLayer'] = True
    config['submitEachCamera'] = False
    config['submitSceneFile'] = False
    config['ignoreDefaultCamera'] = False

    config['output_loc'] = r'\\ice-lac\Storage\Projects\external\%(project)s\02_production\%(episode)s\%(sequence)s\%(shot)s'
    config['bundle_loc'] = r'%(bundle_base)s\%(project)s\%(episode)s\%(sequence)s\%(shot)s'
    config['illegal_layer_names'] = ['.*depth.*']
    config['illegal_camera_names'] = []
    config['pools'] = {
        'none':{
            'bases':[bundle_base%{'poolidx':idx} for idx in range(1, num_pools+1)],
            'base_selection': 'random_choice'
        }
    }
    config['pool_selection'] = 'random_choice'

    config['overrides'] = [
            { # first override
                'Conditions':[[ 'Renderer', 'redshift' ]],
                'match_all': True,
                'settings': {
                    'pools': {
                        'rs'+str(idx): {
                            'bases':[bundle_base%{'poolidx':idx}],
                            'base_selection':'random_choice' }
                        for idx in range(1, num_pools+1)
                        },
                    'pool_selection': 'min_frames_pending' }
            },
            { # second override
                'Conditions':[[ 'renderer', 'arnold' ]],
                'match_all': True,
                'settings': {
                    'pools': {
                        'hp': {
                            'bases':[bundle_base%{'poolidx':idx} for idx in range(1,
                            num_pools+1)],
                            'base_selection': 'random_choice'
                        }
                    }
                }
            }
    ]

#all_pools = config['pools'].copy
#for key, value in [override['settings']['pools'].items() for override in
        #config['overrides'] if override['settings'].has_key('pools')]:
    #all_pools.update( value )

random.seed(time.time())

all_pools = {}

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
    submitter.submitEachRenderLayer = submitEachRenderLayer
    submitter.submitEachCamera = submitEachCamera
    submitter.submitSceneFile = submitSceneFile
    submitter.ignoreDefaultCamera = ignoreDefaultCamera

    submitter.priority = priority
    submitter.chunkSize = chunkSize

    jobs = submitter.createJobs()

    for job in jobs[:]:
        job_deleted = False

        for pattern in illegal_layer_names:
            if re.match(pattern, str(job.pluginInfo['RenderLayer']), re.I):
                jobs.remove(job)
                job_deleted = True
                break
        if job_deleted:
            continue

        for pattern in illegal_camera_names:
            if re.match(pattern, str(job.pluginInfo['Camera']), re.I):
                jobs.remove(job)
                job_deleted = True
                break
        if job_deleted:
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

