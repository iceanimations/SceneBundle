import math
import os
import random
import time
import re
import shutil

import ideadline as dl
import ideadline.maya as dlm
import imaya

variables = [
    'bundle_base', 'poolidx', 'project', 'episode', 'sequence', 'shot'
]
num_pools = 3
bundle_base = r'\\hp-001\drive%(poolidx)d'

config = {}

configfile = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'config', '_deadline.yml')
try:
    import yaml
    with open(configfile) as f:
        config = yaml.load(f)
except Exception as e:
    print "Error not read config file (%s) ... using defaults" % str(e)

if not config:
    config['priority'] = 25
    config['chunkSize'] = 50
    config['submitAsSuspended'] = False
    config['submitEachRenderLayer'] = True
    config['submitEachCamera'] = True
    config['submitSceneFile'] = False
    config['ignoreDefaultCamera'] = False

    config['output_base'] = r'\\renders\Storage\Projects\external'
    config['output_loc'] = (
            r'%(output_base)s\%(project)s'
            r'\02_production\%(episode)s\%(sequence)s\%(shot)s')
    config['bundle_loc'] = (
            r'%(bundle_base)s\%(project)s\%(episode)s'
            r'\%(sequence)s\%(shot)s')
    config['job_name'] = (
            '%(project)s_%(episode)s_%(sequence)s_%(shot)s - %(name)s')
    # config['illegal_layer_names'] = ['.*depth.*']
    config['illegal_layer_names'] = []
    config['illegal_camera_names'] = []
    config['pools'] = {
        'none': {
            'bases': [
                bundle_base % {
                    'poolidx': idx
                } for idx in range(1, num_pools + 1)
            ],
            'base_selection': 'random_choice'
        }
    }
    config['pool_selection'] = 'random_choice'
    config['secondaryPool'] = 'none'

    config['overrides'] = [
        {  # first override
            'conditions': [['Renderer', 'redshift']],
            'match_all': True,
            'settings': {
                'pools': {
                    'rs' + str(idx): {
                        'bases': [bundle_base % {'poolidx': idx}],
                        'base_selection': 'random_choice'}
                    for idx in range(1, num_pools + 1)
                },
                'pool_selection': 'min_frames_pending'}
        },
        {  # second override
            'conditions': [['renderer', 'arnold']],
            'match_all': True,
            'settings': {
                'pools': {
                    'hp': {
                        'bases': [bundle_base % {'poolidx': idx}
                                  for idx in range(1, num_pools + 1)],
                        'base_selection': 'random_choice'
                    }
                }
            }
        }
    ]

random.seed(time.time())


class DeadlineBundleSubmitter(dlm.DeadlineMayaSubmitter):
    def __init__(self, name, project, episode, sequence, shot, *args,
                 **kwargs):
        super(DeadlineBundleSubmitter, self).__init__(*args, **kwargs)
        self.chosen_pools = []
        self.project_paths = []
        self.name = name
        self.project = project
        self.episode = episode
        self.sequence = sequence
        self.shot = shot

    def evalOverrideConditions(self, conditions):
        applyOverride = False

        match_all = True
        if conditions:
            if isinstance(conditions[-1], basestring):
                if conditions[-1] == 'match_all':
                    match_all = True
                elif conditions[-1] == 'match_any':
                    match_all = False

        for cond in conditions:

            try:
                if not isinstance(cond, list):
                    continue

                if isinstance(cond[0], list):
                    applyOverride = self.evalOverrideConditions(cond)

                else:
                    operand1 = None
                    operand2 = cond[1]
                    method = 'eq'

                    if len(cond) == 3:
                        method = cond[1]
                        operand2 = cond[2]

                    if cond[0] == 'renderer':
                        operand1 = imaya.currentRenderer()
                    elif cond[0] == 'project':
                        operand1 = self.project
                    elif cond[0] == 'episode':
                        operand1 = self.episode
                    elif cond[0] == 'sequence':
                        operand1 = self.sequence
                    elif cond[0] == 'shot':
                        operand1 = self.shot
                    elif cond[0] == 'name':
                        operand1 = self.name
                    else:
                        raise ValueError('Unknown condition')

                    applyOverride = dl.matchValue(operand1, operand2, method)

                if ((not applyOverride and match_all) or
                        (applyOverride and not match_all)):
                    break

            except Exception as e:
                print 'ignoring condition %r due to error %r' % (
                    cond, e)

        return applyOverride

    def configure(self, sync=True):
        self.conf = config.copy()

        for override in self.conf.pop('overrides'):
            conditions = override['conditions']
            applyOverride = False

            if conditions and isinstance(conditions, list):
                applyOverride = self.evalOverrideConditions(conditions)

            if applyOverride:
                for key, value in override.get('settings', {}).items():
                    self.conf[key] = value

        self.validatePools('pools')

        if sync:
            self.syncWithConf()

        for pattern in self.conf.get('illegal_layer_names', []):
            if re.match(pattern, str(self._currentLayer), re.I):
                return False

        for pattern in self.conf.get('illegal_camera_names', []):
            if re.match(pattern, str(self._currentCamera), re.I):
                return False

        return True

    def syncWithConf(self):
        chunkSize = self.conf.get("chunkSize")
        if chunkSize is not None:
            self.chunkSize = chunkSize

        ignoreDefaultCamera = self.conf.get("ignoreDefaultCamera")
        if ignoreDefaultCamera is not None:
            self.ignoreDefaultCamera = ignoreDefaultCamera

        priority = self.conf.get("priority")
        if priority is not None:
            self.priority = priority

        submitAsSuspended = self.conf.get("submitAsSuspended")
        if submitAsSuspended is not None:
            self.submitAsSuspended = submitAsSuspended

        submitEachCamera = self.conf.get("submitEachCamera")
        if submitEachCamera is not None:
            self.submitEachCamera = submitEachCamera

        submitEachRenderLayer = self.conf.get("submitEachRenderLayer")
        if submitEachRenderLayer is not None:
            self.submitEachRenderLayer = submitEachRenderLayer

        submitSceneFile = self.conf.get("submitSceneFile")
        if submitSceneFile is not None:
            self.submitSceneFile = submitSceneFile

        self.pool = self.getPreferredPool('pools')
        self.bundle_base = self.getPreferredBase()

        secondaryPool = self.conf.get('secondaryPool')
        if secondaryPool is not None:
            self.secondaryPool = secondaryPool

        self.vardict = {
            'output_base': self.conf.get("output_base"),
            'bundle_base': self.bundle_base,
            'project': self.project,
            'episode': self.episode,
            'sequence': self.sequence,
            'shot': self.shot,
            'name': self.name
        }
        self.bundle_loc = self.conf['bundle_loc'] % self.vardict
        self.jobName = self.conf['job_name'] % self.vardict
        self.outputPath = self.conf['output_loc'] % self.vardict

        self.projectPath = self.getNewProjectPath()
        filename = os.path.basename(imaya.cmds.file(q=1, sn=1))
        self.sceneFile = os.path.join(self.projectPath, "scenes", filename)

    def copyBundles(self):
        for path in self.project_paths:
            shutil.copytree(imaya.cmds.workspace(q=1, rd=1), path)

    def createJobs(self):
        self.chosen_pools = []
        self.project_paths = []
        return super(DeadlineBundleSubmitter, self).createJobs()

    def getNewProjectPath(self):
        count = 0
        projectPath = os.path.join(self.bundle_loc, self.name)

        for chosen_path in self.project_paths:
            if self.bundle_base in chosen_path:
                return chosen_path

        while os.path.exists(projectPath):
            count += 1
            projectPath = os.path.join(self.bundle_loc, "%s_%03d" % (self.name,
                                                                     count))
        self.project_paths.append(projectPath)
        return projectPath

    def getPreferredBase(self):
        bases = self.conf['pools'][self.pool].get('bases')
        if not bases:
            raise Exception('No basepaths for pool %s' % self.pool)
        # see if a valid base is already selected, stick to it
        for chosen_path in self.project_paths:
            for base in bases:
                if base in chosen_path:
                    return base
        return random.choice(bases)

    def getPreferredPool(self, key='pools'):
        pools = self.conf.get(key, {})
        method = self.conf.get('pool_selection')

        if not pools:
            return None

        # if a valid pools is already selected stick to it
        for chosen_pool in self.chosen_pools:
            if chosen_pool in pools.keys():
                return chosen_pool

        # if a valid base is already selected, select its pool
        for pool, pool_settings in pools.items():
            bases = pool_settings['bases']
            for base in bases:
                for path in self.project_paths:
                    if base in path:
                        return pool

        # else choose according to scheme
        if method == 'min_frames_pending':
            poolframes = self.getFramesPendingOnPools()
            newpool = min(poolframes.keys(), key=lambda x: poolframes[x])
            self.chosen_pools.append(newpool)
            return newpool
        elif method == 'user_sequential':
            choice = random.choice(range(len(pools.keys())))
            seqFile = os.path.join(
                os.path.expanduser('~'), '.sceneBundleChoice')
            try:
                with open(seqFile) as fil:
                    choice = int(fil.read())
            except (ValueError, IOError):
                pass
            choice %= len(pools.keys())
            with open(seqFile, 'w+') as fil:
                fil.write(str(choice + 1))
            return pools.keys()[choice]
        else:
            return random.choice(pools.keys())

    def getFramesPendingInJob(self, job):
        ''' read job dict to find out number of pending frames '''
        totalFrames = len(job["Frames"].split(","))
        ratio = 1 - float(job["CompletedChunks"]) / int(job["TaskCount"])
        return int(math.ceil(totalFrames * ratio))

    def getFramesPendingOnPools(self, statuses=["Queued", "Active"]):
        if not hasattr(self, 'deadline_jobs'):
            self.deadline_jobs = dl.getJobs()
        jobs = self.deadline_jobs
        jobs = dl.filterItems(jobs, [("Status", status)
                                     for status in statuses])
        frames = dict()
        for pool in self.conf['pools']:
            pooljobs = dl.filterItems(jobs, [("PoolOverride", pool)])
            frames[pool] = sum(
                [self.getFramesPendingInJob(job) for job in pooljobs])
        return frames

    def validatePools(self, key='pools'):
        pools = self.conf.get(key, {})

        if not hasattr(self, 'deadline_pools'):
            self.deadline_pools = dl.pools()
        deadline_pools = self.deadline_pools

        valid_pools = {}
        for pool, pool_settings in pools.items():
            if pool not in deadline_pools:
                continue

            bases = pool_settings.get('bases', [])
            valid_bases = []
            for base in bases:
                if base and os.path.exists(base) and os.path.isdir(base):
                    valid_bases.append(base)

            if valid_bases:
                pool_settings['bases'] = valid_bases
                valid_pools[pool] = pool_settings

        if not valid_pools:
            valid_pools = config.get(key, {})

        self.conf[key] = valid_pools
