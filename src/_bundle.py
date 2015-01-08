'''
Created on Nov 5, 2014

@author: qurban.ali
'''
import qtify_maya_window as qtfy
from uiContainer import uic
import msgBox
from PyQt4.QtGui import QMessageBox, QFileDialog, qApp, QIcon, QRegExpValidator
from PyQt4.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, QRegExp
import os.path as osp
import shutil
import os
import re
import subprocess
import _utilities as util
import pymel.core as pc
import maya.cmds as cmds
import appUsageApp
from . import _deadline as deadline
reload(deadline)

root_path = osp.dirname(osp.dirname(__file__))
ui_path = osp.join(root_path, 'ui')
ic_path = osp.join(root_path, 'icons')

_regexp = QRegExp('[a-zA-Z0-9_]*')
__validator__ = QRegExpValidator(_regexp)

mapFiles = util.mapFiles

Form, Base = uic.loadUiType(osp.join(ui_path, 'bundle.ui'))
class BundleMaker(Form, Base):
    def __init__(self, parent=qtfy.getMayaWindow()):
        super(BundleMaker, self).__init__(parent)
        self.setupUi(self)
        
        self.rootPath = None
        self.texturesMapping = {}
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
        
        self.progressBar.hide()
        
        path = osp.join(osp.expanduser('~'), 'scene_bundle_log')
        if not osp.exists(path):
            os.mkdir(path)
        self.logFilePath = osp.join(path, 'log.txt')

        appUsageApp.updateDatabase('sceneBundle')
        
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
        return script

    def closeEvent(self, event):
        self.closeLogFile()
        self.deleteLater()
        del self
        
    def isCurrentScene(self):
        return self.currentSceneButton.isChecked()
        
    def callCreateBundle(self):
        self.openLogFile()
        if not self.isCurrentScene():
            if not self.getPath():
                return
            total = self.filesBox.count()
            if total == 0:
                msgBox.showMessage(self, title='Scene Bundle',
                                   msg='No file added to the files box',
                                   icon=QMessageBox.Information)
                return
            
            for i in range(total):
                if len(self.filesBox.item(i).text().split(' | ')) < 2:
                    msgBox.showMessage(self, title='Scene Bundle',
                                       msg='Name not specified for the item',
                                       icon=QMessageBox.Information)
                    return
            for i in range(total):
                self.statusLabel.setText('Opening scene '+ str(i+1) +' of '+ str(total))
                item = self.filesBox.item(i)
                item.setBackground(Qt.gray)
                qApp.processEvents()
                name, filename = item.text().split(' | ')
                if osp.splitext(filename)[-1] in ['.ma', '.mb']:
                    cmds.file(filename, o=True, f=True, prompt=False)
                    self.createBundle(name)
        else:
            self.createBundle()
        self.closeLogFile()
        self.showLogFileMessage()
        
        #cmds.file(new=True, f=True)
        
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
                    subprocess.call(self.logFilePath, shell=True)
    
    def createLog(self, details):
        if self.logFile:
            self.logFile.write(details)
            self.logFile.write('\r\n'+'-'*100+'\r\n'*3)

    def createBundle(self, name=None):
        if cmds.file(q=True, modified=True) and self.isCurrentScene():
            msgBox.showMessage(self, title='Scene Bundle',
                               msg='Your scene contains unsaved changes, save them before proceeding',
                               icon=QMessageBox.Warning)
            return
        ws = pc.workspace(o=True, q=True)
        self.progressBar.show()
        self.bundleButton.setEnabled(False)
        qApp.processEvents()
        if self.createProjectFolder(name):
            pc.workspace(self.rootPath, o=True)
            if self.collectTextures():
                if self.collectReferences():
                    if self.collectCaches():
                        pc.workspace(ws, o=True)
                        if self.collectParticleCache():
                            pc.workspace(self.rootPath, o=True)
                            if self.copyRef():
                                self.mapTextures()
                                self.mapCache()
                                self.saveSceneAs(name)
                                if self.deadlineCheck.isChecked():
                                    self.submitToDeadline()
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
                return path
            else:
                msgBox.showMessage(self, title='Scene Bundle',
                                   msg='Specified path does not exist',
                                   icon=QMessageBox.Information)
        else:
            msgBox.showMessage(self, title='Scene Bundle',
                               msg='Path not specified',
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
        path = QFileDialog.getExistingDirectory(self, 'Select Folder', '')
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

    def getNiceName(self, nodeName):
        return nodeName.replace(':', '_').replace('|', '_')

    def getFileNodes(self):
        return pc.ls(type=['file', 'aiImage'])

    def getUDIMFiles(self, path):
        dirname = osp.dirname(path)
        if not osp.exists(dirname):
            return []
        fileName = osp.basename(path)
        try:
            first, byProduct, last = fileName.split('.')
        except:
            return []
        pattern = first +'\.\d+\.'+ last
        goodFiles = []
        fileNames = os.listdir(dirname)
        for fName in fileNames:
            if re.match(pattern, fName):
                goodFiles.append(osp.join(dirname, fName))
        return goodFiles
    
    def currentFileName(self):
        return cmds.file(location=True, q=True)

    def collectTextures(self):
        self.statusLabel.setText('Checking texture files...')
        textureFileNodes = self.getFileNodes()
        badTexturePaths = []
        for node in textureFileNodes:
            try:
                filePath = node.fileTextureName.get()
            except:
                filePath = node.filename.get()
            if filePath:
                if '<udim>' in filePath.lower():
                    fileNames = self.getUDIMFiles(filePath)
                    if not fileNames:
                        badTexturePaths.append(filePath)
                else:
                    if not osp.exists(filePath):
                        badTexturePaths.append(filePath)

        if badTexturePaths:
            detail = 'Following textures do not exist\r\n'
            for texture in badTexturePaths:
                detail += '\r\n'+ texture
            if self.isCurrentScene():
                btn = msgBox.showMessage(self, title='Scene Bundle',
                                         msg='Some textures used in the scene not found in the file system',
                                         ques='Do you want to proceed?',
                                         details=detail,
                                         icon=QMessageBox.Information,
                                         btns=QMessageBox.Yes|QMessageBox.No)
                if btn == QMessageBox.Yes:
                    pass
                else:
                    return
            else:
                detail = self.currentFileName() +'\r\n'*2 + detail
                self.createLog(detail)
        newName = 0
        self.statusLabel.setText('collecting textures...')
        qApp.processEvents()
        imagesPath = osp.join(self.rootPath, 'sourceImages')
        self.progressBar.setMaximum(len(textureFileNodes))
        for node in textureFileNodes:
            folderPath = osp.join(imagesPath, str(newName))
            relativePath = osp.join(osp.basename(imagesPath), str(newName))
            os.mkdir(folderPath)
            try:
                textureFilePath = node.fileTextureName.get()
            except AttributeError:
                textureFilePath = node.filename.get()
            if textureFilePath:
                if '<udim>' in textureFilePath.lower():
                    fileNames = self.getUDIMFiles(textureFilePath)
                    if fileNames:
                        for phile in fileNames:
                            shutil.copy(phile, folderPath)
                            self.copyTxFile(phile, folderPath)
                        relativeFilePath = osp.join(relativePath, re.sub('\.\d+\.', '.<udim>.', osp.basename(fileNames[0])))
                        self.texturesMapping[node] = relativeFilePath
                else:
                    if osp.exists(textureFilePath):
                        shutil.copy(textureFilePath, folderPath)
                        self.copyTxFile(textureFilePath, folderPath)
                        relativeFilePath = osp.join(relativePath, osp.basename(textureFilePath))
                        self.texturesMapping[node] = relativeFilePath
            newName = newName + 1
            self.progressBar.setValue(newName)
            qApp.processEvents()
        self.progressBar.setValue(0)
        qApp.processEvents()
        self.statusLabel.setText('All textures collected successfully...')
        qApp.processEvents()
        return True

    def copyTxFile(self, path, path2):
        directoryPath, ext = osp.splitext(path)
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
        self.statusLabel.setText('collecting references info...')
        refNodes = self.getRefNodes()
        self.progressBar.setMaximum(len(refNodes))
        if refNodes:
            c = 1
            badRefs = {}
            for ref in refNodes:
                try:
                    if ref.isLoaded():
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
                    detail = self.currentFileName() +'\r\n'*2 + detail
                    self.createLog(detail)
        else:
            self.statusLabel.setText('No references found in the scene...')
            qApp.processEvents()
        return True

    def getCacheNodes(self):
        return pc.ls(type=pc.nt.CacheFile)

    def collectCaches(self):
        self.statusLabel.setText('Prepering to collect cache files...')
        qApp.processEvents()
        cacheNodes = self.getCacheNodes()
        badCachePaths = []
        self.statusLabel.setText('checking cache files...')
        qApp.processEvents()
        for node in cacheNodes:
            files = node.getFileName()
            if files:
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
                detail = self.currentFileName() +'\r\n'*2 + detail
                self.createLog(detail)
        self.statusLabel.setText('collecting cache files...')
        qApp.processEvents()
        cacheFolder = osp.join(self.rootPath, 'cache')
        newName = 0
        self.progressBar.setMaximum(len(cacheNodes))
        errors = {}
        for node in cacheNodes:
            cacheFiles = node.getFileName()
            if cacheFiles:
                cacheXMLFilePath, cacheMCFilePath = cacheFiles
                newName = newName + 1
                relativePath = osp.join(osp.basename(cacheFolder), str(newName))
                folderPath = osp.join(cacheFolder, str(newName))
                os.mkdir(folderPath)
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
                                         btns=QMessageBox.Yes|QMessageBox.No,
                                         icon=QMessageBox.Warning)
                if btn == QMessageBox.Yes:
                    pass
                else: return
            else:
                detail = self.currentFileName() +'\r\n'*2 + detail
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
        self.statusLabel.setText('Collecting mcfi files')
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
        self.statusLabel.setText('Collecting particle cache...')
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
                        detail = self.currentFileName() +'\r\n'*2 + detail
                        self.createLog(detail)
                self.progressBar.setValue(0)
                self.statusLabel.setText('particle cache collected successfully')
                qApp.processEvents()
            else:
                self.statusLabel.setText('No particle cache found...')
        return True

    def copyRef(self):
        self.statusLabel.setText('copying references...')
        qApp.processEvents()
        c = 0
        self.progressBar.setMaximum(len(self.refNodes))
        if self.refNodes:
            refsPath = osp.join(self.rootPath, 'scenes', 'refs')
            os.mkdir(refsPath)
            errors = {}
            for ref in self.refNodes:
                try:
                    if osp.exists(osp.join(refsPath, osp.basename(ref.path))):
                        continue
                    shutil.copy(ref.path, refsPath)
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
                    detail = self.currentFileName() +'\r\n'*2 + detail
                    self.createLog(detail)
        return True

    def mapTextures(self):
        self.statusLabel.setText('Mapping collected textures...')
        qApp.processEvents()
        self.progressBar.setMaximum(len(self.texturesMapping))
        c = 0
        for node in self.texturesMapping:
            try:
                node.fileTextureName.set(self.texturesMapping[node])
            except AttributeError:
                node.filename.set(self.texturesMapping[node])
            c += 1
            self.progressBar.setValue(c)
            qApp.processEvents()
        self.progressBar.setValue(0)
        qApp.processEvents()


    def mapCache(self):
        self.statusLabel.setText('Mapping cache files...')
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

    def exportScene(self):
        self.statusLabel.setText('Exporting scene...')
        qApp.processEvents()
        self.createScriptNode()
        scenePath = osp.join(self.rootPath, 'scenes', str(self.nameBox.text()))
        pc.exportAll(scenePath, type=cmds.file(q=True, type=True)[0],
                     f=True, pr=True)
        self.statusLabel.setText('Scene bundled successfully...')
        qApp.processEvents()

    def saveSceneAs(self, name=None):
        if not name:
            name = self.nameBox.text()
        self.statusLabel.setText('Saving Scene in New Location')
        qApp.processEvents()
        self.createScriptNode()
        scenePath = osp.join(self.rootPath, 'scenes', name)
        cmds.file(rename=scenePath)
        cmds.file(f=True, save=True, options="v=0;", type=cmds.file(q=True, type=True)[0])
        self.statusLabel.setText('Scene bundled successfully...')
        qApp.processEvents()

    def submitToDeadline(self):
        deadline.initDeadline()
        deadline.openSubmissionWindow()

Form1, Base1 = uic.loadUiType(osp.join(ui_path, 'form.ui'))
class EditForm(Form1, Base1):
    def __init__(self, parent=None):
        super(EditForm, self).__init__(parent)
        self.setupUi(self)
        
        self.parentWin = parent
        self.inputFields = []
        
        self.populate()
        
        self.okButton.clicked.connect(self.ok)
        
    def populate(self):
        paths = self.parentWin.getPaths()
        for path in paths:
            name = ''
            if ' | ' in path:
                name, path = path.split(' | ')
            iField = InputField(self, name, path)
            self.itemsLayout.addWidget(iField)
            self.inputFields.append(iField)

    def ok(self):
        paths = []
        for iField in self.inputFields:
            name = iField.getName()
            path = iField.getPath()
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
            paths.append(name +' | '+ path)
        self.parentWin.setPaths(paths)
        self.accept()
        
        
Form2, Base2 = uic.loadUiType(osp.join(ui_path, 'input_field.ui'))
class InputField(Form2, Base2):
    def __init__(self, parent=None, name=None, path=None):
        super(InputField, self).__init__(parent)
        self.setupUi(self)
        
        if name:
            self.nameBox.setText(name)
        if path:
            self.pathBox.setText(path)
        
        self.nameBox.setValidator(__validator__)
        
        self.browseButton.clicked.connect(self.browseFolder)
    
    def closeEvent(self, event):
        self.deleteLater()
        del self
        
    def browseFolder(self):
        filename = QFileDialog.getSaveFileName(self, 'Select File', '', '*.ma *.mb')
        if filename:
            self.pathBox.setText(filename)
            
    def closeEvent(self, event):
        self.deleteLater()
        del self
        
    def setName(self, name):
        self.nameBox.setText(name)
        
    def setPath(self, path):
        self.pathBox.setText(path)
        
    def getName(self):
        return self.nameBox.text()
    
    def getPath(self):
        return self.pathBox.text()