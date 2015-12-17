'''
Created on Nov 5, 2014

@author: qurban.ali
'''
import qtify_maya_window as qtfy
from uiContainer import uic
import msgBox
reload(msgBox)
from PyQt4.QtGui import QMessageBox, QFileDialog, qApp, QIcon, QRegExpValidator
from PyQt4.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, QRegExp
import PyQt4.QtCore as core
import os.path as osp
import shutil
import os
import re
import subprocess
import _utilities as util
import pymel.core as pc
import maya.cmds as cmds
import appUsageApp
import yaml
import imaya
reload(imaya)
from . import _archiving as arch
from . import _deadline as deadline
reload(deadline)

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
    print 'Cannot read projects config file ... using defaults', e

def populateProjectsBox(box):
    box.addItems(projects_list)

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


Form, Base = uic.loadUiType(osp.join(ui_path, 'bundle.ui'))
class BundleMaker(Form, Base):
    settings = BundleSettings()
    def __init__(self, parent=qtfy.getMayaWindow(), standalone=False):
        super(BundleMaker, self).__init__(parent)
        self.standalone = standalone
        self.setupUi(self)

        self.textureExceptions = []
        self.rootPath = None
        self.texturesMapping = {}
        self.collectedTextures = {}
        self.refNodes = []
        self.cacheMapping = {}
        self.logFile = None

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
        map(lambda btn: btn.clicked.connect(lambda: self.makeButtonsExclussive(btn)),
            [self.deadlineCheck, self.makeZipButton, self.keepBundleButton])
        boxes = [self.epBox, self.seqBox, self.shBox, self.epBox2, self.seqBox2, self.shBox2, self.nameBox]
        map(lambda box: box.currentIndexChanged.connect(lambda: fillName(*boxes)), [self.epBox, self.seqBox, self.shBox])
        map(lambda box: box.textChanged.connect(lambda: fillName(*boxes)), [self.epBox2, self.seqBox2, self.shBox2])
        addEventToBoxes(self.epBox, self.seqBox, self.shBox, self.epBox2, self.seqBox2, self.shBox2)

        #self.projectBox.hide()
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

        path = osp.join(osp.expanduser('~'), 'scene_bundle_log')
        if not osp.exists(path):
            os.mkdir(path)
        self.logFilePath = osp.join(path, 'log.txt')

        appUsageApp.updateDatabase('sceneBundle')


        
    def setStatus(self, msg):
        self.statusLabel.setText(msg)

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

    def showEditForm(self):
        EditForm(self).show()

    def removeSelected(self):
        for i in self.filesBox.selectedItems():
            item = self.filesBox.takeItem(self.filesBox.row(i))
            del item

    def animateWindow(self, state):
        if state:
            self.shrinkWindow()
        else:
            self.expandWindow()

    def expandWindow(self):
        self.animation.setStartValue(QRect(self.x()+8, self.y()+30, self.width(), self.height()))
        self.animation.setEndValue(QRect(self.x()+8, self.y()+30, self.width(), 420))
        self.animation.start()

    def shrinkWindow(self):
        self.animation.setStartValue(QRect(self.x()+8, self.y()+30, self.width(), self.height()))
        self.animation.setEndValue(QRect(self.x()+8, self.y()+30, self.width(), 160))
        self.animation.start()

    def createScriptNode(self):
        '''Creates a unique script node which remap file in bundles scripts'''
        script = None
        try:
            script = filter(
                    lambda x: ( x.st.get() == 1 and x.stp.get() == 1 and
                            x.before.get().strip().startswith('#ICE_BundleScript')),
                    pc.ls( 'ICE_BundleScript', type='script'))[0]
        except IndexError:
            sceneLoadScripts = filter(
                    lambda x: (x.st.get() in [1, 2] and x.stp.get() == 1
                        and x.before.get().strip().startswith('import pymel.core as pc')
                        and not x.after.get()),
                    pc.ls('script*', type='script'))
            if sceneLoadScripts:
                script = sceneLoadScripts[0]

        if script:
            script.before.set(mapFiles)
            script.st.set(1)
            script.rename('ICE_BundleScript')
        else:
            script = pc.scriptNode(name='ICE_BundleScript', st=1, bs=mapFiles,
                    stp='python')
        try:
            util.createReconnectAiAOVScript()
        except Exception as e:
            pc.warning('cannot create reconnect script: %s' % e)

        return script

    def closeEvent(self, event):
        self.closeLogFile()
        self.deleteLater()
        del self

    def isCurrentScene(self):
        return self.currentSceneButton.isChecked()

    def isDeadlineCheck(self):
        return self.deadlineCheck.isChecked()

    def callCreateBundle(self):
        self.openLogFile()
        pro = self.projectBox.currentText()
        if self.isDeadlineCheck():
            if pro == '--Project--':
                msgBox.showMessage(self, title='Scene Bundle',
                                   msg='Project name not selected',
                                   icon=QMessageBox.Information)
                return
        if not self.isCurrentScene():
            if not self.getPath(): # Bundle location path
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
                                       msg='Name, Episode, Sequence and/or Shot not specified for the item',
                                       icon=QMessageBox.Information)
                    return
            for i in range(total):
                self.setStatus('Opening scene '+ str(i+1) +' of '+ str(total))
                item = self.filesBox.item(i)
                item.setBackground(Qt.darkGray)
                qApp.processEvents()
                name, filename, ep, seq, sh = item.text().split(' | ')
                if osp.splitext(filename)[-1] in ['.ma', '.mb']:
                    try:
                        #cmds.file(filename, o=True, f=True, prompt=False)
                        imaya.openFile(filename)
                    except:
                        pass
                    self.createBundle(name=name, project=pro, ep=ep, seq=seq, sh=sh)
        else:
            self.createBundle(project=pro)
        self.closeLogFile()
        self.showLogFileMessage()

    def showLogFileMessage(self):
        with open(self.logFilePath, 'rb') as f:
            details = f.read()
            if details:
                btn = msgBox.showMessage(self, title='Scene Bundle',
                                         msg='Some errors occured while creating bundle\n'+self.logFilePath,
                                         ques='Do you want to view log file now?',
                                         icon=QMessageBox.Information,
                                         btns=QMessageBox.Yes|QMessageBox.No)
                if btn == QMessageBox.Yes:
                    subprocess.Popen(self.logFilePath, shell=True)

    def createLog(self, details):
        if self.logFile:
            details = self.currentFileName() +'\r\n'*2 + details
            self.logFile.write(details)
            self.logFile.write('\r\n'+'-'*100+'\r\n'*3)

    def createBundle(self, name=None, project=None, ep=None, seq=None, sh=None):
        if self.isDeadlineCheck():
            if self.isCurrentScene():
                ep = self.epBox.currentText()
                if ep == 'Custom':
                    ep = self.epBox2.text()
                if ep == '--Episode--':
                    msgBox.showMessage(self, title='Scene Bundle',
                                       msg='Episode name not selected',
                                       icon=QMessageBox.Information)
                    return
                seq = self.seqBox.currentText()
                if seq == 'Custom':
                    seq = self.seqBox2.text()
                if seq == '--Sequence--':
                    msgBox.showMessage(self, title='Scene Bundle',
                                       msg='Sequence name not selected',
                                       icon=QMessageBox.Information)
                    return
                sh = self.shBox.currentText()
                if sh == 'Custom':
                    sh = self.shBox2.text()
                if sh == '--Shot--':
                    msgBox.showMessage(self, title='Scene Bundle',
                                       msg='Shot name not selected',
                                       icon=QMessageBox.Information)
                    return
                self.settings.bundle_episode = self.epBox.currentText()
                self.settings.bundle_custom_episode = self.epBox2.text()
                self.settings.bundle_sequence = self.seqBox.currentText()
                self.settings.bundle_custom_sequence = self.seqBox2.text()
                self.settings.bundle_project = self.projectBox.currentText()
                name = self.getName()
        ws = pc.workspace(o=True, q=True)
        self.progressBar.show()
        self.bundleButton.setEnabled(False)
        qApp.processEvents()
        if self.createProjectFolder(name):
            if self.deadlineCheck.isChecked():
                if self.zdepthButton.isChecked():
                    util.turnZdepthOn()
            pc.workspace(self.rootPath, o=True)
            if self.collectTextures():
                if self.collectReferences():
                    if self.collectCaches():
                        pc.workspace(ws, o=True)
                        if self.collectParticleCache():
                            pc.workspace(self.rootPath, o=True)
                            self.mapTextures()
                            self.mapCache()
                            if self.keepReferencesButton.isChecked():
                                if not self.copyRef():
                                    return
                            else:
                                if not self.importReferences():
                                    return
                            self.saveSceneAs(name)
                            if self.makeZipButton.isChecked():
                                self.archive()
                            if self.deadlineCheck.isChecked():
                                self.submitToDeadline(name, project, ep, seq, sh)
                            if self.isCurrentScene():
                                self.setStatus('Closing scene ...')
                                qApp.processEvents()
                                cmds.file(new=True, f=True)
                            if not self.keepBundleButton.isChecked():
                                self.setStatus('removing bundle ...')
                                qApp.processEvents()
                                self.removeBundle()
                            self.setStatus('Scene bundled successfully...')
                            qApp.processEvents()
        self.progressBar.hide()
        self.bundleButton.setEnabled(True)
        qApp.processEvents()
        pc.workspace(ws, o=True)

    def setPaths(self, paths):
        self.filesBox.clear()
        self.filesBox.addItems(paths)

    def getPaths(self):
        return [self.filesBox.item(i).text() for i in range(self.filesBox.count())]

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

    def createProjectFolder(self, name=None):
        self.clearData()
        path = self.getPath()
        if not name:
            name = self.getName()
        if path and name:
            dest = osp.join(path, name)
            if osp.exists(dest):
                if self.isCurrentScene():
                    if not osp.isfile(dest):
                        files = os.listdir(dest)
                        if files:
                            btn = msgBox.showMessage(self, title='Scene Bundle',
                                                     msg='A directory already exists with the specified name at specified path and is not empty',
                                                     ques='Do you want to replace it?',
                                                     btns=QMessageBox.Yes|QMessageBox.No,
                                                     icon=QMessageBox.Warning)
                            if btn == QMessageBox.Yes:
                                errors = {}
                                try:
                                    shutil.rmtree(dest)
                                except Exception as ex:
                                    errors[dest] = str(ex)
                                if errors:
                                    detail = 'Could not delete the following files'
                                    for key, value in errors.items():
                                        detail += '\n\n'+key+'\nReason: '+value
                                    msgBox.showMessage(self, title='Scene Bundle',
                                                        msg='Could not delete files',
                                                        icon=QMessageBox.Information,
                                                        details=detail)
                                    return
                            else:
                                return
                        else:
                            try:
                                os.rmdir(dest)
                            except Exception as ex:
                                msgBox.showMessage(self, title='Scene Bundle',
                                                   msg=str(ex),
                                                   icon=QMessageBox.Information)
                                return
                else:
                    count = 1
                    dest += '('+ str(count) +')'
                    while 1:
                        if not osp.exists(dest):
                            break
                        dest = dest.replace('('+ str(count) +')', '('+ str(count+1) +')')
                        count += 1
            src = r"R:\Pipe_Repo\Users\Qurban\templateProject"
            shutil.copytree(src, dest)
            self.rootPath = dest
            return True

    def getName(self):
        name = str(self.nameBox.text())
        if name:
            return name
        else:
            msgBox.showMessage(self, title='Scene Bundle',
                               msg='Name not specified',
                               icon=QMessageBox.Information)

    def browseFolder(self):
        path = QFileDialog.getExistingDirectory(self, 'Select Folder',
                self.getPath())
        if path:
            self.pathBox.setText(path)

    def browseFolder2(self):
        paths = QFileDialog.getOpenFileNames(self, 'Select Folder', '', '*.ma *.mb')
        if paths:
            for path in paths:
                if osp.splitext(path)[-1] in ['.ma', '.mb']:
                    self.filesBox.addItem(path)

    def clearData(self):
        self.rootPath = None
        self.cacheMapping.clear()
        del self.refNodes[:]
        self.texturesMapping.clear()
        self.collectedTextures.clear()

    def getNiceName(self, nodeName):
        return nodeName.replace(':', '_').replace('|', '_')

    def getFileNodes(self):
        return pc.ls(type='file')

    def getUDIMFiles(self, path):
        dirname = osp.dirname(path)
        if not osp.exists(dirname):
            return []
        fileName = osp.basename(path)
        if '<udim>' in fileName.lower():
            try:
                parts = fileName.split('<udim>')
                if len(parts) != 2:
                    parts = fileName.split('<UDIM>')
                    if len(parts) != 2:
                        return []
                first, last = parts
            except:
                return []
        if '<f>' in fileName.lower():
            try:
                parts = fileName.split('<f>')
                if len(parts) != 2:
                    parts = fileName.split('<F>')
                    if len(parts) != 2:
                        return []
                first, last = parts
            except:
                return []
        pattern = first +'\d+'+ last
        goodFiles = []
        fileNames = os.listdir(dirname)
        for fName in fileNames:
            if re.match(pattern, fName):
                goodFiles.append(osp.join(dirname, fName))
        return goodFiles

    def currentFileName(self):
        return cmds.file(location=True, q=True)

    def collectTextures(self):
        self.setStatus('Checking texture files...')
        textureFileNodes = self.getFileNodes()
        badTexturePaths = []
        for node in textureFileNodes:
            try:
                filePath = imaya.getFullpathFromAttr(node.fileTextureName)
            except:
                filePath = imaya.getFullpathFromAttr(node.filename)
            if filePath:
                if '<udim>' in filePath.lower() or '<f>' in filePath.lower():
                    fileNames = self.getUDIMFiles(filePath)
                    if not fileNames:
                        badTexturePaths.append(filePath)
                        continue
                else:
                    if not osp.exists(filePath):
                        badTexturePaths.append(filePath)
                        continue
                try:
                    if pc.lockNode(node, q=True, lock=True)[0]:
                        pc.lockNode(node, lock=False)
                    if pc.getAttr(node.ftn, l=True):
                        pc.setAttr(node.ftn, l=False)
                except Exception as ex:
                    badTexturePaths.append('Could not unlock: '+ filePath)

        if badTexturePaths:
            detail = 'Following textures do not exist or could not unlock a locked attribute\r\n'
            for texture in badTexturePaths:
                detail += '\r\n'+ texture
            if self.isCurrentScene():
                btn = msgBox.showMessage(self, title='Scene Bundle',
                                         msg='Errors occurred while collecting textures',
                                         ques='Do you want to proceed?',
                                         details=detail,
                                         icon=QMessageBox.Information,
                                         btns=QMessageBox.Yes|QMessageBox.No)
                if btn == QMessageBox.Yes:
                    pass
                else:
                    return
            else:
                self.createLog(detail)
        newName = 0
        self.setStatus('collecting textures...')
        qApp.processEvents()
        imagesPath = osp.join(self.rootPath, 'sourceImages')
        self.progressBar.setMaximum(len(textureFileNodes))
        for node in textureFileNodes:
            folderPath = osp.join(imagesPath, str(newName))
            relativePath = osp.join(osp.basename(imagesPath), str(newName))
            if not osp.exists(folderPath):
                os.mkdir(folderPath)
            try:
                textureFilePath = imaya.getFullpathFromAttr(node.fileTextureName)
            except AttributeError:
                textureFilePath = imaya.getFullpathFromAttr(node.filename)
            if textureFilePath:
                try:
                    if node.useFrameExtension.get():
                        self.textureExceptions.append(textureFilePath)
                except AttributeError:
                    pass
                if osp.normcase(osp.normpath(textureFilePath)) not in [osp.normcase(osp.normpath(path)) for path in self.textureExceptions]:
                    if textureFilePath not in self.collectedTextures.keys():
                        if pc.attributeQuery('excp', n=node, exists=True):
                            pc.deleteAttr('excp', n=node)
                        if '<udim>' in textureFilePath.lower() or '<f>' in textureFilePath.lower():
                            fileNames = self.getUDIMFiles(textureFilePath)
                            if fileNames:
                                for phile in fileNames:
                                    shutil.copy(phile, folderPath)
                                    self.copyRSFile(phile, folderPath)
                                match = re.search('(?i)<udim>\.', textureFilePath)
                                if match:
                                    relativeFilePath = osp.join(relativePath, re.sub('\d{4}\.', match.group(), osp.basename(fileNames[0])))
                                else:
                                    relativeFilePath = osp.join(relativePath, re.sub('\d{4}\.', '<f>.', osp.basename(fileNames[0])))
                                relativeFilePath = relativeFilePath.replace('\\', '/')
                                self.texturesMapping[node] = relativeFilePath
                            else: continue
                        else:
                            if osp.exists(textureFilePath):
                                shutil.copy(textureFilePath, folderPath)
                                self.copyRSFile(textureFilePath, folderPath)
                                relativeFilePath = osp.join(relativePath, osp.basename(textureFilePath))
                                self.texturesMapping[node] = relativeFilePath
                            else: continue
                        self.collectedTextures[textureFilePath] = relativeFilePath
                    else:
                        self.texturesMapping[node] = self.collectedTextures[textureFilePath]
                        continue
                else:
                    if not pc.attributeQuery('excp', n=node, exists=True):
                        pc.addAttr(node, sn='excp', ln='exception', dt='string')
                        continue
            else:
                continue
            newName = newName + 1
            self.progressBar.setValue(newName)
            qApp.processEvents()
        self.progressBar.setValue(0)
        qApp.processEvents()
        self.setStatus('All textures collected successfully...')
        qApp.processEvents()
        return True

    def copyRSFile(self, path, path2):
        directoryPath, ext = osp.splitext(path)
        directoryPath += '.rstexbin'
        if osp.exists(directoryPath):
            shutil.copy(directoryPath, path2)
        directoryPath += '.tx'
        if osp.exists(directoryPath):
            shutil.copy(directoryPath, path2)

    def getRefNodes(self):
        nodes = []
        for node in pc.ls(type=pc.nt.Reference):
            if not node.referenceFile():
                continue
            try:
                nodes.append(pc.FileReference(node))
            except:
                pass
        return nodes

    def collectReferences(self):
        self.setStatus('collecting references info...')
        refNodes = self.getRefNodes()
        self.progressBar.setMaximum(len(refNodes))
        if refNodes:
            c = 1
            badRefs = {}
            for ref in refNodes:
                try:
                    if not osp.exists(ref.path):
                        badRefs[ref] = 'Does not exist in file system'
                        continue
                    self.refNodes.append(ref)
                except Exception as ex:
                    badRefs[ref] = str(ex)
                self.progressBar.setValue(c)
                qApp.processEvents()
                c += 1
            self.progressBar.setValue(0)
            qApp.processEvents()
            if badRefs:
                detail = 'Following references can not be collected\r\n'
                for node in badRefs:
                    detail += '\r\n'+ node.path + '\r\nReason: '+ badRefs[node]
                if self.isCurrentScene():
                    btn = msgBox.showMessage(self, title='Scene Bundle',
                                             msg='Errors occured while collecting references',
                                             ques='Do you want to proceed?',
                                             icon=QMessageBox.Warning,
                                             btns=QMessageBox.Yes|QMessageBox.No,
                                             details=detail)
                    if btn == QMessageBox.Ok:
                        pass
                    else: return False
                else:
                    self.createLog(detail)
        else:
            self.setStatus('No references found in the scene...')
            qApp.processEvents()
        return True

    def getCacheNodes(self):
        return pc.ls(type=pc.nt.CacheFile)

    def collectCaches(self):
        self.setStatus('Prepering to collect cache files...')
        qApp.processEvents()
        cacheNodes = self.getCacheNodes()
        badCachePaths = []
        self.setStatus('checking cache files...')
        qApp.processEvents()
        for node in cacheNodes:
            files = node.getFileName()
            if files:
                if len(files) != 2:
                    badCachePaths.append(files[0])
                    continue
                cacheXMLFilePath, cacheMCFilePath = files
                if not osp.exists(cacheXMLFilePath):
                    badCachePaths.append(cacheXMLFilePath)
                if not osp.exists(cacheMCFilePath):
                    badCachePaths.append(cacheMCFilePath)
        if badCachePaths:
            detail = 'Following cache files not found\r\n'
            for phile in badCachePaths:
                detail += '\r\n'+ phile
            if self.isCurrentScene():
                btn = msgBox.showMessage(self, title='Scene Bundle',
                                         msg='Some cache files used in the scene not found in the file system',
                                         ques='Do you want to proceed?',
                                         details=detail,
                                         icon=QMessageBox.Information,
                                         btns=QMessageBox.Yes|QMessageBox.No)
                if btn == QMessageBox.Yes:
                    pass
                else:
                    return
            else:
                self.createLog(detail)
        self.setStatus('collecting cache files...')
        qApp.processEvents()
        cacheFolder = osp.join(self.rootPath, 'data')
        newName = 0
        self.progressBar.setMaximum(len(cacheNodes))
        errors = {}
        for node in cacheNodes:
            cacheFiles = node.getFileName()
            if cacheFiles:
                if len(cacheFiles) != 2:
                    continue
                cacheXMLFilePath, cacheMCFilePath = cacheFiles
                newName = newName + 1
                #osp.join(osp.basename(cacheFolder), str(newName))
                #folderPath = osp.join(cacheFolder, str(newName))
                folderPath = cacheFolder
                #os.mkdir(folderPath)
                try:
                    shutil.copy(cacheXMLFilePath, folderPath)
                    shutil.copy(cacheMCFilePath, folderPath)
                except Exception as ex:
                    errors[osp.splitext(cacheMCFilePath)[0]] = str(ex)
                self.cacheMapping[node] = osp.join(folderPath, osp.splitext(osp.basename(cacheMCFilePath))[0])
                self.progressBar.setValue(newName)
                qApp.processEvents()
        if errors:
            detail = 'Could not collect following cache files'
            for cPath in errors.keys():
                detail += '\r\n\r\n'+ cPath + '\r\nReason: '+ errors[cPath]
            if self.isCurrentScene():
                btn = msgBox.showMessage(self, title='Scene Bundle',
                                         msg='Could not collect some of the cache files. '+
                                         'This would result in loss of animation',
                                         ques='Do you want to proceed?',
                                         details=detail,
                                         btns=QMessageBox.Yes|QMessageBox.No,
                                         icon=QMessageBox.Warning)
                if btn == QMessageBox.Yes:
                    pass
                else: return
            else:
                self.createLog(detail)
        self.progressBar.setValue(0)
        qApp.processEvents()
        return True

    def getParticleNode(self):
        return pc.PyNode(pc.dynGlobals(a=True, q=True))

    def getParticleCacheDirectory(self):
        node = self.getParticleNode()
        if node.useParticleDiskCache.get():
            pfr = pc.workspace(fre='particles')
            pcp = pc.workspace(en=pfr)
            return osp.join(pcp, node.cd.get())

    def collectMCFIs(self):
        self.setStatus('Collecting mcfi files')
        qApp.processEvents()
        path = pc.workspace(en=pc.workspace(fre='diskCache'))
        targetPath = osp.join(self.rootPath, 'data')
        if path and osp.exists(path):
            files = os.listdir(path)
            count = 1
            self.progressBar.setMaximum(len(files))
            qApp.processEvents()
            for fl in files:
                fullPath = osp.join(path, fl)
                if osp.isfile(fullPath):
                    if osp.splitext(fullPath)[-1] == '.mcfi':
                        shutil.copy(fullPath, targetPath)
                self.progressBar.setValue(count)
                qApp.processEvents()
                count += 1
            self.progressBar.setValue(0)
            qApp.processEvents()

    def collectParticleCache(self):
        self.collectMCFIs()
        self.setStatus('Collecting particle cache...')
        qApp.processEvents()
        path = self.getParticleCacheDirectory()
        if path:
            particlePath = osp.join(self.rootPath, 'cache', 'particles')
            particleCachePath = osp.join(particlePath, osp.basename(path))
            os.mkdir(particleCachePath)
            files = os.listdir(path)
            if files:
                count = 1
                self.progressBar.setMaximum(len(files))
                errors = {}
                for phile in files:
                    fullPath = osp.join(path, phile)
                    try:
                        shutil.copy(fullPath, particleCachePath)
                    except Exception as ex:
                        errors[fullPath] = str(ex)
                    self.progressBar.setValue(count)
                    qApp.processEvents()
                    count += 1
                if errors:
                    detail = 'Could not collect following cache files'
                    for cPath in errors.keys():
                        detail += '\r\n\r\n'+cPath + '\r\nReason: '+ errors[cPath]
                    if self.isCurrentScene():
                        btn = msgBox.showMessage(self, title='Scene Bundle',
                                                 msg='Could not collect some of the particle cache files. '+
                                                 'This would result in loss of animation',
                                                 ques='Do you want to proceed?',
                                                 details=detail,
                                                 btns=QMessageBox.Yes|QMessageBox.No,
                                                 icon=QMessageBox.Warning)
                        if btn == QMessageBox.Yes:
                            pass
                        else: return
                    else:
                        self.createLog(detail)
                self.progressBar.setValue(0)
                self.setStatus('particle cache collected successfully')
                qApp.processEvents()
            else:
                self.setStatus('No particle cache found...')
        return True

    def copyRef(self):
        self.setStatus('copying references...')
        qApp.processEvents()
        c = 0
        self.progressBar.setMaximum(len(self.refNodes))
        if self.refNodes:
            refsPath = osp.join(self.rootPath, 'scenes', 'refs')
            os.mkdir(refsPath)
            errors = {}
            for ref in self.refNodes:
                try:
                    newPath = osp.join(refsPath, osp.basename(ref.path))
                    if osp.exists(osp.normpath(newPath)):
                        ref.replaceWith(newPath.replace('\\', '/'))
                        continue
                    shutil.copy(ref.path, refsPath)
                    ref.replaceWith(newPath.replace('\\', '/'))
                except Exception as ex:
                    errors[ref] = str(ex)
                c += 1
                self.progressBar.setValue(c)
                qApp.processEvents()
            self.progressBar.setValue(0)
            qApp.processEvents()
            if errors:
                detail = 'Could not copy following references\r\n'
                for node in errors:
                    detail += '\r\n'+ node.path + '\r\nReason: '+errors[node]
                if self.isCurrentScene():
                    btn = msgBox.showMessage(self, title='Scene Bundle',
                                             msg='Errors occured while copying references',
                                             ques='Do you want to proceed?',
                                             icon=QMessageBox.Warning,
                                             btns=QMessageBox.Yes|QMessageBox.No)
                    if btn == QMessageBox.Yes:
                        pass
                    else: return False
                else:
                    self.createLog(detail)
        self.progressBar.setValue(0)
        return True

    def importReferences(self):
        self.setStatus('importing references ...')
        qApp.processEvents()
        c=0
        self.progressBar.setMaximum(len(self.refNodes))
        errors = {}
        while self.refNodes:
            try:
                ref = self.refNodes.pop()
                if ref.parent() is None:
                    refPath = ref.path
                    ref.importContents()
                else:
                    self.refNodes.insert(0, ref)
            except Exception as e:
                errors[refPath] = str(e)
            c += 1
            self.progressBar.setValue(c)
        if errors:
            detail = 'Could not import following references\r\n'
            for node in errors:
                detail += '\r\n'+ node + '\r\nReason: '+errors[node]
            if self.isCurrentScene():
                btn = msgBox.showMessage(self, title='Scene Bundle',
                                            msg='Errors occured while importing references',
                                            ques='Do you want to proceed?',
                                            icon=QMessageBox.Warning,
                                            details=detail,
                                            btns=QMessageBox.Yes|QMessageBox.No)
                if btn == QMessageBox.Yes:
                    pass
                else:
                    return False
            else:
                self.createLog(detail)
        self.progressBar.setValue(0)
        return True

    def mapTextures(self):
        self.setStatus('Mapping collected textures...')
        qApp.processEvents()
        self.progressBar.setMaximum(len(self.texturesMapping))
        c = 0
        for node in self.texturesMapping:
            fullPath = osp.join(self.rootPath, self.texturesMapping[node]).replace('\\', '/')
            try:
                node.fileTextureName.set(fullPath)
            except AttributeError:
                node.filename.set(fullPath)
            except RuntimeError:
                pass
            c += 1
            self.progressBar.setValue(c)
            qApp.processEvents()
        self.progressBar.setValue(0)
        qApp.processEvents()
        


    def mapCache(self):
        self.setStatus('Mapping cache files...')
        qApp.processEvents()
        self.progressBar.setMaximum(len(self.cacheMapping))
        c = 0
        for node in self.cacheMapping:
            node.cachePath.set(osp.dirname(self.cacheMapping[node]), type="string")
            node.cacheName.set(osp.basename(self.cacheMapping[node]), type="string")
            c += 1
            self.progressBar.setValue(c)
            qApp.processEvents()
        self.progressBar.setValue(0)
        qApp.processEvents()

    def mapParticleCache(self):
        # no need to map particle cache
        # because we set the workspace
        # at the time of scene open
        pass

    def archive(self):
        archiver = arch.getFormats().values()[0]
        self.setStatus(
                'Creating Archive %s ...'%(self.rootPath+archiver.ext))
        try:
            arch.make_archive(self.rootPath, archiver.name,
                    progressBar=self.progressBar)
        except arch.ArchivingError as e:
            if self.isCurrentScene():
                msgBox.showMessage(self, title='Scene Bundle', msg=str(e),
                        icon=QMessageBox.Information)
            else:
                detail = "\nArchiving Error: " + str(e)
                self.createLog(detail)
            return False
        return True

    def exportScene(self):
        self.setStatus('Exporting scene...')
        qApp.processEvents()
        self.createScriptNode()
        scenePath = osp.join(self.rootPath, 'scenes', str(self.nameBox.text()))
        pc.exportAll(scenePath, type=cmds.file(q=True, type=True)[0],
                     f=True, pr=True)
        self.setStatus('Scene bundled successfully...')
        qApp.processEvents()

    def saveSceneAs(self, name=None):
        if not name:
            name = self.nameBox.text()
        self.setStatus('Saving Scene in New Location')
        qApp.processEvents()
        self.createScriptNode()
        scenePath = osp.join(self.rootPath, 'scenes', name)
        cmds.file(rename=scenePath)
        cmds.file(f=True, save=True, options="v=0;", type=cmds.file(q=True, type=True)[0])

    def submitToDeadline(self, name, project, episode, sequence, shot):
        ''' hello world '''
        ###############################################################################
        #                       configuring Deadline submitter                        #
        ###############################################################################
        self.progressBar.setMaximum(0)
        self.setStatus('configuring deadline submitter...')
        qApp.processEvents()
        try:
            subm = deadline.DeadlineBundleSubmitter(name, project, episode,
                    sequence, shot)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            detail = 'Deadline submission error: '+str(ex)
            if self.isCurrentScene():
                msgBox.showMessage(self, title='Scene Bundle',
                                   msg=str(detail), icon=QMessageBox.Information)
            else:
                self.createLog(detail)
            return False

        ###############################################################################
        #                                creating jobs                                #
        ###############################################################################
        self.setStatus('creating jobs ')
        qApp.processEvents()
        try:
            jobs = subm.createJobs()
        except Exception as e:
            import traceback
            traceback.print_exc()
            detail = "\nError in Creating Job"
            detail += "\n" + str(e)
            if self.isCurrentScene():
                msgBox.showMessage(self, title='Scene Bundle',
                            msg='Cannot create jobs to deadline\n' + str(e),
                            icon=QMessageBox.Information)
            else:
                self.createLog(detail)
            return False

        ###############################################################################
        #                           copying to directories                            #
        ###############################################################################
        self.progressBar.setMaximum(len(subm.project_paths))
        for pi, projectPath in enumerate(subm.project_paths):
            try:
                self.setStatus('copying %s to directory %s ...'%(
                    self.rootPath, projectPath))
                qApp.processEvents()
                shutil.copytree(cmds.workspace(q=1, rd=1), projectPath)
                self.progressBar.setValue(pi)
                qApp.processEvents()
            except Exception as e:
                import traceback
                traceback.print_exc()
                detail = "\nError in copying to directory" + projectPath
                detail += "\n" + str(e)
                if self.isCurrentScene():
                    msgBox.showMessage(self, title='Scene Bundle',
                                    msg='Cannot copy to rendering server\n'+str(e),
                                    icon=QMessageBox.Information)
                else:
                    self.createLog(detail)
                return False

        ###############################################################################
        #                               submitting jobs                               #
        ###############################################################################
        self.progressBar.setMaximum(len(jobs))
        self.setStatus('creating jobs ')
        qApp.processEvents()
        for ji, job in enumerate(jobs):
            self.setStatus('submitting job %d of %d' % (ji+1, len(jobs)))
            self.progressBar.setValue(ji)
            qApp.processEvents()
            try:
                job.submit()
            except Exception as e:
                import traceback
                traceback.print_exc()
                detail = "\nError in submitting Job" + job.jobInfo["Name"]
                detail += "\n" + str(e)
                if self.isCurrentScene() and False:
                    msgBox.showMessage(self, title='Scene Bundle',
                                        msg='Cannot submit Job ' + str(e),
                                        icon=QMessageBox.Information)
                else:
                    self.createLog(detail)
                return False
        self.progressBar.setValue(0)
        qApp.processEvents()
        return True

    def removeBundle(self):
        self.setStatus('Removing directory %s ...'%self.rootPath)
        try:
            shutil.rmtree(self.rootPath)
        except Exception as e:
            if self.isCurrentScene():
                msgBox.showMessage(self, title='Scene Bundle', msg=str(e),
                        icon=QMessageBox.Information)
            else:
                detail = "\nError in Removing Bundle:"
                detail = self.currentFileName() + '\r\n'*2 + detail
                self.createLog(detail)
            return False
        return True

    def showExceptionsWindow(self):
        Exceptions(self, self.textureExceptions).show()

    def addExceptions(self, paths):
        self.textureExceptions = paths

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
        addEventToBoxes(self.epBox, self.seqBox, self.shBox, self.epBox2, self.seqBox2, self.shBox2)

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
            iField.epBox.setCurrentIndex(self.getIndexOfBox(iField.epBox, self.epBox.currentText()))
            iField.seqBox.setCurrentIndex(self.getIndexOfBox(iField.seqBox, self.seqBox.currentText()))
            iField.shBox.setCurrentIndex(self.getIndexOfBox(iField.shBox, self.shBox.currentText()))

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
    def __init__(self, parent=None, name=None, path=None, ep=None, seq=None, sh=None):
        super(InputField, self).__init__(parent)
        self.setupUi(self)

        populateBoxes(self.epBox, self.seqBox, self.shBox)
        addEventToBoxes(self.epBox, self.seqBox, self.shBox, self.epBox2, self.seqBox2, self.shBox2)

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
        boxes = [self.epBox, self.seqBox, self.shBox, self.epBox2, self.seqBox2, self.shBox2, self.nameBox]
        map(lambda box: box.currentIndexChanged.connect(lambda: fillName(*boxes)), [self.epBox, self.seqBox, self.shBox])
        map(lambda box: box.textChanged.connect(lambda: fillName(*boxes)), [self.epBox2, self.seqBox2, self.shBox2])

        self.browseButton.clicked.connect(self.browseFolder)

    def closeEvent(self, event):
        self.deleteLater()
        del self

    def browseFolder(self):
        filename = QFileDialog.getSaveFileName(self, 'Select File', '', '*.ma *.mb')
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
        print index
        if index == -1:
            index = self.shBox.count() - 1
            print index
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
