"""Bootstrap CLI: update funciona incluso si faltan dependencias del motor."""
import sys


def main():
    if sys.argv[1:2] == ['recovery']:
        from core.recovery import main as recovery_main
        return recovery_main(sys.argv[2:])
    if sys.argv[1:2] == ['update']:
        from core.updater import main as update_main
        return update_main(sys.argv[2:])
    from biorag import main as memory_main
    return memory_main()
