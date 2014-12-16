import pymel.core as pc
from ._utilities import which, findUIObjectByLabel
import subprocess
import os
import re
import getpass


__deadlineShelfName__ = "Thinkbox"
__deadlineShelfButton__ = "ICE_DeadlineSubmitter"

__deadlineCommandCmd__ = 'DeadlineCommand'
__deadlineWindowName__ = 'DeadlineSubmitWindow'

__deadlineRepoPath__ = r'\\ice-sql\Deadline_5.2\DeadlineRepository'
__deadlineBinPath__ = lambda: os.path.join(__deadlineRepoPath__, "bin", "Windows")
__deadlineCmd__ = os.path.join(__deadlineBinPath__(), __deadlineCommandCmd__ )

__deadlineStatus__ = False
__deadlineWinExists__ = lambda: pc.window(__deadlineWindowName__, exists=1)

__deadlineInitScript__ = os.path.join(__deadlineRepoPath__, "clientSetup", "Maya",
        "InitDeadlineSubmitter.mel")
__deadlineSubmitScript__ = os.path.join(__deadlineRepoPath__, "submission", "Maya",
        "SubmitMayaToDeadline.mel")

__removePattern__ = re.compile('[\s.;:\\/?"<>|]+')


class deadlineError(Exception):
    pass


def initDeadline(addToShelf=True):
    ''' get repo paths and source and stuff
    '''

    global __deadlineStatus__
    global __deadlineRepoPath__
    global __deadlineInitScript__
    global __deadlineSubmitScript__
    global __deadlineCmd__

    __deadlineCmd__ = which(__deadlineCommandCmd__)
    if not __deadlineCmd__:
        binpath = __deadlineBinPath__()
        pathvar = os.environ['path']
        if not binpath in pathvar:
            os.environ['path'] += (os.pathsep + binpath)
        __deadlineCmd__= which(__deadlineCommandCmd__)

    else:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        __deadlineRepoPath__ = subprocess.check_output(
                [__deadlineCmd__, '-getrepositoryroot'],
                startupinfo=startupinfo).strip()

    if __deadlineCmd__:
        __deadlineStatus__ = True

    __deadlineInitScript__ = os.path.join(__deadlineRepoPath__, "clientSetup", "Maya",
            "InitDeadlineSubmitter.mel")
    __deadlineSubmitScript__ = os.path.join(__deadlineRepoPath__, "submission", "Maya",
            "SubmitMayaToDeadline.mel")

    try:
        pc.mel.source(__deadlineInitScript__.replace("\\", "\\\\"))
    except:
        __deadlineStatus__ = False
        raise deadlineError,'__initScript__ Source Error'

    if addToShelf:
        addCustomWindowToShelf()

def addCustomWindowToShelf():
    if not __deadlineStatus__:
        raise deadlineError, 'Deadline not initialized'

    command =('import sceneBundle.src._deadline as deadlineSubmitter;'
            'deadlineSubmitter.openSubmissionWindow()')
    try:
        pc.uitypes.ShelfButton(__deadlineShelfButton__).setCommand(command)

    except:
        pc.shelfButton( __deadlineShelfButton__, parent=__deadlineShelfName__,
                annotation= __deadlineShelfButton__ + ": Use this one to submit",
                image1="pythonFamily.xpm", stp="python",
                command=command)

def getEditProjectButton():
    return findUIObjectByLabel('DeadlineSubmitWindow', pc.uitypes.Button, "Edit Project")


def openSubmissionWindow(init=False, customize=True):
    if init:
        initDeadline()
    if not __deadlineStatus__:
        raise deadlineError, 'Deadline not initialized'
    pc.mel.SubmitJobToDeadline()
    if customize:
        getEditProjectButton().setCommand(pc.Callback(pc.mel.projectWindow))
        hideAndDisableUIElements()
        setJobName(buildJobName())

def hideAndDisableUIElements():
    ''' Enable disable unrelated components
    '''
    if not __deadlineWinExists__:
        raise deadlineError, "Window does not exist"

    pc.checkBox('frw_submitAsSuspended', e=True, v=True, en=False)

    job = findUIObjectByLabel(__deadlineWindowName__, pc.uitypes.FrameLayout,
            "Job Scheduling")
    if job:
        job.setCollapse(True)
        job.setEnable(False)

    tile = findUIObjectByLabel(__deadlineWindowName__, pc.uitypes.FrameLayout,
            "Tile Rendering")
    if tile:
        tile.setCollapse(True)
        tile.setEnable(False)

    rend = findUIObjectByLabel(__deadlineWindowName__, pc.uitypes.FrameLayout,
            "Maya Render Job")
    if rend:
        rend.setCollapse(True)
        rend.setEnable(False)

    submit = findUIObjectByLabel(__deadlineWindowName__, pc.uitypes.CheckBox,
            "Submit Maya Scene File")
    if submit:
        submit.setEnable(False)

    pc.uitypes.OptionMenuGrp('frw_mayaBuild').setEnable(False)
    pc.uitypes.OptionMenuGrp('frw_mayaJobType').setEnable(False)
    pc.uitypes.CheckBox('frw_useMayaBatchPlugin').setEnable(False)
    pc.uitypes.IntSliderGrp('frw_FrameGroup').setValue(4)
    pc.uitypes.ColumnLayout('shotgunTabLayout').setEnable(False)


def submitRender(close=True):
    if not __deadlineWinExists__:
        raise deadlineError, "Window does not exist"
    submitButton = findUIObjectByLabel(__deadlineWindowName__,
            pc.uitypes.Button, "Submit Job")
    if not submitButton:
        raise deadlineError, "Cannot find submit Button"
    if close:
        pc.deleteUI(__deadlineWindowName__, win=True)


def buildJobName(project='', username='', basename=''):
    import maya.cmds as mc
    if not basename:
        basename = os.path.splitext(
                os.path.basename(mc.file(q=True, sceneName=True)))[0]
    basename = __removePattern__.sub( '_', basename.strip() )
    if not username:
        username = getpass.getuser()
    username = __removePattern__.sub( '_', username.strip() )
    if not project:
        project="mansour_s02"
    project = __removePattern__.sub( '_', project.strip() )
    return '%s__%s__%s' % (project, username, basename)


def setJobName(jobname):
    pc.textFieldGrp('frw_JobName', e=True, text=jobname)


def setComment(comment):
    pc.textFieldGrp('frw_JobComment', e=True, text=comment)


def setDepartment(department):
    pc.textFieldGrp('frw_Department', e=True, text=department)


def setProjectPath(projectpath):
    pc.textFieldGrp('frw_projectPath', e=True, text=projectpath)


def setOutputPath(outputpath):
    pc.textFieldGrp('frw_outputFilePath', e=True, text=outputpath)


def setCamera(camera):
    pc.optionMenuGrp('frw_camera')


if __name__ == '__main__':
    initDeadline()
    openSubmissionWindow()
    hideAndDisableUIElements()
    setJobName(buildJobName())

