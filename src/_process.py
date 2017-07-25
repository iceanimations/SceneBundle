import subprocess
import re
import os
import time

from ._base import (OnError, loggerName, BundleException, BundleMakerBase,
                    mayaVersion, isMaya64)
import tempfile

currentdir = os.path.dirname(os.path.abspath(__file__))

mayaPathTemplate = r"C:\Program Files%(bits)s\Autodesk\Maya%(ver)s\bin\%(exe)s"


def getMayaPath(is64=True,
                ver='2015',
                exe='mayabatch',
                template=mayaPathTemplate):
    params = {
        'bits': '' if is64 else ' (x86)',
        'ver': str(ver),
        'exe': exe + '.exe'
    }
    return template % params


mayapyPaths = {(str(ver) + ('x64' if is64 else 'x86')): getMayaPath(
    is64, str(ver), 'mayapy')
               for ver in range(2010, 2018) for is64 in [True, False]}

mayabatchPaths = {(str(ver) + ('x64' if is64 else 'x86')): getMayaPath(
    is64, str(ver), 'mayabatch')
                  for ver in range(2010, 2018) for is64 in [True, False]}

mountCommand = '''
import sys
if sys.platform == 'win32':
    import subprocess
    proc = subprocess.Popen(r"\\ice-tactic\pipeline\mount\mount.bat",
                            shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    out, _ = proc.communicate()
    print (out)
'''

scriptStart = '''
import sys
s = r"%s"
sys.path.insert(0, s)
import sceneBundle
from sceneBundle import main
args = []
''' % os.path.dirname(os.path.dirname(currentdir))

scriptEnd = '''
bm = main(args=args)
'''


class BundleMakerProcess(BundleMakerBase):
    ''' Creates a bundle in a separate maya process by providing it appropriate
    data, parses output to give status '''
    process = None
    line = ''
    next_line = None
    resp = OnError.LOG

    # regular expressions for parsing output
    bundle_re = re.compile(
        r'\s*%s\s*:' % loggerName + '\s*(?P<level>[^\s]*)\s*:' +
        r'\s*(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}?)\s*:' +
        r'(?P<stuff>.*)')
    sentinel_re = re.compile(r'\s*:\s*(?P<sentinel>END_%s)' % loggerName)
    question_re = re.compile(r'\s*Question\s*:\s*(?P<question>.*)' +
                             sentinel_re.pattern)
    progress_re = re.compile(
        '\s*Progress\s*:' +
        '\s*(?P<process>[^\s]*)\s*:\s*(?P<val>\d+)\s*of\s*(?P<maxx>\d+)\s*' +
        sentinel_re.pattern)
    error_re = re.compile(r'\s*(?P<msg>.*)\s*(' + sentinel_re.pattern +
                          ')?\s*')
    warning_re = re.compile(r'\s*(?P<msg>.*)\s*' + sentinel_re.pattern +
                            '?\s*')
    process_re = re.compile(r'\s*Process\s*:\s*(?P<process>[^\s]*)\s*' +
                            sentinel_re.pattern)
    status_re = re.compile(r'\s*Status\s*:\s*(?P<process>[^\s]*)\s*:' +
                           r'\s*(?P<status>.*)\s*' + sentinel_re.pattern)
    done_re = re.compile(r'\s*DONE\s*' + sentinel_re.pattern)

    def __init__(self, *args, **kwargs):
        self.mayabatch = kwargs.pop('mayabatch', True)
        self.is64 = kwargs.pop('is64', isMaya64
                               if isMaya64 is not None else True)
        self.ver = kwargs.pop('version', mayaVersion
                              if mayaVersion else '2015')
        self.pythonFileName = None
        super(BundleMakerProcess, self).__init__(*args, **kwargs)

    @property
    def mayapyPath(self):
        return getMayaPath(is64=self.is64, ver=self.ver, exe='mayapy')

    @property
    def mayabatchPath(self):
        return getMayaPath(is64=self.is64, ver=self.ver, exe='mayabatch')

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
        if self.mayabatch:
            self._createByMayaBatch(
                name=name,
                project=project,
                episode=episode,
                sequence=sequence,
                shot=shot)
        else:
            self._createByMayaPy(
                name=name,
                project=project,
                episode=episode,
                sequence=sequence,
                shot=shot)

    def launchProcess(self, command):
        ''':type command: list'''
        self.status.setProcess('LaunchProcess')
        self.status.setStatus(
            'Launching Maya in Background while opening %s' % self.filename)

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            startupinfo=startupinfo)

    def writePyFile(self,
                    name=None,
                    project=None,
                    episode=None,
                    sequence=None,
                    shot=None,
                    pythonFileName=None):
        '''Write python file to disk'''
        if pythonFileName is None:
            if self.pythonFileName is None:
                self.setPythonFileName()
            pythonFileName = self.pythonFileName

        name = self.name if name is None else name
        project = self.project if project is None else project
        episode = self.episode if episode is None else episode
        sequence = self.sequence if sequence is None else sequence
        shot = self.shot if shot is None else shot

        with open(pythonFileName, 'w+') as pythonFile:
            pythonFile.write(mountCommand)
            pythonFile.write(scriptStart)
            pythonFile.write(
                'args.append(\"%s\")\n' % self.filename.replace('\\', '/'))
            pythonFile.write('args.append("-do")\n')
            pythonFile.write('args.append("-tp")\n')
            pythonFile.write(
                'args.append("%s")\n' % self.path.replace('\\', '/'))
            pythonFile.write('args.append("-n")\n')
            pythonFile.write('args.append("%s")\n' % name)
            if self.keepReferences:
                pythonFile.write('args.append("-r")\n')
            if self.archive:
                pythonFile.write('args.append("-a")\n')
            if self.delete:
                pythonFile.write('args.append("-x")\n')
            if self.deadline:
                pythonFile.write('args.append("-d")\n')
                pythonFile.write('args.append("-p")\n')
                pythonFile.write('args.append("%s")\n' % project)
                pythonFile.write('args.append("-ep")\n')
                pythonFile.write('args.append("%s")\n' % episode)
                pythonFile.write('args.append("-s")\n')
                pythonFile.write('args.append("%s")\n' % sequence)
                pythonFile.write('args.append("-t")\n')
                pythonFile.write('args.append("%s")\n' % shot)
            for exc in self.textureExceptions:
                pythonFile.write('args.append("-e")')
                pythonFile.write('args.append("%s")\n' % exc)
            pythonFile.write(scriptEnd)

    def setPythonFileName(self, filename=None):
        if filename is None:
            self.pythonFileName = tempfile.mktemp(
                prefix=time.strftime("%Y_%m_%d_%H_%M_%S",
                                     time.localtime()).replace(' ', '_'),
                suffix='.py')
        else:
            self.pythonFileName = filename

    def _createByMayaBatch(self,
                           name=None,
                           project=None,
                           episode=None,
                           sequence=None,
                           shot=None):
        name = self.name if name is None else name
        project = self.project if project is None else project
        episode = self.episode if episode is None else episode
        sequence = self.sequence if sequence is None else sequence
        shot = self.shot if shot is None else shot

        self.setPythonFileName()
        self.writePyFile()

        melcommand = (
            'eval( "python( \\"execfile( \\\\\\"' +
            self.pythonFileName.replace("\\", "/") + '\\\\\\" )\\" );");')

        command = []
        command.append(self.mayabatchPath)
        command.append('-file')
        command.append(self.filename)
        command.append('-command')
        command.append(melcommand)

        self.launchProcess(command)
        self.communicate()

    def _createByMayaPy(self,
                        name=None,
                        project=None,
                        episode=None,
                        sequence=None,
                        shot=None):
        name = self.name if name is None else name
        project = self.project if project is None else project
        episode = self.episode if episode is None else episode
        sequence = self.sequence if sequence is None else sequence
        shot = self.shot if shot is None else shot
        command = []
        command.append(self.mayapyPath)
        command.append(os.path.dirname(currentdir))
        command.append(self.filename)
        command.extend(['-tp', self.path])
        command.extend(['-n', name])
        if self.keepReferences:
            command.append('-r')
        if self.archive:
            command.append('-a')
        if self.delete:
            command.extend(['-x'])
        if self.deadline:
            command.append('-d')
            command.extend(['-p', project])
            command.extend(['-ep', episode])
            command.extend(['-s', sequence])
            command.extend(['-t', shot])
        for exc in self.textureExceptions:
            command.extend(['-e', exc])
        command.extend(['-err', str(self.onError)])

        self.launchProcess(command)
        self.communicate()

    def communicate(self):
        while self.process.poll() is None:
            for line in iter(self.process.stdout.readline, b''):
                self.line = line
                self._parseLine()
        retcode = self.process.returncode
        if retcode is None:
            self.status.error('Process Exited Prematurely')
        elif retcode != 0:
            self.status.error(
                'Process Exited Prematurely: Exit Code %d' % retcode)
            self.status.done()
        return

    def _parseLine(self, line=None):
        if line is None:
            line = self.line
        match = self.bundle_re.match(line)
        if match:
            stuff = match.group('stuff')
            level = match.group('level')
        else:
            return match
        _match = self._parseQuestion(stuff, level)
        if _match:
            return _match
        _match = self._parseError(stuff, level)
        if _match:
            return _match
        _match = self._parseWarning(stuff, level)
        if _match:
            return _match
        _match = self._parseProcess(stuff, level)
        if _match:
            return _match
        _match = self._parseStatus(stuff, level)
        if _match:
            return _match
        _match = self._parseProgress(stuff, level)
        if _match:
            return _match
        _match = self._parseDone(stuff, level)
        if _match:
            return _match
        return match

    def cleanup(self):
        return
        try:
            if self.pythonFileName:
                os.unlink(self.pythonFileName)
        except:
            pass

    def killProcess(self):
        try:
            self.process.kill()
        except WindowsError:
            pass
        self.cleanup()

    def _parseQuestion(self, line=None, level='INFO'):
        if line is None:
            line = self.line
        match = self.question_re.match(line)
        if match:
            if OnError.EXIT & self.onError:
                try:
                    self.killProcess()
                except WindowsError:
                    pass
            elif OnError.RAISE & self.onError:
                self.process.stdin.write('n\n')
            else:
                self.process.stdin.write('y\n')
        return match

    def _parseError(self, line=None, level='ERROR'):
        if level != 'ERROR':
            return
        if line is None:
            line = self.line
        match = self.error_re.match(line)
        if match:
            error = match.group('msg')
            _match = self.sentinel_re.search(self.line)
            if not _match:
                for self.line in iter(self.process.stdout.readline, b''):
                    _match = self.sentinel_re.search(self.line)
                    if _match:
                        error += self.sentinel_re.sub('', self.line)
                        break
                    else:
                        error += self.line
            try:
                self.status.error(error)
            except BundleException:
                self.killProcess()
                self.done()
        return match

    def _parseWarning(self, line=None, level='WARNING'):
        if level != 'WARNING':
            return
        if line is None:
            line = self.line
        match = self.warning_re.match(line)
        if match:
            warning = match.group('msg')
            _match = self.sentinel_re.search(self.line)
            if not _match:
                for self.line in iter(self.process.stdout.readline, b''):
                    _match = self.sentinel_re.search(self.line)
                    if _match:
                        warning += self.sentinel_re.sub('', self.line)
                        break
                    else:
                        warning += self.line
            self.status.warning(warning)
        return match

    def _parseProcess(self, line=None, level='INFO'):
        if line is None:
            line = self.line
        match = self.process_re.match(line)
        if match:
            process = match.group('process')
            self.status.setProcess(process)
        return match

    def _parseStatus(self, line=None, level='INFO'):
        if line is None:
            line = self.line
        match = self.status_re.match(line)
        if match:
            status = match.group('status')
            self.status.setStatus(status)
        return match

    def _parseProgress(self, line=None, level='INFO'):
        if line is None:
            line = self.line
        match = self.progress_re.match(line)
        if match:
            maxx = int(match.group('maxx'))
            val = int(match.group('val'))
            self.status.setMaximum(maxx)
            self.status.setValue(val)
        return match

    def _parseDone(self, line=None, level='INFO'):
        if line is None:
            line = self.line
            self.killProcess()
        match = self.done_re.match(line)
        if match:
            self.status.done()
        return match
