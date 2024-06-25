from common.db import DatabaseAccess, DB_PATH
from common.db_obj import Person
from PySide6.QtWidgets import QApplication
import sys
from common.main_gui import DataNotifier, ClientLawyerGUI
from PySide6.QtCore import QTimer


app = QApplication(sys.argv)

db_access = DatabaseAccess(DB_PATH)
notifier = DataNotifier(db_access)

gui = ClientLawyerGUI("curly-sniffle", db_access)

notifier.dataChanged.connect(gui.update_data)

timer = QTimer()
timer.timeout.connect(notifier.poll_for_changes)
timer.start(1000)  # Poll every second

gui.show()
app.exec()

from aplustools.io import diagnose_shutdown_blockers
diagnose_shutdown_blockers()

from common.common_gui import global_theme_sensor

db_access.cleanup()
global_theme_sensor.cleanup()
