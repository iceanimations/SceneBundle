'''
Created on Nov 5, 2014

@author: qurban.ali
'''
from uiContainer import uic
import msgBox
# reload(msgBox)
from PyQt4.QtGui import ( QMessageBox, QFileDialog, qApp, QIcon,
        QRegExpValidator )
from PyQt4.QtCore import ( Qt, QPropertyAnimation, QRect, QEasingCurve,
        QRegExp )
import qtify_maya_window as qtfy
import PyQt4.QtCore as core
import os.path as osp
import os
import subprocess
import _utilities as util
import appUsageApp
import yaml
import traceback
import logging

isMaya = True
isMayaGUI = True
try:
    import maya.cmds as cmds
    if cmds.about(q=True, batch=True):
        isMayaGUI = False
except ImportError:
    isMaya = False
    isMayaGUI = False

from . import _bundle
from . import _process
BundleMaker = _bundle.BundleMaker
BundleMakerProcess = _process.BundleMakerProcess
OnError = _bundle.OnError

root_path = osp.dirname(osp.dirname(__file__))
ui_path = osp.join(root_path, 'ui')
ic_path = osp.join(root_path, 'icons')
conf_path = osp.join(root_path, 'config')

_regexp = QRegExp('[a-zA-Z0-9_]*')
__validator__ = QRegExpValidator(_regexp)

mapFiles = util.mapFiles

projects_list = [
    'Dubai_Park',
    'Ding_Dong',
    'Al_Mansour_Season_02',
    'Captain_Khalfan',
    'Lavalantula',
]

try:
    _project_conf = osp.join(conf_path, '_projects.yml')
    with open(_project_conf) as f:
        projects_list = yaml.load(f)
except IOError as e:
    logging.getLogger(__name__).warning(
        'Error: %r \r\nCannot read projects config file ... using defaults'%e )

class BundleMakerUIProcessAdapter(core.QObject, BundleMakerProcess):
    gui = None
    process = None

    processSignal = core.pyqtSignal(str)
    statusSignal = core.pyqtSignal(str)
    maximumSignal = core.pyqtSignal(int)
    valueSignal = core.pyqtSignal(int)
    warningSignal = core.pyqtSignal(str)
    errorSignal = core.pyqtSignal(str)
    doneSignal = core.pyqtSignal()

    def __init__(self, progressHandler=None, path=None, filename=None,
            name=None, deadline=True, doArchive=False, delete=False,
            keepReferences=False, project=None, zdepth=None, sequence=None,
            episode=None, shot=None):
        gui = progressHandler
        super(BundleMakerUIProcessAdapter, self).__init__()
        BundleMakerProcess.__init__(self, progressHandler=self,
                path=path, filename=filename, name=name, deadline=deadline,
                doArchive=doArchive, delete=delete,
                keepReferences=keepReferences, project=project, zdepth=zdepth,
                sequence=sequence, episode=episode, shot=shot)

        self.gui = gui
        self.thread = core.QThread(self.gui)
        gui.thread = self.thread
        self.moveToThread(self.thread)

        self.thread.started.connect(self.start)
        self.thread.finished.connect(self.deleteLater)
        self.doneSignal.connect(self.thread.terminate)

        self.processSignal.connect(gui.setProcess)
        self.statusSignal.connect(gui.setStatus)
        self.maximumSignal.connect(gui.setMaximum)
        self.valueSignal.connect(gui.setValue)
        self.errorSignal.connect(gui.error)
        self.warningSignal.connect(gui.warning)
        self.doneSignal.connect(gui.done)

    def setProcess(self, process):
        return self.processSignal.emit(process)

    def setStatus(self, status):
        return self.statusSignal.emit(status)

    def setMaximum(self, maxx):
        return self.maximumSignal.emit(maxx)

    def setValue(self, val):
        return self.valueSignal.emit(val)

    def error(self, val):
        return self.errorSignal.emit(val)

    def warning(self, msg):
        return self.warningSignal.emit(msg)

    def done(self):
        return self.doneSignal.emit()

    def setErrorResp(self, resp):
        self.resp = resp

    @property
    def onError(self):
        return self.gui.onError
    @onError.setter
    def onError(self, val):
        self.gui.onError = val

    def createBundle(self, name=None, project=None, episode=None,
            sequence=None, shot=None):
        self.name = name
        self.project = project
        self.episode = episode
        self.sequence = sequence
        self.shot = shot
        self.thread.start()

    def start(self):
        BundleMakerProcess.createBundle(self)

BundleProcess = BundleMakerUIProcessAdapter

class Setting(object):
    def __init__(self, keystring, default):
        self.keystring = keystring
        self.default = default

    def __get__(self, instance, owner):
        return instance.value(self.keystring, self.default)

    def __set__(self, instance, value):
        instance.setValue(self.keystring, value)

class BundleSettings(core.QSettings):
    bundle_path = Setting('bundle_path', os.path.expanduser('~'))
    bundle_project = Setting('bundle_project', None)
    bundle_sequence = Setting('bundle_sequence', None)
    bundle_episode = Setting('bundle_episode', None)
    bundle_custom_sequence = Setting('bundle_custom_sequence', '')
    bundle_custom_episode = Setting('bundle_custom_episode', '')

    def __init__(self, organization='ICE Animations', product='Scene Bundle'):
        super(BundleSettings, self).__init__(organization, product)

class PathStatus(object):
    kFailed  = -1
    kWaiting =  0
    kBusy    =  1
    kError   =  2
    kSuccess =  3
    kDone = kSuccess

Form, Base = uic.loadUiType(osp.join(ui_path, 'bundle.ui'))
class BundleMakerUI(Form, Base):
    settings = BundleSettings()
    bundleMaker = None
    filename = None
    onError = OnError.LOG
    pathStatus = None

    def __init__(self, parent=qtfy.getMayaWindow(), standalone=False):
        super(BundleMakerUI, self).__init__(parent)
        self.standalone = standalone
        self.setupUi(self)
        self.bundler = BundleMaker(self)
        self.textureExceptions = []
        self.pathStatus = []
        self.currentIndex = 0
        self.errors = []

        self.animation = QPropertyAnimation(self, 'geometry')
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.OutBounce)

        self.addButton.setIcon(QIcon(osp.join(ic_path, 'ic_plus.png')))
        self.removeButton.setIcon(QIcon(osp.join(ic_path, 'ic_minus.png')))
        self.selectButton.setIcon(QIcon(osp.join(ic_path, 'ic_mark.png')))
        self.nameBox.setValidator(__validator__)

        self.bundleButton.clicked.connect(self.callCreateBundle)
        self.browseButton.clicked.connect(self.browseFolder)
        self.nameBox.returnPressed.connect(self.callCreateBundle)
        self.pathBox.returnPressed.connect(self.callCreateBundle)
        self.addButton.clicked.connect(self.browseFolder2)
        self.currentSceneButton.toggled.connect(self.animateWindow)
        self.removeButton.clicked.connect(self.removeSelected)
        self.selectButton.clicked.connect(self.filesBox.selectAll)
        self.filesBox.doubleClicked.connect(self.showEditForm)
        self.deadlineCheck.clicked.connect(self.toggleBoxes)
        self.currentSceneButton.clicked.connect(self.toggleBoxes)
        self.addExceptionsButton.clicked.connect(self.showExceptionsWindow)
        map(lambda btn: btn.clicked.connect(
            lambda: self.makeButtonsExclussive(btn)), [self.deadlineCheck,
                self.makeZipButton, self.keepBundleButton])
        boxes = [self.epBox, self.seqBox, self.shBox, self.epBox2,
                self.seqBox2, self.shBox2, self.nameBox]
        map(lambda box: box.currentIndexChanged.connect(lambda:
            fillName(*boxes)), [self.epBox, self.seqBox, self.shBox])
        map(lambda box: box.textChanged.connect(lambda: fillName(*boxes)),
                [self.epBox2, self.seqBox2, self.shBox2])
        addEventToBoxes(self.epBox, self.seqBox, self.shBox, self.epBox2,
                self.seqBox2, self.shBox2)

        self.bgButton.setChecked(True)

        if self.standalone:
            self.currentSceneButton.setEnabled(False)
        self.progressBar.hide()
        self.zdepthButton.hide()
        self.pathBox.setText(self.settings.bundle_path)
        setComboBoxText(self.projectBox, self.settings.bundle_project)
        populateBoxes(self.epBox, self.seqBox, self.shBox)
        populateProjectsBox(self.projectBox)
        self.setBoxesFromSettings()
        self.hideBoxes()
        self.epBox2.hide()
        self.seqBox2.hide()
        self.shBox2.hide()

        addKeyEvent(self.epBox, self.epBox2)
        addKeyEvent(self.seqBox, self.seqBox2)
        addKeyEvent(self.shBox, self.shBox2)

        self.epBox2.setValidator(__validator__)
        self.seqBox2.setValidator(__validator__)
        self.shBox2.setValidator(__validator__)

        self.logFilePath = osp.join(osp.expanduser('~'), 'scene_bundle_log',
                'latestErrorLog.txt')
        self.thread = None

        appUsageApp.updateDatabase('sceneBundle')

    def makeButtonsExclussive(self, btn):
        if not any([self.deadlineCheck.isChecked(),
                   self.makeZipButton.isChecked(),
                   self.keepBundleButton.isChecked()]):
            btn.setChecked(True)
        self.toggleBoxes()

    def populateBoxes(self):
        self.shBox.addItems(['SH'+str(val).zfill(3) for val in range(1, 101)])
        self.epBox.addItems(['EP'+str(val).zfill(3) for val in range(1, 27)])
        self.seqBox.addItems(['SQ'+str(val).zfill(3) for val in range(1, 31)])

    def setBoxesFromSettings(self):
        setComboBoxText(self.seqBox, self.settings.bundle_sequence)
        setComboBoxText(self.epBox, self.settings.bundle_episode)
        setComboBoxText(self.projectBox, self.settings.bundle_project)
        self.seqBox2.setText(self.settings.bundle_custom_sequence)
        self.epBox2.setText(self.settings.bundle_custom_episode)

    def toggleBoxes(self):
        if self.isCurrentScene() and self.isDeadlineCheck():
            self.showBoxes()
        else:
            self.hideBoxes()

    def showBoxes(self):
        self.epBox.show()
        switchBox(self.epBox, self.epBox2)
        self.seqBox.show()
        switchBox(self.seqBox, self.seqBox2)
        self.shBox.show()
        switchBox(self.shBox, self.shBox2)

    def hideBoxes(self):
        self.epBox.hide()
        self.epBox2.hide()
        self.seqBox.hide()
        self.seqBox2.hide()
        self.shBox.hide()
        self.shBox2.hide()

    def showEditForm(self):
        EditForm(self).show()

    def animateWindow(self, state):
        if state:
            self.shrinkWindow()
        else:
            self.expandWindow()

    def expandWindow(self):
        self.animation.setStartValue(QRect(self.x()+8, self.y()+30,
            self.width(), self.height()))
        self.animation.setEndValue(QRect(self.x()+8, self.y()+30, self.width(),
            420))
        self.animation.start()

    def shrinkWindow(self):
        self.animation.setStartValue(QRect(self.x()+8, self.y()+30,
            self.width(), self.height()))
        self.animation.setEndValue(QRect(self.x()+8, self.y()+30, self.width(),
            160))
        self.animation.start()

    def closeEvent(self, event):
        self.closeLogFile()
        self.deleteLater()
        del self

    def isCurrentScene(self):
        return self.currentSceneButton.isChecked()

    def isDeadlineCheck(self):
        return self.deadlineCheck.isChecked()

    def getPendingPaths(self):
        pending = []
        paths = self.getPaths()
        for path, status in zip(self.pathStatus, paths):
            if status == PathStatus.kWaiting:
                pending.append(path)

    def numPending(self):
        return len(filter( None, (status in [PathStatus.kWaiting,
            PathStatus.kFailed] for status in self.pathStatus )))

    def numDone(self):
        return len(filter( None, (status in [PathStatus.kSuccess,
            PathStatus.kError] for status in self.pathStatus )))

    def getNextPathIndex(self):
        count = self.filesBox.count()
        idx = self.currentIndex if self.currentIndex < count else 0
        while 1:
            if self.pathStatus[idx] in [PathStatus.kFailed and
                    PathStatus.kWaiting]:
                self.currentIndex = idx + 1
                return idx
            else:
                idx = idx + 1 if idx + 1 < count else 0
            if idx == self.currentIndex:
                return -1

    def callCreateBundle(self):
        self.progressBar.show()
        self.bundleButton.setEnabled(False)
        self.bgButton.setEnabled(False)
        qApp.processEvents()

        ep, seq, sh = None, None, None

        try:
            pro = self.projectBox.currentText()
            if self.isDeadlineCheck():
                if pro == '--Project--':
                    msgBox.showMessage(self, title='Scene Bundle',
                                    msg='Project name not selected',
                                    icon=QMessageBox.Information)
                    return

            if not self.isCurrentScene():

                if not self.bgButton.isChecked():
                    self.addButton.setEnabled(False)
                    self.removeButton.setEnabled(False)

                if not self.getPath(): # Bundle location path
                    print '((((((((((((((((((((((()))))))))))))))))))))))'
                    return

                total = self.filesBox.count()

                if total == 0:
                    msgBox.showMessage(self, title='Scene Bundle',
                                    msg='No file added to the files box',
                                    icon=QMessageBox.Information)
                    return

                for i in range(total):
                    if len(self.filesBox.item(i).text().split(' | ')) < 5:
                        msgBox.showMessage(self, title='Scene Bundle',
                            msg=( 'Name, Episode, Sequence and/or Shot not '
                                'specified for the item' ),
                            icon=QMessageBox.Information)
                        return

                while self.numPending() > 0:
                    idx = self.getNextPathIndex()
                    self.setStatus('Bundling Item '+ str(self.numDone()+1) +
                            ' of '+ str(total))
                    item = self.filesBox.item(idx)
                    text = item.text()

                    failed = False
                    if len(text.split(' | ')) < 5:
                        failed = True
                    else:
                        name, filename, ep, seq, sh = item.text().split(' | ')
                        if not osp.splitext(filename)[-1] in ['.ma', '.mb']:
                            failed = True
                        if self.isDeadlineCheck():
                            if not all([name, ep, seq, sh, filename]):
                                failed=True
                        else:
                            if not all([name, filename]):
                                failed=True

                    if failed:
                        self.pathStatus[idx] = PathStatus.kFailed
                        item.setBackground(Qt.darkRed)
                        continue

                    if self.bgButton.isChecked():
                        self.bundler = BundleProcess(self)
                    else:
                        self.bundler = BundleMaker(self)

                    self.pathStatus[idx] = PathStatus.kBusy
                    item.setBackground(Qt.darkGreen)

                    qApp.processEvents()
                    if osp.splitext(filename)[-1] in ['.ma', '.mb']:
                        self.filename = filename
                        try:
                            self.bundler.openFile(filename)
                        except:
                            pass
                        self.bundler.filename = filename
                        errors = self.errors[:]
                        self.createBundle(name=name, project=pro, episode=ep,
                                sequence=seq, shot=sh)

                        if len(errors) != len(self.errors):
                            self.pathStatus[idx] = PathStatus.kError
                            item.setBackground(Qt.darkYellow)
                        else:
                            self.pathStatus[idx] = PathStatus.kSuccess
                            item.setBackground(Qt.darkGray)


                    while self.thread:
                        qApp.processEvents()

            else:
                self.bundler = BundleMaker(self)
                self.filename = cmds.file(q=1, sn=1)
                self.createBundle(project=pro, episode=self.getEp(),
                        sequence=self.getSeq(), shot=self.getSh())
        finally:
            self.progressBar.hide()
            self.bundleButton.setEnabled(True)
            self.bgButton.setEnabled(True)
            self.addButton.setEnabled(True)
            self.removeButton.setEnabled(True)
            qApp.processEvents()
            self.showLogFileMessage()

    def createBundle(self, name=None, project=None, episode=None,
            sequence=None, shot=None):
        self.bundler.path = self.getPath()
        if name is None:
            name = self.getName()
        self.bundler.filename = self.filename
        self.bundler.name = name
        self.bundler.deadline = self.deadlineCheck.isChecked()
        self.bundler.archive = self.makeZipButton.isChecked()
        self.bundler.delete = not self.keepBundleButton.isChecked()
        self.bundler.keepReferences = self.keepReferencesButton.isChecked()
        self.bundler.textureExceptions = self.textureExceptions
        try:
            self.openLogFile()
            self.bundler.createBundle(name=name, project=project,
                    episode=episode, sequence=sequence, shot=shot)
        finally:
            self.closeLogFile()

    def showLogFileMessage(self):
        with open(self.logFilePath, 'rb') as f:
            details = f.read()
            if details:
                btn = msgBox.showMessage(self, title='Scene Bundle',
                        msg=( 'Some errors occured while creating bundle\n' +
                            self.logFilePath ),
                        ques='Do you want to view log file now?',
                        icon=QMessageBox.Information,
                        btns=QMessageBox.Yes|QMessageBox.No)
                if btn == QMessageBox.Yes:
                    subprocess.Popen(self.logFilePath, shell=True)

    def getPath(self):
        path = str(self.pathBox.text())
        if path:
            if osp.exists(path):
                self.settings.bundle_path = path
                return path
            else:
                msgBox.showMessage(self, title='Scene Bundle',
                                   msg='Specified path does not exist',
                                   icon=QMessageBox.Information)
        else:
            msgBox.showMessage(self, title='Scene Bundle',
                               msg='Location path not specified',
                               icon=QMessageBox.Information)

    def getName(self):
        name = str(self.nameBox.text())
        if name:
            return name
        else:
            msgBox.showMessage(self, title='Scene Bundle',
                               msg='Name not specified',
                               icon=QMessageBox.Information)

    def getEp(self):
        text = self.epBox.currentText()
        if text == 'Custom':
            return self.epBox2.text()
        if text == '--Episode--':
            text = ''
        return text

    def getSeq(self):
        text = self.seqBox.currentText()
        if text == 'Custom':
            return self.seqBox2.text()
        if text == '--Sequence--':
            text = ''
        return text

    def getSh(self):
        text = self.shBox.currentText()
        if text == 'Custom':
            return self.shBox2.text()
        if text == '--Shot--':
            text = ''
        return text

    def browseFolder(self):
        path = QFileDialog.getExistingDirectory(self, 'Select Folder',
                self.getPath())
        if path:
            self.pathBox.setText(path)

    def browseFolder2(self):
        paths = QFileDialog.getOpenFileNames(self, 'Select Folder', '',
                '*.ma *.mb')
        if paths:
            for path in paths:
                if osp.splitext(path)[-1] in ['.ma', '.mb']:
                    self.filesBox.addItem(path)
                    item = self.filesBox.item(self.filesBox.count()-1)
                    self.pathStatus.append(PathStatus.kWaiting)
                    item.setBackground(Qt.White)

    def setPaths(self, paths):
        for row in range( len(paths) ):
            try:
                status = self.pathStatus[row]
                item = self.filesBox.item(row)
                if status in [PathStatus.kWaiting, PathStatus.kFailed]:
                    item.setText(paths[row])
                    if status == PathStatus.kFailed:
                        self.pathStatus[row] = PathStatus.kWaiting
                        item.setBackground(Qt.white)
            except IndexError:
                self.filesBox.addItem(paths[row])
                item = self.filesBox.item(self.filesBox.count()-1)
                item.setBackground(Qt.white)
                self.pathStatus.append(PathStatus.kWaiting)

    def getPaths(self):
        return [self.filesBox.item(idx).text() for idx in
                range(self.filesBox.count())]

    def removeSelected(self):
        for item in self.filesBox.selectedItems():
            idx = self.filesBox.row(item)
            status = self.pathStatus[idx]
            if status != PathStatus.kBusy:
                item = self.filesBox.takeItem(idx)
                del item
                del self.pathStatus[idx]

    def showExceptionsWindow(self):
        Exceptions(self, self.textureExceptions).show()

    def addExceptions(self, paths):
        self.textureExceptions = paths[:]

    def openLogFile(self):
        try:
            self.logFile = open(self.logFilePath, 'wb')
        except:
            pass

    def closeLogFile(self):
        try:
            self.logFile.close()
            self.logFile = None
        except:
            pass

    def createLog(self, details):
        if self.logFile:
            details = self.currentFileName() +'\r\n'*2 + details
            self.logFile.write(details)
            self.logFile.write('\r\n'+'-'*100+'\r\n'*3)

    def setStatus(self, msg):
        self.status = msg
        self.statusLabel.setText(msg)
        qApp.processEvents()

    def setMaximum(self, maxx):
        self.maxx = maxx
        self.progressBar.setMaximum(maxx)
        qApp.processEvents()

    def setValue(self, val):
        self.val = val
        self.progressBar.setValue(val)
        qApp.processEvents()

    def setProcess(self, process):
        self.process = process
        self.statusLabel.setText('Process: %s ... ' % process)
        qApp.processEvents()

    def done(self):
        cmds.file(new=1, f=1)
        if self.thread:
            try:
                self.thread.terminate
            except:
                pass
            self.thread = None

    def error(self, msg):
        exc = traceback.format_exc()
        if exc.strip() == str(None):
            exc = ''
        errMsg = '\r\nError:' + msg + '\n'*2 + exc
        self.errors.append(errMsg)
        self.createLog(errMsg)
        if self.isCurrentScene():
            btn = msgBox.showMessage(self, title='Scene Bundle',
                    msg='Errors occurred while %s: %s'%(self.process,
                        self.status),
                    ques='Do you want to proceed?',
                    details=msg,
                    icon=QMessageBox.Information,
                    btns=QMessageBox.Yes|QMessageBox.No)
            if btn == QMessageBox.Yes:
                return OnError.LOG
            else:
                return OnError.LOG_RAISE
        else:
            return OnError.LOG

    def warning(self, msg):
        self.createLog('\r\nWarning:' + msg)

    def currentFileName(self):
        return cmds.file(location=True, q=True)

Form1, Base1 = uic.loadUiType(osp.join(ui_path, 'form.ui'))
class EditForm(Form1, Base1):
    def __init__(self, parent=None):
        super(EditForm, self).__init__(parent)
        self.setupUi(self)

        self.parentWin = parent
        self.inputFields = []

        populateBoxes(self.epBox, self.seqBox, self.shBox)
        self.populate()
        self.epBox.currentIndexChanged.connect(self.switchAllBoxes)
        self.seqBox.currentIndexChanged.connect(self.switchAllBoxes)
        self.shBox.currentIndexChanged.connect(self.switchAllBoxes)
        addEventToBoxes(self.epBox, self.seqBox, self.shBox, self.epBox2,
                self.seqBox2, self.shBox2)

        self.epBox2.setValidator(__validator__)
        self.seqBox2.setValidator(__validator__)
        self.shBox2.setValidator(__validator__)

        addKeyEvent(self.epBox, self.epBox2)
        addKeyEvent(self.seqBox, self.seqBox2)
        addKeyEvent(self.shBox, self.shBox2)

        self.epBox2.textChanged.connect(self.fillAllBoxes)
        self.seqBox2.textChanged.connect(self.fillAllBoxes)
        self.shBox2.textChanged.connect(self.fillAllBoxes)

        self.epBox2.hide()
        self.seqBox2.hide()
        self.shBox2.hide()

        if not self.parentWin.isDeadlineCheck():
            self.epBox.hide()
            self.seqBox.hide()
            self.shBox.hide()


        self.okButton.clicked.connect(self.ok)

    def populateBoxes(self):
        self.shBox.addItems(['SH'+str(val).zfill(3) for val in range(1, 101)])
        self.epBox.addItems(['EP'+str(val).zfill(3) for val in range(1, 27)])
        self.seqBox.addItems(['SQ'+str(val).zfill(3) for val in range(1, 31)])

    def populate(self):
        paths = self.parentWin.getPaths()
        for path in paths:
            name = ep = seq = sh = ''
            if ' | ' in path:
                name, path, ep, seq, sh = path.split(' | ')
            iField = InputField(self, name, path, ep, seq, sh)
            self.itemsLayout.addWidget(iField)
            self.inputFields.append(iField)

    def switchAllBoxes(self):
        for iField in self.inputFields:
            iField.epBox.setCurrentIndex(self.getIndexOfBox(iField.epBox,
                self.epBox.currentText()))
            iField.seqBox.setCurrentIndex(self.getIndexOfBox(iField.seqBox,
                self.seqBox.currentText()))
            iField.shBox.setCurrentIndex(self.getIndexOfBox(iField.shBox,
                self.shBox.currentText()))

    def fillAllBoxes(self):
        for iField in self.inputFields:
            iField.epBox2.setText(self.epBox2.text())
            iField.seqBox2.setText(self.seqBox2.text())
            iField.shBox2.setText(self.shBox2.text())

    def ok(self):
        paths = []
        for iField in self.inputFields:
            name = iField.getName()
            path = iField.getPath()
            ep = iField.getEp()
            seq = iField.getSeq()
            sh = iField.getSh()
            if not name:
                msgBox.showMessage(self, title='Scene Bundle',
                    msg='Name not specified for the bundle',
                    icon=QMessageBox.Information)
                return
            if not path:
                msgBox.showMessage(self, title='Scene Bundle',
                    msg='Path not specified for the bundle',
                    icon=QMessageBox.Information)
                return
            if self.parentWin.isDeadlineCheck():
                if not ep:
                    msgBox.showMessage(self, title='Scene Bundle',
                        msg='Episode not specified for the bundle',
                        icon=QMessageBox.Information)
                    return
                if not seq:
                    msgBox.showMessage(self, title='Scene Bundle',
                        msg='Sequence not specified for the bundle',
                        icon=QMessageBox.Information)
                    return
                if not sh:
                    msgBox.showMessage(self, title='Scene Bundle',
                        msg='Shot not specified fot the bundle',
                        icon=QMessageBox.Information)
                    return
            paths.append(' | '.join([name, path, ep, seq, sh]))
        self.parentWin.setPaths(paths)
        self.accept()

    def getIndexOfBox(self, box, text):
        for i in range(box.count()):
            if box.itemText(i) == text:
                return i
        return -1

Form2, Base2 = uic.loadUiType(osp.join(ui_path, 'input_field.ui'))
class InputField(Form2, Base2):
    def __init__(self, parent=None, name=None, path=None, ep=None, seq=None,
            sh=None):
        super(InputField, self).__init__(parent)
        self.setupUi(self)

        populateBoxes(self.epBox, self.seqBox, self.shBox)
        addEventToBoxes(self.epBox, self.seqBox, self.shBox, self.epBox2,
                self.seqBox2, self.shBox2)

        addKeyEvent(self.epBox, self.epBox2)
        addKeyEvent(self.seqBox, self.seqBox2)
        addKeyEvent(self.shBox, self.shBox2)

        self.epBox2.hide()
        self.seqBox2.hide()
        self.shBox2.hide()

        if name:
            self.nameBox.setText(name)
        if path:
            self.pathBox.setText(path)
        if ep:
            self.setEp(ep)
        if seq:
            self.setSeq(seq)
        if sh:
            self.setSh(sh)

        if not parent.parentWin.isDeadlineCheck():
            self.epBox.hide()
            self.seqBox.hide()
            self.shBox.hide()

        self.nameBox.setValidator(__validator__)
        self.epBox2.setValidator(__validator__)
        self.seqBox2.setValidator(__validator__)
        self.shBox2.setValidator(__validator__)
        boxes = [self.epBox, self.seqBox, self.shBox, self.epBox2,
                self.seqBox2, self.shBox2, self.nameBox]
        map(lambda box: box.currentIndexChanged.connect(lambda:
            fillName(*boxes)), [self.epBox, self.seqBox, self.shBox])
        map(lambda box: box.textChanged.connect(lambda: fillName(*boxes)),
                [self.epBox2, self.seqBox2, self.shBox2])

        self.browseButton.clicked.connect(self.browseFolder)

    def closeEvent(self, event):
        self.deleteLater()
        del self

    def browseFolder(self):
        filename = QFileDialog.getSaveFileName(self, 'Select File', '',
                '*.ma *.mb')
        if filename:
            self.pathBox.setText(filename)

    def setEp(self, ep):
        index = self.getIndexOfBox(self.epBox, ep)
        if index == -1:
            index = self.epBox.count() - 1
            self.epBox2.setText(ep)
        self.epBox.setCurrentIndex(index)

    def setSeq(self, seq):
        index = self.getIndexOfBox(self.seqBox, seq)
        if index == -1:
            index = self.seqBox.count() - 1
            self.seqBox2.setText(seq)
        self.seqBox.setCurrentIndex(index)

    def setSh(self, sh):
        index = self.getIndexOfBox(self.shBox, sh)
        if index == -1:
            index = self.shBox.count() - 1
            self.shBox2.setText(sh)
        self.shBox.setCurrentIndex(index)

    def getIndexOfBox(self, box, text):
        for i in range(box.count()):
            if box.itemText(i) == text:
                return i
        return -1

    def setName(self, name):
        self.nameBox.setText(name)

    def setPath(self, path):
        self.pathBox.setText(path)

    def getName(self):
        return self.nameBox.text()

    def getPath(self):
        return self.pathBox.text()

    def getEp(self):
        text = self.epBox.currentText()
        if text == 'Custom':
            return self.epBox2.text()
        if text == '--Episode--':
            text = ''
        return text

    def getSeq(self):
        text = self.seqBox.currentText()
        if text == 'Custom':
            return self.seqBox2.text()
        if text == '--Sequence--':
            text = ''
        return text

    def getSh(self):
        text = self.shBox.currentText()
        if text == 'Custom':
            return self.shBox2.text()
        if text == '--Shot--':
            text = ''
        return text

Form3, Base3 = uic.loadUiType(osp.join(ui_path, 'exceptions.ui'))
class Exceptions(Form3, Base3):
    def __init__(self, parent, paths):
        super(Exceptions, self).__init__(parent)
        self.setupUi(self)
        self.parentWin = parent
        self.populate(paths)

        self.addButton.clicked.connect(self.add)
        self.pathsBox.returnPressed.connect(self.add)

    def populate(self, paths):
        self.pathsBox.setText(','.join(paths))

    def closeEvent(self, event):
        self.deleteLater()

    def add(self):
        paths = self.pathsBox.text()
        if paths:
            paths = paths.split(',')
            paths = [path.strip().strip("\"") for path in paths if path]
        else:
            paths = []
        self.parentWin.addExceptions(paths)
        self.accept()

def fillName(epBox, seqBox, shBox, epBox2, seqBox2, shBox2, nameBox):
    ep = epBox.currentText()
    seq = seqBox.currentText()
    sh = shBox.currentText()
    names = []
    if ep != '--Episode--':
        text = epBox2.text() if ep == 'Custom' else ep
        if text:
            names.append(text)
    if seq != '--Sequence--':
        text = seqBox2.text() if seq == 'Custom' else seq
        if text:
            names.append(text)
    if sh != '--Shot--':
        text = shBox2.text() if sh == 'Custom' else sh
        if text:
            names.append(text)
    name = '_'.join(names) if names else '_'
    nameBox.setText(name)

def populateProjectsBox(box):
    box.addItems(projects_list)

def populateBoxes(epBox, seqBox, shBox):
    shBox.addItems(['SH'+str(val).zfill(3) for val in range(1, 101)])
    epBox.addItems(['EP'+str(val).zfill(3) for val in range(1, 27)])
    seqBox.addItems(['SQ'+str(val).zfill(3) for val in range(1, 31)])

    for item in [epBox, seqBox, shBox]:
        item.addItem('Custom')

def keyPress(box):
    box.setCurrentIndex(0)

def addKeyEvent(box1, box2):
    box2.mouseDoubleClickEvent = lambda event: keyPress(box1)

def switchBox(box1, box2):
    if box1.currentText() == 'Custom':
        box2.show()
        box1.hide()
    else:
        box2.hide()
        box1.show()

def setComboBoxText(box, value):
    for idx in range(box.count()):
        if value == box.itemText(idx):
            box.setCurrentIndex(idx)

def addEventToBoxes(epBox, seqBox, shBox, epBox2, seqBox2, shBox2):
    epBox.currentIndexChanged.connect(lambda: switchBox(epBox, epBox2))
    seqBox.currentIndexChanged.connect(lambda: switchBox(seqBox, seqBox2))
    shBox.currentIndexChanged.connect(lambda: switchBox(shBox, shBox2))
