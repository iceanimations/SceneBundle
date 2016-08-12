import pymel.core as pc
import maya.cmds as cmds

import os
import os.path as osp
import re
import shutil
import abc
import types

import logging

# local libraries
import imaya
reload(imaya)
import iutil
reload(iutil)

# relative imports
from . import _archiving as arch
reload(arch)
from . import _deadline as deadline
reload(deadline)
from . import _utilities as util
reload(util)

mapFiles = util.mapFiles

class BundleProgressHandler(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def setStatus(self, msg):
        pass

    @abc.abstractmethod
    def setMaximum(self, maxx):
        pass

    @abc.abstractmethod
    def setValue(self, val):
        pass

    @abc.abstractmethod
    def error(self, msg):
        pass

    @abc.abstractmethod
    def warning(self, msg):
        pass

class _ProgressLogHandler(BundleProgressHandler):
    _progressHandler = None
    errors = None
    warnings = None

    maxx = None
    value = None

    def __init__(self, progressHandler=None):
        self.progressHandler = progressHandler

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logHandler = logging.FileHandler(self.logFilePath)
        self.logger.addHandler(self.logHandler)

        self.errors = []
        self.warnings = []

        path = osp.join(osp.expanduser('~'), 'scene_bundle_log')
        if not osp.exists(path):
            os.mkdir(path)
        self.logFilePath = osp.join(path, 'log.txt')

    def setStatus(self, msg):
        self.status = msg
        self.logger.info(msg)
        if self.progressHandler:
            self.progressHandler.setStatus(msg)

    def setMaximum(self, maxx):
        self.maxx = maxx
        if self.progressHandler:
            self.progressHandler.setMaximum(maxx)

    def setValue(self, val):
        self.value = val
        if self.maxx > 0:
            self.logger.info('%s of %s' % (self.value, self.maxx))
        if self.progressHandler:
            self.progressHandler.setValue()

    def error(self, msg, exc_info=True):
        self.errors.append(msg)
        self.logger.error(msg)
        if self.progressHandler:
            self.progressHandler.error(msg)

    def warning(self, msg):
        self.warnings.append(msg)
        self.logger.warning(msg)
        if self.progressHandler:
            self.progressHandler.warning(msg)

    def step(self):
        if self.value < self.maxx:
            self.setValue(self.value+1)

    @property
    def progressHandler(self):
        return self._progressHandler

    @progressHandler.setter
    def progressHandler(self, ph):
        if isinstance(ph, BundleProgressHandler) or all((
            hasattr(ph, fun) for fun in dir(BundleProgressHandler)
            if ( not fun.startswith('_') ) and type(
                getattr(BundleProgressHandler, fun) == types.MethodType)
            )):
            self._progressHandler = ph
        else:
            raise TypeError,\
                    'progressHandler must be of type "BundleProgressHandler"'

    @progressHandler.deleter
    def progressHandler(self):
        self._progressHandler = None

class BundleMaker(object):
    '''Bundle Maker class containing all functions'''

    def __init__(self, progressHandler=None, path=None):
        ''':type progressHandler: BundleProgressHandler'''
        self.textureExceptions = []
        self.rootPath = None
        self.texturesMapping = {}
        self.collectedTextures = {}
        self.refNodes = []
        self.cacheMapping = {}
        self.status = _ProgressLogHandler(progressHandler)

        self.deadline = True
        self.archive = False
        self.delete = False

        self.path = path

        self.paths = []
        self.name = []
        self.pro = None
        self.seq = None
        self.ep = None
        self.shot = None

    def setProgressHandler(self, ph=None):
        if not ph:
            del self._progressLogHandler.progressHandler
        else:
            self._progressLogHandler.progressHandler = ph

    @property
    def errors(self):
        return self.status.errors

    @property
    def warnings(self):
        return self.status.warnings

    @property
    def logFilePath(self):
        return self.status.logFilePath

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
            self.status.warning('cannot create reconnect script: %s' % e)

        return script

    def createBundle(self, name=None, project=None, ep=None, seq=None, sh=None):
        ws = pc.workspace(o=True, q=True)
        if self.createProjectFolder(name):
            if self.deadlineCheck.isChecked():
                if self.zdepthButton.isChecked():
                    util.turnZdepthOn()
            pc.workspace(self.rootPath, o=True)
            if self.collectTextures():
                if self.collectRedshiftProxies():
                    if self.collectRedshiftSprites():
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
                                        self.status.setStatus('Closing scene ...')
                                        cmds.file(new=True, f=True)
                                    if not self.keepBundleButton.isChecked():
                                        self.deleteCacheNodes()
                                        self.status.setStatus('removing bundle ...')
                                        self.removeBundle()
                                    self.status.setStatus('Scene bundled successfully...')
        pc.workspace(ws, o=True)

    def deleteCacheNodes(self):
        pc.delete(pc.ls(type=['cacheFile', pc.nt.RedshiftProxyMesh]))

    def getPath(self):
        return self._path
    def setPath(self, path):
        self._path = path
    path = property(fget=getPath, fset=setPath)

    def createProjectFolder(self, name=None):
        self.clearData()
        path = self.getPath()
        if not name:
            name = self.getName()
        if path and name:
            try:
                dest = osp.join(path, name)
                if osp.exists(dest):
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
            except Exception as e:
                self.status.error('Cannot Create Project Folder: %s' % e)
        else:
            self.status.error('No Path Found')

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
        self.status.setStatus('Checking texture files...')
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
                    badTexturePaths.append('Could not unlock: %s: %s' %(
                        filePath, ex ))

        if badTexturePaths:
            detail = 'Following textures do not exist or could not unlock a locked attribute\r\n'
            for texture in badTexturePaths:
                detail += '\r\n'+ texture
            self.status.error(detail)

        newName = 0
        self.status.setStatus('collecting textures...')
        imagesPath = osp.join(self.rootPath, 'sourceImages')
        self.status.setMaximum(len(textureFileNodes))
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
            self.status.setValue(newName)
        self.status.setValue(0)
        self.status.setStatus('All textures collected successfully...')
        return True

    def collectRedshiftProxies(self):
        try:
            nodes = pc.ls(type=pc.nt.RedshiftProxyMesh)
        except AttributeError:
            return True
        if nodes:
            badPaths = []
            for node in nodes:
                path = node.fileName.get()
                if not osp.exists(path):
                    badPaths.append(path)
            if badPaths:
                detail = 'Could not find following proxy files\r\n'+'\r\n'.join(badPaths)
                self.status.error(details)
            self.setStatus('Collecting Redshift Proxies...')
            nodesLen = len(nodes)
            proxyPath = osp.join(self.rootPath, 'proxies')
            if not osp.exists(proxyPath):
                os.mkdir(proxyPath)
            self.status.setMaximum(nodesLen)
            for i, node in enumerate(nodes):
                path = node.fileName.get()
                if osp.basename(osp.dirname(path)) == 'low_res':
                    lowRes = True
                    mainPath = iutil.dirname(path, 3)
                else:
                    lowRes = False
                    mainPath = iutil.dirname(path, 2)
                assetName = osp.basename(mainPath)
                texturePath = osp.join(mainPath, 'texture')
                if lowRes:
                    texturePath = osp.join(texturePath, 'low_res')
                assetPath = osp.join(proxyPath, assetName)
                if not osp.exists(assetPath):
                    os.mkdir(assetPath)
                relPath = osp.dirname(osp.relpath(path, mainPath))
                iutil.mkdir(assetPath, relPath)
                newProxyPath = osp.join(assetPath, relPath)
                newTexturePath = osp.join(assetPath, 'texture')
                if lowRes: newTexturePath = osp.join(newTexturePath, 'low_res')
                if osp.exists(path):
                    if not osp.exists(osp.join(newProxyPath, osp.basename(path))):
                        shutil.copy(path, newProxyPath)
                        if osp.exists(texturePath):
                            iutil.mkdir(assetPath, 'texture' if not lowRes else osp.join('texture', 'low_res'))
                            files = [osp.join(texturePath, phile) for phile in os.listdir(texturePath) if osp.isfile(osp.join(texturePath, phile)) and not phile.endswith('.link')]
                            for phile in files:
                                shutil.copy(phile, newTexturePath)
                    node.fileName.set(osp.join(newProxyPath, osp.basename(path)))
                self.status.setValue(i+1)
                qApp.processEvents()
            self.setValue(0)
        return True

    def collectRedshiftSprites(self):
        try:
            nodes = pc.ls(exactType=pc.nt.RedshiftSprite)
        except AttributeError:
            return True
        if nodes:
            badPaths = []
            for node in nodes:
                path = node.tex0.get()
                if not osp.exists(path):
                    badPaths.append(path)
            if badPaths:
                detail = 'Could not find following Redshift Sprite Textures\r\n'+'\r\n'.join(badPaths)
                if self.isCurrentScene():
                    btn = msgBox.showMessage(self, title='Scene Bundle',
                                             msg='Some Redshift Sprite Textures not found in the file system',
                                             ques='Do you want to continue?',
                                             details=detail,
                                             icon=QMessageBox.Warning,
                                             btns=QMessageBox.Yes|QMessageBox.No)
                    if btn == QMessageBox.No: return False
                else:
                    self.createLog(detail)
            self.setStatus('Collecting Redshift Sprite Textures...')
            nodeLen = len(nodes)
            texturePath = osp.join(self.rootPath, 'spriteTextures')
            if not osp.exists(texturePath):
                os.mkdir(texturePath)
            self.setMaximum(nodeLen)
            qApp.processEvents()
            for i, node in enumerate(nodes):
                newPath = osp.join(texturePath, str(i))
                if not osp.exists(newPath):
                    os.mkdir(newPath)
                path = node.tex0.get()
                if osp.exists(path) and osp.isfile(path):
                    files = []
                    if node.useFrameExtension.get():
                        parts = osp.basename(path).split('.')
                        if len(parts) == 3:
                            for phile in os.listdir(osp.dirname(path)):
                                if re.match(parts[0]+'\.\d+\.'+parts[2], phile):
                                    files.append(osp.join(osp.dirname(path), phile))
                            if not files:
                                files.append(path)
                        else:
                            files.append(path)
                    else:
                        files.append(path)
                    if files:
                        for phile in files:
                            shutil.copy(phile, newPath)
                        node.tex0.set(osp.join(newPath, osp.basename(files[0])))
                self.setValue(i+1)
                qApp.processEvents()
        self.setValue(0)
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
        self.setMaximum(len(refNodes))
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
                self.setValue(c)
                qApp.processEvents()
                c += 1
            self.setValue(0)
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
                    if btn == QMessageBox.Yes:
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
        self.setMaximum(len(cacheNodes))
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
                self.setValue(newName)
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
        self.setValue(0)
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
            self.setMaximum(len(files))
            qApp.processEvents()
            for fl in files:
                fullPath = osp.join(path, fl)
                if osp.isfile(fullPath):
                    if osp.splitext(fullPath)[-1] == '.mcfi':
                        shutil.copy(fullPath, targetPath)
                self.setValue(count)
                qApp.processEvents()
                count += 1
            self.setValue(0)
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
                self.setMaximum(len(files))
                errors = {}
                for phile in files:
                    fullPath = osp.join(path, phile)
                    try:
                        shutil.copy(fullPath, particleCachePath)
                    except Exception as ex:
                        errors[fullPath] = str(ex)
                    self.setValue(count)
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
                self.setValue(0)
                self.setStatus('particle cache collected successfully')
                qApp.processEvents()
            else:
                self.setStatus('No particle cache found...')
        return True

    def copyRef(self):
        self.setStatus('copying references...')
        qApp.processEvents()
        c = 0
        self.setMaximum(len(self.refNodes))
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
                self.setValue(c)
                qApp.processEvents()
            self.setValue(0)
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
        self.setValue(0)
        return True

    def importReferences(self):
        self.setStatus('importing references ...')
        qApp.processEvents()
        c=0
        self.setMaximum(len(self.refNodes))
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
            self.setValue(c)
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
        self.setValue(0)
        return True

    def mapTextures(self):
        self.setStatus('Mapping collected textures...')
        qApp.processEvents()
        self.setMaximum(len(self.texturesMapping))
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
            self.setValue(c)
            qApp.processEvents()
        self.setValue(0)
        qApp.processEvents()

    def mapCache(self):
        self.setStatus('Mapping cache files...')
        qApp.processEvents()
        self.setMaximum(len(self.cacheMapping))
        c = 0
        for node in self.cacheMapping:
            node.cachePath.set(osp.dirname(self.cacheMapping[node]), type="string")
            node.cacheName.set(osp.basename(self.cacheMapping[node]), type="string")
            c += 1
            self.setValue(c)
            qApp.processEvents()
        self.setValue(0)
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
                    progressBar=self.progressHandler)
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
        self.setMaximum(0)
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
        self.setMaximum(len(subm.project_paths))
        for pi, projectPath in enumerate(subm.project_paths):
            try:
                self.setStatus('copying %s to directory %s ...'%(
                    self.rootPath, projectPath))
                qApp.processEvents()
                shutil.copytree(cmds.workspace(q=1, rd=1), projectPath)
                self.setValue(pi)
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
        self.setMaximum(len(jobs))
        self.setStatus('creating jobs ')
        qApp.processEvents()
        for ji, job in enumerate(jobs):
            self.setStatus('submitting job %d of %d' % (ji+1, len(jobs)))
            self.setValue(ji)
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
        self.setValue(0)
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
                detail = "\r\nError in Removing Bundle: "+ str(e)
                detail = self.currentFileName() + '\r\n'*2 + detail
                self.createLog(detail)
            return False
        return True

    def addExceptions(self, paths):
        self.textureExceptions = paths[:]

