import os
import sys
import re
import tkinter as tk
import customtkinter as Ctk
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from PIL import Image, ImageTk
import math
from math import sqrt
import textwrap

class MainPage(Ctk.CTk):
    def __init__(self, *args, **kwargs):
        Ctk.CTk.__init__(self, *args, **kwargs)

        # Set Geometry of the page
        self.geometry("800x600")
        self.configure(bg="#FFFFFF")
        self.resizable(True, True)

        # Initialize a frame for the TabView (tab container)
        self.tab_frame = tk.Frame(self)
        self.tab_frame.place(relwidth=1, relheight=1)  # Fill the entire window

        # Initialize the TabView (tab container)
        self.tab_view = Ctk.CTkTabview(self.tab_frame)
        self.tab_view.pack(fill="both", expand=True)

        # Set Shared data variables
        self.shared_data = {}

        self.frames = {}
        for F in (
            DashboardPage,
            TutorialPage,
            ReplacePage,
            OffsetFixerPage,
            RunwayDimFixerPage,
            FoldersCreatorPage,
            ReformatParentsPage
        ):
            page_name = F.__name__
            frame = F(parent=self, controller=self)
            self.frames[page_name] = frame

        # Add different pages to the TabView
        self.add_page(DashboardPage, "MainBoard")
        self.add_page(TutorialPage, "Tutorial")
        self.add_page(ReplacePage, "Replace Features")
        self.add_page(OffsetFixerPage, "Offset Fixer")
        self.add_page(RunwayDimFixerPage, "RunwayDim Fixer")
        self.add_page(FoldersCreatorPage, "Folder Creator")
        self.add_page(ReformatParentsPage, "Reformat Parents")
        self.add_page(ParkingFixerPage, "Parking Fixer")

        # Set Name and Icon
        self.title("Simple Database Toolkit v1.3")
        icon_path = os.path.join("media", "128_Icon.ico")
        self.iconbitmap(icon_path)

    def add_page(self, page_class, title):
        """Add a new page to the TabView."""
        tab = self.tab_view.add(title)
        page = page_class(parent=tab, controller=self)
        self.frames[page_class.__name__] = page
        page.pack(fill="both", expand=True)


class DashboardPage(Ctk.CTkFrame):
    def __init__(self, parent, controller):
        Ctk.CTkFrame.__init__(self, parent)
        self.controller = controller

        # Load the image
        image_path = os.path.join("media", "Main.png")
        pil_image = Image.open(image_path)

        # Convert PIL image to Tkinter-compatible photo image
        self.tk_image = ImageTk.PhotoImage(pil_image)

        # Create a label to display the image
        image_label = tk.Label(self, image=self.tk_image, bg="#dbdbdb")
        image_label.pack(pady=10, padx=10)


class ReplacePage(Ctk.CTkFrame):
    def __init__(self, parent, controller):
        Ctk.CTkFrame.__init__(self, parent)
        self.controller = controller

        # Start label and entry
        self.start_frame = Ctk.CTkFrame(self)
        self.start_frame.pack(pady=30, fill="x")

        start_label = Ctk.CTkLabel(
            self.start_frame,
            text="Please choose a CT/Folder and specify the Feature’s CT number which you willing to replace",
        )
        start_label.pack()

        # Frame for XML file selection
        self.xml_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.xml_frame.pack(pady=10, padx=10, fill="x")

        # Frame for FCD entries
        fcd_num_frame = Ctk.CTkFrame(self, fg_color="transparent")
        fcd_num_frame.pack(pady=10, padx=10, fill="x")

        # Label and Entry for Read
        fcd_out_label = Ctk.CTkLabel(fcd_num_frame, text="Feature num# to remove: ")
        fcd_out_label.pack(side="left", padx=(0, 5))
        self.fcd_out_entry = Ctk.CTkEntry(fcd_num_frame, width=200)
        self.fcd_out_entry.pack(side="left", fill="x", expand=True)

        # Label and Entry for fcd in
        fcd_in_label = Ctk.CTkLabel(fcd_num_frame, text="Feature num# to place: ")
        fcd_in_label.pack(side="left", padx=(10, 5))
        self.fcd_in_entry = Ctk.CTkEntry(fcd_num_frame, width=200)
        self.fcd_in_entry.pack(side="left", fill="x", expand=True)

        # Switch for All/Single mode
        self.left_swtich_label = Ctk.CTkLabel(self.xml_frame, text="Single")
        self.left_swtich_label.pack(side="left", padx=(0, 10))
        self.mode_switch = Ctk.CTkSwitch(
            self.xml_frame, text=" All", command=self.toggle_mode
        )
        self.mode_switch.pack(side="left", padx=(5, 10))

        # Label and Entry for XML file path
        self.xml_label = Ctk.CTkLabel(self.xml_frame, text="Objective Folder:")
        self.xml_label.pack(side="left", padx=(0, 5))

        self.xml_path_entry = Ctk.CTkEntry(self.xml_frame, width=400, state="readonly")
        self.xml_path_entry.pack(side="left", fill="x", expand=True)

        # Button to browse for XML file
        self.browse_button = Ctk.CTkButton(
            self.xml_frame,
            text="Select Folder",
            command=self.browse_folder_path,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.browse_button.pack(side="left", padx=(5, 0))

        # Button to replace directory and read data
        self.replace_button = Ctk.CTkButton(
            self,
            text="Replace",
            command=self.replace_directory,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.replace_button.pack(pady=10)

        # Log text box with scrollbar
        self.empty_label = Ctk.CTkLabel(self, text="")
        self.empty_label.pack(pady=45, padx=20)
        self.text_log_frame = Ctk.CTkFrame(self)
        self.text_log_frame.pack(fill="x")
        self.replace_label = Ctk.CTkLabel(self.text_log_frame, text="Replacement Log:")
        self.replace_label.pack()

        # Log text box with scrollbar
        self.log_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.log_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Text box with scrollbar for summary
        self.summary_text = tk.Text(self.log_frame, height=10, width=80, state="normal")
        self.summary_text.pack(side="left", fill="both", expand=True)

        # Create a scrollbar for the text box
        self.scrollbar = tk.Scrollbar(self.log_frame, command=self.summary_text.yview)
        self.scrollbar.pack(side="right", fill="y")

        # Configure the text box to use the scrollbar
        self.summary_text.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.summary_text.yview)

        self.summary_text.tag_configure("success", foreground="green")
        self.summary_text.tag_configure("error", foreground="red")

    def toggle_mode(self):
        if self.mode_switch.get() == 1:  # All mode
            self.xml_label.configure(text="Class Table XML:")
            self.browse_button.configure(text="Browse")
            self.browse_button.configure(command=self.browse_xml_file)
        else:  # Single mode
            self.xml_label.configure(text="Objective Folder:")
            self.browse_button.configure(text="Select Folder")
            self.browse_button.configure(command=self.browse_folder_path)
        self.xml_path_entry.configure(state="normal")
        self.xml_path_entry.delete(0, tk.END)
        self.xml_path_entry.configure(state="readonly")

    def browse_xml_file(self):
        """Open a file dialog to select an XML file."""
        file_path = filedialog.askopenfilename(
            title="Select XML File", filetypes=[("XML Files", "*.xml")]
        )
        if file_path:
            self.xml_path_entry.configure(state="normal")  # Enable entry to set text
            self.xml_path_entry.delete(0, tk.END)  # Clear previous text
            self.xml_path_entry.insert(0, file_path)  # Insert selected file path
            self.xml_path_entry.configure(state="readonly")  # Set back to read-only

    def browse_folder_path(self):
        """Open a file dialog to select a folder."""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.xml_path_entry.configure(state="normal")  # Enable entry to set text
            self.xml_path_entry.delete(0, tk.END)  # Clear previous text
            self.xml_path_entry.insert(0, folder_path)  # Insert selected file path
            self.xml_path_entry.configure(state="readonly")  # Set back to read-only

    def replace_directory(self):
        path = self.xml_path_entry.get()
        if not path:
            messagebox.showerror("Error", "Please select a file or folder first.")
            return

        # Clear the log before applying changes
        self.summary_text.delete(1.0, tk.END)

        if self.mode_switch.get() == 1:  # All mode
            self.replace_all(path)
        else:  # Single mode
            self.replace_single(path)

    def replace_all(self, class_table_path):
        base_directory = os.path.dirname(class_table_path)
        target_directory = os.path.join(base_directory, "ObjectiveRelatedData")

        if not os.path.exists(target_directory):
            messagebox.showerror(
                "Error", f"The directory '{target_directory}' does not exist."
            )
            return

        replacements_count = {}
        for folder in os.listdir(target_directory):
            if folder.startswith("OCD_"):
                folder_path = os.path.join(target_directory, folder)
                fed_file_name = f"FED_{folder[4:]}.xml"
                fed_file_path = os.path.join(folder_path, fed_file_name)
                if os.path.exists(fed_file_path):
                    count = self.replace_feature_ct_idx(fed_file_path)
                    replacements_count[folder] = count

        self.display_summary(replacements_count)

    def replace_single(self, ocd_folder_path):
        fed_file_name = f"FED_{os.path.basename(ocd_folder_path)[4:]}.xml"
        fed_file_path = os.path.join(ocd_folder_path, fed_file_name)
        if os.path.exists(fed_file_path):
            count = self.replace_feature_ct_idx(fed_file_path)
            self.display_summary({os.path.basename(ocd_folder_path): count})
        else:
            messagebox.showerror("Error", "FED file not found in the selected folder.")

    def replace_feature_ct_idx(self, fed_file_path):
        try:
            tree = ET.parse(fed_file_path)
            root = tree.getroot()

            fcd_out = self.fcd_out_entry.get().strip()
            fcd_in = self.fcd_in_entry.get().strip()

            if not fcd_out or not fcd_in:
                messagebox.showerror("Error", "Please enter both Feature numbers.")
                return 0

            replacements_count = 0
            for fed in root.findall("FED"):
                feature_ct_idx = fed.find("FeatureCtIdx")
                if feature_ct_idx is not None and feature_ct_idx.text == fcd_out:
                    feature_ct_idx.text = fcd_in
                    replacements_count += 1

            # Convert the ElementTree to a string
            xml_str = ET.tostring(root, encoding="utf-8", method="xml")

            # Parse the string with minidom
            dom = minidom.parseString(xml_str)

            # Write the XML to file with the declaration and proper formatting
            with open(fed_file_path, "w", encoding="utf-8") as f:
                f.write(dom.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8"))

            return replacements_count
        except ET.ParseError as e:
            messagebox.showerror(
                "Error", f"Failed to parse XML file '{fed_file_path}': {e}"
            )
            return 0

    def remove_whitespace_nodes(self, node):
        """Remove unnecessary whitespace nodes from the DOM."""
        for child in list(node.childNodes):
            if child.nodeType == minidom.Node.TEXT_NODE and not child.data.strip():
                node.removeChild(child)
            elif child.hasChildNodes():
                self.remove_whitespace_nodes(child)
        return node

    def display_summary(self, replacements_count):
        if replacements_count:
            summary = "\n".join(
                [
                    f"{folder}: {count} replacements"
                    for folder, count in replacements_count.items()
                ]
            )
        else:
            summary = "No replacements were made."

        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, summary, "success")


class OffsetFixerPage(Ctk.CTkFrame):
    def __init__(self, parent, controller):
        Ctk.CTkFrame.__init__(self, parent)
        self.controller = controller

        # Start label and entry
        self.start_frame = Ctk.CTkFrame(self)
        self.start_frame.pack(pady=30, fill="x")

        start_label = Ctk.CTkLabel(
            self.start_frame,
            text="Please choose a CT/Folder, specify the Feature’s CT number, and provide the desired offset for correction",
        )
        start_label.pack()

        # Frame for file selection
        self.xml_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.xml_frame.pack(pady=10, padx=10, fill="x")

        # Switch for All/Single mode
        self.left_switch_label = Ctk.CTkLabel(self.xml_frame, text="Single ")
        self.left_switch_label.pack(side="left", padx=(0, 10))
        self.mode_switch = Ctk.CTkSwitch(
            self.xml_frame, text=" All", command=self.toggle_mode
        )
        self.mode_switch.pack(side="left", padx=(5, 10))

        self.xml_label = Ctk.CTkLabel(self.xml_frame, text="Objective Folder:")
        self.xml_label.pack(side="left", padx=(0, 5))

        self.xml_path_entry = Ctk.CTkEntry(self.xml_frame, width=400, state="readonly")
        self.xml_path_entry.pack(side="left", fill="x", expand=True)

        self.browse_button = Ctk.CTkButton(
            self.xml_frame,
            text="Select Folder",
            command=self.browse_folder_path,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.browse_button.pack(side="left", padx=(5, 0))

        # Frame for feature number entry
        feature_frame = Ctk.CTkFrame(self, fg_color="transparent")
        feature_frame.pack(pady=10, padx=10, fill="x")

        feature_label = Ctk.CTkLabel(feature_frame, text="Feature Number:")
        feature_label.pack(side="left", padx=(0, 5))

        self.feature_entry = Ctk.CTkEntry(feature_frame, width=200)
        self.feature_entry.pack(side="left", fill="x", expand=True)

        # Radio buttons for offset type
        self.offset_type = tk.StringVar(value="xy")

        radio_frame = Ctk.CTkFrame(self, fg_color="transparent")
        radio_frame.pack(pady=10, padx=10, fill="x")

        xy_radio = Ctk.CTkRadioButton(
            radio_frame,
            text="Fix XY Offsets",
            variable=self.offset_type,
            value="xy",
            command=self.show_offset_entries,
            fg_color="#7A92A9",
            text_color="#000000",
        )
        xy_radio.pack(side="left", padx=(0, 10))

        z_radio = Ctk.CTkRadioButton(
            radio_frame,
            text="Fix Z Offset",
            variable=self.offset_type,
            value="z",
            command=self.show_offset_entries,
            fg_color="#7A92A9",
            text_color="#000000",
        )
        z_radio.pack(side="left", padx=(0, 10))

        rotation_radio = Ctk.CTkRadioButton(
            radio_frame,
            text="Fix Rotation",
            variable=self.offset_type,
            value="rotation",
            command=self.show_offset_entries,
            fg_color="#7A92A9",
            text_color="#000000",
        )
        rotation_radio.pack(side="left")
        rotation_radio = Ctk.CTkRadioButton(
            radio_frame,
            text="Fix Value",
            variable=self.offset_type,
            value="value",
            command=self.show_offset_entries,
            fg_color="#7A92A9",
            text_color="#000000",
        )
        rotation_radio.pack(side="left")

        # Frame for offset entries
        self.offset_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.offset_frame.pack(pady=10, padx=10, fill="x")

        # XY offset entries
        self.x_label = Ctk.CTkLabel(self.offset_frame, text="X Offset (Real Y):")
        self.x_entry = Ctk.CTkEntry(self.offset_frame, width=100)
        self.y_label = Ctk.CTkLabel(self.offset_frame, text="Y Offset (Real X):")
        self.y_entry = Ctk.CTkEntry(self.offset_frame, width=100)

        # Z offset entry
        self.z_label = Ctk.CTkLabel(self.offset_frame, text="Z Offset:")
        self.z_entry = Ctk.CTkEntry(self.offset_frame, width=100)

        # Rotation entry
        self.rotation_label = Ctk.CTkLabel(self.offset_frame, text="Rotation:")
        self.rotation_entry = Ctk.CTkEntry(self.offset_frame, width=100)

        # Value entry
        self.value_label = Ctk.CTkLabel(self.offset_frame, text="Value:")
        self.value_entry = Ctk.CTkEntry(self.offset_frame, width=100)

        # Initially show XY offset entries
        self.show_offset_entries()

        # Button frame for Apply and Check Data buttons
        button_frame = Ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=10)

        self.apply_button = Ctk.CTkButton(
            button_frame,
            text="Apply Changes",
            command=self.apply_changes,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.apply_button.pack(side="left", padx=(0, 5))

        self.check_button = Ctk.CTkButton(
            button_frame,
            text="Check Data",
            command=self.check_data,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.check_button.pack(side="left", padx=(5, 0))
        self.check_button.pack(pady=10,padx=10)

        # Log text box with scrollbar
        self.space_label = Ctk.CTkLabel(self, text="")
        self.space_label.pack()
        self.text_log_frame = Ctk.CTkFrame(self)
        self.text_log_frame.pack(fill="x")
        self.choice_label = Ctk.CTkLabel(self.text_log_frame, text="Offset Fixing Log:")
        self.choice_label.pack()

        self.log_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.log_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.log_text = tk.Text(self.log_frame, height=10, width=80, state="normal")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log_scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=self.log_scrollbar.set)

        # Define tags for coloring text
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("error", foreground="red")

    def toggle_mode(self):
        if self.mode_switch.get() == 1:  # All mode
            self.xml_label.configure(text="Class Table XML:")
            self.browse_button.configure(text="Browse")
            self.browse_button.configure(command=self.browse_xml_file)
        else:  # Single mode
            self.xml_label.configure(text="Objective Folder:")
            self.browse_button.configure(text="Select Folder")
            self.browse_button.configure(command=self.browse_folder_path)

        self.xml_path_entry.configure(state="normal")
        self.xml_path_entry.delete(0, tk.END)
        self.xml_path_entry.configure(state="readonly")

    def browse_xml_file(self):
        """Open a file dialog to select an XML file."""
        file_path = filedialog.askopenfilename(
            title="Select XML File", filetypes=[("XML Files", "*.xml")]
        )
        if file_path:
            self.xml_path_entry.configure(state="normal")
            self.xml_path_entry.delete(0, tk.END)
            self.xml_path_entry.insert(0, file_path)
            self.xml_path_entry.configure(state="readonly")

    def browse_folder_path(self):
        """Open a file dialog to select a folder."""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.xml_path_entry.configure(state="normal")
            self.xml_path_entry.delete(0, tk.END)
            self.xml_path_entry.insert(0, folder_path)
            self.xml_path_entry.configure(state="readonly")

    def show_offset_entries(self):
        for widget in self.offset_frame.winfo_children():
            widget.pack_forget()

        if self.offset_type.get() == "xy":
            self.x_label.pack(side="left", padx=(0, 5))
            self.x_entry.pack(side="left", padx=(0, 10))
            self.y_label.pack(side="left", padx=(0, 5))
            self.y_entry.pack(side="left")
        elif self.offset_type.get() == "z":
            self.z_label.pack(side="left", padx=(0, 5))
            self.z_entry.pack(side="left")
        elif self.offset_type.get() == "rotation":
            self.rotation_label.pack(side="left", padx=(0, 5))
            self.rotation_entry.pack(side="left")
        else:
            self.value_label.pack(side="left", padx=(0, 5))
            self.value_entry.pack(side="left")

    def apply_changes(self):
        """
        Main function to start the offset fixing process based on the selected mode.
        """
        path = self.xml_path_entry.get()
        feature_number = self.feature_entry.get().strip()
        offset_type = self.offset_type.get()

        self.log_text.delete(1.0, tk.END)  # Clear previous log

        if not path:
            messagebox.showerror("Error", "Please select a file or folder.")
            return

        if not feature_number:
            messagebox.showerror("Error", "Please enter a feature number.")
            return

        if self.mode_switch.get() == 1:  # All mode
            self.apply_changes_all(path, feature_number, offset_type)
        else:  # Single mode
            self.apply_changes_single(path, feature_number, offset_type)

    def apply_changes_all(self, class_table_path, feature_number, offset_type):
        """
        Process all OCD folders found in the ObjectiveRelatedData directory.
        """
        base_directory = os.path.dirname(class_table_path)
        target_directory = os.path.join(base_directory, "ObjectiveRelatedData")

        if not os.path.exists(target_directory):
            self.log_text.insert(tk.END, f"Error: The directory '{target_directory}' does not exist.\n", "error")
            return

        changes_made = 0
        log_summary = []
        for folder in os.listdir(target_directory):
            if folder.startswith("OCD_"):
                folder_path = os.path.join(target_directory, folder)
                fed_file_name = f"FED_{folder[4:]}.xml"
                fed_file_path = os.path.join(folder_path, fed_file_name)
                ocd_file_name = f"OCD_{folder[4:]}.xml"
                ocd_file_path = os.path.join(folder_path, ocd_file_name)

                if os.path.exists(fed_file_path) and os.path.exists(ocd_file_path):
                    count = self.update_xml_file(fed_file_path, feature_number, offset_type)
                    ocd_name = self.get_ocd_name(ocd_file_path)
                    if count > 0:
                        log_summary.append(f"{folder} ({ocd_name}): {count} features updated.")
                        changes_made += count

        for log in log_summary:
            self.log_text.insert(tk.END, log + "\n", "success")

        if changes_made > 0:
            self.log_text.insert(tk.END, f"Total changes applied to {changes_made} features.\n", "success")
        else:
            self.log_text.insert(tk.END, "No changes were made.\n", "error")

        self.log_text.see(tk.END)  # Scroll to the end

    def apply_changes_single(self, folder_path, feature_number, offset_type):
        """
        Process a single OCD folder.
        """
        fed_file_name = f"FED_{os.path.basename(folder_path)[4:]}.xml"
        fed_file_path = os.path.join(folder_path, fed_file_name)
        ocd_file_name = f"OCD_{os.path.basename(folder_path)[4:]}.xml"
        ocd_file_path = os.path.join(folder_path, ocd_file_name)

        if os.path.exists(fed_file_path) and os.path.exists(ocd_file_path):
            count = self.update_xml_file(fed_file_path, feature_number, offset_type)
            ocd_name = self.get_ocd_name(ocd_file_path)
            if count > 0:
                self.log_text.insert(tk.END,
                                     f"Changes applied to {count} features in {os.path.basename(folder_path)} ({ocd_name}).\n",
                                     "success")
            else:
                self.log_text.insert(tk.END, "No changes were made.\n", "error")
        else:
            messagebox.showerror("Error", f"FED or OCD file not found in the selected folder.")

    def update_xml_file(self, file_path, feature_number, offset_type):
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            changes_count = 0
            for fed in root.findall("FED"):
                if fed.find("FeatureCtIdx").text == feature_number:
                    if offset_type == "xy":
                        self.fix_xy_offsets(fed)
                    elif offset_type == "z":
                        self.fix_z_offset(fed)
                    else:  # rotation
                        self.fix_rotation(fed)
                    changes_count += 1

            if changes_count > 0:
                tree.write(file_path, encoding="utf-8", xml_declaration=True)
            return changes_count
        except Exception as e:
            messagebox.showerror(
                "Error", f"An error occurred while updating {file_path}: {str(e)}"
            )
            return 0

    def fix_xy_offsets(self, fed):
        # Fix string "" not been changed to 0 in the GUI
        if self.x_entry.get().strip() == "":
            x_offset = 0
        else:
            x_offset = float(self.x_entry.get().strip())
        if self.y_entry.get().strip() == "":
            y_offset = 0
        else:
            y_offset = float(self.y_entry.get().strip())

        heading = float(fed.find("Heading").text)

        # Convert heading to radians
        heading_rad = math.radians(heading)

        # Calculate new offsets based on heading
        new_x_offset = (
            float(fed.find("OffsetX").text)
            + x_offset * math.sin(heading_rad)
            + y_offset * math.cos(heading_rad)
        )
        new_y_offset = (
            float(fed.find("OffsetY").text)
            + x_offset * math.cos(heading_rad)
            - y_offset * math.sin(heading_rad)
        )

        # Update the XML with the new offsets, rounded to 3 decimal places
        fed.find("OffsetX").text = f"{new_x_offset:.3f}"
        fed.find("OffsetY").text = f"{new_y_offset:.3f}"

    def fix_z_offset(self, fed):
        z_offset = float(self.z_entry.get().strip())
        new_z = float(fed.find("OffsetZ").text) + z_offset
        fed.find("OffsetZ").text = f"{new_z:.3f}"

    def fix_rotation(self, fed):
        rotation = float(self.rotation_entry.get().strip())
        new_heading = (float(fed.find("Heading").text) + rotation) % 360
        fed.find("Heading").text = f"{new_heading:.1f}"

    def fix_value(self, fed):
        value = float(self.value_entry.get().strip())
        new_value = float(fed.find("Heading").text) + value
        fed.find("Value").text = f"{new_value:.0f}"
    def check_data(self):
        """
        Check all OCD folders and print the amount of features found, including the OCD number and name.
        """
        path = self.xml_path_entry.get()
        feature_number = self.feature_entry.get().strip()
        self.log_text.delete(1.0, tk.END)  # Clear previous log

        if not path:
            messagebox.showerror("Error", "Please select a file or folder.")
            return

        if not feature_number:
            messagebox.showerror("Error", "Please enter a feature number.")
            return

        if self.mode_switch.get() == 1:  # All mode
            found_any = self.check_data_all(path, feature_number)
            if not found_any:
                self.log_text.insert(tk.END, f"The feature {feature_number} was not found in any objectives.\n", "error")
        else:  # Single mode
            found_any = self.check_data_single(path, feature_number)
            if not found_any:
                self.log_text.insert(tk.END, f"No instances of feature {feature_number} found in the selected folder.\n", "error")

    def check_data_all(self, class_table_path, feature_number):
        """
        Check all OCD folders in the ObjectiveRelatedData directory for the specified feature number.
        """
        base_directory = os.path.dirname(class_table_path)
        target_directory = os.path.join(base_directory, "ObjectiveRelatedData")

        if not os.path.exists(target_directory):
            self.log_text.insert(tk.END, f"Error: The directory '{target_directory}' does not exist.\n", "error")
            return False

        found_any = False
        for folder in os.listdir(target_directory):
            if folder.startswith("OCD_"):
                folder_path = os.path.join(target_directory, folder)
                found_in_folder = self.process_folder(folder, folder_path, feature_number)
                if found_in_folder:
                    found_any = True

        self.log_text.see(tk.END)  # Scroll to the end
        return found_any

    def check_data_single(self, folder_path, feature_number):
        """
        Check a single OCD folder for the specified feature number.
        """
        folder = os.path.basename(folder_path)
        found_in_folder = self.process_folder(folder, folder_path, feature_number)
        self.log_text.see(tk.END)  # Scroll to the end
        return found_in_folder

    def process_folder(self, folder, folder_path, feature_number):
        """
        Process a single folder to count features and get OCD name.
        """
        fed_file_name = f"FED_{folder[4:]}.xml"
        fed_file_path = os.path.join(folder_path, fed_file_name)
        ocd_file_name = f"OCD_{folder[4:]}.xml"
        ocd_file_path = os.path.join(folder_path, ocd_file_name)

        if os.path.exists(fed_file_path) and os.path.exists(ocd_file_path):
            feature_count = self.count_features(fed_file_path, feature_number)
            ocd_name = self.get_ocd_name(ocd_file_path)
            if feature_count > 0:
                self.log_text.insert(tk.END, f"{folder}: {feature_count} instances of feature {feature_number} found. Name: {ocd_name}\n", "success")
                return True
            else:
                return False
        else:
            self.log_text.insert(tk.END, f"Missing FED or OCD file in {folder}\n", "error")
            return False

    def count_features(self, file_path, feature_number):
        """
        Count the number of specific features in the given FED file.
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            return sum(1 for fed in root.findall('FED') if fed.find('FeatureCtIdx').text == feature_number)
        except Exception as e:
            self.log_text.insert(tk.END, f"An error occurred while counting features in {file_path}: {str(e)}\n", "error")
            return 0

    def get_ocd_name(self, file_path):
        """
        Get the name of the OCD from the given OCD file.
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            ocd = root.find('OCD')
            if ocd is not None:
                return ocd.find('Name').text
            return "Unknown"
        except Exception as e:
            self.log_text.insert(tk.END, f"An error occurred while reading OCD name from {file_path}: {str(e)}\n", "error")
            return "Unknown"

class RunwayDimFixerPage(Ctk.CTkFrame):
    def __init__(self, parent, controller):
        Ctk.CTkFrame.__init__(self, parent)
        self.controller = controller

        # Start label and entry
        self.start_frame = Ctk.CTkFrame(self)
        self.start_frame.pack(pady=30, fill="x")

        start_label = Ctk.CTkLabel(
            self.start_frame,
            text="Please choose a CT/Folder, specify your prefered prefix runway for assigning it's data into the RunwayDimType",
        )
        start_label.pack()

        # Frame for file selection
        self.xml_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.xml_frame.pack(pady=10, padx=10, fill="x")

        # Switch for All/Single mode
        self.left_switch_label = Ctk.CTkLabel(self.xml_frame, text="Single ")
        self.left_switch_label.pack(side="left", padx=(0, 10))
        self.mode_switch = Ctk.CTkSwitch(
            self.xml_frame, text=" All", command=self.toggle_mode
        )
        self.mode_switch.pack(side="left", padx=(5, 10))

        self.xml_label = Ctk.CTkLabel(self.xml_frame, text="Objective Folder:")
        self.xml_label.pack(side="left", padx=(0, 5))

        self.xml_path_entry = Ctk.CTkEntry(self.xml_frame, width=400, state="readonly")
        self.xml_path_entry.pack(side="left", fill="x", expand=True)

        self.browse_button = Ctk.CTkButton(
            self.xml_frame,
            text="Select Folder",
            command=self.browse_folder_path,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.browse_button.pack(side="left", padx=(5, 0))

        # Switch for First/Second choice
        self.choice_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.choice_frame.pack(pady=10, padx=10, fill="x")

        self.choice_label = Ctk.CTkLabel(self.choice_frame, text="First Choice ")
        self.choice_label.pack(side="left", padx=(0, 5))

        self.choice_switch = Ctk.CTkSwitch(self.choice_frame, text=" Second Choice")
        self.choice_switch.pack(side="left", padx=(5, 10))

        # Assign Heading button
        self.assign_button = Ctk.CTkButton(
            self,
            text="Assign Heading",
            command=self.assign_heading,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.assign_button.pack(pady=10)

        # Switch for First/Second choice
        self.space_label = Ctk.CTkLabel(self, text=" ")
        self.space_label.pack()
        self.space2_label = Ctk.CTkLabel(self, text=" ")
        self.space2_label.pack()

        self.text_log_frame = Ctk.CTkFrame(self)
        self.text_log_frame.pack(fill="x")
        self.choice_label = Ctk.CTkLabel(self.text_log_frame, text="RunwayDimType Log:")
        self.choice_label.pack()

        # Log text box with scrollbar
        self.log_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.log_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.log_text = tk.Text(self.log_frame, height=10, width=80, state="normal")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log_scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=self.log_scrollbar.set)

        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("error", foreground="red")

    def toggle_mode(self):
        """
        Toggle between 'All' and 'Single' modes, updating UI elements accordingly.
        """
        if self.mode_switch.get() == 1:  # All mode
            self.xml_label.configure(text="Class Table XML:")
            self.browse_button.configure(text="Browse")
            self.browse_button.configure(command=self.browse_xml_file)
        else:  # Single mode
            self.xml_label.configure(text="Objective Folder:")
            self.browse_button.configure(text="Select Folder")
            self.browse_button.configure(command=self.browse_folder_path)

        self.xml_path_entry.configure(state="normal")
        self.xml_path_entry.delete(0, tk.END)
        self.xml_path_entry.configure(state="readonly")

    def browse_xml_file(self):
        """
        Open a file dialog to select an XML file and update the path entry.
        """
        file_path = filedialog.askopenfilename(
            title="Select XML File", filetypes=[("XML Files", "*.xml")]
        )
        if file_path:
            self.xml_path_entry.configure(state="normal")
            self.xml_path_entry.delete(0, tk.END)
            self.xml_path_entry.insert(0, file_path)
            self.xml_path_entry.configure(state="readonly")

    def browse_folder_path(self):
        """
        Open a file dialog to select a folder and update the path entry.
        """
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.xml_path_entry.configure(state="normal")
            self.xml_path_entry.delete(0, tk.END)
            self.xml_path_entry.insert(0, folder_path)
            self.xml_path_entry.configure(state="readonly")

    def assign_heading(self):
        """
        Main function to start the heading assignment process based on the selected mode.
        """
        path = self.xml_path_entry.get()
        if not path:
            messagebox.showerror("Error", "Please select a file or folder.")
            return

        self.log_text.delete(1.0, tk.END)  # Clear previous log

        if self.mode_switch.get() == 1:  # All mode
            self.process_all_folders(path)
        else:  # Single mode
            self.process_single_folder(path)

    def process_all_folders(self, class_table_path):
        """
        Process all OCD folders found in the ObjectiveRelatedData directory.
        """
        base_directory = os.path.dirname(class_table_path)
        target_directory = os.path.join(base_directory, "ObjectiveRelatedData")

        if not os.path.exists(target_directory):
            messagebox.showerror(
                "Error", f"The directory '{target_directory}' does not exist."
            )
            return

        for folder in os.listdir(target_directory):
            if folder.startswith("OCD_"):
                folder_path = os.path.join(target_directory, folder)
                self.process_phd_file(folder_path)

    def process_single_folder(self, folder_path):
        """
        Process a single OCD folder.
        """
        self.process_phd_file(folder_path)

    def process_phd_file(self, folder_path):
        """
        Process the PHD file in the given folder, assigning headings based on the selected choice.
        """
        phd_file_name = f"PHD_{os.path.basename(folder_path)[4:]}.xml"
        phd_file_path = os.path.join(folder_path, phd_file_name)

        if not os.path.exists(phd_file_path):
            self.log_text.insert(
                tk.END,
                f"PHD file not found in {os.path.basename(folder_path)}\n",
                "error",
            )
            return

        try:
            tree = ET.parse(phd_file_path)
            root = tree.getroot()

            type_1_data = {}
            type_8_count = 0
            changes_made = 0

            for phd in root.findall("PHD"):
                phd_type = phd.find("Type").text
                runway_number = phd.find("RunwayNumber").text

                if phd_type == "1":
                    if runway_number not in type_1_data:
                        type_1_data[runway_number] = []
                    type_1_data[runway_number].append(phd.find("Data").text)
                elif phd_type == "8":
                    type_8_count += 1

            for phd in root.findall("PHD"):
                if phd.find("Type").text == "8":
                    runway_number = phd.find("RunwayNumber").text
                    if (
                        runway_number in type_1_data
                        and len(type_1_data[runway_number]) >= 2
                    ):
                        choice_index = 1 if self.choice_switch.get() == 1 else 0
                        phd.find("Data").text = type_1_data[runway_number][choice_index]
                        changes_made += 1
                    else:
                        self.log_text.insert(
                            tk.END,
                            f"RunwayListType data for Runway {runway_number} in {os.path.basename(folder_path)}\n",
                            "error",
                        )

            if changes_made > 0:
                tree.write(phd_file_path, encoding="utf-8", xml_declaration=True)
                self.log_text.insert(
                    tk.END,
                    f"{os.path.basename(folder_path)}: {changes_made} changes assigned for {type_8_count} RunwayDimTypes\n",
                    "success",
                )
            else:
                self.log_text.insert(
                    tk.END,
                    f"{os.path.basename(folder_path)}: {changes_made} changes assigned for {type_8_count} RunwayDimTypes\n",
                )

            if type_8_count * 2 != sum(len(data) for data in type_1_data.values()):
                self.log_text.insert(
                    tk.END,
                    f"Warning: Mismatch in RunwayListType and RunwayDimType counts in {os.path.basename(folder_path)}\n",
                    "error",
                )

        except ET.ParseError as e:
            self.log_text.insert(
                tk.END, f"Error parsing {phd_file_name}: {str(e)}\n", "error"
            )

        self.log_text.see(tk.END)  # Scroll to the end of the log


class FoldersCreatorPage(Ctk.CTkFrame):
    def __init__(self, parent, controller):
        """
        Initialize the FoldersCreatorPage with all necessary UI elements.
        """
        Ctk.CTkFrame.__init__(self, parent)
        self.controller = controller

        # Start label and entry
        self.start_frame = Ctk.CTkFrame(self)
        self.start_frame.pack(pady=30, fill="x")

        start_label = Ctk.CTkLabel(
            self.start_frame,
            text="Please specify the starting and ending numbers for creating folders",
        )
        start_label.pack()

        self.first_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.first_frame.pack(pady=10, padx=10)

        # Start label and entry
        start_label = Ctk.CTkLabel(self.first_frame, text="Start:  ")
        start_label.pack(side="left", padx=(0, 5))
        self.start_entry = Ctk.CTkEntry(self.first_frame)
        self.start_entry.pack(side="left", fill="x", expand=True)

        # End label and entry
        end_label = Ctk.CTkLabel(self.first_frame, text="End:  ")
        end_label.pack(side="left", padx=(5, 5))
        self.end_entry = Ctk.CTkEntry(self.first_frame)
        self.end_entry.pack(side="left", fill="x", expand=True)

        # Checkbox for adding Parent.dat file
        self.add_parent_file_var = tk.BooleanVar()
        parent_file_checkbox = Ctk.CTkCheckBox(self.first_frame, text="Add Parent.dat", variable=self.add_parent_file_var)
        parent_file_checkbox.pack(side="left", padx=(10, 5))

        self.directory_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.directory_frame.pack(pady=10, padx=10)

        # Directory selection button and entry
        select_button = Ctk.CTkButton(
            self.directory_frame,
            text="Select Directory",
            command=self.select_directory,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        select_button.pack(side="left", padx=(5, 0))

        self.directory_entry = Ctk.CTkEntry(
            self.directory_frame, width=600, state="readonly"
        )
        self.directory_entry.pack(side="left", fill="x", expand=True)

        # Create folders button
        create_button = Ctk.CTkButton(
            self,
            text="Create folders",
            command=self.create_folders,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        create_button.pack(pady=10)

    def select_directory(self):
        """
        Open a file dialog to select a directory and update the path entry.
        """
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.directory_entry.configure(state="normal")
            self.directory_entry.delete(0, tk.END)
            self.directory_entry.insert(0, folder_path)
            self.directory_entry.configure(state="readonly")

    def create_folders(self):
        """
        Create folders based on the start and end numbers provided by the user.
        """
        try:
            start = int(self.start_entry.get())
            end = int(self.end_entry.get())
            directory = self.directory_entry.get()
            if not directory:
                messagebox.showerror("Error", "Please select a directory first.")
                return

            for i in range(start, end + 1):
                folder_path = os.path.join(directory, str(i))
                if os.path.exists(folder_path):
                    messagebox.showerror("Error", f"Folder name '{i}' already exists")
                    return
                else:
                    os.mkdir(folder_path)
                    if self.add_parent_file_var.get():
                        self.create_parent_file(folder_path)

            messagebox.showinfo("Success", f"Folders created from {start} to {end} in {directory}")
        except ValueError:
            messagebox.showerror("Error", "Please enter valid start and end numbers.")


    def create_parent_file(self, folder_path):
        """
        Create a Parent.dat file in the specified folder.
        """
        parent_file_content = """Dimensions       = 0 0 0 0 0 0 0
TextureSets      = 1
Switches         = 0
Dofs             = 0
        """
        parent_file_path = os.path.join(folder_path, "Parent.dat")
        with open(parent_file_path, "w") as file:
            file.write(parent_file_content)

class TutorialPage(Ctk.CTkFrame):
    def __init__(self, parent, controller):
        Ctk.CTkFrame.__init__(self, parent)
        self.controller = controller

        # Start label and entry
        self.start_frame = Ctk.CTkFrame(self)
        self.start_frame.pack(pady=30, fill="x")

        start_label = Ctk.CTkLabel(
            self.start_frame, text="Please Choose the Tutorial you wish to view"
        )
        start_label.pack()

        # Frame for the sidebar
        sidebar_frame = Ctk.CTkFrame(self, width=200)
        sidebar_frame.pack(side="left", fill="y")

        # Main frame for the content
        content_frame = Ctk.CTkFrame(self)
        content_frame.pack(side="right", fill="both", expand=True)

        # Scrollable text widget for explanations
        self.text_widget = tk.Text(content_frame, wrap="word")
        self.text_widget.pack(side="left", fill="both", expand=True)

        # Scrollbar for the text widget
        scrollbar = tk.Scrollbar(content_frame, command=self.text_widget.yview)
        scrollbar.pack(side="right", fill="y")
        self.text_widget.config(yscrollcommand=scrollbar.set)

        # Add buttons to the sidebar for each tutorial section
        self.add_sidebar_button(
            sidebar_frame, "Replace Page", self.show_replace_page_explanation
        )
        self.add_sidebar_button(
            sidebar_frame, "Offset Fixer", self.show_offset_fixer_explanation
        )
        self.add_sidebar_button(
            sidebar_frame, "Runway Dim Fixer", self.show_runway_dim_fixer_explanation
        )
        self.add_sidebar_button(
            sidebar_frame, "Folders Creator", self.show_folders_creator_explanation
        )
        self.add_sidebar_button(
            sidebar_frame, "reformat Parents", self.show_reformat_parents_explanation
        )
        self.add_sidebar_button(sidebar_frame, "Parking Fixer", self.show_parking_fixer_explanation)

    def add_sidebar_button(self, frame, text, command):
        button = Ctk.CTkButton(
            frame,
            text=text,
            command=command,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        button.pack(fill="x", pady=5)

    def show_replace_page_explanation(self):
        explanation = textwrap.dedent("""
        ## Replace Page

        The Replace page allows users to replace specific feature numbers in XML files across multiple folders.

        ### Purpose:
        - To automate the process of updating feature numbers in FED (Feature Element Data) XML files
        - To provide a way to make bulk changes across multiple OCD (Objective-Data) folders

        ### Functionality:
        - Supports both single folder and multiple folder (All) modes
        - Allows users to specify the feature number to remove and the new feature number to place
        - Processes FED_XXXXX.xml files in selected folders
        - Provides a summary log of changes made

        ### Usage:
        1. Select mode (Single or All)
        2. Choose the folder or Class Table XML file
        3. Enter the Class Table feature number to remove and the new Class Table feature number
        4. Click "Replace" to process the files
        5. View the summary log for details on changes made

        ### Additional demands and knowledge:
        - Accurate input of Class table feature numbers to prevent errors (Can be found in BMS Editor)
        - Correct selection of folders or XML files
        - Careful review of the summary log to ensure desired changes were made
        
        """)
        self.display_explanation(explanation,None)

    def show_offset_fixer_explanation(self):
        explanation = textwrap.dedent("""
        ## Offset Fixer Page

        The Offset Fixer page allows users to adjust offsets and rotations for specific features in XML files.

        ### Purpose:
        - To provide a tool for fine-tuning or orientation based on the center position of a feature
        - To allow bulk updates of offsets across multiple files

        ### Functionality:
        - Supports both single folder and multiple folder (All) modes
        - Allows adjustment of XY offsets, Z offset, or rotation or value
        - Calculates new offsets based on the feature's heading
        - Updates FED_XXXXX.xml files with new offset values
        - Provides a log of changes made

        ### Usage:
        1. Select mode (Single or All)
        2. Choose the folder or Class Table XML file
        3. Enter the Class Table number of the feature
        4. Select the type of offset to adjust (XY, Z,Rotation or value)
        5. Enter the new offset values
        6. Click "Apply Changes" to process the files
        7. Review the log for details on changes made

        ### Additional Considerations:
        - Ensure accurate input of feature numbers and offset values. The difference between centers can be determined by placing two features in the same location (in the objective viewer), then selecting Options -> Draw Selected Items Distances. This action will display an arrow with a number, representing the distance in feet. You need to calculate the X and Y offsets to accurately reposition the model.
        - Offsets and rotations affecting feature positioning are linked to the "center mass" assigned by 3D modelers. By selecting the feature in the objective viewer or viewing it in the model viewer, you can understand where that location is positioned.
        - Carefully review the log to confirm that the desired changes have been made.
        
        ### Example of Required Adjustments Between Models with Different Centers:
        
        """)
        image_path = os.path.join("media", "tut_1.png")
        self.display_explanation(explanation, image_path)

    def show_runway_dim_fixer_explanation(self):
        explanation = textwrap.dedent("""
        ## Runway Dimension Fixer Page

        The Runway Dimension Fixer page allows users to automate runway dimensions in PHD XML files.

        ### Purpose:
        - To automate the process of updating runway heading
        - To ensure consistency between RunwayListType and RunwayDimType data in PHD files

        ### Functionality:
        - Supports both single folder and multiple folder (All) modes
        - Allows selection between first and second choice of heading data
        - Processes PHD_XXXXX.xml files in selected folders
        - Updates RunwayDimType data based on corresponding RunwayListType data
        - Provides a log of changes and any issues encountered

        ### Usage:
        1. Select mode (Single or All)
        2. Choose the folder or Class Table XML file
        3. Select first or second choice for dimension data
        4. Click "Assign Heading" to process the files
        5. Review the log for details on changes and any warnings

        ### Additional demands and knowledge:
        - Correct selection of folders or XML files
        - Each RunwayDimType suppose to have 2x RunwayListType. Therefore 2 heading options are available to place in each RunwayDimType heading.
        - Careful review of the log to ensure desired changes were made and to address any warnings
        """)
        self.display_explanation(explanation,None)

    def show_folders_creator_explanation(self):
        explanation =textwrap.dedent("""
        ## Folders Creator Page

        The Folders Creator page provides a tool for creating multiple numbered folders within a specified directory.

        ### Purpose:
        - To automate the process of creating multiple folders with numerical names
        - To save time when setting up project structures or organizing large numbers of files

        ### Functionality:
        - Allows users to specify a start and end number for folder names
        - Lets users select a target directory for folder creation
        - Creates folders with names ranging from the start to end number
        - Prevents overwriting of existing folders

        ### Usage:
        1. Enter the start number for folder names
        2. Enter the end number for folder names
        3. Click "Select Directory" to choose where the folders will be created
        4. Click "Create folders" to generate the folders
        5. Review the success message or error notifications

        ### Demands:
        - Valid numerical input for start and end numbers
        - Selection of an appropriate target directory
        - Awareness of existing folder names to avoid conflicts
        """)
        self.display_explanation(explanation,None)

    def show_reformat_parents_explanation(self):
        explanation = textwrap.dedent("""
        ## reformat Parents Page

        The reformat Parents page allows users to reformat and reformat parent.dat files in the database.

        ### Purpose:
        - To ensure consistency in parent.dat file formatting
        - To automate the process of reformating parent files before integrating them into the database
        - Fix Bugs related to un-assigned BMLs or bad assignments

        ### Functionality:
        - Supports both single file and father folder (All) modes
        - Reformats parent.dat files to a standardized format
        - Renames all processed files to "Parent.dat"
        - Provides an option to convert ".lod" to ".bml" naming 
        - Checks for mismatches between BML files mentioned in parent.dat and those present in the folder
        - Displays a log of changes and any issues encountered

        ### Usage:
        1. Select mode (Single or All)
        2. Choose the parent.dat file or father folder containing folders which having parent.dat file in it
        3. (Optional) Check the "LOD to BML" box to convert ".lod" references to ".bml"
        4. Click "reformat Parents" to process the files
        5. Click "Check BML Files" to verify BML file consistency
        6. Review the log for details on changes and any warnings

        ### Limitations and Demands:
        - Requires accurate selection of parent.dat files or folders
        - The "LOD to BML" conversion only changes file extensions in the parent.dat file, not the actual files
        - Users should backup their data before performing bulk operations
        - Careful review of the log is necessary to ensure desired changes were made
        - The feature assumes a specific format for parent.dat files

        ### Parent.dat File Format:
        The feature expects and produces parent.dat files in the following format:

        ```
        Dimensions       = [7 float values]
        TextureSets      = [integer]
        Switches         = [integer]
        Dofs             = [integer]
        AddLOD           = [filename] [float]
        ```

        ### Additional Notes:
        - The feature preserves the precision of Dimensions values while removing unnecessary trailing zeros
        - AddSlot lines are reformatted to remove '+' signs and standardize decimal places
        - Users should ensure that all necessary BML files are present in the folder to avoid warnings
        """)
        self.display_explanation(explanation, None)

    def show_parking_fixer_explanation(self):
        explanation = textwrap.dedent("""
        ## Parking Fixer Page

        The Parking Fixer page allows users to adjust parking points to align with hangars in Falcon BMS objectives.

        ### Purpose:
        - To automate the process of relocating parking points closer to the Center of the hangars and HAS.

        ### Functionality:
        - Supports both single folder and multiple folder (All) modes.
        - Allows selection of a CT XML file and an Objective folder.
        - Adjusts parking points within a specified radius to hangar locations.
        - Provides a log of changes made.

        ### Usage:
        1. Select mode (Single or All).
        2. Choose the CT XML file and the Objective folder.
        3. Enter the radius and CT numbers (not FCD) of hangars/Shelters.
        4. Click "Fix Parking" to process the files.
        5. Review the log for details on changes made.

        ### Additional Considerations:
        - Ensure accurate input of hangar CT numbers and radius.
        - Carefully review the log to confirm desired changes.
        - it is recommended to start reviewing radiuses from lower number, and then step up and check the results for each iteration.
        - note that restart for editor is needed in order to see the changes.
        - None selection of Hangars will cause the algorithm to search Parking points closer to any hangar in the database.
        - Multiple selection of hangars and shelters is available by seperating the numbers
        """)

        self.display_explanation(explanation, None)

    def display_explanation(self, explanation, image_path):
        self.text_widget.config(state='normal')
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(tk.END, explanation)

        # Load and display the image
        try:
            pil_image = Image.open(image_path)
            self.tk_image = ImageTk.PhotoImage(pil_image)
            self.text_widget.image_create(tk.END, image=self.tk_image)
        except Exception as e:
            print(0)
        self.text_widget.config(state='disabled')

class ReformatParentsPage(Ctk.CTkFrame):
    def __init__(self, parent, controller):
        Ctk.CTkFrame.__init__(self, parent)
        self.controller = controller
        self.all_folders_ok = True  # New attribute to track overall status
        self.max_float_precision = min(sys.float_info.dig, 10)

        # Start label
        self.start_frame = Ctk.CTkFrame(self)
        self.start_frame.pack(pady=30, fill="x")
        start_label = Ctk.CTkLabel(
            self.start_frame,
            text="Select a parent.dat file or a folder containing parent.dat files to reformat",
        )
        start_label.pack()

        # Frame for file/folder selection
        self.selection_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.selection_frame.pack(pady=10, padx=10, fill="x")

        # Switch for Single/All mode
        self.left_switch_label = Ctk.CTkLabel(self.selection_frame, text="Single")
        self.left_switch_label.pack(side="left", padx=(0, 10))
        self.mode_switch = Ctk.CTkSwitch(
            self.selection_frame,
            text="All",
            command=self.toggle_mode
        )
        self.mode_switch.pack(side="left", padx=(5, 10))

        # Label and Entry for file/folder path
        self.path_label = Ctk.CTkLabel(self.selection_frame, text="Parent File:")
        self.path_label.pack(side="left", padx=(0, 5))
        self.path_entry = Ctk.CTkEntry(self.selection_frame, width=400, state="readonly")
        self.path_entry.pack(side="left", fill="x", expand=True)

        # Button to browse for file/folder
        self.browse_button = Ctk.CTkButton(
            self.selection_frame,
            text="Browse",
            command=self.browse_path,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.browse_button.pack(side="left", padx=(5, 0))

        # Frame for buttons
        self.button_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(pady=15)

        # reformat button
        self.reformat_button = Ctk.CTkButton(
            self.button_frame,
            text="reformat Parents",
            command=self.reformat_parents,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.reformat_button.pack(side="left", padx=(0, 5))

        # Check BML Files button
        self.check_bml_button = Ctk.CTkButton(
            self.button_frame,
            text="Check BML Files",
            command=self.check_bml_files,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.check_bml_button.pack(side="left", padx=(5, 0))

        # Add checkbox for LOD to BML conversion
        self.lod_to_bml_var = Ctk.BooleanVar()
        self.lod_to_bml_checkbox = Ctk.CTkCheckBox(
            self.button_frame,
            text="LOD to BML",
            variable=self.lod_to_bml_var,
            onvalue=True,
            offvalue=False
        )
        self.lod_to_bml_checkbox.pack(side="left", padx=(10, 0))

        # Log text box with scrollbar
        self.text_log_frame = Ctk.CTkFrame(self)
        self.text_log_frame.pack(fill="x")
        self.choice_label = Ctk.CTkLabel(self.text_log_frame, text="Reformat Log:")
        self.choice_label.pack()


        self.log_frame = Ctk.CTkFrame(self, fg_color="transparent")
        self.log_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.log_text = tk.Text(self.log_frame, height=10, width=80, state="normal")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log_scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=self.log_scrollbar.set)

        # Define tags for coloring text
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("error", foreground="red")

    def toggle_mode(self):
        if self.mode_switch.get() == 1:  # All mode
            self.path_label.configure(text="Parent Folder:")
            self.browse_button.configure(text="Select Folder")
        else:  # Single mode
            self.path_label.configure(text="Parent File:")
            self.browse_button.configure(text="Browse")

        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, tk.END)
        self.path_entry.configure(state="readonly")

    def browse_path(self):
        if self.mode_switch.get() == 1:  # All mode
            path = filedialog.askdirectory(title="Select Folder")
        else:  # Single mode
            path = filedialog.askopenfilename(
                title="Select Parent File",
                filetypes=[("DAT Files", "*.dat")]
            )

        if path:
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)
            self.path_entry.configure(state="readonly")

    def reformat_parents(self):
        path = self.path_entry.get()
        if not path:
            messagebox.showerror("Error", "Please select a file or folder first.")
            return

        self.log_text.delete(1.0, tk.END)

        if self.mode_switch.get() == 1:  # All mode
            self.reformat_all(path)
        else:  # Single mode
            self.reformat_single(path)

    def reformat_single(self, file_path):
        try:
            folder_path = os.path.dirname(file_path)
            new_file_path = os.path.join(folder_path, "Parent.dat")

            with open(file_path, 'r') as file:
                content = file.read()

            formatted_content = self.format_parent_content(content)

            with open(new_file_path, 'w') as file:
                file.write(formatted_content)

            if file_path.lower() != new_file_path.lower():
                os.rename(file_path, new_file_path)

            self.log_text.insert(tk.END, f"Rebuilt and formatted: {new_file_path}\n", "success")
        except Exception as e:
            self.log_text.insert(tk.END, f"Error processing {file_path}: {str(e)}\n", "error")

    def reformat_all(self, folder_path):
        for root, dirs, files in os.walk(folder_path):
            parent_file = next((f for f in files if f.lower() == 'parent.dat'), None)
            if parent_file:
                file_path = os.path.join(root, parent_file)
                new_file_path = os.path.join(root, "Parent.dat")
                self.reformat_single(file_path)
                if file_path != new_file_path:
                    os.rename(file_path, new_file_path)

    def format_parent_content(self, content):
        lines = content.strip().split('\n')
        formatted_lines = []

        for line in lines:
            parts = line.split('=', 1)
            if len(parts) == 2:
                key, value = parts
                key = key.strip()
                value = value.strip()

                if key == 'Dimensions':
                    dimensions = [float(d) for d in value.split()]
                    formatted_value = ' '.join(f"{d:.{self.max_float_precision}g}" for d in dimensions)
                    formatted_lines.append(f"{key:<16} = {formatted_value}")
                elif key in ['TextureSets', 'Switches', 'Dofs']:
                    formatted_lines.append(f"{key:<16} = {value}")
                elif key == 'AddLOD':
                    model, distance = value.rsplit(None, 1)
                    if self.lod_to_bml_var.get() and model.lower().endswith('.lod'):
                        model = model[:-4] + '.bml'
                    formatted_lines.append(f"{key:<16} = {model} {float(distance):.0f}")
                elif key == 'AddSlot':
                    slot_values = [float(v.strip('+')) for v in value.split()]
                    formatted_value = ' '.join(f"{v:.{self.max_float_precision}g}" for v in slot_values)
                    formatted_lines.append(f"{key:<16} = {formatted_value}")
                else:
                    formatted_lines.append(line)

        # Add a new line at the end of the file
        formatted_lines.append("")

        return '\n'.join(formatted_lines)

    def check_bml_files(self):
        path = self.path_entry.get()
        if not path:
            messagebox.showerror("Error", "Please select a file or folder first.")
            return

        self.log_text.delete(1.0, tk.END)
        self.all_folders_ok = True  # Reset the status

        if self.mode_switch.get() == 1:  # All mode
            self.check_bml_all(path)
            if self.all_folders_ok:
                self.log_text.insert(tk.END, "All BML files are correctly referenced in all parent.dat files\n", "success")
        else:  # Single mode
            self.check_bml_single(path)

    def check_bml_all(self, base_path):
        for root, dirs, files in os.walk(base_path):
            if any(f.lower() == "parent.dat" for f in files):
                self.check_bml_folder(root, is_all_mode=True)

    def check_bml_single(self, file_path):
        folder_path = os.path.dirname(file_path)
        self.check_bml_folder(folder_path, is_all_mode=False)

    def check_bml_folder(self, folder_path, is_all_mode):
        parent_file = next((f for f in os.listdir(folder_path) if f.lower() == "parent.dat"), None)
        if not parent_file:
            self.log_text.insert(tk.END, f"Error: parent.dat not found in {folder_path}\n", "error")
            self.all_folders_ok = False
            return

        bml_files = set(f.lower() for f in os.listdir(folder_path) if f.lower().endswith('.bml'))
        mentioned_bmls = set()

        with open(os.path.join(folder_path, parent_file), 'r') as file:
            for line in file:
                if line.strip().lower().startswith('addlod'):
                    parts = line.split('=')[1].strip().split()
                    if parts:
                        mentioned_bmls.add(parts[0].lower())

        missing_bmls = mentioned_bmls - bml_files
        extra_bmls = bml_files - mentioned_bmls

        if missing_bmls:
            self.log_text.insert(tk.END, f"Error: The following BML files are mentioned in parent.dat but not found in {folder_path},:\n", "error")
            for bml in missing_bmls:
                self.log_text.insert(tk.END, f"- {bml}\n", "error")
            self.all_folders_ok = False

        if extra_bmls:
            self.log_text.insert(tk.END, f"Error: The following BML files are in {folder_path}, but not mentioned in parent.dat:\n", "error")
            for bml in extra_bmls:
                self.log_text.insert(tk.END, f"- {bml}\n", "error")
            self.all_folders_ok = False

        if not missing_bmls and not extra_bmls and not is_all_mode:
            self.log_text.insert(tk.END, "All BML files are correctly referenced in parent.dat\n", "success")


class ParkingFixerPage(Ctk.CTkFrame):
    def __init__(self, parent, controller):
        Ctk.CTkFrame.__init__(self, parent)
        self.controller = controller
        self.ct_xml_path = ""
        self.obj_path = ""
        self.obj_name = ""
        self.hangars = []
        self.parking_points = []
        self.create_widgets()

    def create_widgets(self):

        # Start label
        self.start_frame = Ctk.CTkFrame(self)
        self.start_frame.pack(pady=30, fill="x")
        start_label = Ctk.CTkLabel(
            self.start_frame,
            text="Select the CT XML file of the desired Theater, and the Objective/ObjectiveRelatedData Folder",
        )
        start_label.pack()
        # Mode Selection
        mode_frame = Ctk.CTkFrame(self)
        mode_frame.pack(pady=10, padx=10, fill="x")
        self.mode_var = Ctk.StringVar(value="Single")
        self.mode_switch = Ctk.CTkSwitch(mode_frame, text="Single/All", variable=self.mode_var,
                                         onvalue="All", offvalue="Single")
        self.mode_switch.pack(side="left", padx=(0, 10))

        # Browse Frame
        browse_frame = Ctk.CTkFrame(self)
        browse_frame.pack(pady=5, padx=10, fill="x")

        self.browse_button = Ctk.CTkButton(browse_frame, text="Browse Folder", command=self.browse_folder, width=120,
        fg_color = "#A1B9D0",
        hover_color = "#7A92A9",
        text_color = "#000000"
        )
        self.browse_button.pack(side="left", padx=(0, 10))

        self.browse_entry = Ctk.CTkEntry(browse_frame, width=400)
        self.browse_entry.pack(side="left", expand=True, fill="x")

        # CT XML Frame
        ct_xml_frame = Ctk.CTkFrame(self)
        ct_xml_frame.pack(pady=5, padx=10, fill="x")

        self.ct_xml_button = Ctk.CTkButton(ct_xml_frame, text="Browse CT XML", command=self.browse_ct_xml, width=120,
        fg_color = "#A1B9D0",
        hover_color = "#7A92A9",
        text_color = "#000000"
        )
        self.ct_xml_button.pack(side="left", padx=(0, 10))

        self.ct_xml_entry = Ctk.CTkEntry(ct_xml_frame, width=400)
        self.ct_xml_entry.pack(side="left", expand=True, fill="x")

        # Radius and Hangar Numbers Frame
        params_frame = Ctk.CTkFrame(self, fg_color="transparent")
        params_frame.pack(pady=10, padx=10, fill="x")

        radius_label = Ctk.CTkLabel(params_frame, text="Radius (ft):")
        radius_label.pack(side="left", padx=(0, 5))

        self.radius_entry = Ctk.CTkEntry(params_frame, width=80)
        self.radius_entry.insert(0, "10")
        self.radius_entry.pack(side="left")

        hangar_label = Ctk.CTkLabel(params_frame, text="CT Num of Hangars:")
        hangar_label.pack(side="left", padx=(10, 5))

        self.hangar_entry = Ctk.CTkEntry(params_frame, width=200)
        self.hangar_entry.insert(0, "0")
        self.hangar_entry.pack(side="left", fill="x", expand=True)


        # Fix Parking Button
        self.fix_button = Ctk.CTkButton(self, text="Fix Parking", command=self.fix_parking,
        fg_color = "#A1B9D0",
        hover_color = "#7A92A9",
        text_color = "#000000"
        )
        self.fix_button.pack(pady=10)

        # Log Area
        self.text_log_frame = Ctk.CTkFrame(self)
        self.text_log_frame.pack(fill="x")
        self.choice_label = Ctk.CTkLabel(self.text_log_frame, text="Parking Fixing Log:")
        self.choice_label.pack()

        self.log_area = tk.Text(self, height=20, width=80)
        self.log_area.pack(pady=10, padx=10, fill="both", expand=True)
        self.log_area.tag_configure("success", foreground="green")
        self.log_area.tag_configure("failure", foreground="red")
        self.log_area.tag_configure("info", foreground="black")

    def browse_folder(self):
        """Open a file dialog to select a folder."""
        if self.mode_var.get() == "Single":
            self.obj_path = filedialog.askdirectory(title="Select Folder")
        else:
            self.obj_path = filedialog.askdirectory(title="Select Folder")
        if self.obj_path:
            self.browse_entry.delete(0, Ctk.END)
            self.browse_entry.insert(0, self.obj_path)
            self.log_message(f"Selected path: {self.obj_path}", "info")

    def browse_ct_xml(self):
        self.ct_xml_path = filedialog.askopenfilename(title="Select CT XML File", filetypes=[("XML Files", "*.xml")])
        if self.ct_xml_path:
            self.ct_xml_entry.delete(0, Ctk.END)
            self.ct_xml_entry.insert(0, self.ct_xml_path)
            self.log_message(f"Selected CT XML: {self.ct_xml_path}", "info")

    def fix_parking(self):
        if not self.obj_path:
            messagebox.showerror("Error", "Please select a folder or file first.")
            return
        if not self.ct_xml_path:
            messagebox.showerror("Error", "Please select a CT XML file.")
            return

        radius = float(self.radius_entry.get())
        needed_hangars = [str(num) for num in re.findall(r'\d+', self.hangar_entry.get())]

        if self.mode_var.get() == "Single":
            self.process_single_file(self.obj_path, radius, needed_hangars)
        else:
            self.process_multiple_files(self.obj_path, radius, needed_hangars)

    def process_single_file(self, obj_path, radius, needed_hangars):
        self.process_files(obj_path, radius, needed_hangars)

    def process_multiple_files(self, directory, radius, needed_hangars):
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith('ct.xml'):
                    self.process_files(file, radius, needed_hangars)

    def process_files(self, obj_path, radius, needed_hangars):
        # Find the OCD file in the obj_path
        ocd_file = next((f for f in os.listdir(obj_path) if f.startswith('OCD_') and f.lower().endswith('.xml')), None)

        if not ocd_file:
            self.log_message(f"Error: No OCD file found in {obj_path}", "failure")
            return

        # Extract the XXXX number from the OCD file name
        xxxx_number = ocd_file[4:9]  # Assumes format OCD_XXXXX.xml

        # Construct file paths for PHD, PDX, FED, and OCD files
        phd_file = f"PHD_{xxxx_number}.xml"
        pdx_file = f"PDX_{xxxx_number}.xml"
        fed_file = f"FED_{xxxx_number}.xml"
        ocd_file = f"OCD_{xxxx_number}.xml"

        # Full paths for the files
        phd_path = os.path.join(obj_path, phd_file)
        pdx_path = os.path.join(obj_path, pdx_file)
        fed_path = os.path.join(obj_path, fed_file)
        ocd_path = os.path.join(obj_path, ocd_file)

        # Get the actual name of the objective
        obj_name = self.extract_ocd_name(ocd_path)

        try:
            self.parse_ct_xml(needed_hangars)
            self.parse_pdx_xml(pdx_path)
            self.parse_fed_xml(fed_path)
            self.relocate_parking_points(radius)
            self.save_changes(pdx_path,ocd_file,obj_name)
        except Exception as e:
            self.log_message(f"Error processing {ocd_file}: {str(e)}", "failure")


    def extract_ocd_name(self,ocd_path):
        try:
            # Parse the XML file
            tree = ET.parse(ocd_path)
            root = tree.getroot()

            # Find the OCD element
            ocd = root.find('OCD')

            # Extract the Name
            name = ocd.find('Name').text

            return name
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
            return None
        except AttributeError as e:
            print(f"Error finding Name element: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

    def parse_ct_xml(self,needed_hangars):
        tree = ET.parse(self.ct_xml_path)
        root = tree.getroot()
        self.hangars = []
        for ct in root.findall("CT"):
            feature_type = ct.find("Type").text
            if feature_type == "45":  # Hangar type
                ct_idx = str(ct.get("Num"))
                self.hangars.append(ct_idx)
        #Get only the relevant
        print(len(needed_hangars))
        print(needed_hangars[0])
        if needed_hangars[0] == "0" or len(needed_hangars) == 0:
            self.filtered_hangars = self.hangars
        else:
            self.filtered_hangars = list(set(self.hangars) & set(needed_hangars))
            if len(self.filtered_hangars) == 0:
                raise "Error"


    def parse_fed_xml(self, file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()
        self.hangar_locations = []
        for fed in root.findall("FED"):
            feature_ct_idx = fed.find("FeatureCtIdx").text
            if feature_ct_idx in self.filtered_hangars:
                x = float(fed.find("OffsetX").text)
                y = float(fed.find("OffsetY").text)
                self.hangar_locations.append({"x": x, "y": y})

    def parse_pdx_xml(self, file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()
        self.parking_points = []
        for point in root.findall("PD"):
            point_type = point.find("Type").text
            if point_type in ["11", "12"]:  # Small and Large parking
                x = float(point.find("OffsetX").text)
                y = float(point.find("OffsetY").text)
                self.parking_points.append({"x": x, "y": y, "idx": point.get("Num")})

    def relocate_parking_points(self, radius):
        for point in self.parking_points:
            closest_hangar = None
            min_distance = float('inf')
            for hangar in self.hangar_locations:
                distance = sqrt((point["x"] - hangar["x"]) ** 2 + (point["y"] - hangar["y"]) ** 2)
                if distance <= radius and distance < min_distance:
                    closest_hangar = hangar
                    min_distance = distance

            if closest_hangar:
                point["x"] = closest_hangar["x"]
                point["y"] = closest_hangar["y"]

    def save_changes(self, file_path,ocd_file, obj_name):
        tree = ET.parse(file_path)
        root = tree.getroot()
        count_of_relocations = 0
        changes_made = False

        # Update coordinates if they differ
        for obj in root.findall("PD"):
            point_type = obj.find("Type").text
            class_index = obj.get("Num")
            if point_type in ["11", "12"]:  # Small and Large parking
                x_elem = obj.find("OffsetX")
                y_elem = obj.find("OffsetY")
                for point in self.parking_points:
                    if point["idx"] == class_index and (float(x_elem.text) != point["x"] or float(y_elem.text) != point["y"]):
                        x_elem.text = str(point["x"])
                        y_elem.text = str(point["y"])
                        count_of_relocations += 1
                        changes_made = True

        # Write changes back to file
        if changes_made:
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
            self.log_message(
                f"Relocated {count_of_relocations} parking point(s) to hangar(s) at {ocd_file} Objective ({obj_name})",
                "success")
        else:
            self.log_message(f"No parking points were relocated at {ocd_file} Objective ({obj_name}).", "info")


    def log_message(self, message, tag):
        self.log_area.insert(tk.END, message + "\n", tag)
        self.log_area.see(tk.END)



if __name__ == "__main__":
    app = MainPage()
    app.mainloop()
