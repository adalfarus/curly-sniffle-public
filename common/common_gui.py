from PySide6.QtWidgets import (QWidget, QPushButton, QVBoxLayout, QLabel, QLineEdit,
                               QHBoxLayout, QFrame, QScrollArea, QTextEdit, QGroupBox,
                               QListWidget, QFileDialog, QDialog, QDialogButtonBox,
                               QDateEdit, QCheckBox, QMessageBox, QComboBox, QListWidgetItem)
from PySide6.QtGui import QPixmap, QRegularExpressionValidator
from PySide6.QtCore import Qt, Signal, QUrl, QObject, QRegularExpression, QDate, QSize
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from aplustools.io.environment import System, SystemTheme
from aplustools.package.timid import TimidTimer
from typing import Literal
import itertools
import sys
import os
from aplustools.io.gui import QNoSpacingHBoxLayout, QQuickHBoxLayout, QBulletPointTextEdit, QNoSpacingVBoxLayout


class QThemeSensor(QObject):
    themeChanged = Signal()

    def __init__(self):
        super().__init__()
        self.timer = TimidTimer(start_now=False)

        self.system = System.system()
        self.theme = self.system.get_system_theme()

        self.timer.fire(1, self.check_theme)

    def check_theme(self):
        current_theme = self.system.get_system_theme()
        if current_theme != self.theme:
            self.theme = current_theme
            self.themeChanged.emit()

    def cleanup(self):
        self.__del__()

    def __del__(self):
        self.timer.stop_fire()


global_theme_sensor = QThemeSensor()


class SmartTextEdit(QTextEdit):
    def __init__(self, max_height=100, parent=None):
        super().__init__(parent)
        self.max_height = max_height
        self.textChanged.connect(self.adjustHeight)

    def adjustHeight(self):
        doc_height = self.document().size().height()
        if doc_height > self.max_height:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.setFixedHeight(self.max_height)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setFixedHeight(int(doc_height))

    def showEvent(self, event):
        super().showEvent(event)
        self.adjustHeight()

    def text(self) -> str:
        return self.toPlainText()


class QBaseDocumentViewerControls(QWidget):
    fit_changed = Signal(str)
    pop_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Document Viewer')

        self.mode_iterator = itertools.cycle(("./assets/fit_both.svg", "./assets/no_limit.svg", "./assets/fit_width.svg", "./assets/fit_height.svg"))
        self.popout_iterator = itertools.cycle(("./assets/pop_out.svg", "./assets/pop_in.svg"))

        self.main_layout = QHBoxLayout(self)
        self.controls_layout = QVBoxLayout(self)

        self.pop_button = QPushButton()
        self.pop_button.setIcon(QPixmap(next(self.popout_iterator)))
        self.pop_button.clicked.connect(self.change_pop)
        self.pop_button.setFixedSize(40, 40)
        self.controls_layout.addWidget(self.pop_button)

        self.fit_button = QPushButton()
        self.fit_button.setIcon(QPixmap(next(self.mode_iterator)))
        self.fit_button.clicked.connect(self.change_fit)
        self.fit_button.setFixedSize(40, 40)
        self.controls_layout.addWidget(self.fit_button)

        self.fit_window_button = QPushButton()
        self.fit_window_button.setIcon(QPixmap("assets/fit_window.svg"))
        self.FIT_WINDOW = self.fit_window_button.clicked
        self.fit_window_button.setFixedSize(40, 40)
        self.controls_layout.addWidget(self.fit_window_button)

        self.controls_frame = QFrame()
        self.controls_frame.setMaximumWidth(60)
        self.controls_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.controls_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.controls_frame.setLayout(self.controls_layout)

        self.setMinimumSize(300, 200)

        self.main_layout.addWidget(self.controls_frame, alignment=Qt.AlignmentFlag.AlignLeft)

        self.setLayout(self.main_layout)

        self.fit_emit = "fit_both"
        self.pop_emit = "pop_out"

    def change_fit(self):
        fit = next(self.mode_iterator)
        self.fit_button.setIcon(QPixmap(fit))
        self.fit_emit = os.path.basename(fit).split(".")[0]
        self.fit_changed.emit(self.fit_emit)

    def change_pop(self):
        pop = next(self.popout_iterator)
        self.pop_button.setIcon(QPixmap(pop))
        self.pop_emit = os.path.basename(pop).split(".")[0]
        self.pop_changed.emit(self.pop_emit)


class QDocumentViewer(QBaseDocumentViewerControls):
    def __init__(self, parent=None, allow_multiple_popouts: bool = False):
        super().__init__(parent)
        self.theme = global_theme_sensor.theme
        self.scroll_area = QScrollArea()  # Scroll area for the content
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setFrameShape(QFrame.Shape.StyledPanel)
        self.scroll_area.setFrameShadow(QFrame.Shadow.Raised)
        self.scroll_area.setStyleSheet(f"""
                    QScrollArea {{
                        border-radius: 5px;
                        background-color: #{"2d2d2d" if self.theme == SystemTheme.DARK else "fbfbfb"};
                        margin: 1px;
                    }}
                    QScrollArea > QWidget > QWidget {{
                        border: none;
                        border-radius: 15px;
                        background-color: transparent;
                    }}
                    QScrollBar:vertical {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        width: 15px;
                        margin: 15px 0 15px 0;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:vertical {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-height: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                        background: none;
                    }}
                    QScrollBar:horizontal {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        height: 15px;
                        margin: 0 15px 0 15px;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:horizontal {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-width: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                        background: none;
                    }}
                """)

        self.general_preview_widget = QLabel()
        self.general_preview_widget.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.general_preview_widget.setWordWrap(True)

        self.video_widget = QVideoWidget()
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setLoops(QMediaPlayer.Loops.Infinite)

        self.pdf_view = QPdfView()
        self.pdf_document = QPdfDocument(self)
        self.pdf_view.setDocument(self.pdf_document)

        self.scroll_layout.addWidget(self.general_preview_widget)
        self.scroll_layout.addWidget(self.video_widget)
        self.scroll_layout.addWidget(self.pdf_view)
        self.general_preview_widget.hide()
        self.video_widget.hide()
        self.pdf_view.hide()

        self.main_layout.addWidget(self.scroll_area)
        self.is_popped_out = False
        self.current_file_path = ""
        self.pop_changed.connect(self.pop_out_in)
        self.wins = []
        self.allow_multiple_popouts = allow_multiple_popouts
        self.fit_changed.connect(self.fit_content)
        self.FIT_WINDOW.connect(self.fit_window)
        global_theme_sensor.themeChanged.connect(self.reapply_theme)

    def fit_content(self):
        if self.fit_emit == "fit_width":
            if self.pdf_view.isVisible():
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            elif self.video_widget.isVisible():
                self.video_widget.setFixedSize(self.scroll_area.width(), self.video_widget.height())
            elif self.general_preview_widget.isVisible():
                if self.general_preview_widget.pixmap().isNull():
                    self.general_preview_widget.setWordWrap(False)
                else:
                    pixmap = QPixmap(self.current_file_path)
                    self.general_preview_widget.setPixmap(pixmap.scaled(self.scroll_area.width(), pixmap.height(),
                                                                        Qt.AspectRatioMode.KeepAspectRatio))
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        elif self.fit_emit == "fit_height":
            if self.pdf_view.isVisible():
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
                self.pdf_view.setZoomFactor(0.0)
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
                self.pdf_view.setZoomFactor((self.scroll_area.height() / self.pdf_document.pagePointSize(0).height()) / 1.4)
            elif self.video_widget.isVisible():
                self.video_widget.setFixedSize(self.video_widget.width(), self.scroll_area.height())
            if self.general_preview_widget.isVisible():
                if self.general_preview_widget.pixmap().isNull():
                    self.general_preview_widget.setWordWrap(True)
                else:
                    pixmap = QPixmap(self.current_file_path)
                    self.general_preview_widget.setPixmap(pixmap.scaled(pixmap.width(), self.scroll_area.height(),
                                                                        Qt.AspectRatioMode.KeepAspectRatio))
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        elif self.fit_emit == "fit_both":
            if self.pdf_view.isVisible():
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
            elif self.video_widget.isVisible():
                self.video_widget.setFixedSize(self.scroll_area.size())
            elif self.general_preview_widget.isVisible():
                if self.general_preview_widget.pixmap().isNull():
                    self.general_preview_widget.setWordWrap(True)
                else:
                    pixmap = QPixmap(self.current_file_path)
                    self.general_preview_widget.setPixmap(pixmap.scaled(self.scroll_area.size()))
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        elif self.fit_emit == "no_limit":  # fit_none
            if self.pdf_view.isVisible():
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
                self.pdf_view.setZoomFactor(1.0)
            elif self.video_widget.isVisible():
                self.video_widget.setFixedSize(600, 400)
            if self.general_preview_widget.isVisible():
                if self.general_preview_widget.pixmap().isNull():
                    self.general_preview_widget.setWordWrap(True)
                else:
                    pixmap = QPixmap(self.current_file_path)
                    self.general_preview_widget.setPixmap(pixmap)
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def pop_out_in(self):
        if self.is_popped_out:
            self.close()
        else:
            if not self.allow_multiple_popouts and len(self.wins) > 0:
                self.wins[0].close()
                del self.wins[0]
            win = QDocumentViewer()
            win.preview_document(self.current_file_path)
            win.pop_button.setIcon(QPixmap(next(win.popout_iterator)))
            win.is_popped_out = True
            win.show()
            win.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value())
            win.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().value())
            win.fit_in(self.fit_emit, itertools.tee(self.mode_iterator)[0])
            win.fit_content()
            self.wins.append(win)

    def fit_in(self, current_fit, iterator):
        self.mode_iterator = iterator
        self.fit_button.setIcon(QPixmap(f"./assets/{current_fit}.svg"))
        self.fit_emit = current_fit

    def change_pop(self):
        pop = next(self.popout_iterator)
        self.pop_emit = os.path.basename(pop).split(".")[0]
        self.pop_changed.emit(self.pop_emit)

    def preview_document(self, file_path: str):
        self.current_file_path = file_path

        self.general_preview_widget.hide()
        self.video_widget.hide()
        self.pdf_view.hide()

        if not file_path:
            return

        if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
            self.general_preview_widget.show()
            self.general_preview_widget.setPixmap(QPixmap(file_path))
        elif file_path.lower().endswith('.pdf'):
            self.pdf_view.show()
            self.pdf_document.load(file_path)
        elif file_path.lower().endswith(('.mp4', '.mov')):
            self.video_widget.show()
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            self.media_player.play()
        else:
            self.general_preview_widget.show()
            try:
                with open(file_path, 'r') as f:
                    contents = f.read()
                self.general_preview_widget.setText(contents)
            except Exception:
                self.general_preview_widget.setText(f"Unsupported file format: {file_path}")

        self.fit_content()

    def fit_window(self, arg):
        if self.is_popped_out:
            # Adjust the scroll area to its contents
            self.scroll_area.adjustSize()

            # Calculate the new size based on the content
            content_size = self.scroll_content.sizeHint()

            # Set the scroll area size to match the content size
            self.setMinimumSize(content_size)
            self.setMaximumSize(content_size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_content()

    def reapply_theme(self):
        self.theme = global_theme_sensor.theme
        self.scroll_area.setStyleSheet(f"""
                    QScrollArea {{
                        border-radius: 5px;
                        background-color: #{"2d2d2d" if self.theme == SystemTheme.DARK else "fbfbfb"};
                        margin: 1px;
                    }}
                    QScrollArea > QWidget > QWidget {{
                        border: none;
                        border-radius: 15px;
                        background-color: transparent;
                    }}
                    QScrollBar:vertical {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        width: 15px;
                        margin: 15px 0 15px 0;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:vertical {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-height: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                        background: none;
                    }}
                    QScrollBar:horizontal {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        height: 15px;
                        margin: 0 15px 0 15px;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:horizontal {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-width: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                        background: none;
                    }}
                """)


class QPersonWidget(QFrame):
    clicked = Signal()
    selected = Signal()

    def __init__(self, nb: int, name: str, representative_nb: int, representative: str,
                 representation_type: Literal["self_represented", "extern", "homegrown"], parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.theme = global_theme_sensor.theme
        self.setStyleSheet(f"""
            QPersonWidget {{
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 5px;
            }}
            QPushButton {{
                border: 1px solid #ccc;
                border-radius: 5px;
            }}""")
        self.isSelected = False

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(9)

        self.nb = nb
        self.name_label = QLabel(name)
        self.representative_nb = representative_nb
        self.representation_label = QLabel(representative if representative else representation_type.replace("_", " ").title())

        self.remove_button = QPushButton('Remove')
        self.remove_button.setFixedSize(60, 25)
        self.remove_button.clicked.connect(self.remove_person)

        layout.addWidget(self.name_label)
        layout.addWidget(self.representation_label)
        layout.addWidget(self.remove_button)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setLayout(layout)
        global_theme_sensor.themeChanged.connect(self.reapply_theme)

    def setSelectable(self, selectable):
        self.isSelected = selectable

    def updateSelectionStyle(self):
        if self.isSelected:
            self.setStyleSheet("""
                QPersonWidget {
                    background-color: #e6f7ff;
                    border: 1px solid #007bff;
                    border-radius: 5px;
                }
                QPushButton {
                    background-color: #e6f7ff;
                    border: 1px solid #007bff;
                    border-radius: 5px;
                }""")
        else:
            self.setStyleSheet("""
                QPersonWidget {
                    background-color: white;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }
                QPushButton {
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }""")

    def remove_person(self):
        self.parent().people.remove(self)
        self.setParent(None)

    def deselect(self):
        self.setSelectable(False)
        self.updateSelectionStyle()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.isSelected:
                self.selected.emit()
                self.setSelectable(True)
                self.updateSelectionStyle()
            else:
                self.clicked.emit()

    def focusInEvent(self, event):
        self.setSelectable(True)
        self.updateSelectionStyle()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.setSelectable(False)
        self.updateSelectionStyle()
        super().focusOutEvent(event)

    def reapply_theme(self):
        self.theme = global_theme_sensor.theme
        pass  # Reapply themes


class QPersonListWidget(QWidget):
    personActivated = Signal(QPersonWidget)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.selected_widget = None
        self.people = []

    def add_person(self, nb: int, name: str, representative_nb: int, representative: str,
                   representation_type: Literal["self_represented", "extern", "homegrown"]):
        person_widget = QPersonWidget(nb, name, representative_nb, representative, representation_type)
        person_widget.clicked.connect(lambda: self.on_person_clicked(person_widget))
        person_widget.selected.connect(lambda: self.on_person_selected(person_widget))
        self.people.append(person_widget)
        self.layout.addWidget(person_widget)

    def on_person_selected(self, person_widget: QPersonWidget):
        if self.selected_widget and self.selected_widget != person_widget:
            self.selected_widget.deselect()
        self.selected_widget = person_widget

    def on_person_clicked(self, person_widget: QPersonWidget):
        self.personActivated.emit(person_widget)

    def clear(self):
        for person in self.people:
            person.remove_person()


class NewPersonFrame(QFrame):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()

        self.setStyleSheet("""
            QComboBox {
                border: 1px solid #808080;
                border-radius: 5px;
                padding: 5px;
                background-color: #ffffff;
                selection-background-color: #c0c0c0;
                selection-color: black;
            }
            QComboBox::drop-down {
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: url(assets/arrow-down.png);
            }
            QComboBox QAbstractItemView {
                border: 1px solid #808080;
                background-color: #ffffff;
                border-radius: 5px;
                margin-top: -5px;
            }
        """)

        # Top space
        top_space_layout = QQuickHBoxLayout(9, (0, 0, 0, 0))
        image_label = QLabel()
        image_label.setPixmap(QPixmap("assets/unknown_person.jpg").scaled(200, int(200 * 1.1)))
        image_label.setFixedSize(200, int(200 * 1.1))
        image_label.setStyleSheet("""
            QLabel {
                border-radius: 10px;  /* Slightly rounded corners */
            }
        """)
        top_space_layout.addWidget(image_label)

        main_info_layout = QVBoxLayout()
        main_info_groupbox = QGroupBox("Main Information")
        name_info_layout = QQuickHBoxLayout(5, (0, 0, 0, 0))
        self.first_name_edit = QLineEdit()
        self.first_name_edit.setPlaceholderText("First Name")
        self.first_name_edit.setStyleSheet("font-size: 24px; height: 40px; background-color: palette(base);")
        self.last_name_edit = QLineEdit()
        self.last_name_edit.setPlaceholderText("Last Name")
        self.last_name_edit.setStyleSheet("font-size: 24px; height: 40px; background-color: palette(base);")
        name_info_layout.addWidget(self.first_name_edit)
        name_info_layout.addWidget(self.last_name_edit)
        main_info_layout.addLayout(name_info_layout)

        small_info_layout = QQuickHBoxLayout(5, (0, 0, 0, 0))
        self.birthday_edit = QDateEdit()
        self.birthday_edit.setStyleSheet("font-size: 20; height: 30px;")
        self.birthday_edit.setCalendarPopup(True)
        self.birthday_edit.setDate(QDate.currentDate())
        small_info_layout.addWidget(self.birthday_edit)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(['Male', 'Female', 'Other'])
        small_info_layout.addWidget(self.gender_combo)
        self.lawyer_checkbox = QCheckBox("Can be a lawyer")
        small_info_layout.addWidget(self.lawyer_checkbox)

        small_info_layout_2 = QQuickHBoxLayout(5, (0, 0, 0, 0))
        self.address_edit = QLineEdit()
        self.address_edit.setStyleSheet("font-size: 20; height: 30px;")
        self.address_edit.setPlaceholderText("Address")
        small_info_layout_2.addWidget(self.address_edit)
        self.contact_method_edit = QLineEdit()
        self.contact_method_edit.setStyleSheet("font-size: 20; height: 30px;")
        self.contact_method_edit.setPlaceholderText("Enter a valid email")
        self.contact_method_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"[^@]+@[^@]+\.[^@]+")))
        small_info_layout_2.addWidget(self.contact_method_edit)
        main_info_layout.addLayout(small_info_layout_2)
        main_info_layout.addLayout(small_info_layout)
        main_info_groupbox.setLayout(main_info_layout)
        top_space_layout.addWidget(main_info_groupbox)
        main_layout.addLayout(top_space_layout)

        extra_info_layout = QHBoxLayout()
        description_groupbox = QGroupBox("Description")
        self.description_edit = QTextEdit()
        description_layout = QQuickHBoxLayout(0, (9, 9, 9, 9))
        description_layout.addWidget(self.description_edit)
        description_groupbox.setLayout(description_layout)
        self.description_edit.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        notes_groupbox = QGroupBox("Notes")
        self.notes_edit = QBulletPointTextEdit()
        notes_layout = QQuickHBoxLayout(0, (9, 9, 9, 9))
        notes_layout.addWidget(self.notes_edit)
        notes_groupbox.setLayout(notes_layout)
        self.notes_edit.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        extra_info_layout.addWidget(description_groupbox)
        extra_info_layout.addWidget(notes_groupbox)
        main_layout.addLayout(extra_info_layout)

        self.setLayout(main_layout)


class AddPersonDialog(QDialog):  # Quick and dirty
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Person")
        self.resize(1000, 600)

        main_layout = QVBoxLayout()
        self.setStyleSheet("""
            QPushButton {
                border: 1px solid #aaaaaa;
                border-radius: 5px;
                padding: 5px;
                background-color: #ffffff;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)

        self.new_person_frame = NewPersonFrame()
        main_layout.addWidget(self.new_person_frame)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)


class NewCaseFrame(QFrame):
    saveClicked = Signal()

    def __init__(self, main, parent=None):
        self.main = main
        super().__init__(parent)
        main_layout = QVBoxLayout()
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

        # Title input
        title_layout = QQuickHBoxLayout(9, (0, 0, 0, 0))
        self.title_input = QLineEdit(self)
        self.title_input.setPlaceholderText("Title")
        self.title_input.setStyleSheet("font-size: 24px; height: 40px; background-color: palette(base);")
        save_case_button = QPushButton("Create Case")
        save_case_button.clicked.connect(self.save_clicked)
        title_layout.addWidget(self.title_input)
        title_layout.addWidget(save_case_button)
        main_layout.addLayout(title_layout)

        # [Description] & Notes
        extra_info_layout = QQuickHBoxLayout(9, (0, 0, 0, 0))
        description_groupbox = QGroupBox("Description")
        self.description_text = QTextEdit()
        self.description_text.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        description_layout = QVBoxLayout()
        description_layout.addWidget(self.description_text)
        description_groupbox.setLayout(description_layout)
        extra_info_layout.addWidget(description_groupbox)
        # Description & [Notes]
        notes_groupbox = QGroupBox("Notes")
        self.notes_text = QBulletPointTextEdit()
        self.notes_text.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        notes_layout = QVBoxLayout()
        notes_layout.addWidget(self.notes_text)
        notes_groupbox.setLayout(notes_layout)
        extra_info_layout.addWidget(notes_groupbox)
        main_layout.addLayout(extra_info_layout)

        # Documents
        document_layout = QHBoxLayout()
        document_groupbox = QGroupBox("Documents")
        document_selection_layout = QVBoxLayout()
        self.documents_list = QListWidget()
        self.documents_list.setStyleSheet(f"""
            QListWidget {{
                border-radius: 10px;
                background-color: palette(base);
            }}
            QScrollBar:vertical {{
                border: none;
                background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                width: 15px;
                margin: 15px 0 15px 0;
                border-radius: 7px;
            }}
            QScrollBar::handle:vertical {{
                background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                min-height: 20px;
                border-radius: 7px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                height: 15px;
                margin: 0 15px 0 15px;
                border-radius: 7px;
            }}
            QScrollBar::handle:horizontal {{
                background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                min-width: 20px;
                border-radius: 7px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                border: none;
                background: none;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """)
        self.documents_list.currentItemChanged.connect(self.preview_document)

        box_layout = QQuickHBoxLayout(9, (0, 0, 0, 0))
        remove_document_button = QPushButton("- Remove Document")
        remove_document_button.clicked.connect(self.remove_document)
        box_layout.addWidget(remove_document_button)
        add_document_button = QPushButton("+ Add Document")
        add_document_button.clicked.connect(self.add_document)
        box_layout.addWidget(add_document_button)
        document_selection_layout.addWidget(self.documents_list)
        document_selection_layout.addLayout(box_layout)
        document_layout.addLayout(document_selection_layout)
        # Preview
        self.preview = QDocumentViewer(allow_multiple_popouts=True)
        document_layout.addWidget(self.preview)
        document_groupbox.setLayout(document_layout)
        main_layout.addWidget(document_groupbox)

        # People selection
        people_groupbox = QGroupBox("People")
        people_layout = QHBoxLayout()

        self.for_it_list = QPersonListWidget()
        self.against_it_list = QPersonListWidget()

        add_for_it_button = QPushButton("+ Add Person (For it)")
        add_for_it_button.clicked.connect(lambda: self.search_person(self.for_it_list))

        add_against_it_button = QPushButton("+ Add Person (Against it)")
        add_against_it_button.clicked.connect(lambda: self.search_person(self.against_it_list))

        for_it_layout = QVBoxLayout()
        for_it_layout.addWidget(QLabel("For it"))
        for_it_layout.addWidget(self.for_it_list)
        for_it_layout.addWidget(add_for_it_button)

        against_it_layout = QVBoxLayout()
        against_it_layout.addWidget(QLabel("Against it"))
        against_it_layout.addWidget(self.against_it_list)
        against_it_layout.addWidget(add_against_it_button)

        people_layout.addLayout(for_it_layout)
        people_layout.addLayout(against_it_layout)

        people_groupbox.setLayout(people_layout)
        main_layout.addWidget(people_groupbox)

        self.setLayout(main_layout)
        global_theme_sensor.themeChanged.connect(self.reapply_theme)

    def save_clicked(self, _):
        if self.title_input.text() != "" and self.for_it_list.people != []and self.against_it_list.people != []:
            self.saveClicked.emit()
        else:
            QMessageBox.information(self, "Information", "You've left out some required fields, please fill them!\nRequired fields are Title and people.")

    def clear_fields(self):
        self.title_input.setText("")
        self.description_text.setText("")
        self.notes_text.setText("• ")
        self.documents_list.clear()
        self.for_it_list.clear()
        self.against_it_list.clear()

    def add_document(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Add Document(s)", "",
                                                    "PDF Files (*.pdf);;"
                                                    "Images (*.png *.jpg *.jpeg);;"
                                                    "Videos (*.mp4 *.mov);;"
                                                    "All Files (*.*)")

        if file_names:
            for file_name in file_names:
                self.documents_list.addItem(file_name)
            self.documents_list.setCurrentRow(self.documents_list.count() - 1)

    def remove_document(self):
        current_item = self.documents_list.currentItem()
        if current_item:
            self.documents_list.takeItem(self.documents_list.row(current_item))

    def preview_document(self, current, _):
        self.preview.preview_document(current.text() if current is not None else "")

    def _refresh_search_results(self, search, list_widget, filter_lawyers: bool = False):
        list_widget.clear()
        # Populate with existing people for demonstration (in practice, fetch from a database or other source)
        results, ret_vals = self.main._db_access.restricted_search(search.text(), "user")

        if ret_vals == ("",):
            return

        for i in results:
            person = self.main._persons.get(i)
            if not person:
                continue

            vals = [getattr(person, x) for x in ret_vals if x]

            name = ""
            for j, val in enumerate(vals):
                if val == "":
                    continue
                if ret_vals[j] not in ("can_be_lawyer",):
                    name += " " + val
                else:
                    name += " {Lawyer}" if val else " {Client}"

            if (filter_lawyers and "can_be_lawyer" in ret_vals and vals[ret_vals.index("can_be_lawyer")] == 1) or not filter_lawyers:
                list_item = QListWidgetItem(name)
                list_item.setData(Qt.ItemDataRole.UserRole, i)
                list_widget.addItem(list_item)

    def search_person(self, list_widget: QPersonListWidget):
        from PySide6.QtWidgets import QAbstractItemView
        dialog = QDialog(self)
        dialog.setWindowTitle('Search Person')

        dialog_layout = QVBoxLayout(dialog)

        # Search results for person group members
        person_group_label = QLabel('Person Group Members:', dialog)
        dialog_layout.addWidget(person_group_label)

        person_group_results = QListWidget(dialog)
        person_group_results.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)  # Allow multiple selection
        dialog_layout.addWidget(person_group_results)

        person_group_input = QLineEdit(dialog)
        person_group_input.setPlaceholderText('Search for a person group member...')
        person_group_input.textChanged.connect(
            lambda: self._refresh_search_results(person_group_input, person_group_results))
        person_group_input.textChanged.emit("")
        dialog_layout.addWidget(person_group_input)

        # Search results for lawyers
        lawyer_label = QLabel('Lawyer:', dialog)
        dialog_layout.addWidget(lawyer_label)

        lawyer_results = QListWidget(dialog)
        lawyer_results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)  # Allow only single selection
        dialog_layout.addWidget(lawyer_results)

        lawyer_input = QLineEdit(dialog)
        lawyer_input.setPlaceholderText('Search for a lawyer...')
        lawyer_input.textChanged.connect(lambda: self._refresh_search_results(lawyer_input, lawyer_results, True))
        lawyer_input.textChanged.emit("")
        dialog_layout.addWidget(lawyer_input)

        def _add_selected_person():
            selected_person_groups = person_group_results.selectedItems()
            if len(lawyer_results.selectedItems()) > 0:
                selected_lawyer = lawyer_results.selectedItems()[0]
            else:
                return

            if selected_person_groups and selected_lawyer:
                for item in selected_person_groups:
                    if item.text() != selected_lawyer.text():
                        list_widget.add_person(item.data(Qt.ItemDataRole.UserRole), item.text(), selected_lawyer.data(Qt.ItemDataRole.UserRole), selected_lawyer.text(), "homegrown")
                    else:
                        list_widget.add_person(item.data(Qt.ItemDataRole.UserRole), item.text(), item.data(Qt.ItemDataRole.UserRole), '', "self_represented")
                dialog.accept()
            else:
                QMessageBox.warning(dialog, 'Selection Required',
                                    'Please select at least one person group member and one lawyer.')

        select_button = QPushButton('Select', dialog)
        select_button.clicked.connect(_add_selected_person)
        dialog_layout.addWidget(select_button)

        create_new_person_button = QPushButton('Create New Person', dialog)
        create_new_person_button.clicked.connect(lambda: self.create_new_person(list_widget))
        dialog_layout.addWidget(create_new_person_button)

        dialog.resize(752, 580)

        dialog.exec()

    def create_new_person(self, list_widget):
        dialog = AddPersonDialog(self)
        dialog.exec()

        from common.db_obj import Person
        new_person_frame = dialog.new_person_frame
        Person.new(self.main._db_access, new_person_frame.last_name_edit.text(), new_person_frame.first_name_edit.text(),
                   new_person_frame.address_edit.text(), new_person_frame.birthday_edit.text(), new_person_frame.contact_method_edit.text(),
                   new_person_frame.gender_combo.currentText(), new_person_frame.description_edit.toPlainText(),
                   new_person_frame.notes_edit.get_bullet_points(), new_person_frame.lawyer_checkbox.isChecked())

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
        self.title_input.setStyleSheet("font-size: 24px; height: 40px; background-color: palette(base);")
        self.description_text.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        self.notes_text.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        self.documents_list.setStyleSheet(f"""
                    QListWidget {{
                        border-radius: 10px;
                        background-color: palette(base);
                    }}
                    QScrollBar:vertical {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        width: 15px;
                        margin: 15px 0 15px 0;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:vertical {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-height: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                        background: none;
                    }}
                    QScrollBar:horizontal {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        height: 15px;
                        margin: 0 15px 0 15px;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:horizontal {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-width: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                        background: none;
                    }}
                """)


class QEditableGroupBox(QGroupBox):
    editButtonClicked = Signal()

    def __init__(self, title, alignment: str = "vert", editable: bool = True, parent=None):
        super().__init__(title, parent)
        self.setLayout(QVBoxLayout() if alignment == "vert" else QHBoxLayout())
        self.is_editing = False

        # Create the edit button
        self.edit_button = QPushButton(self)
        self.edit_button.setIcon(QPixmap("assets/edit.svg"))
        self.edit_button.setIconSize(QSize(16, 16))
        self.edit_button.setFixedSize(20, 20)
        self.edit_button.clicked.connect(self.toggle_edit_mode)
        self.edit_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
            }
        """)

        if not editable:
            self.edit_button.hide()

    def toggle_edit_mode(self, callback: bool = False):
        self.is_editing = not self.is_editing
        for widget in self.findChildren(QWidget):
            if isinstance(widget, (QLineEdit, QTextEdit)):
                widget.setReadOnly(not self.is_editing)
        self.edit_button.setIcon(QPixmap("assets/save.svg") if self.is_editing else QPixmap("assets/edit.svg"))
        if not callback:
            self.editButtonClicked.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.edit_button.move(self.width() - self.edit_button.width() - 5, 0)


class EditCaseFrame(QFrame):
    oneEditStarted = Signal(str)
    oneEditSaved = Signal(str)

    def __init__(self, nb, main, editable: bool = True, parent=None):
        super().__init__(parent)
        self.nb = nb
        self.main = main
        self.case = main._cases[nb]
        self.max_editors = 3
        self.current_editors = 0
        main_layout = QVBoxLayout()
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

        # Title input
        title_layout = QQuickHBoxLayout(9, (0, 0, 0, 0))
        self.title_label = QLabel(self.case.name)
        self.title_label.setStyleSheet("font-size: 24px; height: 40px; background-color: #f3f3f3;")
        self.title_input = QLineEdit(self)
        self.title_input.setStyleSheet("font-size: 24px; height: 40px; background-color: palette(base);")
        self.title_input.hide()

        self.title_edit_button = QPushButton()
        self.title_edit_button.setIcon(QPixmap("assets/edit.svg"))
        self.title_edit_button.setIconSize(QSize(16, 16))
        self.title_edit_button.setFixedSize(20, 20)
        self.title_edit_button.clicked.connect(self.toggle_edit_title)

        if not editable:
            self.title_edit_button.hide()

        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.title_input)
        title_layout.addWidget(self.title_edit_button)
        main_layout.addLayout(title_layout)

        # [Description] & Notes
        extra_info_layout = QQuickHBoxLayout(9, (0, 0, 0, 0))
        description_groupbox = QEditableGroupBox("Description", editable=editable)
        description_groupbox.editButtonClicked.connect(lambda: self.toggle_edit(description_groupbox))
        self.description_text = QTextEdit(self.case.description)
        self.description_text.setReadOnly(True)
        self.description_text.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        description_groupbox.layout().addWidget(self.description_text)
        extra_info_layout.addWidget(description_groupbox)
        # Description & [Notes]
        notes_groupbox = QEditableGroupBox("Notes", editable=editable)
        notes_groupbox.editButtonClicked.connect(lambda: self.toggle_edit(notes_groupbox))
        self.notes_text = QBulletPointTextEdit(self.case.notes)
        self.notes_text.setReadOnly(True)
        self.notes_text.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        notes_groupbox.layout().addWidget(self.notes_text)
        extra_info_layout.addWidget(notes_groupbox)
        main_layout.addLayout(extra_info_layout)

        # Documents
        document_groupbox = QEditableGroupBox("Documents", "hor", editable=editable)
        document_layout = document_groupbox.layout()
        document_groupbox.editButtonClicked.connect(self.toggle_edit_document)
        document_selection_layout = QVBoxLayout()
        self.documents_list = QListWidget()
        self.documents_list.currentItemChanged.connect(self.preview_document)
        self.documents_list.setStyleSheet(f"""
                    QListWidget {{
                        border-radius: 10px;
                        background-color: palette(base);
                    }}
                    QScrollBar:vertical {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        width: 15px;
                        margin: 15px 0 15px 0;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:vertical {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-height: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                        background: none;
                    }}
                    QScrollBar:horizontal {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        height: 15px;
                        margin: 0 15px 0 15px;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:horizontal {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-width: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                        background: none;
                    }}
                """)

        docu = self.case.documents if isinstance(self.case.documents, tuple) else (self.case.documents,)
        for nb in docu:
            item = QListWidgetItem(self.main._documents[nb].path)
            item.setData(Qt.ItemDataRole.UserRole, nb)
            self.documents_list.addItem(item)

        box_layout = QQuickHBoxLayout(9, (0, 0, 0, 0))
        self.remove_document_button = QPushButton("- Remove Document")
        self.remove_document_button.clicked.connect(self.remove_document)
        box_layout.addWidget(self.remove_document_button)
        self.remove_document_button.hide()
        self.add_document_button = QPushButton("+ Add Document")
        self.add_document_button.clicked.connect(self.add_document)
        box_layout.addWidget(self.add_document_button)
        self.add_document_button.hide()
        document_selection_layout.addWidget(self.documents_list)
        document_selection_layout.addLayout(box_layout)
        document_layout.addLayout(document_selection_layout)
        # Preview
        self.preview = QDocumentViewer(allow_multiple_popouts=True)
        document_layout.addWidget(self.preview)
        main_layout.addWidget(document_groupbox)

        # People GroupBox
        people_groupbox = QEditableGroupBox("People", "hor", editable=editable)
        people_groupbox.editButtonClicked.connect(self.toggle_edit_people)
        people_layout = people_groupbox.layout()

        self.for_it_list = QPersonListWidget()
        self.against_it_list = QPersonListWidget()

        for nb, lawyer_nb, side in self.case.persons:
            person = self.main._persons[nb]
            lawyer = self.main._persons[lawyer_nb]

            person_name = ' '.join([person.first_name, person.last_name] + ["{Lawyer}" if person.can_be_lawyer else "{Client}"])
            lawyer_name = ' '.join([lawyer.first_name, lawyer.last_name] + ["{Lawyer}"])

            if side:
                if nb == lawyer_nb:
                    self.against_it_list.add_person(nb, "", lawyer_nb, "", "self_represented")
                else:
                    self.against_it_list.add_person(nb, person_name, lawyer_nb, lawyer_name, "homegrown")
            else:
                if nb == lawyer_nb:
                    self.for_it_list.add_person(nb, "", lawyer_nb, "", "self_represented")
                else:
                    self.for_it_list.add_person(nb, person_name, lawyer_nb, lawyer_name, "homegrown")

        self.add_for_it_button = QPushButton("+ Add Person (For it)")
        self.add_for_it_button.clicked.connect(lambda: self.search_person(self.for_it_list))

        self.add_against_it_button = QPushButton("+ Add Person (Against it)")
        self.add_against_it_button.clicked.connect(lambda: self.search_person(self.against_it_list))

        self.add_for_it_button.hide()
        self.add_against_it_button.hide()

        for_it_layout = QVBoxLayout()
        for_it_layout.addWidget(QLabel("For it"))
        for_it_layout.addWidget(self.for_it_list)
        for_it_layout.addWidget(self.add_for_it_button)

        against_it_layout = QVBoxLayout()
        against_it_layout.addWidget(QLabel("Against it"))
        against_it_layout.addWidget(self.against_it_list)
        against_it_layout.addWidget(self.add_against_it_button)

        people_layout.addLayout(for_it_layout)
        people_layout.addLayout(against_it_layout)

        people_groupbox.setLayout(people_layout)
        main_layout.addWidget(people_groupbox)

        self.setLayout(main_layout)
        global_theme_sensor.themeChanged.connect(self.reapply_theme)

    def toggle_edit(self, widget: QEditableGroupBox):
        if widget.is_editing:
            if self.current_editors < self.max_editors:
                self.current_editors += 1
                self.oneEditStarted.emit(f"Cases.{self.nb}")
            else:
                widget.toggle_edit_mode(callback=True)
        else:
            self.current_editors -= 1
            self.oneEditSaved.emit(f"Cases.{self.nb}")

    def toggle_edit_title(self):
        if self.title_input.isVisible():
            self.title_edit_button.setIcon(QPixmap("assets/edit.svg"))
            self.title_label.setText(self.title_input.text())
            self.title_input.hide()
            self.title_label.show()
            self.current_editors -= 1
            self.oneEditSaved.emit(f"Cases.{self.nb}")
        else:
            if self.current_editors < self.max_editors:
                self.title_edit_button.setIcon(QPixmap("assets/save.svg"))
                self.title_input.setText(self.title_label.text())
                self.title_label.hide()
                self.title_input.show()
                self.current_editors += 1
                self.oneEditStarted.emit(f"Cases.{self.nb}")

    def toggle_edit_document(self):
        if self.remove_document_button.isVisible() and self.add_document_button.isVisible():
            self.remove_document_button.hide()
            self.add_document_button.hide()
            self.current_editors -= 1
            self.oneEditSaved.emit(f"Cases.{self.nb}")
        else:
            if self.current_editors < self.max_editors:
                self.remove_document_button.show()
                self.add_document_button.show()
                self.current_editors += 1
                self.oneEditStarted.emit(f"Cases.{self.nb}")

    def toggle_edit_people(self):
        if self.add_for_it_button.isVisible() and self.add_against_it_button.isVisible():
            self.add_for_it_button.hide()
            self.add_against_it_button.hide()

            for person in self.for_it_list.people + self.against_it_list.people:
                person.remove_button.hide()
            self.current_editors -= 1
            self.oneEditSaved.emit(f"Cases.{self.nb}")
        else:
            if self.current_editors < self.max_editors:
                self.add_against_it_button.show()
                self.add_for_it_button.show()

                for person in self.for_it_list.people + self.against_it_list.people:
                    person.remove_button.show()
                self.current_editors += 1
                self.oneEditStarted.emit(f"Cases.{self.nb}")

    def add_document(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Add Document(s)", "",
                                                    "PDF Files (*.pdf);;"
                                                    "Images (*.png *.jpg *.jpeg);;"
                                                    "Videos (*.mp4 *.mov);;"
                                                    "All Files (*.*)")

        if file_names:
            for file_name in file_names:
                item = QListWidgetItem(file_name)
                item.setData(Qt.ItemDataRole.UserRole, file_name)
                self.documents_list.addItem(item)
            self.documents_list.setCurrentRow(self.documents_list.count() - 1)

    def remove_document(self):
        current_item = self.documents_list.currentItem()
        if current_item:
            self.documents_list.takeItem(self.documents_list.row(current_item))

    def preview_document(self, current, _):
        self.preview.preview_document(current.text() if current is not None else "")

    def _refresh_search_results(self, search, list_widget, filter_lawyers: bool = False):
        list_widget.clear()
        # Populate with existing people for demonstration (in practice, fetch from a database or other source)
        results, ret_vals = self.main._db_access.restricted_search(search.text(), "user")

        if ret_vals == ("",):
            return

        for i in results:
            person = self.main._persons.get(i)
            if not person:
                continue

            vals = [getattr(person, x) for x in ret_vals if x]

            name = ""
            for j, val in enumerate(vals):
                if val == "":
                    continue
                if ret_vals[j] not in ("can_be_lawyer",):
                    name += " " + val
                else:
                    name += " {Lawyer}" if val else " {Client}"

            if (filter_lawyers and "can_be_lawyer" in ret_vals and vals[ret_vals.index("can_be_lawyer")] == 1) or not filter_lawyers:
                list_item = QListWidgetItem(name)
                list_item.setData(Qt.ItemDataRole.UserRole, i)
                list_widget.addItem(list_item)

    def search_person(self, list_widget: QPersonListWidget):
        from PySide6.QtWidgets import QAbstractItemView
        dialog = QDialog(self)
        dialog.setWindowTitle('Search Person')

        dialog_layout = QVBoxLayout(dialog)

        # Search results for person group members
        person_group_label = QLabel('Person Group Members:', dialog)
        dialog_layout.addWidget(person_group_label)

        person_group_results = QListWidget(dialog)
        person_group_results.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)  # Allow multiple selection
        dialog_layout.addWidget(person_group_results)

        person_group_input = QLineEdit(dialog)
        person_group_input.setPlaceholderText('Search for a person group member...')
        person_group_input.textChanged.connect(
            lambda: self._refresh_search_results(person_group_input, person_group_results))
        person_group_input.textChanged.emit("")
        dialog_layout.addWidget(person_group_input)

        # Search results for lawyers
        lawyer_label = QLabel('Lawyer:', dialog)
        dialog_layout.addWidget(lawyer_label)

        lawyer_results = QListWidget(dialog)
        lawyer_results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)  # Allow only single selection
        dialog_layout.addWidget(lawyer_results)

        lawyer_input = QLineEdit(dialog)
        lawyer_input.setPlaceholderText('Search for a lawyer...')
        lawyer_input.textChanged.connect(lambda: self._refresh_search_results(lawyer_input, lawyer_results, True))
        lawyer_input.textChanged.emit("")
        dialog_layout.addWidget(lawyer_input)

        def _add_selected_person():
            selected_person_groups = person_group_results.selectedItems()
            if len(lawyer_results.selectedItems()) > 0:
                selected_lawyer = lawyer_results.selectedItems()[0]
            else:
                return

            if selected_person_groups and selected_lawyer:
                for item in selected_person_groups:
                    if item.text() != selected_lawyer.text():
                        list_widget.add_person(item.data(Qt.ItemDataRole.UserRole), item.text(), selected_lawyer.data(Qt.ItemDataRole.UserRole), selected_lawyer.text(), "homegrown")
                    else:
                        list_widget.add_person(item.data(Qt.ItemDataRole.UserRole), item.text(), item.data(Qt.ItemDataRole.UserRole), '', "self_represented")
                dialog.accept()
            else:
                QMessageBox.warning(dialog, 'Selection Required',
                                    'Please select at least one person group member and one lawyer.')

        select_button = QPushButton('Select', dialog)
        select_button.clicked.connect(_add_selected_person)
        dialog_layout.addWidget(select_button)

        create_new_person_button = QPushButton('Create New Person', dialog)
        create_new_person_button.clicked.connect(lambda: self.create_new_person(list_widget))
        dialog_layout.addWidget(create_new_person_button)

        dialog.resize(752, 580)

        dialog.exec_()

    def create_new_person(self, list_widget):
        dialog = AddPersonDialog(self)
        dialog.exec()

        from common.db_obj import Person
        new_person_frame = dialog.new_person_frame
        Person.new(self.main._db_access, new_person_frame.last_name_edit.text(), new_person_frame.first_name_edit.text(),
                   new_person_frame.address_edit.text(), new_person_frame.birthday_edit.text(), new_person_frame.contact_method_edit.text(),
                   new_person_frame.gender_combo.currentText(), new_person_frame.description_edit.toPlainText(),
                   new_person_frame.notes_edit.get_bullet_points(), new_person_frame.lawyer_checkbox.isChecked())

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
        self.title_input.setStyleSheet("font-size: 24px; height: 40px; background-color: palette(base);")
        self.description_text.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        self.notes_text.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        self.documents_list.setStyleSheet(f"""
                    QListWidget {{
                        border-radius: 10px;
                        background-color: palette(base);
                    }}
                    QScrollBar:vertical {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        width: 15px;
                        margin: 15px 0 15px 0;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:vertical {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-height: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                        background: none;
                    }}
                    QScrollBar:horizontal {{
                        border: none;
                        background: #{'3c3c3c' if self.theme == SystemTheme.DARK else 'f0f0f0'};
                        height: 15px;
                        margin: 0 15px 0 15px;
                        border-radius: 7px;
                    }}
                    QScrollBar::handle:horizontal {{
                        background: #{'888888' if self.theme == SystemTheme.DARK else 'cccccc'};
                        min-width: 20px;
                        border-radius: 7px;
                    }}
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                        border: none;
                        background: none;
                    }}
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                        background: none;
                    }}
                """)


class EditPersonFrame(QFrame):
    oneEditStarted = Signal(str)
    oneEditSaved = Signal(str)

    def __init__(self, nb: int, main, editable: bool = True, parent=None):
        super().__init__(parent)
        self.nb = nb
        self.person = main._persons[self.nb]
        main_layout = QVBoxLayout()
        self.current_editors = 0

        self.setStyleSheet("""
            QComboBox {
                border: 1px solid #808080;
                border-radius: 5px;
                padding: 5px;
                background-color: #ffffff;
                selection-background-color: #c0c0c0;
                selection-color: black;
            }
            QComboBox::drop-down {
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: url(assets/arrow-down.png);
            }
            QComboBox QAbstractItemView {
                border: 1px solid #808080;
                background-color: #ffffff;
                border-radius: 5px;
                margin-top: -5px;
            }
        """)

        # Top space
        top_space_layout = QQuickHBoxLayout(9, (0, 0, 0, 0))
        image_label = QLabel()
        image_label.setPixmap(QPixmap("assets/unknown_person.jpg").scaled(200, int(200 * 1.1)))
        image_label.setFixedSize(200, int(200 * 1.1))
        image_label.setStyleSheet("""
            QLabel {
                border-radius: 10px;  /* Slightly rounded corners */
            }
        """)
        top_space_layout.addWidget(image_label)

        self.main_info_groupbox = QEditableGroupBox("Main Information", editable=editable)
        self.main_info_groupbox.editButtonClicked.connect(self.toggle_main_info_edit)
        main_info_layout = self.main_info_groupbox.layout()
        name_info_layout = QQuickHBoxLayout(5, (0, 0, 0, 0))
        self.first_name_edit = QLineEdit(self.person.first_name)
        self.first_name_edit.setPlaceholderText("First Name")
        self.first_name_edit.setStyleSheet("font-size: 24px; height: 40px; background-color: palette(base);")
        self.last_name_edit = QLineEdit(self.person.last_name)
        self.last_name_edit.setPlaceholderText("Last Name")
        self.last_name_edit.setStyleSheet("font-size: 24px; height: 40px; background-color: palette(base);")
        name_info_layout.addWidget(self.first_name_edit)
        name_info_layout.addWidget(self.last_name_edit)
        main_info_layout.addLayout(name_info_layout)

        small_info_layout = QQuickHBoxLayout(5, (0, 0, 0, 0))
        self.birthday_edit = QDateEdit(QDate.fromString(self.person.birth_date.replace("-", "."), "dd.MM.yyyy"))
        self.birthday_edit.setStyleSheet("font-size: 20; height: 30px;")
        self.birthday_edit.setCalendarPopup(True)
        self.birthday_edit.setDate(QDate.currentDate())
        small_info_layout.addWidget(self.birthday_edit)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(['Male', 'Female', 'Other'])
        self.gender_combo.setCurrentText(self.person.gender)
        small_info_layout.addWidget(self.gender_combo)
        self.lawyer_checkbox = QCheckBox("Can be a lawyer")
        self.lawyer_checkbox.setChecked(self.person.can_be_lawyer)
        small_info_layout.addWidget(self.lawyer_checkbox)

        small_info_layout_2 = QQuickHBoxLayout(5, (0, 0, 0, 0))
        self.address_edit = QLineEdit(self.person.address)
        self.address_edit.setStyleSheet("font-size: 20; height: 30px;")
        self.address_edit.setPlaceholderText("Address")
        small_info_layout_2.addWidget(self.address_edit)
        self.contact_method_edit = QLineEdit(self.person.contact_info)
        self.contact_method_edit.setStyleSheet("font-size: 20; height: 30px;")
        self.contact_method_edit.setPlaceholderText("Enter a valid email")
        self.contact_method_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"[^@]+@[^@]+\.[^@]+")))
        small_info_layout_2.addWidget(self.contact_method_edit)
        main_info_layout.addLayout(small_info_layout_2)
        main_info_layout.addLayout(small_info_layout)
        top_space_layout.addWidget(self.main_info_groupbox)
        main_layout.addLayout(top_space_layout)

        description_groupbox = QEditableGroupBox("Description", "hor", editable=editable)
        description_groupbox.editButtonClicked.connect(lambda: self.toggle_edit(description_groupbox))
        extra_info_layout = QHBoxLayout()
        self.description_edit = QTextEdit(self.person.description)
        self.description_edit.setReadOnly(True)
        description_layout = description_groupbox.layout()
        description_layout.addWidget(self.description_edit)
        self.description_edit.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        notes_groupbox = QEditableGroupBox("Notes", "hor", editable=editable)
        notes_groupbox.editButtonClicked.connect(lambda: self.toggle_edit(notes_groupbox))
        self.notes_edit = QBulletPointTextEdit(self.person.notes)
        self.notes_edit.setReadOnly(True)
        notes_layout = notes_groupbox.layout()
        notes_layout.addWidget(self.notes_edit)
        self.notes_edit.setStyleSheet("border-radius: 10px; background-color: palette(base);")
        extra_info_layout.addWidget(description_groupbox)
        extra_info_layout.addWidget(notes_groupbox)
        main_layout.addLayout(extra_info_layout)

        self.setLayout(main_layout)
        self.toggle_main_info_edit()

    def toggle_edit(self, widget: QEditableGroupBox):
        if widget.is_editing:
            self.current_editors += 1
            self.oneEditStarted.emit(f"Persons.{self.nb}")
        else:
            self.current_editors -= 1
            self.oneEditSaved.emit(f"Persons.{self.nb}")

    def toggle_main_info_edit(self):
        if self.main_info_groupbox.is_editing:
            self.first_name_edit.setEnabled(True)
            self.last_name_edit.setEnabled(True)
            self.address_edit.setEnabled(True)
            self.contact_method_edit.setEnabled(True)
            self.gender_combo.setEnabled(True)
            self.lawyer_checkbox.setEnabled(True)
            self.birthday_edit.setCalendarPopup(True)
            self.current_editors += 1
            self.oneEditStarted.emit(f"Persons.{self.nb}")
        else:
            self.first_name_edit.setEnabled(False)
            self.last_name_edit.setEnabled(False)
            self.address_edit.setEnabled(False)
            self.contact_method_edit.setEnabled(False)
            self.gender_combo.setEnabled(False)
            self.lawyer_checkbox.setEnabled(False)
            self.birthday_edit.setCalendarPopup(False)
            self.current_editors -= 1
            self.oneEditSaved.emit(f"Persons.{self.nb}")
