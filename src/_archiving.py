import shutil
import subprocess
import os
from collections import namedtuple, OrderedDict
try:
    from ._utilities import which
except:
    from _utilities import which
import logging
import zipfile

location_rar = which('Rar')
if not location_rar:
    location_rar = r"C:\Program Files\WinRAR\rar.exe"

location_7z = which('7z')
if not location_7z:
    location_7z = r"C:\Program Files\7-Zip\7z.exe"

Archiver = namedtuple('Archiver', ['name', 'ext', 'comp_levels'])

_formats = OrderedDict()
if os.path.exists(location_7z):
    sevenZ = Archiver('7z', '.7z', [0] + range(1, 10, 2))
    _formats['7z'] = sevenZ

if os.path.exists(location_rar):
    rar = Archiver('rar', '.rar', range(6))
    _formats['rar'] = rar

_formats['zip64'] = Archiver('zip64', '.zip', [1])
_formats['zip'] = Archiver('zip', '.7z', [1])
_formats['gztar'] = Archiver('gztar', '.tar.gz', [1])
_formats['bztar'] = Archiver('bztar', '.tar.gz', [1])


class ProgressHandler(logging.Handler):
    progress = None
    keyword = None

    def __init__(self, progress=None, maximum=1, keyword="adding", **kwargs):
        super(ProgressHandler, self).__init__(**kwargs)
        self.maximum = maximum
        self.value = 0
        self.keyword = keyword
        self.setProgress(progress)

    def setKeyword(self, keyword):
        self.keyword = keyword

    def setProgress(self, progress):
        self.progress = progress
        if progress:
            progress.setMaximum(self.maximum)
            progress.setValue(self.value)

    def emit(self, record):
        if not self.progress:
            return
        msg = self.format(record)
        if self.keyword and msg.startswith(self.keyword):
            self.step()

    def setMaximum(self, val):
        self.maximum = val
        if self.progress:
            self.progress.setMaximum(val)

    def setValue(self, val):
        self.value = val
        if val > self.maximum:
            self.value = self.maximum
        if self.progress:
            self.progress.setValue(self.value)

    def getPercentage(self, val):
        return self.value * 100.0 / self.maximum

    def step(self):
        self.setValue(self.value + 1)


def getFormats():
    return _formats


def countFiles(dirname):
    if not os.path.exists(dirname):
        return 0
    if not os.path.isdir(dirname):
        return 1
    numfiles = 0
    for dirpath, dirnames, filenames in os.walk(dirname):
        numfiles += len(filenames)
    return numfiles


def remove_file(dirname, ext):
    archive = dirname + ext
    if os.path.exists(archive):
        os.remove(archive)
    return archive


class ArchivingError(Exception):
    pass


def make_archive(dirname, format='7z', comp_level=1, progressBar=None):
    dirname = os.path.normpath(dirname)
    while dirname.endswith(os.sep):
        dirname = dirname[:-1]

    if not os.path.exists(dirname) or not os.path.isdir(dirname):
        raise ArchivingError("Directory is not valid")

    progressLogger = logging.getLogger(__name__ + ".Progress")
    map(progressLogger.removeHandler, progressLogger.handlers)
    progressHandler = ProgressHandler(
        progress=progressBar, maximum=countFiles(dirname))
    progressHandler.setFormatter(logging.Formatter('%(message)s'))
    progressLogger.addHandler(progressHandler)
    progressLogger.setLevel(logging.DEBUG)

    ext = _formats[format].ext
    levels = _formats[format].comp_levels
    if comp_level not in levels:
        raise ArchivingError("Unknown Compression level")

    try:
        archive = remove_file(dirname, ext)
    except Exception as e:
        raise ArchivingError("Cannot remove existing Archive %s " % archive +
                             str(e))
    if os.path.exists(archive):
        raise ArchivingError("Cannot remove existing Archive %s" % archive)

    try:
        if format in ['zip', 'bztar', 'gztar']:
            shutil.make_archive(
                dirname,
                format,
                os.path.dirname(dirname),
                dirname,
                logger=progressLogger)
        elif format == 'zip64':
            z = zipfile.ZipFile(
                archive,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                allowZip64=True)
            for path, dirs, files in os.walk(dirname):
                for filename in files:
                    filepath = os.path.join(path, filename)
                    z.write(filepath,
                            os.path.relpath(filepath,
                                            os.path.dirname(dirname)),
                            zipfile.ZIP_DEFLATED)
                    progressLogger.info("adding %s" % filepath)
        else:
            child = None
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            if format == 'rar':
                progressHandler.setKeyword("Adding")
                child = subprocess.Popen(
                    [
                        location_rar, "a",
                        "-m%d" % comp_level, "-ep1", archive, dirname
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    startupinfo=startupinfo)
                # stderr=subprocess.PIPE)
            elif format == '7z':
                progressHandler.setKeyword("Compressing")
                child = subprocess.Popen(
                    [
                        location_7z, "a", "-t7z",
                        "-mx=%d" % comp_level, archive, dirname
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    startupinfo=startupinfo)

            map(progressLogger.info, iter(child.stdout.readline, b''))

    except Exception as e:
        raise ArchivingError("Error Encountered during archiving: " + str(e))

    return archive


if __name__ == '__main__':
    dirname = r'D:\shared\alternate\SQ016_SH002_v07'
    format = getFormats()

    class prog(object):
        def setValue(self, val):
            print val

        def setMaximum(self, max):
            print max

    make_archive(dirname, 'zip64', progressBar=prog())
