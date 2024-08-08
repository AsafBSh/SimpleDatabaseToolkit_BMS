import os
import tkinter as tk
import customtkinter as Ctk
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from PIL import Image, ImageTk
import math
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

        # Set Name and Icon
        self.title("Simple Database Toolkit v1.1")
        self.iconbitmap("128_Icon.ico")

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
        pil_image = Image.open("Main.png")

        # Resize the image if needed
        # pil_image = pil_image.resize((300, 200), Image.ANTIALIAS)

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

        # Apply button
        self.apply_button = Ctk.CTkButton(
            self,
            text="Apply Changes",
            command=self.apply_changes,
            fg_color="#A1B9D0",
            hover_color="#7A92A9",
            text_color="#000000",
        )
        self.apply_button.pack(pady=10,padx=10)

        # Check Data button
        self.check_button = Ctk.CTkButton(self,
            text="Check Data",
            command=self.check_data,
            fg_color = "#A1B9D0",
            hover_color = "#7A92A9",
            text_color = "#000000"
        )
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
        - To provide a tool for fine-tuning or orientation the center position of a feature
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
        self.display_explanation(explanation, "tut_1.png")

    def show_runway_dim_fixer_explanation(self):
        explanation = textwrap.dedent("""
        ## Runway Dimension Fixer Page

        The Runway Dimension Fixer page allows users to update runway dimensions in PHD XML files.

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


if __name__ == "__main__":
    app = MainPage()
    app.mainloop()
