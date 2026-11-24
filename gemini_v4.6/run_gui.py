import sys


def main() -> int:
    if "--legacy" in sys.argv:
        from nganhangde import gui_qt
        return gui_qt.main() if hasattr(gui_qt, "main") else 0

    from nganhangde.ui.main_window import main as mylt_main
    return mylt_main(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
