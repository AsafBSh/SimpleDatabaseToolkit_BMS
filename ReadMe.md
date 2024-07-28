## Simple Database Toolkit

## Overview

The **Simple Database Toolkit** is a user-friendly application designed to assist users in automating repeatable actions and adjusting database-related files in Falcon BMS , particularly XML files. The toolkit provides various functionalities, including offset fixing, folder creation, and runway dimension adjustments, all through a graphical user
interface (GUI).

## Pages Overview

## 1. Replace Page

- **Purpose**: Automates the process of replacing specific feature numbers in XML files.

- **Functionality**:
  
  - Supports single folder and multiple folder (All) modes.
  - Allows users to specify the feature number to remove and the new feature number to place.
  - Processes `FED_XXXXX.xml` files in selected folders.
  - Provides a summary log of changes made.

- **Usage**:
  
  1. Select mode (Single or All).
  2. Choose the folder or Class Table XML file.
  3. Enter the feature number to remove and the new feature number.
  4. Click "Replace" to process the files.
  5. View the summary log for details on changes made.

## 2. Offset Fixer Page

- **Purpose**: Adjusts offsets and rotations for specific features in XML files.

- **Functionality**:
  
  - Supports single folder and multiple folder (All) modes.
  - Allows adjustment of XY offsets, Z offsets, or rotation.
  - Calculates new offsets based on the feature's heading.
  - Updates `FED_XXXXX.xml` files with new offset values.
  - Provides a log of changes made.

- **Usage**:
  
  1. Select mode (Single or All).
  2. Choose the folder or Class Table XML file.
  3. Enter the feature number to modify.
  4. Select the type of offset to adjust (XY, Z, or Rotation).
  5. Enter the new offset values.
  6. Click "Apply Changes" to process the files.
  7. Review the log for details on changes made.

## 3. Runway Dimension Fixer Page

- **Purpose**: Updates runway dimensions in PHD (Possibly Heading Data) XML files.

- **Functionality**:
  
  - Supports single folder and multiple folder (All) modes.
  - Allows selection between first and second choice for dimension data.
  - Processes `PHD_XXXXX.xml` files in selected folders.
  - Updates Type 8 (RunwayDim) data based on corresponding Type 1 data.
  - Provides a log of changes and any issues encountered.

- **Usage**:
  
  1. Select mode (Single or All).
  2. Choose the folder or Class Table XML file.
  3. Select first or second choice for dimension data.
  4. Click "Assign Heading" to process the files.
  5. Review the log for details on changes and any warnings.

## 4. Folders Creator Page

- **Purpose**: Automates the creation of multiple numbered folders within a specified directory.

- **Functionality**:
  
  - Allows users to specify a start and end number for folder names.
  - Lets users select a target directory for folder creation.
  - Creates folders with names ranging from the start to end number.
  - Prevents overwriting of existing folders.

- **Usage**:
  
  1. Enter the start number for folder names.
  2. Enter the end number for folder names.
  3. Click "Select Directory" to choose where the folders will be created.
  4. Click "Create folders" to generate the folders.
  5. Review the success message or error notifications.


