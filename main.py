import site
site.addsitedir(r'R:\Pipe_Repo\Users\Qurban\utilities')
import uiContainer
from PyQt4.QtGui import QApplication
import sys
import src._bundle as bun
reload(bun)

app = QApplication(sys.argv)
bun.BundleMaker().show()
sys.exit(app.exec_())