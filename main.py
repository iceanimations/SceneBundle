import site
site.addsitedir(r'R:\Pipe_Repo\Users\Qurban\utilities')
import uiContainer
from PyQt4.QtGui import QApplication
import sys
import src._bundle as bun
reload(bun)
#import arnold
#import mtoa
#import mtoa.cmds.registerArnoldRenderer;mtoa.cmds.registerArnoldRenderer.registerArnoldRenderer()

app = QApplication(sys.argv)
win = bun.BundleMaker(standalone=True)
win.show()
sys.exit(app.exec_())