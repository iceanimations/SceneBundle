'''
Created on Nov 25, 2014

@author: qurban.ali
'''

mapFiles = '''
import pymel.core as pc
import maya.cmds as cmds
import os.path as osp
rootPath = osp.dirname(osp.dirname(cmds.file(q=True, location=True)))
msg = False
pc.workspace(rootPath, o=True)
for node in pc.ls(type="reference"):
    if not node.referenceFile():
        continue
    try:
        fNode = pc.FileReference(node)
        refPath = osp.join(rootPath, "scenes", "refs", osp.basename(fNode.path))
        fNode.replaceWith(refPath)
    except:
        msg = True
if msg:
    pc.confirmDialog(title="Scene Bundle", message="Could not load all references, please see the Reference Editor", button="Ok")
def getLast3(path):
    b1 = osp.basename(path)
    b2 = osp.basename(osp.dirname(path))
    b3 = osp.basename(osp.dirname(osp.dirname(path)))
    return osp.join(b3, b2, b1)
for node in pc.ls(type=["aiImage", "file"]):
    try:
        node.fileTextureName.set(osp.join(rootPath, getLast3(node.fileTextureName.get())))
    except:
        node.filename.set(osp.join(rootPath, getLast3(node.filename.get())))
for node in pc.ls(type="cacheFile"):
    path = node.cachePath.get()
    if path:
        base2 = osp.basename(path)
        base1 = osp.basename(osp.dirname(path))
        path = osp.join(rootPath, base1, base2)
        node.cachePath.set(path)
'''