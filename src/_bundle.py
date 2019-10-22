'''Contains the core BundleMaker class'''

import os
import os.path as osp
import re
import shutil
import glob

# maya libs
import pymel.core as pc
import maya.cmds as cmds

# local libraries
import imaya
import iutil

# relative imports
from . import _archiving as arch
from . import _deadline as deadline
from . import _utilities as util
from ._base import BundleMakerBase, OnError, BundleMakerHandler

reload(imaya)
reload(iutil)
reload(arch)
reload(util)
reload(deadline)

MAX_PATH_LENGTH = 256
mapFiles = util.mapFiles


class BundleMaker(BundleMakerBase):
    '''Bundle Maker class containing all functions'''

    def __init__(self, *args, **kwargs):
        ''':type progressHandler: BundleProgressHandler'''
        self.status = BundleMakerHandler()
        super(BundleMaker, self).__init__(*args, **kwargs)

        self.textureExceptions = []
        self.rootPath = None
        self.texturesMapping = {}
        self.collectedTextures = {}
        self.collectedProxies = {}
        self.refNodes = []
        self.cacheMapping = {}
        self.paths = []
        self.copiedFiles = []
        self.seq_size_limit = 300L * 1024 * 1024

    def setProgressHandler(self, ph=None):
        self.status.progressHandler = ph

    def _restoreAttribute(attrName):
        def _decorator(method):
            def _wrapper(self, *args, **kwargs):
                ret = None
                val = getattr(self, attrName)
                try:
                    ret = method(self, *args, **kwargs)
                finally:
                    setattr(self, attrName, val)
                return ret

            return _wrapper

        return _decorator

    @property
    def errors(self):
        return self.status.errors

    @property
    def warnings(self):
        return self.status.warnings

    @property
    def logFilePath(self):
        return self.status.logFilePath

    def createScriptNode(self):
        '''Creates a unique script node which remap file in bundles scripts'''
        self.status.setProcess('CreateScriptNode')
        self.status.setMaximum(0)
        self.status.setValue(0)
        script = None
        try:
            script = filter(
                lambda x: (
                    x.st.get() == 1 and x.stp.get() == 1 and
                    x.before.get().strip().startswith('#ICE_BundleScript')),
                pc.ls('ICE_BundleScript', type='script'))[0]
        except IndexError:
            sceneLoadScripts = filter(
                lambda x: (
                    x.st.get() in [1, 2] and x.stp.get() == 1 and
                    x.before.get().strip().startswith(
                        'import pymel.core as pc') and
                    not x.after.get()),
                pc.ls('script*', type='script'))
            if sceneLoadScripts:
                script = sceneLoadScripts[0]

        if script:
            script.before.set(mapFiles)
            script.st.set(1)
            script.rename('ICE_BundleScript')
        else:
            script = pc.scriptNode(
                name='ICE_BundleScript', st=1, bs=mapFiles, stp='python')
        try:
            util.createReconnectAiAOVScript()
        except Exception as e:
            self.status.warning('cannot create reconnect script: %s' % e)

        return script

    @_restoreAttribute('onError')
    def openFile(self, filename=None):
        self.status.setProcess('FileOpen')
        self.status.setMaximum(0)
        self.status.setValue(0)
        self.onError = OnError.LOG_RAISE
        if filename is None:
            filename = self.filename
        self.status.setStatus('Opening File %s for bundling!' % self.filename)
        try:
            if not os.path.exists(filename):
                raise RuntimeError('File Does Not Exist')
            imaya.openFile(self.filename)
        except RuntimeError as e:
            self.status.error('Cannot Open File %s ... %s' % (filename,
                                                              str(e)))

    def copyfile(self, file_, folder):
        path = osp.relpath(
            osp.normpath(osp.join(folder, osp.basename(file_))),
            start=self.rootPath)
        shutil.copy(file_, folder)
        self.copiedFiles.append(os.path.normpath(path))

    def closeFile(self):
        self.status.setProcess('CloseFile')
        self.status.setStatus('Closing File ...')
        imaya.newScene()

    def createBundle(self,
                     name=None,
                     project=None,
                     episode=None,
                     sequence=None,
                     shot=None):
        if name is None:
            name = self.name
        if project is None:
            project = self.project
        if episode is None:
            episode = self.episode
        if sequence is None:
            sequence = self.sequence
        if shot is None:
            shot = self.shot
        self.status.setProcess('CreateBundle')
        self.status.setMaximum(0)
        self.status.setValue(0)
        ws = pc.workspace(o=True, q=True)
        if self.open:
            self.openFile()
        if self.createProjectFolder(name):
            if self.deadline:
                if self.zdepth:
                    util.turnZdepthOn()
            pc.workspace(self.rootPath, o=True)
            if self.collectTextures():
                if self.collectRedshiftProxies():
                    if self.collectRedshiftSpritesNMaps():
                        if self.collectReferences():
                            if self.collectCaches():
                                pc.workspace(ws, o=True)
                                if self.collectParticleCache():
                                    pc.workspace(self.rootPath, o=True)
                                    self.mapTextures()
                                    self.mapCache()
                                    if self.keepReferences:
                                        if not self.copyRef():
                                            return
                                    else:
                                        if not self.importReferences():
                                            return
                                    self.saveSceneAs(name)
                                    if self.doArchive:
                                        self.archive()
                                    if self.deadline:
                                        self.submitToDeadline(
                                            name, project, episode, sequence,
                                            shot)
                                    if self.delete:
                                        self.deleteCacheNodes()
                                        self.closeFile()
                                        self.removeBundle()
                                    self.status.setStatus(
                                        'Scene bundled successfully!')
                                    self.status.done()
        pc.workspace(ws, o=True)

    def deleteCacheNodes(self):
        pc.delete(pc.ls(type=['cacheFile', 'RedshiftProxyMesh']))

    def createProjectFolder(self, name=None):
        self.clearData()
        path = self.path
        if name is None:
            name = self.getName()
        if path and name:
            try:
                dest = osp.join(path, name)
                if osp.exists(dest):
                    count = 1
                    dest += '(' + str(count) + ')'
                    while 1:
                        if not osp.exists(dest):
                            break
                        dest = dest.replace('(' + str(count) + ')',
                                            '(' + str(count + 1) + ')')
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
        if not path:
            return []
        dirname = osp.dirname(path)
        if not osp.exists(dirname):
            return []
        fileName = osp.basename(path)
        first, last = None, None
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

        if first is None or last is None:
            return []

        pattern = first + '\d+' + last
        goodFiles = []
        fileNames = os.listdir(dirname)
        for fName in fileNames:
            if re.match(pattern, fName,
                        re.I if os.name == 'nt' else 0):
                goodFiles.append(osp.join(dirname, fName))
        return goodFiles

    def currentFileName(self):
        return cmds.file(location=True, q=True)

    @_restoreAttribute('onError')
    def collectTextures(self):
        self.status.setProcess('CollectTextures')
        self.status.setStatus('Checking texture files ...')
        textureFileNodes = self.getFileNodes()
        badTexturePaths = []

        self.status.setMaximum(0)
        self.status.setValue(0)
        for node in textureFileNodes:
            try:
                filePath = imaya.readPathAttr(node.fileTextureName)
            except:
                filePath = imaya.readPathAttr(node.filename)

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
                    badTexturePaths.append('Could not unlock: %s: %s' %
                                           (filePath, ex))

        if badTexturePaths:
            detail = ('Some textures do not exist or could not unlock a '
                      'locked attribute\r\n')
            for texture in badTexturePaths:
                detail += '\r\n' + texture
            self.status.error(detail)

        newName = 0
        count = 0
        self.status.setStatus('collecting textures ...')
        imagesPath = osp.join(self.rootPath, 'sourceImages')
        self.status.setMaximum(len(textureFileNodes))
        self.status.setValue(0)
        for node in textureFileNodes:
            count += 1
            folderPath = osp.join(imagesPath, str(newName))
            relativePath = osp.join(osp.basename(imagesPath), str(newName))
            if not osp.exists(folderPath):
                os.mkdir(folderPath)
            try:
                textureFilePath = imaya.getFullpathFromAttr(
                    node.fileTextureName)
            except AttributeError:
                textureFilePath = imaya.getFullpathFromAttr(node.filename)
            if textureFilePath:
                try:
                    if node.useFrameExtension.get():
                        path = imaya.readPathAttr(node.fileTextureName)
                        if util.getSequenceSize(path) > self.seq_size_limit:
                            util.addExceptionAttr(node)
                            continue
                except AttributeError:
                    pass
                if not self.isTextureException(textureFilePath):
                    if textureFilePath not in self.collectedTextures.keys():
                        util.removeExceptionAttr(node)
                        if ('<udim>' in textureFilePath.lower()
                                or '<f>' in textureFilePath.lower()):
                            fileNames = self.getUDIMFiles(textureFilePath)
                            if fileNames:
                                for phile in fileNames:
                                    self.copyfile(phile, folderPath)
                                    self.copyRSFile(phile, folderPath)
                                match = re.search('(?i)<udim>',
                                                  textureFilePath)
                                if match:
                                    relativeFilePath = osp.join(
                                        relativePath,
                                        re.sub('1\d{3}',
                                               match.group(),
                                               osp.basename(fileNames[0])))
                                else:
                                    relativeFilePath = osp.join(
                                        relativePath,
                                        re.sub('\d{3,}', '<f>',
                                               osp.basename(fileNames[0])))
                                relativeFilePath = relativeFilePath.replace(
                                    '\\', '/')
                                self.texturesMapping[node] = relativeFilePath
                            else:
                                continue
                        else:
                            if osp.exists(textureFilePath):
                                self.copyfile(textureFilePath, folderPath)
                                self.copyRSFile(textureFilePath, folderPath)
                                relativeFilePath = osp.join(
                                    relativePath,
                                    osp.basename(textureFilePath))
                                self.texturesMapping[node] = relativeFilePath
                            else:
                                continue
                        self.collectedTextures[
                            textureFilePath] = relativeFilePath
                    else:
                        self.texturesMapping[node] = self.collectedTextures[
                            textureFilePath]
                        continue
                else:
                    util.addExceptionAttr(node)
                    continue
            else:
                continue
            newName = newName + 1
            self.status.setValue(count)
        self.status.setMaximum(0)
        self.status.setStatus('All textures collected successfully ...')
        return True

    def collectRedshiftProxies(self):
        if not self.keepProxies:
            try:
                nodes = pc.ls(type='RedshiftProxyMesh')
            except AttributeError:
                return True
            if nodes:
                badPaths = []
                for node in nodes:
                    try:
                        path = node.computerFileNamePattern.get()
                    except AttributeError:
                        path = node.fileName.get()
                    if not util.getSequence(path) and not osp.exists(path):
                        badPaths.append(path)
                if badPaths:
                    detail = ('Could not find following proxy files\r\n' +
                              '\r\n'.join(badPaths))
                    self.status.error(detail)
                self.status.setProcess('CollectRedshiftProxies')
                self.status.setStatus('Collecting Redshift Proxies ...')
                nodesLen = len(nodes)
                proxyPath = osp.join(self.rootPath, 'proxies')
                if not osp.exists(proxyPath):
                    os.mkdir(proxyPath)
                self.status.setMaximum(nodesLen)
                self.status.setValue(0)
                self.collectedProxies = {}
                for i, node in enumerate(nodes):
                    newProxyPath = self.collectOneRSProxy(node, i, proxyPath)
                    if not newProxyPath: continue
                    newProxyPath = os.path.realpath(newProxyPath)
                    if newProxyPath:
                        node.fileName.set(newProxyPath)
                    self.status.setValue(i + 1)
                self.status.setMaximum(0)
        return True

    def isTextureException(self, path):
        path = osp.normcase(osp.normpath(path))
        for _path in self.textureExceptions:
            if path == osp.normcase(osp.normpath(_path)):
                return True
        return False

    def collectOneRSProxy(self, node, num, bundleProxyDir):
        '''Given a proxy node copy the proxy pointed to and its textures to
        appropriate locations within the given bundleProxyDir'''

        try:
            path = node.computedFileNamePattern.get()
        except AttributeError:
            path = node.fileName.get()

        _path = osp.normcase(osp.normpath(path))
        if _path.startswith('\\\\') or _path.startswith('//'):
            return
        if _path in self.collectedProxies:
            return self.collectedProxies[_path]

        sequence = util.getSequence(path)

        if not sequence and not osp.exists(path):
            return path

        path = osp.normpath(path)
        dirname = osp.dirname(path)
        basename = osp.basename(path)

        if self.isTextureException(dirname):
            util.addExceptionAttr(node)
            return path

        # get base context ( = process)
        rank = 999
        process = ''
        process_candidates = ['shaded', 'model', 'rig', 'texture']
        for candidate in process_candidates:
            try:
                index = dirname.split(os.sep).index(candidate)
                if index < rank:  # and candidate in basename.split('_'):
                    process = candidate
                    rank = index
            except ValueError:
                pass

        # asset_name, asset_dir and rel_dir
        asset_name = basename
        asset_name = re.sub('[._]?#+.*$', '', asset_name)
        asset_name = re.sub('[._]?v\d+.*$', '', asset_name)
        asset_name = re.sub('_?' + process + '.*$', '', asset_name)
        if not asset_name:
            asset_name = str(num)
        asset_dir = dirname

        if process and rank > 0:
            asset_name = dirname.split(os.sep)[rank - 1]
            asset_dir = os.sep.join(dirname.split(os.sep)[:rank])
        rel_dir = osp.relpath(dirname, asset_dir)

        new_asset_dir = osp.join(bundleProxyDir, asset_name)
        if not osp.exists(new_asset_dir):
            iutil.mkdir(bundleProxyDir, asset_name)

        # if this is a shaded proxy we need to find and copy its textures
        if process == 'shaded':
            rel_texture_dir = os.sep.join(['texture'] +
                                          rel_dir.split(os.sep)[1:])
            texture_dir = osp.join(asset_dir, rel_texture_dir)
            if osp.exists(texture_dir):
                # make texture directory
                new_texture_dir = osp.join(new_asset_dir, rel_texture_dir)
                if not osp.exists(new_texture_dir):
                    iutil.mkdir(new_asset_dir, rel_texture_dir)
                # find files
                files = [
                    osp.join(texture_dir, file_)
                    for file_ in os.listdir(texture_dir)
                    if osp.isfile(osp.join(texture_dir, file_)) and
                    not file_.endswith('.link') and not file_.startswith('.')
                ]
                # copy over
                for file_ in files:
                    self.copyfile(file_, new_texture_dir)

        # copy co-existing textures
        files = [
            phile for phile in os.listdir(dirname)
            if osp.splitext(phile)[-1] in [
                '.jpg', '.png', '.tga', '.tiff', '.tif', '.bmp', '.rsmap',
                '.jpeg'
            ]
        ]

        # make proxy dir
        new_proxy_dir = osp.join(new_asset_dir, rel_dir)
        if not osp.exists(new_proxy_dir):
            iutil.mkdir(new_asset_dir, rel_dir)

        # copy textures
        for phile in files:
            try:
                self.copyfile(osp.join(dirname, phile), new_proxy_dir)
            except:
                pass

        # copy the actual proxy
        if sequence:
            for path in sequence:
                self.copyfile(path, new_proxy_dir)
        else:
            self.copyfile(path, new_proxy_dir)

        new_path = osp.join(new_proxy_dir, basename)
        self.collectedProxies[_path] = new_path

        return new_path

    def collectRedshiftSpritesNMaps(self):
        self.status.setProcess('CollectRedshiftSpritesNMaps')
        self.status.setStatus('Collecting Redshift Sprites and Normal maps')
        self.status.setMaximum(0)
        self.status.setValue(0)
        try:
            nodes = pc.ls(exactType=['RedshiftSprite', 'RedshiftNormalMap'])
        except AttributeError:
            return True

        udim_map = {}
        if nodes:
            badPaths = []
            for node in nodes:
                path = node.tex0.get()
                udims = self.getUDIMFiles(path)
                if path and udims:
                    udim_map[path] = udims
                if path and not osp.exists(path) and not udims:
                    badPaths.append(path)

            if badPaths:
                detail = (
                    'Could not find following Redshift Sprite Textures\r\n' +
                    '\r\n'.join(badPaths))
                self.status.error(detail)

            self.status.setStatus('Collecting Redshift Sprite Textures ...')
            nodeLen = len(nodes)
            texturePath = osp.join(self.rootPath, 'spriteTextures')
            if not osp.exists(texturePath):
                os.mkdir(texturePath)
            self.status.setMaximum(nodeLen)
            self.status.setValue(0)

            for i, node in enumerate(nodes):
                path = node.tex0.get()
                if not path:
                    continue
                newPath = osp.join(texturePath, str(i))
                if not osp.exists(newPath):
                    os.mkdir(newPath)

                files = []
                if path and osp.exists(path) and osp.isfile(path):
                    if node.useFrameExtension.get():
                        parts = osp.basename(path).split('.')
                        if len(parts) == 3:
                            for phile in os.listdir(osp.dirname(path)):
                                if re.match(parts[0] + '\.\d+\.' + parts[2],
                                            phile,
                                            re.I if os.name == 'nt' else 0):
                                    files.append(
                                        osp.join(osp.dirname(path), phile))
                            if not files:
                                files.append(path)
                        else:
                            files.append(path)
                    else:
                        files.append(path)
                else:
                    files.extend(udim_map.get(path, []))

                if files:
                    for phile in files:
                        self.copyfile(phile, newPath)
                    if path:
                        node.tex0.set(osp.join(newPath, osp.basename(path)))
                    else:
                        node.tex0.set(
                            osp.join(newPath, osp.basename(files[0])))

                self.status.setValue(i + 1)

        self.status.setMaximum(0)
        return True

    def copyRSFile(self, path, path2):
        directoryPath, ext = osp.splitext(path)
        directoryPath += '.rstexbin'
        if osp.exists(directoryPath):
            self.copyfile(directoryPath, path2)
        directoryPath += '.tx'
        if osp.exists(directoryPath):
            self.copyfile(directoryPath, path2)

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
        self.status.setProcess('CollectReferences')
        self.status.setStatus('collecting references info ...')
        refNodes = self.getRefNodes()
        self.status.setMaximum(len(refNodes))
        self.status.setValue(0)
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
                self.status.setValue(c)
                c += 1
            self.status.setMaximum(0)
            if badRefs:
                detail = 'Following references can not be collected\r\n'
                for node in badRefs:
                    detail += (
                        '\r\n' + node.path + '\r\nReason: ' + badRefs[node])
                # self.createLog(detail)
                self.status.error(detail, exc_info=False)
        else:
            self.status.setStatus('No references found in the scene ...')
        return True

    def getCacheNodes(self):
        return pc.ls(type=pc.nt.CacheFile)

    def collectCaches(self):
        self.status.setProcess('CollectCaches')
        self.status.setStatus('Prepering to collect cache files ...')
        self.status.setMaximum(0)
        self.status.setValue(0)
        cacheNodes = self.getCacheNodes()

        badCachePaths = []
        self.status.setStatus('checking cache files ...')
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
                detail += '\r\n' + phile
            # self.createLog(detail)
            self.status.error(detail, exc_info=False)

        self.status.setStatus('collecting cache files ...')
        cacheFolder = osp.join(self.rootPath, 'data')
        newName = 0
        self.status.setMaximum(len(cacheNodes))
        self.status.setValue(0)
        errors = {}

        for node in cacheNodes:
            cacheFiles = node.getFileName()
            if cacheFiles:
                if len(cacheFiles) != 2:
                    continue
                cacheXMLFilePath, cacheMCFilePath = cacheFiles
                newName = newName + 1
                folderPath = cacheFolder
                try:
                    self.copyfile(cacheXMLFilePath, folderPath)
                    self.copyfile(cacheMCFilePath, folderPath)
                except Exception as ex:
                    errors[osp.splitext(cacheMCFilePath)[0]] = str(ex)
                self.cacheMapping[node] = osp.join(
                    folderPath, osp.splitext(osp.basename(cacheMCFilePath))[0])
                self.status.setValue(newName)

        if errors:
            detail = 'Could not collect following cache files'
            for cPath in errors.keys():
                detail += '\r\n\r\n' + cPath + '\r\nReason: ' + errors[cPath]
            # self.createLog(detail)
            self.status.errors(detail)

        self.status.setMaximum(0)
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
        self.status.setProcess('CollectMCFIs')
        self.status.setStatus('Collecting mcfi files ...')
        path = pc.workspace(en=pc.workspace(fre='diskCache'))
        targetPath = osp.join(self.rootPath, 'data')
        if path and osp.exists(path):
            files = os.listdir(path)
            count = 1
            self.status.setMaximum(len(files))
            self.status.setValue(0)
            for fl in files:
                fullPath = osp.join(path, fl)
                if osp.isfile(fullPath):
                    if osp.splitext(fullPath)[-1] == '.mcfi':
                        self.copyfile(fullPath, targetPath)
                self.status.setValue(count)
                count += 1
            self.status.setMaximum(0)

    def collectParticleCache(self):
        self.collectMCFIs()
        self.status.setProcess('CollectParticleCache')
        self.status.setStatus('Collecting particle cache ...')

        path = self.getParticleCacheDirectory()
        if path and osp.exists(path):
            particlePath = osp.join(self.rootPath, 'cache', 'particles')
            particleCachePath = osp.join(particlePath, osp.basename(path))
            os.mkdir(particleCachePath)
            files = os.listdir(path)
            if files:
                count = 1
                self.status.setMaximum(len(files))
                self.status.setValue(0)
                errors = {}
                for phile in files:
                    fullPath = osp.join(path, phile)
                    try:
                        self.copyfile(fullPath, particleCachePath)
                    except Exception as ex:
                        errors[fullPath] = str(ex)
                    self.status.setValue(count)
                    count += 1
                if errors:
                    detail = 'Could not collect following cache files'
                    for cPath in errors.keys():
                        detail += ('\r\n\r\n' + cPath + '\r\nReason: ' +
                                   errors[cPath])
                    self.status.error(detail)

                self.status.setMaximum(0)
                self.status.setStatus('particle cache collected successfully')
            else:
                self.status.setStatus('No particle cache found!')
        return True

    def copyRef(self):
        self.status.setProcess('CopyRef')
        self.status.setStatus('copying references ...')

        c = 0
        self.status.setMaximum(len(self.refNodes))
        self.status.setValue(0)

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
                    self.copyfile(ref.path, refsPath)
                    ref.replaceWith(newPath.replace('\\', '/'))
                except Exception as ex:
                    errors[ref] = str(ex)
                c += 1
                self.status.setValue(c)

            if errors:
                detail = 'Could not copy following references\r\n'
                for node in errors:
                    detail += (
                        '\r\n' + node.path + '\r\nReason: ' + errors[node])
                self.status.error(detail)

        self.status.setMaximum(0)
        return True

    def importReferences(self):
        self.status.setProcess('ImportReferences')
        self.status.setStatus('importing references ...')
        c = 0
        self.status.setMaximum(len(self.refNodes))
        self.status.setValue(0)
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
            self.status.setValue(c)
        if errors:
            detail = 'Could not import following references\r\n'
            for node in errors:
                detail += '\r\n' + node + '\r\nReason: ' + errors[node]
            # self.createLog(detail)
            self.status.error(detail)
        self.status.setMaximum(0)
        return True

    def mapTextures(self):
        self.status.setProcess('MapTextures')
        self.status.setStatus('Mapping collected textures ...')
        self.status.setMaximum(len(self.texturesMapping))
        self.status.setValue(0)
        c = 0
        for node in self.texturesMapping:
            fullPath = osp.join(self.rootPath,
                                self.texturesMapping[node]).replace('\\', '/')
            sequence = False
            try:
                if node.useFrameExtension.get():
                    node.useFrameExtension.set(0)
                    sequence = True
                if '<f>' in fullPath:
                    globs = glob.glob(fullPath.replace('<f>', '*'))
                    if globs:
                        fullPath = globs[0]
                    else:
                        fullPath = fullPath.replace('<f>', '12345')
                colorSpace = node.colorSpace.get()
                node.fileTextureName.set(fullPath)
                node.colorSpace.set(colorSpace)
                if sequence:
                    node.useFrameExtension.set(1)
            except AttributeError:
                node.filename.set(fullPath)
            except RuntimeError:
                pass
            c += 1
            self.status.setValue(c)
        self.status.setMaximum(0)

    def mapCache(self):
        self.status.setProcess('MapCache')
        self.status.setStatus('Mapping cache files ...')
        self.status.setMaximum(len(self.cacheMapping))
        self.status.setValue(0)
        c = 0
        for node in self.cacheMapping:
            node.cachePath.set(
                osp.dirname(self.cacheMapping[node]), type="string")
            node.cacheName.set(
                osp.basename(self.cacheMapping[node]), type="string")
            c += 1
            self.status.setValue(c)
        self.status.setMaximum(0)

    def mapParticleCache(self):
        # no need to map particle cache
        # because we set the workspace
        # at the time of scene open
        pass

    def archive(self):
        self.status.setProcess('Archive')
        archiver = arch.getFormats().values()[0]
        self.status.setStatus('Creating Archive %s ...' %
                              (self.rootPath + archiver.ext))
        try:
            arch.make_archive(
                self.rootPath, archiver.name, progressBar=self.progressHandler)
        except arch.ArchivingError as e:
            detail = "\nArchiving Error: " + str(e)
            self.status.error(detail, exc_info=True)
            return False
        return True

    def exportScene(self):
        self.status.setStatus('ExportScene')
        self.status.setStatus('Exporting scene ...')
        self.createScriptNode()
        scenePath = osp.join(self.rootPath, 'scenes', str(self.nameBox.text()))
        pc.exportAll(
            scenePath, type=cmds.file(q=True, type=True)[0], f=True, pr=True)
        self.status.setStatus('Scene bundled successfully ...')

    def saveSceneAs(self, name=None):
        self.status.setProcess('SaveSceneAs')
        self.status.setMaximum(0)
        self.status.setValue(0)
        name = self.name
        self.status.setStatus('Saving Scene in New Location')
        self.createScriptNode()
        scenePath = osp.join(self.rootPath, 'scenes', name)
        cmds.file(rename=scenePath)
        cmds.file(
            f=True,
            save=True,
            options="v=0;",
            type=cmds.file(q=True, type=True)[0])
        self.status.setStatus('Scene Saved to location: %s' % scenePath)

    @_restoreAttribute('onError')
    def submitToDeadline(self, name, project, episode, sequence, shot):
        ''' Submit Scene to Deadline '''
        #######################################################################
        #               configuring Deadline submitter                        #
        #######################################################################
        self.status.setProcess('SubmitToDeadline')
        self.status.setMaximum(0)
        self.status.setStatus('configuring deadline submitter ...')
        self.onError = OnError.LOG_RAISE
        try:
            subm = deadline.DeadlineBundleSubmitter(name, project, episode,
                                                    sequence, shot)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            detail = 'Deadline submission error: ' + str(ex)
            # self.createLog(detail)
            self.onError |= OnError.RAISE
            self.status.error(detail)
            return False

        #######################################################################
        #                        creating jobs                                #
        #######################################################################
        self.status.setStatus('creating jobs ')
        try:
            jobs = subm.createJobs()
        except Exception as e:
            import traceback
            traceback.print_exc()
            detail = "\nError in Creating Job"
            detail += "\n" + str(e)
            self.onError |= OnError.RAISE
            self.status.error(detail, exc_info=True)
            return False

        #######################################################################
        #                   copying to directories                            #
        #######################################################################
        self.status.setMaximum(len(subm.project_paths))
        self.status.setValue(0)
        for pi, projectPath in enumerate(subm.project_paths):
            try:
                self.status.setStatus('copying %s to directory %s ...' %
                                      (self.rootPath, projectPath))
                shutil.copytree(cmds.workspace(q=1, rd=1), projectPath)
                self.status.setValue(pi)
            except Exception as e:
                import traceback
                traceback.print_exc()
                detail = "\nError in copying to directory" + projectPath
                if self.copiedFiles:
                    lengths = [len(x) for x in self.copiedFiles]
                    max_len = max(lengths)
                    if len(projectPath) + max_len > MAX_PATH_LENGTH:
                        detail += "\nNAMES ARE TOO LONG"
                detail += "\n" + str(e)
                self.onError |= OnError.RAISE
                self.status.error(detail, exc_info=True)
                return False
        self.status.setMaximum(0)

        #######################################################################
        #                       submitting jobs                               #
        #######################################################################
        self.status.setStatus('creating jobs ')
        self.status.setMaximum(len(jobs))
        self.status.setValue(0)
        for ji, job in enumerate(jobs):
            self.status.setStatus('submitting job %d of %d' % (ji + 1,
                                                               len(jobs)))
            self.status.setValue(ji)
            try:
                job.submit()
            except Exception as e:
                import traceback
                traceback.print_exc()
                detail = "\nError in submitting Job" + job.jobInfo["Name"]
                detail += "\n" + str(e)
                self.onError |= OnError.RAISE
                self.status.error(detail, exc_info=True)
                return False
        self.status.setMaximum(0)
        return True

    def removeBundle(self):
        self.status.setProcess('RemoveBundle')
        self.status.setStatus('Removing directory %s ...' % self.rootPath)
        self.status.setMaximum(0)
        self.status.setValue(0)
        try:
            shutil.rmtree(self.rootPath)
        except Exception as e:
            detail = "\r\nError in Removing Bundle: " + str(e)
            detail = self.currentFileName() + '\r\n' * 2 + detail
            self.status.error(detail, exc_info=True)
            return False
        return True
