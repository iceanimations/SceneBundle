import subprocess
import re
import os

from ._base import ( OnError, loggerName, BundleException, BundleMakerBase )

currentdir = os.path.dirname(os.path.abspath( __file__ ))
mayapyPaths = {
        '2014x64': r"C:\Program Files\Autodesk\Maya2014\bin\mayapy.exe",
        '2014x86': r"C:\Program Files (x86)\Autodesk\Maya2014\bin\mayapy.exe",
        '2015x64': r"C:\Program Files\Autodesk\Maya2015\bin\mayapy.exe",
        '2015x86': r"C:\Program Files (x86)\Autodesk\Maya2015\bin\mayapy.exe",
        '2016x64': r"C:\Program Files\Autodesk\Maya2016\bin\mayapy.exe",
        '2016x86': r"C:\Program Files (x86)\Autodesk\Maya2016\bin\mayapy.exe",
}

class BundleMakerProcess(BundleMakerBase):
    ''' Creates a bundle in a separate maya process by providing it appropriate
    data, parses output to give status '''
    process = None
    mayaversion = '2015x64'
    line = ''
    next_line = None
    resp = OnError.LOG

    # regular expressions for parsing output
    bundle_re = re.compile( r'\s*%s\s*:'%loggerName +
            '\s*(?P<level>[^\s]*)\s*:' +
            r'\s*(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}?)\s*:' +
            r'(?P<stuff>.*)')
    sentinel_re = re.compile(r'\s*:\s*(?P<sentinel>END_%s)' % loggerName)
    question_re = re.compile(
            r'\s*Question\s*:\s*(?P<question>.*)' + sentinel_re.pattern)
    progress_re = re.compile( '\s*Progress\s*:' +
            '\s*(?P<process>[^\s]*)\s*:\s*(?P<val>\d+)\s*of\s*(?P<maxx>\d+)\s*'
            + sentinel_re.pattern)
    error_re = re.compile( r'\s*(?P<msg>.*)\s*(' + sentinel_re.pattern + ')?\s*')
    warning_re = re.compile( r'\s*(?P<msg>.*)\s*'  + sentinel_re.pattern +
            '?\s*')
    process_re = re.compile( r'\s*Process\s*:\s*(?P<process>[^\s]*)\s*' +
            sentinel_re.pattern)
    status_re = re.compile( r'\s*Status\s*:\s*(?P<process>[^\s]*)\s*:' +
            r'\s*(?P<status>.*)\s*' + sentinel_re.pattern)
    done_re = re.compile( r'\s*DONE\s*' + sentinel_re.pattern)

    def createBundle(self, name=None, project=None, episode=None,
            sequence=None, shot=None):
        if name is None: name = self.name
        if project is None: project = self.project
        if episode is None: episode = self.episode
        if sequence is None: sequence = self.sequence
        if shot is None: shot = self.shot
        command = []
        command.append(mayapyPaths.get(self.mayaversion))
        command.append(os.path.dirname(currentdir))
        command.append(self.filename)
        command.extend(['-tp', self.path])
        command.extend(['-n', self.name])
        if self.keepReferences:
            command.append('-r')
        if self.archive:
            command.append('-a')
        if self.delete:
            command.extend(['-x'])
        if self.deadline:
            command.append('-d')
            command.extend(['-p', self.project])
            command.extend(['-ep', self.episode])
            command.extend(['-s', self.sequence])
            command.extend(['-t', self.shot])
        for exc in self.textureExceptions:
            command.extend(['-e', exc])
        command.extend(['-err', str( self.onError )])

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                startupinfo=startupinfo)
        self.communicate()

    def communicate(self):

        while self.process.poll() is None:
            for line in iter( self.process.stdout.readline, b''):
                self.line = line
                self._parseLine()
        retcode = self.process.returncode
        if retcode is None:
            self.status.error('Process Exited Prematurely')
        elif retcode != 0:
            self.status.error('Process Exited Prematurely: Exit Code %d' %
                    retcode)
            self.done()
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
        if _match: return _match
        _match = self._parseError(stuff, level)
        if _match: return _match
        _match = self._parseWarning(stuff, level)
        if _match: return _match
        _match = self._parseProcess(stuff, level)
        if _match: return _match
        _match = self._parseStatus(stuff, level)
        if _match: return _match
        _match = self._parseProgress(stuff, level)
        if _match: return _match
        _match = self._parseDone(stuff, level)
        if _match: return _match
        return match

    def killProcess(self):
        try: self.process.kill()
        except WindowsError: pass

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
                    else: error += self.line
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
                    else: warning += self.line
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
            maxx = int( match.group('maxx') )
            val = int( match.group('val' ))
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
