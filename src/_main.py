import argparse
import tempfile
import sys
import logging

sys.path.insert(0, '.')
from _bundle import ( BundleMaker, OnError, bundleFormatter, loggerName )

class CondAction(argparse._StoreTrueAction):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        x = kwargs.pop('to_be_required', [])
        super(CondAction, self).__init__(option_strings, dest, **kwargs)
        self.make_required = x

    def __call__(self, parser, namespace, values, option_string=None):
        for x in self.make_required:
            x.required = True
        try:
            return super(CondAction, self).__call__(parser, namespace, values,
                    option_string)
        except NotImplementedError:
            pass

def build_parser():
    parser = argparse.ArgumentParser(
        description='''Bundles the given maya scene and submits the job to
        deadline if required''', prefix_chars="-+", fromfile_prefix_chars="@")
    parser.add_argument('filename', help='maya file for bundling')
    parser.add_argument('-a', '--archive', action='store_true',
            help='create an archive from the bundle')
    parser.add_argument('-x', '--delete', action='store_true',
            help='delete the bundle after operation')
    parser.add_argument('-r', '--keepReferences', action='store_true',
            help="don't import references copy them in")
    parser.add_argument('-z', '--zdepth', action='store_true',
            help="turn zdepth render layer on")
    proArg = parser.add_argument('-p', '--project')
    epArg = parser.add_argument('-ep', '--episode')
    seqArg = parser.add_argument('-s', '--sequence')
    shotArg = parser.add_argument('-t', '--shot')
    parser.add_argument('-d', '--deadline', action=CondAction,
            to_be_required=[proArg, epArg, seqArg, shotArg],
            help='send the bundle to deadline')
    parser.add_argument('-e', '--addException', action='append',
            help='''Paths where bundle will not collect and remap textures''')
    parser.add_argument('-n', '--name', default='bundle',
            help="name of the folder where the scene bundle will be created")
    parser.add_argument('-tp', '--tempPath',
            help='folder where to create the bundle',
            default=tempfile.gettempdir())
    parser.add_argument('-i', '--infile', type=argparse.FileType('r'),
            default=sys.stdin)
    parser.add_argument('-o', '--outfile', type=argparse.FileType('w'),
            default=sys.stdout)
    return parser

def bundleMain( bm=None, args=None ):
    parser = build_parser()
    args = parser.parse_args( args )
    if bm is None:
        bm = BundleMaker()
    mainLogHandler = logging.StreamHandler(args.outfile)
    mainLogHandler.setLevel(logging.INFO)
    mainLogHandler.setFormatter(bundleFormatter)
    bundleLogger = logging.getLogger(loggerName)
    bundleLogger.addHandler(mainLogHandler)
    bm.filename = args.filename
    bm.archive = args.archive
    bm.delete = args.delete
    bm.keepReferences = args.keepReferences
    bm.zdepth = args.zdepth
    bm.project = args.project
    bm.episode = args.episode
    bm.sequence = args.sequence
    bm.shot = args.shot
    bm.deadline = args.deadline
    bm.name = args.name
    bm.path = args.tempPath
    if args.addException:
        bm.addExceptions( args.addException )
    bm.openFile()
    bm.createBundle()
    bundleLogger.removeHandler(mainLogHandler)
    return bm

if __name__ == "__main__":
    parser = build_parser()
    parser.print_help()
    namespace, _ = parser.parse_known_args([r'd:\temp.txt', '-d', '-p', 'mansour', '-ep',
        'ep65', '-s', 'sq001', '-t', 'sh001', 'discover'])
    print namespace
    for attr in dir(namespace):
        if not attr.startswith('_'):
            print attr, getattr(namespace, attr)
