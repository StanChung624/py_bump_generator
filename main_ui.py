from __future__ import annotations

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from ui.main_window import VBumpUI
from ui.logic import VBumpLogic

def main():
    app = QApplication(sys.argv)
    
    # Define proxy directory
    proxy_dir = Path(__file__).resolve().parent / ".proxy_runtime"
    
    # We need a placeholder for the log function before the UI is created
    # but the UI's log method is what we actually want to use.
    # So we can pass a dummy and then update it, or better, 
    # use a signal/slot or a simple callback update.
    
    def dummy_log(text: str):
        print(f"[Logic] {text}")

    logic = VBumpLogic(proxy_dir, dummy_log)
    ui = VBumpUI(logic)
    
    # Update the logic's log callback to use the UI's log method
    logic.log = ui.log
    
    ui.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
