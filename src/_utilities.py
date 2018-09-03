'''
Created on Nov 25, 2014

@author: qurban.ali
         talha.ahmed
'''
import os
import sys
import pymel.core as pc
import re


import iutil

mapFiles = '''#ICE_BundleScript
#version==0.4
import pymel.core as pc
import maya.cmds as cmds
import os.path as osp
import os

rootPath = osp.dirname(osp.dirname(cmds.file(q=True, location=True)))
refRootPath = osp.normpath(osp.join(rootPath, "scenes", "refs"))

msg = False
pc.workspace(rootPath, o=True)

for node in pc.ls(type="reference"):
    if not node.referenceFile():
        continue
    try:
        fNode = pc.FileReference(node)
        refPath = osp.normpath(osp.abspath(fNode.path))
        if refRootPath not in refPath:
            newRefPath = osp.join(refRootPath, osp.basename(refPath))
            print " reloading  .... ", refPath, "to", newRefPath
            fNode.replaceWith(newRefPath)
    except:
        msg = True

if msg:
    pc.confirmDialog(
        title="Scene Bundle",
        message=("Could not load all references,"
                 " please see the Reference Editor"),
        button="Ok")

def getLast3(path):
    b1 = osp.basename(path)
    b2 = osp.basename(osp.dirname(path))
    b3 = osp.basename(osp.dirname(osp.dirname(path)))
    return osp.join(b3, b2, b1)

for node in pc.ls(type="file"):
    if pc.attributeQuery("excp", n=node, exists=True):
        continue
    cs = node.colorSpace.get()
    node.fileTextureName.set(osp.join(rootPath, getLast3(
            node.fileTextureName.get() )).replace('\\\\', '/'))
    node.colorSpace.set(cs)

for node in pc.ls(type=["RedshiftSprite", "RedshiftNormalMap"]):
    if pc.attributeQuery("excp", n=node, exists=True):
        continue
    node.tex0.set(osp.join(rootPath, getLast3(node.tex0.get())).replace('\\\\',
            '/'))

for node in pc.ls(type=["RedshiftProxyMesh"]):
    if pc.attributeQuery("excp", n=node, exists=True):
        continue
    path = osp.normpath(node.fileName.get())
    try:
        _, relpath = path.split(os.sep + 'proxies' + os.sep)
        node.fileName.set(osp.join(rootPath, 'proxies', relpath))
    except ValueError:
        continue

msg=False
for node in pc.ls(type="cacheFile"):
    path = node.cachePath.get()
    if path:
        base2 = osp.basename(path)
        #base1 = osp.basename(osp.dirname(path))
        path = osp.join(rootPath, base2)
        path = path.replace('\\\\', '/')
        if osp.exists(path):
            node.cachePath.set(path)
        else:
            msg=True
if msg:
    pc.confirmDialog(title="Scene Bundle",
            message="Could not apply some cache files", button="Ok")

'''


def which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """Given a command, mode, and a PATH string, return the path which
    conforms to the given mode on the PATH, or None if there is no such
    file.

    `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
    of os.environ.get("PATH"), or can be overridden with a custom search
    path.

    """

    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.
    def _access_check(fn, mode):
        return (os.path.exists(fn) and os.access(fn, mode) and
                not os.path.isdir(fn))

    # Short circuit. If we're given a full path which matches the mode
    # and it exists, we're done here.
    if _access_check(cmd, mode):
        return cmd

    path = (path or os.environ.get("PATH", os.defpath)).split(os.pathsep)

    if sys.platform == "win32":
        # The current directory takes precedence on Windows.
        if os.curdir not in path:
            path.insert(0, os.curdir)

        pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
        matches = [cmd for ext in pathext if cmd.lower().endswith(ext.lower())]
        files = [cmd] if matches else [cmd + ext.lower() for ext in pathext]
    else:
        files = [cmd]

    seen = set()
    for dir in path:
        dir = os.path.normcase(dir)
        if dir not in seen:
            seen.add(dir)
            for thefile in files:
                name = os.path.join(dir, thefile)
                if _access_check(name, mode):
                    return name
    return None


def findUIObjectByLabel(parentUI, objType, label, case=True):
    try:
        if not case:
            label = label.lower()
        try:
            parentUI = pc.uitypes.Layout(parentUI)
        except:
            parentUI = pc.uitypes.Window(parentUI)

        for child in parentUI.getChildren():
            child
            if isinstance(child, objType):
                thislabel = child.getLabel()
                if not case:
                    thislabel = thislabel.lower()

                if label in thislabel:
                    return child
            if isinstance(child, pc.uitypes.Layout):
                obj = findUIObjectByLabel(child, objType, label, case)
                if obj:
                    return obj

    except Exception as e:
        print parentUI, e
        return None


def turnZdepthOn():
    for layer in pc.ls(type=pc.nt.RenderLayer):
        if 'depth' in layer.name():
            layer.renderable.set(1)
        else:
            layer.renderable.set(0)


reconnectAiAOVScript = """
global proc reconnectAiAOVs()
{
    string $aiAOVs[] = `ls -type aiAOV`;
    string $outputs[];
    string $thisAOV;
    for ($thisAOV in $aiAOVs)
    {
        $outputs = `listConnections -t aiOptions $thisAOV `;
        if (!size( $outputs )){
            connectAttr -f -na ($thisAOV + ".message")
                    defaultArnoldRenderOptions.aovList;
        }

    }
}
reconnectAiAOVs();
"""


def createReconnectAiAOVScript():
    return pc.scriptNode(
        name='reconnectAiAOV', bs=reconnectAiAOVScript, stp='mel', st=1)


def getSequenceSize(path, func=None):
    if func is None:
        func = iutil.getSequenceFiles
    return getSize(func(path))


def getSequence(path, symbol='#'):
    path_dir, path_base = os.path.split(path)
    sequence = []
    if symbol in path_base:
        pattern = re.compile(re.sub(
                '#+', lambda match: r'\d' * len(match.group()),
                os.path.normcase(path_base)))
        if os.path.exists(path_dir) and os.path.isdir(path_dir):
            sequence = [os.path.join(path_dir, fn)
                        for fn in os.listdir(path_dir)
                        if pattern.match(os.path.normcase(fn))]
    return sequence


def getSize(files):
    sizes = []
    for _file in files:
        try:
            sizes.append(os.stat(_file).st_size)
        except:
            pass
    return sum(sizes)


def addExceptionAttr(node):
    if not pc.attributeQuery('excp', n=node, exists=True):
        pc.addAttr(node, sn='excp', ln='exception', dt='string')


def removeExceptionAttr(node):
    if pc.attributeQuery('excp', n=node, exists=True):
        pc.deleteAttr('excp', n=node)
