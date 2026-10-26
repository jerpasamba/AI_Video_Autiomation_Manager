"""Quick environment & project diagnostic check for AI Video Manager."""
import os
import sys

print("Python executable:", sys.executable)
print("Working directory:", os.getcwd())

try:
    from PyQt6.QtWidgets import QApplication
    print("PyQt6: OK")
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(sys.argv)
    print("QApplication: OK")

    import app.main_window as mw
    print("app.main_window: OK")

    w = mw.MainWindow()
    print(f"MainWindow initialized successfully with {w.tabs.count()} tabs:")
    for i in range(w.tabs.count()):
        print(f"  - Tab {i+1}: {w.tabs.tabText(i)}")

    w.worker_pool.stop_all()
    print("\nAll systems operational! Ready to run: python main.py")
except Exception as e:
    import traceback
    traceback.print_exc()
