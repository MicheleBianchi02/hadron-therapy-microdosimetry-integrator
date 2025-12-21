import argparse
import sys

from PyQt6.QtCore import QLocale
from PyQt6.QtWidgets import QApplication
from window import MainWindow


def main(simulate: bool, baud_rate: int, single_channel: bool) -> None:
    application = QApplication(sys.argv)

    # the locale is used to display . instead of , as decimal separator
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))

    window = MainWindow(simulate, baud_rate, single_channel)

    window.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--simulate",
        action="store_true",
        default=False,
        help="Simulate an experimental scenario.",
    )

    parser.add_argument(
        "-b",
        "--baud-rate",
        action="store",
        default=115200,
        type=int,
        help="Set a custom baud rate (default: 115200).",
    )

    parser.add_argument(
        "-c",
        "--single-channel",
        action="store_true",
        default=False,
        help="Set the system to a single channgel.",
    )

    args = parser.parse_args()

    main(args.simulate, args.baud_rate, args.single_channel)
