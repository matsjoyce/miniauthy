import base64
import datetime
import json
import os
import pathlib
import sys
from typing import Any, Iterable, Optional

import pyotp
from cryptography import fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf import pbkdf2
from PySide6 import QtCore, QtGui, QtQml

QML_IMPORT_NAME = "miniauthy"
QML_IMPORT_MAJOR_VERSION = 1

FILE_LOCATION = pathlib.Path("~").expanduser() / ".miniauthy.json.enc"


@QtQml.QmlElement
class TOTPModel(QtCore.QAbstractListModel):
    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._totps = []
        self._salt = b""
        self._key = b""
        self._unlocked = False
        self._failedToLoad = False

    unlockedChanged = QtCore.Signal()

    @QtCore.Property(bool, notify=unlockedChanged)
    def unlocked(self) -> bool:
        return self._unlocked

    @QtCore.Property(bool, notify=unlockedChanged)
    def firstTime(self) -> bool:
        return not FILE_LOCATION.exists()

    failedToLoadChanged = QtCore.Signal()

    @QtCore.Property(bool, notify=failedToLoadChanged)
    def failedToLoad(self) -> bool:
        return self._failedToLoad

    @QtCore.Slot(str)
    def unlock(self, password: str) -> None:
        if FILE_LOCATION.exists():
            data = FILE_LOCATION.read_bytes()
            if len(data) < 16:
                return
        else:
            data = os.urandom(16)
        salt = data[:16]
        key = base64.urlsafe_b64encode(
            pbkdf2.PBKDF2HMAC(
                algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000
            ).derive(password.encode())
        )
        if len(data) > 16:
            try:
                data = fernet.Fernet(key).decrypt(data[16:])
            except fernet.InvalidToken:
                self._failedToLoad = True
                self.failedToLoadChanged.emit()
                return
            totps = json.loads(data)
        else:
            totps = []

        self.beginResetModel()
        self._totps = [pyotp.parse_uri(totp) for totp in totps]
        self.endResetModel()
        self._salt, self._key = salt, key
        if not FILE_LOCATION.exists():
            self._save()
        self._unlocked = True
        self.unlockedChanged.emit()

    def _save(self) -> None:
        totps = json.dumps([totp.provisioning_uri() for totp in self._totps]).encode()
        data = self._salt + fernet.Fernet(self._key).encrypt(totps)
        FILE_LOCATION.write_bytes(data)

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self._totps) if not parent.isValid() else 0

    @QtCore.Slot(str, str, str, result=int)
    def add(self, issuer: str, name: str, secret: str) -> int:
        try:
            new_totp = pyotp.TOTP(secret, issuer=issuer, name=name)
            new_totp.now()
        except ValueError:
            return -1
        self.beginInsertRows(QtCore.QModelIndex(), len(self._totps), len(self._totps))
        self._totps.append(new_totp)
        self.endInsertRows()
        self._save()
        return len(self._totps) - 1

    @QtCore.Slot(QtCore.QUrl)
    def importFromFile(self, fname: QtCore.QUrl) -> None:
        with pathlib.Path(fname.toLocalFile()).open("rb") as f:
            contents = json.load(f)

        def _recursiveSearch(obj: Any) -> Iterable[pyotp.TOTP]:
            if isinstance(obj, list):
                for item in obj:
                    yield from _recursiveSearch(item)
            elif isinstance(obj, dict):
                for item in obj.values():
                    yield from _recursiveSearch(item)
            elif isinstance(obj, str):
                if obj.startswith("otpauth://totp"):
                    try:
                        totp = pyotp.parse_uri(obj)
                        totp.now()
                        yield totp
                    except ValueError:
                        pass

        totps = list(_recursiveSearch(contents))
        if totps:
            self.beginInsertRows(
                QtCore.QModelIndex(),
                len(self._totps),
                len(self._totps) + len(totps) - 1,
            )
            self._totps.extend(totps)
            self.endInsertRows()
            self._save()

    def data(
        self,
        index: QtCore.QModelIndex,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not self.checkIndex(
            index,
            QtCore.QAbstractItemModel.CheckIndexOption.IndexIsValid
            | QtCore.QAbstractItemModel.CheckIndexOption.ParentIsInvalid,
        ):
            return None

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if self._totps[index.row()].issuer:
                if self._totps[index.row()].name:
                    return (
                        self._totps[index.row()].issuer
                        + " for "
                        + self._totps[index.row()].name
                    )
                return self._totps[index.row()].issuer
            return self._totps[index.row()].name
        elif role == QtCore.Qt.ItemDataRole.UserRole:
            return self._totps[index.row()]


@QtQml.QmlElement
class TOTP(QtCore.QObject):
    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._model: Optional[TOTPModel] = None
        self._index = -1
        self._code_idx = 0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._update)

    modelChanged = QtCore.Signal()

    @QtCore.Property(TOTPModel, notify=modelChanged)
    def model(self) -> Optional[TOTPModel]:
        return self._model

    @model.setter
    def model(self, model: Optional[TOTPModel]) -> None:
        self._model = model
        self.modelChanged.emit()
        self.currentCodeChanged.emit()
        self.timeLeftChanged.emit()
        if self._model is not None and self._index != -1:
            self._timer.start()
        else:
            self._timer.stop()

    indexChanged = QtCore.Signal()

    @QtCore.Property(int, notify=indexChanged)
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, index: int) -> None:
        self._index = index
        self.indexChanged.emit()
        self.currentCodeChanged.emit()
        self.timeLeftChanged.emit()
        if self._model is not None and self._index != -1:
            self._timer.start()
        else:
            self._timer.stop()

    @QtCore.Property(float, notify=indexChanged)
    def timeInterval(self) -> float:
        if self._model is None or self._index == -1:
            return 0
        return (
            self._model.index(self._index, 0)
            .data(QtCore.Qt.ItemDataRole.UserRole)
            .interval
        )

    @QtCore.Property(str, notify=indexChanged)
    def name(self) -> str:
        if self._model is None or self._index == -1:
            return ""
        return self._model.index(self._index, 0).data(
            QtCore.Qt.ItemDataRole.DisplayRole
        )

    currentCodeChanged = QtCore.Signal()

    @QtCore.Property(str, notify=currentCodeChanged)
    def currentCode(self) -> str:
        if self._model is None or self._index == -1:
            return ""
        return (
            self._model.index(self._index, 0)
            .data(QtCore.Qt.ItemDataRole.UserRole)
            .now()
        )

    timeLeftChanged = QtCore.Signal()

    @QtCore.Property(float, notify=timeLeftChanged)
    def timeLeft(self) -> float:
        if self._model is None or self._index == -1:
            return 0
        totp = self._model.index(self._index, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        return totp.interval - datetime.datetime.now().timestamp() % totp.interval

    @QtCore.Slot()
    def copy(self) -> None:
        QtGui.QGuiApplication.clipboard().setText(self.currentCode)

    @QtCore.Slot()
    def _update(self) -> None:
        self.timeLeftChanged.emit()
        totp = self._model.index(self._index, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        code_idx = datetime.datetime.now().timestamp() % totp.interval
        if code_idx != self._code_idx:
            self.currentCodeChanged.emit()
            self._code_idx = code_idx


if __name__ == "__main__":
    app = QtGui.QGuiApplication(sys.argv)
    totpModel = TOTPModel()
    engine = QtQml.QQmlApplicationEngine()
    engine.setInitialProperties({"totpModel": totpModel})
    engine.load(pathlib.Path(__file__).parent / "Main.qml")
    if not engine.rootObjects():
        raise RuntimeError("Could not load Main.qml")
    code = app.exec()
    del engine
    sys.exit(code)
