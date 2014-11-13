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
import pymel.core as pc
import msgBox

root_path = osp.dirname(osp.dirname(__file__))
ui_path = osp.join(root_path, 'ui')

Form, Base = uic.loadUiType(osp.join(ui_path, 'bundle.ui'))
class BundleMaker(Form, Base):
    def __init__(self, parent=qtfy.getMayaWindow()):
        super(BundleMaker, self).__init__(parent)
        self.setupUi(self)
        
        self.rootPath = None
        self.texturesMapping = {}
        
        self.bundleButton.clicked.connect(self.createProjectFolder)
        self.browseButton.clicked.connect(self.browseFolder)
        
    def closeEvent(self, event):
        self.deleteLater()
        
    def browseFolder(self):
        path = QFileDialog.getExistingDirectory(self, 'Select Folder', '')
        if path:
            self.pathBox.setText(path)
        
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
            
    def getName(self):
        name = str(self.nameBox.text())
        if name:
            return name
        else:
            msgBox.showMessage(self, title='Scene Bundle',
                               msg='Name not specified',
                               icon=QMessageBox.Information)
    
    def createProjectFolder(self):
        path = self.getPath()
        name = self.getName()
        if path and name:
            dest = osp.join(path, name)
            if osp.exists(dest):
                if not osp.isfile(dest):
                    files = os.listdir(dest)
                    if files:
                        btn = msgBox.showMessage(self, title='Scene Bundle',
                                                 msg='A directory already exists with the specified name at specified path and is not empty.'+
                                                 '\nPress Ok to proceed and clear the directory or press Cancel to stop the script',
                                                 btns=QMessageBox.Ok|QMessageBox.Cancel,
                                                 icon=QMessageBox.Warning)
                        if btn == QMessageBox.Ok:
                            errors = {}
                            for phile in files:
                                filePath = osp.join(dest, phile)
                                try:
                                    if osp.isfile(filePath):
                                        os.remove(filePath)
                                    else:
                                        shutil.rmtree(filePath)
                                except Exception as ex:
                                    errors[filePath] = str(ex)
                                try:
                                    os.remove(dest)
                                except Exception as ex:
                                    errors[dest] = str(ex)
                            if errors:
                                detail = 'Could not delete the following files'
                                for key, value in errors:
                                    detail += '\n\n'+key+'\nReason: '+value
                                msgBox.showMessage(self, title='Scene Bundle',
                                                    msg='Could not delete files',
                                                    icon=QMessageBox.Information,
                                                    details=detail)
                                return
                        else:
                            return
            src = r"R:\Pipe_Repo\Users\Qurban\templateProject"
            shutil.copytree(src, dest)
            self.rootPath = dest
            
    def getNiceName(self, nodeName):
        return nodeName.replace(':', '_').replace('|', '_')
            
    def getFileNodes(self):
        return pc.ls(type=['file', 'aiImage'])
    
    def getUDIMFiles(self, path):
        dirname = osp.dirname(path)
        fileName = osp.basename(path)
        first, byProduct, last = fileName.split('.')
        pattern = first +'\.\d+\.'+ last
        goodFiles = []
        fileNames = os.listdir(dirname)
        for fName in fileNames:
            if re.match(pattern, fName):
                goodFiles.append(osp.join(dirname, fName))
        return goodFiles


    def collectTextures(self):
        self.statusLabel.setText('Preperring to collect textures...')
        qApp.processEvents()
        for node in self.getFileNodes():
            origName = node.name()
            name = self.getNiceName(origName)
            if name != origName:
                pc.rename(node, name)
        self.statusLabel.setText('Creating folders and placing textures...')
        qApp.processEvents()
        imagesPath = osp.join(self.rootPath, 'sourceImages')
        badTexturePaths = []
        for node in self.getFileNodes():
            folderPath = osp.join(imagesPath, node.name())
            relativePath = osp.join(osp.basename(imagesPath), node.name())
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
                        relativeFilePath = osp.join(relativePath, re.sub('\.\d+\.', '.<UDIM>.', osp.basename(fileNames[0])))
                        self.texturesMapping[node] = relativeFilePath
                    else:
                        badTexturePaths.append(textureFilePath)
                else:
                    if osp.exists(textureFilePath):
                        shutil.copy(textureFilePath, folderPath)
                        relativeFilePath = osp.join(relativePath, osp.basename(textureFilePath))
                        self.texturesMapping[node] = relativeFilePath
                    else:
                        badTexturePaths.append(textureFilePath)
        if badTexturePaths:
            detail = 'Following textures does not exist\n'
            for texture in badTexturePaths:
                detail += '\n'+ texture
            btn = msgBox.showMessage(self, title='Scene Bundle',
                                     msg='Some textures used in the scene not found in the file system',
                                     ques='Do you want to proceed?',
                                     details=detail,
                                     icon=QMessageBox.Information,
                                     btns=QMessageBox.Yes|QMessageBox.No)
            if btn == QMessageBox.Yes:
                self.collectReferences()
            else:
                return
    
    def collectReferences(self):
        