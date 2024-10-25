import os
import glob
import logging

from typing import List

import vtk
import qt
import ctk
import slicer
from slicer.ScriptedLoadableModule import *


class baselineLoader(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Custom Data Loader"
        self.parent.categories = ["Utilities"]
        self.parent.dependencies = []
        self.parent.contributors = ["Your Name"]
        self.parent.helpText = """
            Module for automatic loading of data from dropped folders.
            """
        self.parent.acknowledgementText = """
            Developed for custom data loading workflow.
            """


class GroupSelectionDialog(qt.QDialog):
    def __init__(self, total_groups):
        qt.QDialog.__init__(self)
        self.setWindowTitle("Select Groups to Load")

        layout = qt.QVBoxLayout(self)

        # Add information label
        infoLabel = qt.QLabel(
            f"Found {total_groups} groups.\nEach group contains:\n- 1 deformation field\n- 1 volume\n- 1 segmentation")
        layout.addWidget(infoLabel)

        # Add slider
        self.slider = qt.QSlider(qt.Qt.Horizontal)
        self.slider.setMinimum(1)
        self.slider.setMaximum(total_groups)
        self.slider.setValue(1)

        # Add label to show current value
        self.valueLabel = qt.QLabel("Loading: 1 group")
        self.slider.valueChanged.connect(self.updateLabel)

        layout.addWidget(self.valueLabel)
        layout.addWidget(self.slider)

        # Add OK and Cancel buttons
        self.buttonBox = qt.QDialogButtonBox()
        self.buttonBox.addButton(qt.QDialogButtonBox.Ok)
        self.buttonBox.addButton(qt.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

    def updateLabel(self, value):
        self.valueLabel.text = f"Loading: {value} group{'s' if value > 1 else ''}"

    def getSelectedCount(self):
        return self.slider.value


class DropWidget(qt.QFrame):
    def __init__(self, parent=None):
        # Get the widget's layout widget as the parent
        if parent is not None:
            parent_widget = parent.parent
        else:
            parent_widget = None
        qt.QFrame.__init__(self, parent_widget)

        self.setAcceptDrops(True)
        self.setStyleSheet(
            "QFrame { border: 2px dashed #999; border-radius: 5px; }")
        self.setMinimumHeight(100)

        # Create layout
        layout = qt.QVBoxLayout(self)
        label = qt.QLabel("Drop folder here")
        label.setAlignment(qt.Qt.AlignCenter)
        layout.addWidget(label)

        # Store reference to parent widget for accessing configuration
        self.moduleWidget = parent

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
            self.setStyleSheet(
                "QFrame { border: 2px dashed #44A; border-radius: 5px; background: #EEF; }")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "QFrame { border: 2px dashed #999; border-radius: 5px; }")

    def dropEvent(self, event):
        self.setStyleSheet(
            "QFrame { border: 2px dashed #999; border-radius: 5px; }")
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                paths.append(path)

        if paths and self.moduleWidget:
            self.moduleWidget.logic.loadDataFromFolders(
                paths[0])  # Use first dropped folder


class baselineLoaderWidget(ScriptedLoadableModuleWidget):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.logic = baselineLoaderLogic()

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        # Add path selector at the top
        pathLayout = qt.QHBoxLayout()
        pathLabel = qt.QLabel("Data directory:")
        pathLayout.addWidget(pathLabel)
        self.pathLineEdit = ctk.ctkPathLineEdit()
        self.pathLineEdit.setCurrentPath("/data/LungCT_preprocessed_new")
        pathLayout.addWidget(self.pathLineEdit)
        self.layout.addLayout(pathLayout)

        # Add control panel
        controlsLayout = qt.QHBoxLayout()

        # Add indices input
        indicesLabel = qt.QLabel("Indices:")
        self.indicesInput = qt.QLineEdit()
        self.indicesInput.setToolTip(
            "Enter comma-separated indices (e.g., 0,3,4).\nEmpty input means all")
        controlsLayout.addWidget(indicesLabel)
        controlsLayout.addWidget(self.indicesInput)

        # Add stretch to push everything to the left
        controlsLayout.addStretch()

        # Add controls layout to main layout
        controlWidget = qt.QWidget()
        controlWidget.setLayout(controlsLayout)
        self.layout.addWidget(controlWidget)

        # Add drop zone
        self.dropWidget = DropWidget(self)
        self.layout.addWidget(self.dropWidget)
        self.layout.addStretch(1)

        self.logic.DropWidget = self.dropWidget


class baselineLoaderLogic(ScriptedLoadableModuleLogic):
    def __init__(self):
        self.DropWidget = None

    def collapse_all_segmentations(self) -> None:

        subjectHierarchyNode = slicer.mrmlScene.GetSubjectHierarchyNode()

        if subjectHierarchyNode:
            itemIDs = vtk.vtkIdList()
            subjectHierarchyNode.GetItemChildren(
                subjectHierarchyNode.GetSceneItemID(), itemIDs, True)

            for i in range(itemIDs.GetNumberOfIds()):
                itemID = itemIDs.GetId(i)
                node = subjectHierarchyNode.GetItemDataNode(itemID)
                if node and node.IsA("vtkMRMLSegmentationNode"):

                    subjectHierarchyNode.SetItemExpanded(itemID, False)

    def loadOriginalData(self, file_name: str) -> None:
        file_name = file_name.replace('.nii.gz', '')
        moving_name, fixed_name = file_name.split('_deformed_to_')

        data_path: str = str(
            self.DropWidget.moduleWidget.pathLineEdit.currentPath)

        if data_path == "":
            return

        # find all files recrusively in data_path
        for file in glob.glob(data_path + f"/*/{moving_name}.nii.gz", recursive=True):
            if any([x in file.lower() for x in ['mask', 'seg', 'label']]):
                slicer.util.loadSegmentation(file)
            else:
                slicer.util.loadVolume(file)

        for file in glob.glob(data_path + f"/*/{fixed_name}.nii.gz", recursive=True):
            if any([x in file.lower() for x in ['mask', 'seg', 'label']]):
                slicer.util.loadSegmentation(file)
            else:
                slicer.util.loadVolume(file)

    def loadDataFromFolders(self, rootPath):
        """
        Load data from the specified directory structure
        """
        try:
            # First count how many groups we have
            deformationsPath = os.path.join(rootPath, "deformations")
            deformation_files = [f for f in os.listdir(deformationsPath)
                                 if f.endswith(('.nii.gz'))]

            # srot the files
            deformation_files.sort()

            total_groups = len(deformation_files)

            # Determine which groups to load

            indices_text = self.DropWidget.moduleWidget.indicesInput.text.strip()
            if indices_text == "":
                groups_to_load = list(range(total_groups))

            else:
                # Parse indices from text input
                try:
                    indices: List[int] = [int(idx.strip())
                                          for idx in indices_text.split(',')]
                    groups_to_load: List[int] = [
                        i for i in indices if 0 <= i < total_groups]

                except ValueError:
                    slicer.util.errorDisplay(
                        "Invalid indices format. Please use comma-separated numbers.")
                    return

            # Load the selected groups
            for i in groups_to_load:
                # Load displacement field
                filepath = os.path.join(deformationsPath, deformation_files[i])
                logging.info(f"Loading displacement field: {filepath}")
                slicer.util.loadTransform(filepath)

                # Get base name for matching deformed files
                base_name = deformation_files[i].replace(
                    '_deformation_', '_deformed_')
                deformedPath = os.path.join(rootPath, "deformed")

                # Load volume
                volume_name = base_name
                volume_path = os.path.join(deformedPath, volume_name)
                if os.path.exists(volume_path):
                    logging.info(f"Loading volume: {volume_path}")
                    slicer.util.loadVolume(volume_path)

                # Load segmentation
                seg_name = base_name.replace('.nii.gz', '_seg.nii.gz')
                seg_path = os.path.join(deformedPath, seg_name)
                if os.path.exists(seg_path):
                    logging.info(f"Loading segmentation: {seg_path}")
                    slicer.util.loadSegmentation(seg_path)

                self.loadOriginalData(volume_name)

            # switch to data module
            slicer.util.selectModule("Data")

            self.collapse_all_segmentations()

        except Exception as e:
            logging.error(f"Error loading data: {str(e)}")
            slicer.util.errorDisplay(f"Error loading data: {str(e)}")
