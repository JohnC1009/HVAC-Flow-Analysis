"""Entry point for HVAC Flow Analysis - Psychrometric Tool."""

import sys
from PyQt5.QtWidgets import QApplication
from hvac_flow.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("HVAC Flow Analysis — Psychrometric Tool")
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
