'''
Created on Nov 5, 2014

@author: qurban.ali
'''
import site
site.addsitedir(r"R:\Pipe_Repo\Users\Qurban\utilities")
import qtify_maya_window as qtfy
from uiContainer import uic
import msgBox
from PyQt4.QtGui import QMessageBox, QFileDialog, qApp
import os.path as osp
import shutil
import os
import re
import shutil
import _utilities as util
import pymel.core as pc
import maya.cmds as cmds
import appUsageApp

root_path = osp.dirname(osp.dirname(__file__))
ui_path = osp.join(root_path, 'ui')

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
        
        self.bundleButton.clicked.connect(self.createBundle)
        self.browseButton.clicked.connect(self.browseFolder)
        self.nameBox.returnPressed.connect(self.createBundle)
        self.pathBox.returnPressed.connect(self.createBundle)
        
        self.progressBar.hide()
        
        appUsageApp.updateDatabase('sceneBundle')
        
    def createScriptNode(self):
        pc.scriptNode(st=2, bs=mapFiles, stp='python')
        
    def closeEvent(self, event):
        self.deleteLater()
        del self
        
    def createBundle(self):
        if cmds.file(q=True, modified=True):
            msgBox.showMessage(self, title='Scene Bundle',
                               msg='Your scene contains unsaved changes, save them before proceeding',
                               icon=QMessageBox.Warning)
            return
        ws = pc.workspace(o=True, q=True)
        self.progressBar.show()
        self.bundleButton.setEnabled(False)
        qApp.processEvents()
        modified = False
        if self.createProjectFolder():
            pc.workspace(self.rootPath, o=True)
            if self.collectTextures():
                if self.collectReferences():
                    if self.collectCaches():
                        pc.workspace(ws, o=True)
                        if self.collectParticleCache():
                            pc.workspace(self.rootPath, o=True)
                            if self.copyRef():
                                modified = True
                                self.mapTextures()
                                self.mapCache()
                                self.exportScene()
        self.progressBar.hide()
        self.bundleButton.setEnabled(True)
        #self.statusLabel.setText('')
        qApp.processEvents()
        pc.workspace(ws, o=True)
        if modified:
            btn = msgBox.showMessage(self, title='Scene Bundle',
                                     msg='Some changes were made to the scene, please don\'t save the scene and close it',
                                     ques='Do you want to close it now?',
                                     btns=QMessageBox.Yes|QMessageBox.No,
                                     icon=QMessageBox.Information)
            if btn == QMessageBox.Yes:
                cmds.file(new=True, force=True)
        
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
    
    def createProjectFolder(self):
        self.clearData()
        path = self.getPath()
        name = self.getName()
        if path and name:
            dest = osp.join(path, name)
            if osp.exists(dest):
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
            detail = 'Following textures do not exist\n'
            for texture in badTexturePaths:
                detail += '\n'+ texture
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
                detail = 'Following references can not be collected\n'
                for node in badRefs:
                    detail += '\n'+ node.path + '\nReason: '+ badRefs[node]
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
            detail = 'Following cache files not found\n'
            for phile in badCachePaths:
                detail += '\n'+ phile
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
                detail += '\n\n'+ cPath + '\nReason: '+ errors[cPath]
            btn = msgBox.showMessage(self, title='Scene Bundle',
                                     msg='Could not collect some of the cache files. '+
                                     'This would result in loss of animation',
                                     ques='Do you want to proceed?',
                                     btns=QMessageBox.Yes|QMessageBox.No,
                                     icon=QMessageBox.Warning)
            if btn == QMessageBox.Yes:
                pass
            else: return
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
        
    def collectParticleCache(self):
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
                    detail = 'Could not collect following cacha files'
                    for cPath in errors.keys():
                        detail += '\n\n'+cPath + '\nReason: '+ errors[cPath]
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
                detail = 'Could not copy following references\n'
                for node in errors:
                    detail += '\n'+ node.path + '\nReason: '+errors[node]
                btn = msgBox.showMessage(self, title='Scene Bundle',
                                         msg='Errors occured while copying references',
                                         ques='Do you want to proceed?',
                                         icon=QMessageBox.Warning,
                                         btns=QMessageBox.Yes|QMessageBox.No)
                if btn == QMessageBox.Yes:
                    pass
                else: return False
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