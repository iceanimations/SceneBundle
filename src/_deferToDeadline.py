import os

import ideadline as dl

from _process import BundleMakerProcess, mayaVersion, isMaya64


###############################
#  Deadline Scene Bundle Job  #
###############################

class DeadlineSceneBundleException(dl.DeadlineWrapperException):
    pass

class MayaBatchScriptPluginInfo(dl.DeadlinePluginInfo):
    version = dl.DeadlineAttr('version', '', str)
    build = dl.DeadlineAttr('Build', '64bit', str)
    projectPath = dl.DeadlineAttr('ProjectPath', '', str)
    sceneFile = dl.DeadlineAttr('SceneFile', '', str)
    strictErrorChecking = dl.DeadlineAttr('StrictErrorChecking', False, bool)
    useLegacyRenderLayers=dl.DeadlineAttr('UseLegacyRenderLayers', 0, int)
    scriptJob = dl.DeadlineAttr('ScriptJob', True, bool)
    scriptFilename=dl.DeadlineAttr('ScriptFilename', 'makeBundle.py', str)

class DeadlineSceneBundleJob(dl.DeadlineJob):
    exception = DeadlineSceneBundleException
    pluginInfoClass = MayaBatchScriptPluginInfo

class BundleMakerDeadline(BundleMakerProcess):
    job = None

    version = '2016' if mayaVersion is None else str(mayaVersion)
    build = '64bit' if isMaya64 is None or isMaya64 else '32bit'

    def createBundle(self, name=None, project=None, episode=None,
            sequence=None, shot=None):

        if name is None: name = self.name
        if project is None: project = self.project
        if episode is None: episode = self.episode
        if sequence is None: sequence = self.sequence
        if shot is None: shot = self.shot

        self.status.setProcess('SubmitBundleJob')
        self.status.setStatus('Submitting Bundling Job to Deadline')
        self.job = DeadlineSceneBundleJob()

        self.job.jobInfo.name = ' - '.join(['SceneBundle'] + filter(bool,
            [project, episode, sequence, shot, name]))
        self.job.jobInfo.chunkSize = 1
        self.job.jobInfo.frames = 1
        self.job.jobInfo.onJobComplete = 'Nothing'
        self.job.jobInfo.outputFilename0 = ''
        self.job.jobInfo.pool = 'SceneBundle'

        self.job.pluginInfo = MayaBatchScriptPluginInfo()

        self.job.pluginInfo.version = self.version
        self.job.pluginInfo.build = self.build
        self.job.pluginInfo.projectPath = ''
        self.job.pluginInfo.sceneFile = self.filename
        self.job.pluginInfo.scriptJob = True
        self.writePyFile(name=name, project=project, episode=episode,
                sequence=sequence, shot=shot)
        self.job.pluginInfo.scriptFilename = os.path.basename(
                self.pythonFileName )

        if self.status:
            self.status.setProcess('DeferToDeadline')
            self.status.setStatus('Defering Bundling Job to Deadline ...')
            self.status.setMaximum(0)
            self.status.setValue(0)
        try:
            self.jobid = self.job.submit([self.pythonFileName])
        except self.exception as exc:
            self.status.error('Error Submitting Bundling Job: %s'%str(exc))
        else:
            self.status.setStatus('Bundle Deferred to Deadline: %d'%self.jobid)
            self.status.done()

