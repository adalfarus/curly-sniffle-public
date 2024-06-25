import time

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import (QApplication, QLabel,
                               QVBoxLayout, QWidget,
                               QStackedLayout,
                               QPushButton, QListWidget,
                               QFrame, QHBoxLayout, QMessageBox, QListWidgetItem, QLineEdit, QComboBox)
from aplustools.io.gui import QNoSpacingHBoxLayout, QNoSpacingVBoxLayout
import sys
import os

from .db import CHANGES_LOG_FILE as _CHANGES_LOG_FILE, DatabaseAccess
from .common_gui import SmartTextEdit, NewCaseFrame, global_theme_sensor, EditPersonFrame, EditCaseFrame
from .db_obj import Person, Case, Document
from aplustools.io.environment import SystemTheme


class DataNotifier(QObject):
    dataChanged = Signal(tuple)

    def __init__(self, db_access):
        super().__init__()
        self.db_access = db_access
        self.last_position = 0

    def poll_for_changes(self):
        if os.path.exists(_CHANGES_LOG_FILE):
            with open(_CHANGES_LOG_FILE, 'r') as log_file:
                log_file.seek(self.last_position)  # log_file.seek(0, io.SEEK_END)
                changes = log_file.read()  # self.last_position != log_file.tell()
                self.last_position = log_file.tell()
            if changes:  # Close the file as soon as possible
                unique_changes = tuple(set(changes))
                self.dataChanged.emit(unique_changes)


class LoginRegister(QWidget):
    loginClicked = Signal()
    registerClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.setStyleSheet("background: white;")

    def initUI(self):
        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)

        self.login_register_frame = QFrame(self)
        self.login_register_frame.setFrameShape(QFrame.Shape.Box)

        self.init_login()
        self.init_register()

        self.frame_layout = QVBoxLayout(self.login_register_frame)
        self.frame_layout.addWidget(self.login_widget)
        self.frame_layout.addWidget(self.register_widget)

        self.login_register_frame.setLayout(self.frame_layout)
        self.main_layout.addWidget(self.login_register_frame)

        self.register_widget.hide()

        self.adjust_frame_position()

    def init_login(self):
        self.login_widget = QWidget(self.login_register_frame)
        layout = QVBoxLayout()

        self.login_label = QLabel('Login', self.login_widget)
        self.username_input = QLineEdit(self.login_widget)
        self.username_input.setPlaceholderText('Username')
        self.password_input = QLineEdit(self.login_widget)
        self.password_input.setPlaceholderText('Password')
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_button = QPushButton('Login', self.login_widget)
        self.switch_to_register_button = QPushButton('Switch to Register', self.login_widget)

        layout.addWidget(self.login_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)
        layout.addWidget(self.switch_to_register_button)

        self.login_widget.setLayout(layout)

        self.switch_to_register_button.clicked.connect(self.show_register)
        self.login_button.clicked.connect(self.loginClicked.emit)

    def init_register(self):
        self.register_widget = QWidget(self.login_register_frame)
        layout = QVBoxLayout()

        self.register_label = QLabel('Register', self.register_widget)
        self.new_username_input = QLineEdit(self.register_widget)
        self.new_username_input.setPlaceholderText('Username')
        self.new_password_input = QLineEdit(self.register_widget)
        self.new_password_input.setPlaceholderText('Password')
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_account_role = QComboBox()
        self.new_account_role.addItems(["Admin", "Manager", "Viewer"])
        self.register_button = QPushButton('Register', self.register_widget)
        self.switch_to_login_button = QPushButton('Switch to Login', self.register_widget)

        self.register_button.clicked.connect(self.registerClicked.emit)

        layout.addWidget(self.register_label)
        layout.addWidget(self.new_username_input)
        layout.addWidget(self.new_password_input)
        layout.addWidget(self.new_account_role)
        layout.addWidget(self.register_button)
        layout.addWidget(self.switch_to_login_button)

        self.register_widget.setLayout(layout)

        self.switch_to_login_button.clicked.connect(self.show_login)

    def show_register(self):
        self.login_widget.hide()
        self.register_widget.show()

    def show_login(self):
        self.register_widget.hide()
        self.login_widget.show()

    def resizeEvent(self, event):
        self.adjust_frame_position()
        super().resizeEvent(event)

    def adjust_frame_position(self):
        frame_width = self.width() // 2
        frame_height = self.height() // 2
        self.login_register_frame.resize(frame_width, frame_height)
        self.login_register_frame.move((self.width() - frame_width) // 2, (self.height() - frame_height) // 2)


class ClientLawyerGUI(QWidget):
    def __init__(self, window_title: str, _db_access: DatabaseAccess):
        super().__init__()
        self.theme = global_theme_sensor.theme
        self._db_access = _db_access
        self._persons: dict[int, Person] = _db_access.get_all_person_objs()
        self._cases: dict[int, Case] = _db_access.get_all_case_objs()
        self._documents: dict[int, Document] = _db_access.get_all_document_objs()

        self.current_edit = None

        self.initUI(window_title)
        self.reapply_theme()
        global_theme_sensor.themeChanged.connect(self.reapply_theme)
        self.login_register = LoginRegister(self)
        self.login_register.show()
        self.login_register.resize(self.size())
        self.login_register.raise_()
        self.login_register.loginClicked.connect(self.check_login)
        self.login_register.registerClicked.connect(self.check_register)
        self.role = "Viewer"

    def enter(self):
        self.login_register.hide()
        if self.role == "Viewer":
            self.delete_button.setEnabled(False)
            self.new_case_button.setEnabled(False)
        elif self.role == "Manager":
            self.delete_button.setEnabled(False)

    def check_login(self):
        self.role = self._db_access.authenticate_user(self.login_register.username_input.text(),
                                                      self.login_register.password_input.text())
        self.enter()

    def check_register(self):
        self._db_access.register_user(self.login_register.new_username_input.text(),
                                      self.login_register.new_password_input.text(),
                                      self.login_register.new_account_role.currentText())
        self.role = self._db_access.authenticate_user(self.login_register.new_username_input.text(),
                                                      self.login_register.new_password_input.text())
        self.enter()

    def initUI(self, window_title):
        self.setWindowTitle(window_title)
        self.setGeometry(100, 100, 1200, 800)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.stack_layout = QStackedLayout()
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(self.width() // 3)  # 300

        self.sidebar_layout = QVBoxLayout()
        self.new_case_button = QPushButton("New Case")
        self.new_case_button.clicked.connect(self.create_new_case_frame)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete)

        self.search_input = SmartTextEdit()
        self.search_input.setPlaceholderText("Search for People, Cases, or Documents")
        self.search_input.textChanged.connect(self.search_data)

        self.search_results = QListWidget()
        self.search_results.currentItemChanged.connect(self.display_info)

        self.sidebar_layout.addWidget(self.search_input)
        self.sidebar_layout.addWidget(self.new_case_button)
        self.sidebar_layout.addWidget(self.delete_button)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        self.sidebar_layout.addWidget(line)
        self.sidebar_layout.addWidget(self.search_results)

        self.sidebar.setLayout(self.sidebar_layout)

        self.main_frame = QFrame()
        self.main_layout = QNoSpacingVBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)
        back_layout = QNoSpacingHBoxLayout()
        back_layout.addWidget(self.back_button)
        back_layout.addStretch()
        self.back_frame = QFrame()
        self.back_frame.setLayout(back_layout)
        self.info_display = QLabel("Select an item to see details here")
        self.info_display.setWordWrap(True)
        self.main_layout.addWidget(self.info_display)
        self.main_frame.setLayout(self.main_layout)

        self.stack_layout.addWidget(self.main_frame)

        self.split_layout = QHBoxLayout()
        self.split_layout.addWidget(self.sidebar)
        self.split_layout.addLayout(self.stack_layout)

        self.main_container = QWidget()
        self.main_container_layout = QVBoxLayout()
        self.main_container_layout.addLayout(self.split_layout)
        self.main_container.setLayout(self.main_container_layout)

        self.layout.addWidget(self.main_container)

        self.history = []

        self.search_data()

        self.new_case_frame = NewCaseFrame(self)
        self.new_case_frame.saveClicked.connect(self.create_new_case)
        self.stack_layout.addWidget(self.new_case_frame)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sidebar.setFixedWidth(self.width() // 3)

    def search_data(self):
        query = self.search_input.text()
        self.search_results.clear()

        # For demonstration purposes, we add mock search results
        results = self._db_access.search(query)
        for table, results, ret_vals in results:
            if ret_vals == ('',):
                continue

            for result in results:
                if table == "Persons":
                    person = self._persons[result]
                    vals = [getattr(person, x) for x in ret_vals if x]
                elif table == "Documents":
                    document = self._documents[result]
                    vals = [getattr(document, x) for x in ret_vals if x]
                elif table == "Cases":
                    case = self._cases[result]
                    vals = [getattr(case, x) for x in ret_vals if x]
                else:
                    raise ValueError

                name = ""
                for j, val in enumerate(vals):
                    if ret_vals[j] not in ("can_be_lawyer",):
                        name += ' ' + val
                    else:
                        name += " {Lawyer}" if val else " {Client}"

                list_item = QListWidgetItem(name)
                list_item.setData(Qt.ItemDataRole.UserRole, f"{table}.{result}")
                self.search_results.addItem(list_item)

    def edit_started(self, where: str):
        table, nb = where.split(".")
        if table == "Cases":
            obj = self._cases[int(nb)]
            if self.current_edit.current_editors == 1:
                obj.edit()
                while not obj._edit_lock_acquired:
                    time.sleep(0.1)
        elif table == "Persons":
            obj = self._persons[int(nb)]
            if self.current_edit.current_editors == 0:
                obj.edit()
                while not obj._edit_lock_acquired:
                    time.sleep(0.1)

    def edit_finished(self, where: str):
        table, nb = where.split(".")
        if table == "Cases":
            obj = self._cases[int(nb)]
            if self.current_edit.current_editors == 0:
                obj.name = self.current_edit.title_label.text()
                obj.description = self.current_edit.description_text.toPlainText()
                obj.notes = '\n'.join(self.current_edit.notes_text.get_bullet_points())

                persons = []
                for person in self.current_edit.for_it_list.people:
                    persons.append((person.nb, person.representative_nb, 0))
                for person in self.current_edit.against_it_list.people:
                    persons.append((person.nb, person.representative_nb, 1))
                obj.persons = persons

                docs = []
                for index in range(self.current_edit.documents_list.count()):
                    item = self.current_edit.documents_list.item(index)
                    data = item.data(Qt.ItemDataRole.UserRole)

                    if type(data) == int:
                        docs.append(data)
                    else:
                        doc = Document.new(self._db_access, os.path.basename(data), "", [], data)
                        docs.append(doc.nb)

                obj.documents = docs
                obj.finalize_edit()
        elif table == "Persons":
            obj = self._persons[int(nb)]
            if self.current_edit.current_editors == -1:
                obj.first_name = self.current_edit.first_name_edit.text()
                obj.last_name = self.current_edit.last_name_edit.text()
                obj.address = self.current_edit.address_edit.text()
                obj.contact_info = self.current_edit.contact_method_edit.text()
                obj.birth_date = self.current_edit.birthday_edit.text()
                obj.gender = self.current_edit.gender_combo.currentText()
                obj.can_be_lawyer = self.current_edit.lawyer_checkbox.isChecked()
                obj.description = self.current_edit.description_edit.toPlainText()
                obj.notes = '\n'.join(self.current_edit.notes_edit.get_bullet_points())
                obj.finalize_edit()

    def delete(self):
        if self.current_edit is not None:
            if isinstance(self.current_edit, EditPersonFrame):
                obj = self._persons[self.current_edit.nb]
                obj.delete()
            elif isinstance(self.current_edit, EditCaseFrame):
                obj = self._cases[self.current_edit.nb]
                obj.delete()
            self.search_data()

    def display_info(self, item):
        if self.current_edit is not None:
            if isinstance(self.current_edit, EditPersonFrame):
                obj = self._persons[self.current_edit.nb]
            elif isinstance(self.current_edit, EditCaseFrame):
                obj = self._cases[self.current_edit.nb]
            if obj._edit_mode_engaged or obj._edit_lock_acquired:
                obj.finalize_edit()
        if item is None:
            return
        table, nb = item.data(Qt.ItemDataRole.UserRole).split(".")
        if table == "Cases":
            info_frame = EditCaseFrame(int(nb), self, editable=self.role != "Viewer")
        elif table == "Persons":
            info_frame = EditPersonFrame(int(nb), self, editable=self.role != "Viewer")

        info_frame.oneEditStarted.connect(self.edit_started)
        info_frame.oneEditSaved.connect(self.edit_finished)
        self.current_edit = info_frame
        self.stack_layout.addWidget(info_frame)
        self.stack_layout.setCurrentWidget(info_frame)

        self.history = [self.main_frame, info_frame]
        self.back_button.setEnabled(True)

    def display_related_info(self, item):
        selected_text = item.text()

        if selected_text.startswith("Case"):
            details = f"Details about {selected_text}"
        else:
            details = f"Details about participant {selected_text}"

        related_frame = QFrame()
        related_layout = QVBoxLayout()
        related_label = QLabel(details)
        related_label.setWordWrap(True)
        related_layout.addWidget(related_label)
        related_frame.setLayout(related_layout)

        self.stack_layout.addWidget(related_frame)
        self.stack_layout.setCurrentWidget(related_frame)

        self.history.append(related_frame)

    def create_new_case(self):
        people = []

        for person in self.new_case_frame.for_it_list.people:
            people.append((person.nb, person.representative_nb, 0))
        for person in self.new_case_frame.against_it_list.people:
            people.append((person.nb, person.representative_nb, 1))

        docs = []
        for index in range(self.new_case_frame.documents_list.count()):
            item = self.new_case_frame.documents_list.item(index)  # Check if file already there, check hashes, ...

            doc = Document.new(self._db_access, os.path.basename(item.text()), "", [], item.text())
            docs.append(doc.nb)

        Case.new(self._db_access, self.new_case_frame.title_input.text(), self.new_case_frame.description_text.toPlainText(),
                 '\n'.join(self.new_case_frame.notes_text.get_bullet_points()), people, docs)
        self.new_case_frame.clear_fields()

    def create_new_case_frame(self):
        self.search_results.clearSelection()
        self.stack_layout.setCurrentWidget(self.new_case_frame)
        self.history = [self.main_frame, self.new_case_frame]
        self.back_button.setEnabled(True)

    def save_case(self, case_id, case_name, details):
        # For demonstration, we simply show a message box
        QMessageBox.information(self, "Save Case", f"Case ID: {case_id}\nCase Name: {case_name}\nDetails: {details}")

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            self.stack_layout.setCurrentWidget(self.history[-1])
            if len(self.history) == 1:
                self.search_results.clearSelection()
                self.back_button.setEnabled(False)
        else:
            self.back_button.setEnabled(False)

    def update_data(self, unique_changes):
        def update_dict_if_absent(original_dict, new_data):  # Multiuser fix, don't ignore new values
            keys_to_remove = [key for key in original_dict if key not in new_data]
            for key in keys_to_remove:
                del original_dict[key]
            for key, value in new_data.items():
                obj = original_dict.get(key)
                if obj is not None:
                    obj.update()
                else:
                    original_dict.setdefault(key, value)
        for change in unique_changes:
            match change:
                case "\t":
                    update_dict_if_absent(self._cases, self._db_access.get_all_case_objs())
                case "\n":
                    update_dict_if_absent(self._persons, self._db_access.get_all_person_objs())
                case " ":
                    update_dict_if_absent(self._documents,self._db_access.get_all_document_objs())
        old_index = self.search_results.currentIndex()
        self.search_data()
        self.search_results.setCurrentIndex(old_index)
        if self.current_edit is not None:
            if isinstance(self.current_edit, EditPersonFrame):
                obj = self._persons[self.current_edit.nb]
            elif isinstance(self.current_edit, EditCaseFrame):
                obj = self._cases[self.current_edit.nb]
            if not (obj._edit_mode_engaged or obj._edit_lock_acquired):
                self.display_info(self.search_results.currentItem())

    def reapply_theme(self):
        self.theme = global_theme_sensor.theme
        self.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid #aaaaaa;
                border-radius: 5px;
                padding: 5px;
                background-color: #{"ffffff" if self.theme == SystemTheme.LIGHT else "3c3c3c"};
            }}
            QPushButton:hover {{
                background-color: #{"f6f6f6" if self.theme == SystemTheme.LIGHT else "8c8c8c"};
            }}
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClientLawyerGUI("Law Firm Data Management")
    window.show()
    sys.exit(app.exec())
