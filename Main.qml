import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs as QQD
import QtQuick.Layouts as QQL
import miniauthy as MiniAuthy

QQC.ApplicationWindow {
    id: root

    property bool adding: false
    required property MiniAuthy.TOTPModel totpModel

    minimumHeight: 300
    minimumWidth: 200
    title: "MiniAuthy"
    visible: true

    MiniAuthy.TOTP {
        id: selectedTotp

        model: totpModel
    }

    QQL.GridLayout {
        anchors.fill: parent
        columns: 2

        ListView {
            QQL.Layout.columnSpan: 2
            QQL.Layout.fillHeight: true
            QQL.Layout.fillWidth: true
            clip: true
            model: root.totpModel

            delegate: QQC.Label {
                required property string display
                required property int index

                elide: Text.ElideRight
                font.pixelSize: 14
                height: 24
                text: display
                verticalAlignment: Text.AlignVCenter
                width: parent.width

                background: Rectangle {
                    color: mouseArea.containsMouse ? parent.palette.highlight : "transparent"
                }

                MouseArea {
                    id: mouseArea

                    anchors.fill: parent
                    hoverEnabled: true

                    onClicked: selectedTotp.index = parent.index
                }
            }
        }

        QQC.Button {
            QQL.Layout.fillWidth: true
            text: "Add"

            onClicked: root.adding = true
        }

        QQC.Button {
            QQL.Layout.fillWidth: true
            text: "Import"

            onClicked: importDialog.open()
        }
    }

    QQD.FileDialog {
        id: importDialog

        nameFilters: ["JSON files (*.json)", "All files (*)"]

        onAccepted: root.totpModel.importFromFile(selectedFile)
    }

    QQC.Pane {
        anchors.fill: parent
        visible: selectedTotp.index !== -1

        QQL.GridLayout {
            anchors.fill: parent
            columns: 2

            QQC.Label {
                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
                font.pixelSize: 20
                text: selectedTotp.name
                wrapMode: Text.Wrap
            }

            Item {
                QQL.Layout.columnSpan: 2
                QQL.Layout.fillHeight: true
            }

            QQC.Label {
                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
                font.pixelSize: 30
                horizontalAlignment: Text.AlignHCenter
                text: selectedTotp.currentCode
            }

            QQC.ProgressBar {
                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
                from: 0
                to: selectedTotp.timeInterval
                value: selectedTotp.timeLeft
            }

            Item {
                QQL.Layout.columnSpan: 2
                QQL.Layout.fillHeight: true
            }

            QQC.Button {
                QQL.Layout.fillWidth: true
                text: "Back"

                onClicked: selectedTotp.index = -1
            }

            QQC.Button {
                QQL.Layout.fillWidth: true
                text: "Copy"

                onClicked: selectedTotp.copy()
            }
        }
    }

    QQC.Pane {
        anchors.fill: parent
        visible: root.adding

        QQL.GridLayout {
            anchors.fill: parent
            columns: 2

            QQC.Label {
                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
                text: "Issuer"
            }

            QQC.TextField {
                id: issuerEdit

                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
            }

            QQC.Label {
                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
                text: "Name"
            }

            QQC.TextField {
                id: nameEdit

                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
            }

            QQC.Label {
                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
                text: "Key"
            }

            QQC.TextField {
                id: keyEdit

                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
            }

            QQC.Label {
                id: keyError

                QQL.Layout.columnSpan: 2
                QQL.Layout.fillWidth: true
                color: "#aa0000"
                text: "Incorrect key, please check you copied all the characters"
                visible: false
                wrapMode: Text.Wrap
            }

            Item {
                QQL.Layout.columnSpan: 2
                QQL.Layout.fillHeight: true
            }

            QQC.Button {
                QQL.Layout.fillWidth: true
                text: "Cancel"

                onClicked: {
                    issuerEdit.text = "";
                    nameEdit.text = "";
                    keyEdit.text = "";
                    keyError.visible = false;
                    root.adding = false;
                }
            }

            QQC.Button {
                QQL.Layout.fillWidth: true
                enabled: issuerEdit.text !== "" && keyEdit.text !== ""
                text: "Save"

                onClicked: {
                    selectedTotp.index = root.totpModel.add(issuerEdit.text, nameEdit.text, keyEdit.text);
                    if (selectedTotp.index == -1) {
                        keyError.visible = true;
                        return;
                    }
                    issuerEdit.text = "";
                    nameEdit.text = "";
                    keyEdit.text = "";
                    keyError.visible = false;
                    root.adding = false;
                }
            }
        }
    }

    QQC.Pane {
        anchors.fill: parent
        focus: true
        visible: !root.totpModel.unlocked

        QQL.ColumnLayout {
            anchors.fill: parent

            Item {
                QQL.Layout.fillHeight: true
            }

            QQC.Label {
                QQL.Layout.fillWidth: true
                text: root.totpModel.firstTime ? "Set password" : "Password"
                wrapMode: Text.Wrap
            }

            QQC.TextField {
                id: passwordEdit

                QQL.Layout.fillWidth: true
                echoMode: TextInput.Password
                focus: true

                onAccepted: {
                    root.totpModel.unlock(passwordEdit.text);
                    passwordEdit.text = "";
                }
            }

            QQC.Label {
                QQL.Layout.fillWidth: true
                color: "#aa0000"
                text: "Incorrect password, please try again"
                visible: root.totpModel.failedToLoad
                wrapMode: Text.Wrap
            }

            Item {
                QQL.Layout.fillHeight: true
            }

            QQC.Button {
                QQL.Layout.fillWidth: true
                enabled: passwordEdit.text !== ""
                text: "Unlock"

                onClicked: {
                    root.totpModel.unlock(passwordEdit.text);
                    passwordEdit.text = "";
                }
            }
        }
    }
}
