import os
import os.path as osp
import logging
import abc
import sys
import types

_pc = None
bundleFormatter = logging.Formatter(
        fmt=('%(name)s : %(levelname)s : %(asctime)s : %(message)s :' +
        ' END_%(name)s' ))
loggerName = 'SCENE_BUNDLE'

isMaya = True
isMayaGUI = True
isMayaPy = True
isMayaBatch = True
mayaVersion = None
isMaya64 = None
try:
    import pymel.core as _pc
    if _pc.about(q=True, batch=True):
        _executable = osp.splitext(osp.basename(sys.executable))[0]
        isMayaGUI = False
        if _executable.lower() == 'mayapy':
            isMayaPy, isMayaBatch = True, False
        elif _executable.lower() == 'mayabatch':
            isMayaPy, isMayaBatch = False, True
    else:
        isMayaPy, isMayaBatch = False, False
    mayaVersion = _pc.about(v=True)
    isMaya64 = _pc.about(is64=True)
except ImportError:
    isMaya = False
    isMayaGUI = False
    isMayaPy = False
    isMayaBatch = False

class OnError(object):
    IGNORE    = 0b0000
    LOG       = 0b0001
    RAISE     = 0b0010
    ASK       = 0b0100
    EXIT      = 0b1000
    THROW     = RAISE
    QUIT      = EXIT
    LOG_RAISE = LOG | RAISE
    LOG_ASK   = LOG | ASK
    LOG_EXIT  = LOG | EXIT
    ALL = LOG | RAISE | ASK | EXIT

class BundleException(Exception):
    pass

class BaseBundleHandler(object):
    __metaclass__ = abc.ABCMeta
    onError = OnError.LOG

    @abc.abstractmethod
    def setProcess(self, desc):
        pass

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

    @abc.abstractmethod
    def done(self):
        pass

class ProgressLogHandler(BaseBundleHandler):
    _progressHandler = None
    errors = None
    warnings = None
    maxx = None
    value = None
    complete = None

    logKey = loggerName
    formatter = bundleFormatter

    def __init__(self, progressHandler=None):
        self.progressHandler = progressHandler

        path = osp.join(osp.expanduser('~'), 'scene_bundle_log')
        if not osp.exists(path):
            os.mkdir(path)
        self.logFilePath = osp.join(path, 'log.txt')

        self.logger = logging.getLogger( self.logKey )
        self.logger.setLevel( logging.INFO )
        self.logHandler = logging.FileHandler( self.logFilePath )
        self.logHandler.setFormatter( self.formatter )
        if not self.logger.handlers:
            self.logger.addHandler( self.logHandler )
        self.setMaximum(0)
        self.complete = False

        self.errors = []
        self.warnings = []

    def setProcess(self, process):
        ''':type desc: str'''
        if self.progressHandler:
            resp = self.progressHandler.setProcess(process)
            self.onError = resp or ( self.onError if resp is None else resp )
        self.process = process
        self.setMaximum(0)
        self.logger.info('Process : %s'%self.process)

    def setStatus(self, msg):
        self.status = msg
        self.logger.info('Status : %s : %s' % (self.process, msg))
        if self.progressHandler:
            self.progressHandler.setStatus(msg)

    def setMaximum(self, maxx):
        self.maxx = maxx
        if maxx > self.value:
            self.value = maxx
        if self.progressHandler:
            self.progressHandler.setMaximum(maxx)

    def setValue(self, val):
        self.value = val
        if self.maxx > 0:
            self.logger.info('Progress : %s : %s of %s' % (self.process, self.value,
                self.maxx))
        if self.progressHandler:
            self.progressHandler.setValue(val)

    def error(self,msg, exc_info=True):
        onError = self.onError
        self.errors.append(msg)
        if onError & OnError.LOG:
            self.logger.error(msg, exc_info=exc_info)
        if self.progressHandler:
            resp = self.progressHandler.error('%s : %s'%( self.process, msg ))
            onError = resp or onError
        if onError & OnError.RAISE:
            raise BundleException, msg
        if onError & OnError.EXIT:
            self.exit(1)

    def warning(self, msg):
        self.warnings.append('%s : %s'%( self.process, msg ))
        self.logger.warning(msg)
        if self.progressHandler:
            self.progressHandler.warning(msg)

    def step(self):
        if self.value < self.maxx:
            self.setValue(self.value+1)

    def done(self):
        self.complete = True
        self.logger.info('DONE')
        resp = 0
        if self.progressHandler:
            resp = self.progressHandler.done()
        onError = self.onError
        onError = resp or onError
        if onError & OnError.EXIT:
            self.exit()

    def exit(self, code=0):
        self.logger.info('Exit')
        sys.exit(code)

    @property
    def progressHandler(self):
        return self._progressHandler

    @progressHandler.setter
    def progressHandler(self, ph):
        if isinstance(ph, BaseBundleHandler) or all((
                hasattr(ph, fun) for fun in dir(BaseBundleHandler)
                if ( not fun.startswith('_') ) and type(
                    getattr(BaseBundleHandler, fun) == types.MethodType)
                and hasattr ( fun, '__isabstractmethod__' ) and
                fun.__isabstractmethod__ )):
            self._progressHandler = ph
        else:
            raise ( TypeError,
                    'progressHandler must be of type "BundleProgressHandler"' )

    @progressHandler.deleter
    def progressHandler(self):
        self._progressHandler = None

class BundleMakerHandler(ProgressLogHandler):
    def exit(self, code=0):
        self.logger.info('ExitMaya')
        # if pc.about(q=True, batch=True):
        if isMaya or not isMayaPy:
            _pc.quit(a=1, ec=code)
        else:
            sys.exit(code)

class BundleMakerBase(object):
    '''Base Bundle Maker Class Having all properties'''

    def __init__(self, progressHandler=None, path=None, filename=None,
            name=None, deadline=True, doArchive=False, delete=False,
            keepReferences=False, project=None, zdepth=None, sequence=None,
            episode=None, shot=None, open=True):
        ''':type progressHandler: BundleProgressHandler'''
        self.textureExceptions = []
        self.deadline = deadline
        self.doArchive = doArchive
        self.delete = delete
        self.keepReferences = keepReferences
        self.zdepth = zdepth
        self.path = path
        self.name = name
        self.project = project
        self.sequence = sequence
        self.episode = episode
        self.shot = shot
        self.filename = filename
        self.open = open
        self.setProgressHandler(progressHandler)

    def setProgressHandler(self, ph=None):
        self.status = ph

    @property
    def keepReferences(self):
        return self._keepReferences

    @keepReferences.setter
    def keepReferences(self, val):
        self._keepReferences = val

    @property
    def zdepth(self):
        return self._zdepth

    @zdepth.setter
    def zdepth(self, val):
        self._zdepth = val

    def getPath(self):
        return self._path
    def setPath(self, path):
        self._path = path
    path = property(fget=getPath, fset=setPath)

    def getName(self):
        return self._name
    def setName(self, name):
        self._name = name
    name = property(fget=getName, fset=setName)

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, fn):
        self._filename = fn

    @property
    def onError(self):
        if self.status:
            return self.status.onError
        else:
            return BaseBundleHandler.onError

    @onError.setter
    def onError(self, val):
        self.status.onError = val

    def addExceptions(self, paths):
        self._textureExceptions = paths[:]
    def getTextureExceptions(self):
        return self._textureExceptions[:]
    textureExceptions = property(fget=getTextureExceptions,
            fset=addExceptions)

    def clearData(self):
        self.textureExceptions = []

