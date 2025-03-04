import sys
import os
import subprocess
import urllib.request
import tarfile
import shutil
import toml
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QLabel, QLineEdit, QGridLayout, QProgressBar, QGraphicsDropShadowEffect, QHBoxLayout, QScrollArea, QScrollBar
)
from PyQt6.QtGui import QFont, QFontDatabase, QPixmap, QPalette, QBrush, QColor, QLinearGradient, QIcon
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QPointF

# Directories - I set these up to store package sources, builds, and installs in user-friendly spots
SOURCES_BASE_DIR = os.path.expanduser('/home/user/sources')
BUILD_DIR = os.path.expanduser('/home/user/sources/build')
INSTALL_DIR = os.path.expanduser('/usr')

class InstallationThread(QThread):
    # This is the background worker I wrote to handle installing packages without freezing the GUI
    # It lets the user see progress, get messages, and know when it’s done
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)

    def __init__(self, package_manager, package_name):
        # Set up the thread with the package manager and the package name - pretty straightforward
        super().__init__()
        self.package_manager = package_manager
        self.package_name = package_name
        self.error_details = ""

    def run(self):
        # This is where I handle the actual installation process, step by step - it’s like cooking a recipe!
        try:
            # Grab the package info from its TOML file - I made this easy to find and read
            toml_path = self.package_manager.find_package_toml(self.package_name)
            package_info = self.package_manager.load_package_info(toml_path)
            package = package_info['package']
            build = package_info['build']

            # Let the user know we’re starting by loading the package details
            self.message.emit(f"Loaded: {os.path.basename(toml_path)}")
            # Make sure we’ve got a place to build the package
            os.makedirs(BUILD_DIR, exist_ok=True)
            self.progress.emit(10)

            tarball = self.package_manager.fetch_source(package['src'][0], os.path.dirname(toml_path))
            self.progress.emit(30)
            # Unpack the downloaded file into the build folder
            src_dir = self.package_manager.extract_tarball(tarball, BUILD_DIR)
            self.progress.emit(50)

            # Run the build steps if they’re there - configure, compile, and install the package
            if 'configure' in build:
                self.message.emit("Configuring...")
                self.package_manager.build_package(src_dir, build['configure'], 'Configuring')
                self.progress.emit(60)
            if 'compile' in build:
                self.message.emit("Compiling...")
                self.package_manager.build_package(src_dir, build['compile'], 'Compiling')
                self.progress.emit(80)
            if 'install' in build:
                self.message.emit("Installing...")

                install_cmd = [f"pkexec {cmd}" if "sudo" in cmd else cmd for cmd in build['install']]
                self.package_manager.build_package(src_dir, install_cmd, 'Installing')
                self.progress.emit(90)

            # Clean up the temporary files after we’re done
            shutil.rmtree(src_dir)
            os.remove(tarball)
            self.progress.emit(100)
            self.finished.emit(True, f"'{self.package_name}' installed", "")
        except Exception as e:
            # If something goes wrong, I catch the error and let the user know what happened
            self.error_details = str(e)
            self.finished.emit(False, f"Failed: {str(e)}", self.error_details)

class CustomMessageBox(QWidget):
    # A pop-up I created to show messages like success or errors - I wanted it to look sharp and user-friendly
    def __init__(self, title, text, details="", font=None, parent=None):
        super().__init__(parent)
        # Made it a frameless dialog with a see-through background for that cool glass effect
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.setStyleSheet("""
            background: rgba(255, 255, 255, 50);
            border: 1px solid rgba(255, 255, 255, 50);
            border-radius: 30px;
        """)

        # Put an icon and title up top - a green check for success, red X for errors
        title_layout = QHBoxLayout()
        self.icon_label = QLabel("✅" if "installed" in text.lower() else "❌")
        self.icon_label.setFont(font if font else QFont("Helvetica", 28))
        self.icon_label.setStyleSheet("color: white; background: transparent;")
        title_layout.addWidget(self.icon_label)
        self.title_label = QLabel(title)
        self.title_label.setFont(font if font else QFont("Helvetica", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: white; background: transparent;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Main message area - I made it wrap if the text gets long
        self.message_label = QLabel(text)
        self.message_label.setFont(font if font else QFont("Helvetica", 16))
        self.message_label.setStyleSheet("color: white; background: transparent;")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        # Add extra details if there’s an error or more info - I thought this would be helpful
        if details:
            self.details_label = QLabel(f"Details: {details}")
            self.details_label.setFont(font if font else QFont("Helvetica", 14))
            self.details_label.setStyleSheet("color: rgba(255, 255, 255, 230); background: transparent;")
            self.details_label.setWordWrap(True)
            layout.addWidget(self.details_label)

        # OK button to close it - I styled it to match the glassy look of the rest
        self.ok_button = QPushButton("OK")
        self.ok_button.setFont(font if font else QFont("Helvetica", 16))
        self.ok_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 50);
                color: white;
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 30px;
                padding: 12px 30px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 70);
                border: 1px solid rgba(255, 255, 255, 70);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 90);
                border: 1px solid rgba(255, 255, 255, 90);
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.ok_button.setGraphicsEffect(shadow)
        self.ok_button.clicked.connect(self.close)
        layout.addWidget(self.ok_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(shadow)

        # Position the dialog right in the middle of the parent window - looks nice and centered
        self.setGeometry(parent.geometry().center().x() - 250, parent.geometry().center().y() - 150, 500, 300)
        self.fade_in()

    def fade_in(self):
        # I added a fade-in animation here - it gives a smooth, professional feel when the dialog pops up
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(400)
        self.opacity_anim.setStartValue(0)
        self.opacity_anim.setEndValue(1)
        self.opacity_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.opacity_anim.start()

    def exec(self):
        # Show the dialog and handle its event loop - simple but effective
        self.show()
        loop = QApplication.instance().exec()
        return loop

class PackageManager(QMainWindow):
    # The main window for LXPKG - I built this to look futuristic and be super easy to use
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LXPKG")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()
        self.selected_package = None
        self.install_thread = None
        self.load_all_packages()  # Load packages right away so users don’t have to wait
        self.showMaximized()

    def setup_ui(self):
        # Set up the font - I found a cool font called AUTOMATA, but Helvetica works fine if it’s missing
        font_path = os.path.join('assets', 'fonts', 'AUTOMATA.ttf')
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                self.custom_font = QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 14)
            else:
                self.custom_font = QFont("Helvetica", 14)
        else:
            self.custom_font = QFont("Helvetica", 14)

        # I went with a gradient background - these blues give it a slick, modern vibe
        self.palette = QPalette()
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(0, 0, 50))  # Dark blue at the bottom
        gradient.setColorAt(0.3, QColor(0, 0, 100))  # Medium blue
        gradient.setColorAt(0.6, QColor(0, 191, 255))  # Light blue (cyan)
        gradient.setColorAt(1, QColor(0, 0, 139))  # Deep blue at the top
        self.palette.setBrush(QPalette.ColorRole.Window, QBrush(gradient))
        self.setPalette(self.palette)
        self.setAutoFillBackground(True)  # Make sure the gradient covers the whole window

        # Main layout with everything centered and a right panel for progress/status
        main_widget = QWidget(self)
        main_widget.setStyleSheet("background: transparent;")  # Keep the logo and title see-through on the gradient
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(50, 50, 50, 50)
        main_layout.setSpacing(30)

        screen = self.screen().availableGeometry()
        main_widget.setMinimumSize(int(screen.width() * 0.9), int(screen.height() * 0.9))
        self.setCentralWidget(main_widget)

        # Center section (main content)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setSpacing(30)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        # Logo (Penguin Icon) - I bumped it up to 200x200 for a bigger, bolder look
        logo_path = os.path.join('assets', 'images', 'logo.png')
        logo_label = QLabel()
        if os.path.exists(logo_path):
            logo_pixmap = QPixmap(logo_path).scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
        else:
            logo_label.setText("🐧")
            logo_label.setFont(QFont("Helvetica", 80))  # Bigger penguin emoji
            logo_label.setStyleSheet("color: white;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(logo_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Title - just “LXPKG” in bold, right in the middle
        title_label = QLabel("LXPKG")
        title_label.setFont(self.custom_font)
        title_label.setStyleSheet("color: white; font-size: 30px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Search bar - I made it rounded and glassy for a modern, clean feel
        self.search_bar = QLineEdit(placeholderText="Search...")
        self.search_bar.setFont(self.custom_font)
        self.search_bar.setStyleSheet("""
            QPushButton, QLineEdit {
                background: rgba(255, 255, 255, 50);
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 30px;
                padding: 15px;
                color: white;
                font-size: 18px;
            }
            QPushButton:hover, QLineEdit:focus {
                background: rgba(255, 255, 255, 70);
                border: 1px solid rgba(255, 255, 255, 70);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 90);
                border: 1px solid rgba(255, 255, 255, 90);
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.search_bar.setGraphicsEffect(shadow)
        self.search_bar.textChanged.connect(self.search_packages)
        center_layout.addWidget(self.search_bar, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Package grid - I made this scrollable and pretty, with a modern touch
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background: transparent;")
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # No horizontal scroll
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # Vertical scroll only

        # Custom scrollbar - I designed this to look sleek and not outdated
        scroll_area.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                background: rgba(255, 255, 255, 30);
                width: 15px;
                margin: 0 0 0 0;
                border-radius: 7px;
                border: 1px solid rgba(255, 255, 255, 50);
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 70);
                border-radius: 7px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 90);
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                background: none;
                height: 0px;
            }
            QScrollBar::add-page, QScrollBar::sub-page {
                background: none;
            }
        """)

        package_widget = QWidget()
        self.package_grid = QGridLayout(package_widget)
        self.package_grid.setSpacing(30)
        self.package_grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        package_widget.setStyleSheet("""
            background: rgba(255, 255, 255, 50);
            border: 1px solid rgba(255, 255, 255, 50);
            border-radius: 30px;
            padding: 40px;
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setColor(QColor(0, 0, 0, 120))
        package_widget.setGraphicsEffect(shadow)
        scroll_area.setWidget(package_widget)
        # Make the package box shorter to ensure buttons are fully visible
        scroll_area.setMaximumHeight(int(screen.height() * 0.4))  # Limits to 40% of screen height
        center_layout.addWidget(scroll_area, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Buttons - I kept these glassy and interactive for a nice user experience
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        buttons = [
            ("Search", self.search_packages),
            ("Install", self.start_installation),
            ("Remove", self.remove_package),
            ("Quit", self.close)
        ]
        for text, callback in buttons:
            btn = QPushButton(text)
            btn.setFont(self.custom_font)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 50);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 50);
                    border-radius: 30px;
                    padding: 18px;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 70);
                    border: 1px solid rgba(255, 255, 255, 70);
                }
                QPushButton:pressed {
                    background: rgba(255, 255, 255, 90);
                    border: 1px solid rgba(255, 255, 255, 90);
                }
            """)
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(20)
            shadow.setColor(QColor(0, 0, 0, 120))
            btn.setGraphicsEffect(shadow)
            btn.clicked.connect(callback)
            self.add_button_animation(btn)
            button_layout.addWidget(btn)
        center_layout.addLayout(button_layout)

        # Add center section to main layout
        main_layout.addWidget(center_widget, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Right section (progress and status window)
        right_widget = QWidget()
        right_widget.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_widget.setFixedWidth(200)  # Fixed width for progress/status window

        # Progress bar with rounded corners (single, consistent minimal design)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(255, 255, 255, 50);
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 20px;
                height: 30px;
                text-align: right;
                color: white;
                font-size: 16px;
                padding-right: 20px;
            }
            QProgressBar::chunk {
                background: rgba(120, 160, 255, 220);
                border-radius: 20px;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.progress_bar.setGraphicsEffect(shadow)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("%p%")  # Progress percentage
        right_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        # Animated progress text label (centered in right window, glowing, transparent, consistent minimal design)
        self.progress_text = QLabel("")
        self.progress_text.setFont(self.custom_font)
        self.progress_text.setStyleSheet("""
            QLabel {
                background: rgba(255, 255, 255, 50);
                color: white;
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 15px;
                padding: 10px 20px;
                font-size: 16px;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.progress_text.setGraphicsEffect(shadow)
        self.progress_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.progress_text, alignment=Qt.AlignmentFlag.AlignCenter)
        right_widget.setVisible(False)  # Initially hidden

        # Status label (moved to right, consistent minimal design, visible text)
        self.status_label = QLabel("")
        self.status_label.setFont(self.custom_font)
        self.status_label.setStyleSheet("""
            color: white;
            background: rgba(0, 0, 0, 70);
            border: 1px solid rgba(0, 0, 0, 70);
            border-radius: 30px;
            padding: 10px;
            font-size: 16px;
            max-width: 180px;
            word-wrap: break-word;
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.status_label.setGraphicsEffect(shadow)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        right_widget.setVisible(False)  # Initially hidden

        # Add right section to main layout with animation
        right_anim = QPropertyAnimation(right_widget, b"geometry")
        right_anim.setDuration(500)
        right_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        right_widget.setGeometry(int(screen.width() * 0.7), 0, 200, int(screen.height() * 0.9))  # Initial position (right 30%)
        main_layout.addWidget(right_widget)

    def add_button_animation(self, button):
        # I added a little bounce when you click buttons - it makes them feel more fun to use
        anim = QPropertyAnimation(button, b"geometry")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        button.anim = anim
        def on_press():
            rect = button.geometry()
            anim.setStartValue(rect)
            anim.setEndValue(rect.adjusted(0, 4, 0, -4))
            anim.start()
        def on_release():
            rect = button.geometry()
            anim.setStartValue(rect)
            anim.setEndValue(rect.adjusted(0, -4, 0, 4))
            anim.start()
        button.pressed.connect(on_press)
        button.released.connect(on_release)

    def animate_progress_elements(self, show):
        # I wrote this to slide the main content and progress/status window in and out smoothly
        # It’s a nice touch that makes the app feel polished
        center_widget = self.centralWidget().layout().itemAt(0).widget()
        right_widget = self.centralWidget().layout().itemAt(1).widget()
        screen = self.screen().availableGeometry()

        if show:
            # Move the center stuff left and show the right panel for progress and status
            center_anim = QPropertyAnimation(center_widget, b"geometry")
            center_anim.setDuration(500)
            center_anim.setStartValue(center_widget.geometry())
            center_anim.setEndValue(QRect(0, 0, int(screen.width() * 0.7), int(screen.height() * 0.9)))
            center_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            center_anim.start()

            right_anim = QPropertyAnimation(right_widget, b"geometry")
            right_anim.setDuration(500)
            right_anim.setStartValue(right_widget.geometry())
            right_anim.setEndValue(QRect(int(screen.width() * 0.7), 0, 200, int(screen.height() * 0.9)))
            right_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            right_anim.start()
            right_widget.setVisible(True)
        else:
            # Slide the center back to the middle and hide the right panel
            center_anim = QPropertyAnimation(center_widget, b"geometry")
            center_anim.setDuration(500)
            center_anim.setStartValue(center_widget.geometry())
            center_anim.setEndValue(QRect(0, 0, int(screen.width() * 0.9), int(screen.height() * 0.9)))
            center_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            center_anim.start()

            right_anim = QPropertyAnimation(right_widget, b"geometry")
            right_anim.setDuration(500)
            right_anim.setStartValue(right_widget.geometry())
            right_anim.setEndValue(QRect(int(screen.width() * 0.9), 0, 200, int(screen.height() * 0.9)))
            right_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            right_anim.start()
            QTimer.singleShot(500, lambda: right_widget.setVisible(False))  # Hide after the animation finishes

    def animate_progress_text(self, value):
        # Update the progress text with a fade effect - I think this looks really smooth and professional
        self.progress_text.setText(f"{value}%")
        anim = QPropertyAnimation(self.progress_text, b"windowOpacity")
        anim.setDuration(300)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.start()
        self.animate_progress_elements(True)  # Show the progress/status panel
        QTimer.singleShot(2000, lambda: self.fade_out_progress_text())  # Hide it after 2 seconds

    def fade_out_progress_text(self):
        # Fade out the progress text and slide everything back - I timed it to match the animation for a clean exit
        anim = QPropertyAnimation(self.progress_text, b"windowOpacity")
        anim.setDuration(300)
        anim.setStartValue(1)
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.start()
        QTimer.singleShot(300, lambda: self.animate_progress_elements(False))  # Hide the panel after fading

    def load_package_info(self, toml_path):
        # Load package details from a TOML file - I wrote this to make it easy to read package data
        try:
            with open(toml_path, 'r') as f:
                return toml.load(f)
        except Exception as e:
            raise Exception(f"Oops, couldn’t load the TOML file: {e}")

    def fetch_source(self, url, dest_dir):
        # Download the package source from the web - I added error handling in case it fails
        try:
            filename = os.path.join(dest_dir, os.path.basename(url))
            if not os.path.exists(filename):
                urllib.request.urlretrieve(url, filename)
                self.status_label.setText(f"Got it! Downloaded {os.path.basename(url)}")
            return filename
        except Exception as e:
            raise Exception(f"Uh-oh, couldn’t download the source: {e}")

    def extract_tarball(self, tarball, dest_dir):
        # Unpack the downloaded tarball - this is where we get the package files ready to build
        try:
            with tarfile.open(tarball, 'r:*') as tar:
                tar.extractall(path=dest_dir)
            extracted = [os.path.join(dest_dir, d) for d in os.listdir(dest_dir) 
                        if os.path.isdir(os.path.join(dest_dir, d))]
            return extracted[0] if extracted else dest_dir
        except Exception as e:
            raise Exception(f"Yikes, couldn’t extract the tarball: {e}")

    def build_package(self, src_dir, commands, stage):
        # Build and install the package - I broke it into steps so it’s clear and handles errors well
        try:
            for cmd in commands:
                self.status_label.setText(f"{stage}: {cmd}")
                result = subprocess.run(cmd, shell=True, cwd=src_dir, 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode != 0:
                    error_msg = result.stderr.decode()
                    raise Exception(f"{stage} didn’t work: {error_msg}")
                self.status_label.setText(f"{stage} done")
        except Exception as e:
            raise Exception(f"Oh no, the build failed: {e}")

    def find_package_toml(self, package_name):
        # Look for the package’s TOML file in the sources - I made it search recursively for flexibility
        try:
            for root, _, files in os.walk(SOURCES_BASE_DIR):
                for file in files:
                    if file.endswith('.toml') and package_name.lower() in file.lower():
                        return os.path.join(root, file)
            raise Exception(f"Couldn’t find the package '{package_name}'")
        except Exception as e:
            raise Exception(f"Search for the package failed: {e}")

    def start_installation(self):
        # Start installing a package - I added checks to avoid installing two things at once
        if not self.selected_package:
            CustomMessageBox("Error", "Hey, pick a package first!", "", self.custom_font, self).exec()
            return
        if self.install_thread and self.install_thread.isRunning():
            CustomMessageBox("Error", "Hold on, an installation’s already running!", "", self.custom_font, self).exec()
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.install_thread = InstallationThread(self, self.selected_package)
        self.install_thread.progress.connect(self.animate_progress)
        self.install_thread.message.connect(self.status_label.setText)
        self.install_thread.finished.connect(self.installation_finished)
        self.install_thread.start()

    def animate_progress(self, value):
        # Update the progress bar with a smooth slide - I think this looks really nice and polished
        self.progress_bar.setValue(value)
        self.animate_progress_text(value)
        anim = QPropertyAnimation(self.progress_bar, b"value")
        anim.setDuration(400)
        anim.setStartValue(self.progress_bar.value())
        anim.setEndValue(value)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.start()

    def installation_finished(self, success, message, details):
        # Wrap up the installation and show the result in a message box
        self.progress_bar.setVisible(False)
        CustomMessageBox("Result", message, details, self.custom_font, self).exec()
        self.install_thread = None

    def search_packages(self):
        # Let users search for packages - I made it case-insensitive so it’s more user-friendly
        query = self.search_bar.text().lower()
        self.load_all_packages(query)

    def get_all_package_names(self):
        # Get a list of all package names from TOML files - I wrote this to make finding packages easy
        try:
            return [os.path.splitext(f)[0] for root, _, files in os.walk(SOURCES_BASE_DIR) 
                    for f in files if f.endswith('.toml')]
        except Exception as e:
            raise Exception(f"Couldn’t grab the package names: {e}")

    def load_all_packages(self, query=""):
        # Show all packages or filter them based on the search - I added a fade-in to make it look smooth
        for i in range(self.package_grid.count()):
            self.package_grid.itemAt(i).widget().deleteLater()
        
        packages = [pkg for pkg in self.get_all_package_names() if query in pkg.lower()]
        for i, pkg in enumerate(packages):
            btn = QPushButton(f"📁 {pkg}")
            btn.setFont(self.custom_font)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 50);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 50);
                    border-radius: 30px;
                    padding: 20px 25px;
                    font-size: 20px;
                    min-width: 200px;
                    text-align: center;
                    white-space: normal;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 70);
                    border: 1px solid rgba(255, 255, 255, 70);
                }
                QPushButton:pressed {
                    background: rgba(255, 255, 255, 90);
                    border: 1px solid rgba(255, 255, 255, 90);
                }
            """)
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(25)
            shadow.setColor(QColor(0, 0, 0, 120))
            btn.setGraphicsEffect(shadow)
            btn.clicked.connect(lambda checked, p=pkg: self.package_selected(p))
            row = i // 2
            col = i % 2
            self.package_grid.addWidget(btn, row, col)
        
        anim = QPropertyAnimation(self.package_grid.itemAt(0).widget() if self.package_grid.count() else self, b"windowOpacity")
        anim.setDuration(500)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.start()

    def package_selected(self, pkg):
        # Update the UI when someone picks a package - I added a status message to keep things clear
        self.selected_package = pkg
        self.status_label.setText(f"Selected: {pkg}")

    def remove_package(self):
        # Remove a package - I made sure it’s safe and gives feedback if something goes wrong
        if not self.selected_package:
            CustomMessageBox("Error", "You need to select a package first!", "", self.custom_font, self).exec()
            return
        try:
            toml_path = self.find_package_toml(self.selected_package)
            pkg_info = self.load_package_info(toml_path)
            files = pkg_info.get('install', {}).get('files', [])
            for file in files:
                path = os.path.join(INSTALL_DIR, file.lstrip('/'))
                if os.path.exists(path):
                    os.remove(path)
            CustomMessageBox("Success", f"Removed {self.selected_package}!", "", self.custom_font, self).exec()
        except Exception as e:
            CustomMessageBox("Error", f"Couldn’t remove the package: {str(e)}", str(e), self.custom_font, self).exec()

def main():
    # Launch the app - I kept this simple but it gets LXPKG up and running nicely
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = PackageManager()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

# Written by @user7210unix
