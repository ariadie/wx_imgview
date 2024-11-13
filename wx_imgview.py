# v0.1 : 20241020 from ChatGPT
# v0.4 : add config.json
# v0.5 : using wx.SplitterWindow and Aspect Ratio Preservation
# v0.6 : info created by
# v0.7 : add rename feature
# v0.8 : use pytesseract
# v0.9 : 20241026 - fix drawing rectangle to mark selection 
# v1.0 : 20241026 - add second TextCtrl
# v1.1 : 20241026 - process date text to yyyymmdd 
# v1.2 : 20241027 - process dd-mm-yyyy hh:mm:ss
# v1.3 :
# v1.4 : 20241109 - one mouse click will not call ocr 
# v1.5 : 20241113 - fixing error "StaticBitmap has been deleted"

import wx
import os
import json
import wx.adv
import pytesseract
from PIL import Image

VERSION = 1.4
CONFIG_FILE = "config.json"  # File to store configuration
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'

class ImageFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(ImageFrame, self).__init__(*args, **kw)
        self.current_image = None  # Store the current image file name
        self.folder_path = None    # Store the folder path
        self.image_bitmap = None   # To store the image as a wx.Bitmap
        self.image_widget = None   # Store the wx.StaticBitmap instance for mouse event binding
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False
        self.InitUI()
        self.loadConfig()

    def InitUI(self):
        splitter = wx.SplitterWindow(self)

        # Create panels for the splitter
        left_panel = wx.Panel(splitter)
        right_panel = wx.Panel(splitter)

        # Create sizers for the left and right panels
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        # Left panel content: folder, refresh, checkbox, and listbox
        self.folder_btn = wx.Button(left_panel, label='Choose Folder')
        self.folder_btn.Bind(wx.EVT_BUTTON, self.onChooseFolder)

        self.refresh_btn = wx.Button(left_panel, label='Refresh List')
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.onRefreshList)
        self.refresh_btn.Disable()  # Initially disable, enable after folder selection

        left_sizer.Add(self.folder_btn, 0, wx.ALL | wx.CENTER, 5)
        left_sizer.Add(self.refresh_btn, 0, wx.ALL | wx.CENTER, 5)

        self.scale_checkbox = wx.CheckBox(left_panel, label='Scale to Fit')
        self.scale_checkbox.SetValue(True)  # Default is checked
        self.scale_checkbox.Bind(wx.EVT_CHECKBOX, self.onToggleScale)

        left_sizer.Add(self.scale_checkbox, 0, wx.ALL | wx.CENTER, 5)

        self.image_listbox = wx.ListBox(left_panel, style=wx.LB_SINGLE)
        self.image_listbox.Bind(wx.EVT_LISTBOX, self.onImageSelect)

        left_sizer.Add(self.image_listbox, 1, wx.EXPAND | wx.ALL, 5)

        # Split TextCtrl for filename and extension
        self.rename_base_text = wx.TextCtrl(left_panel)
        self.rename_ext_text = wx.TextCtrl(left_panel, size=(50, -1))  # Smaller width for extension
        self.rename_btn = wx.Button(left_panel, label="Rename")
        self.rename_btn.Bind(wx.EVT_BUTTON, self.onRenameFile)
        self.rename_btn.Disable()  # Disable until an image is selected

        rename_sizer = wx.BoxSizer(wx.HORIZONTAL)
        rename_sizer.Add(self.rename_base_text, 1, wx.EXPAND | wx.ALL, 5)
        rename_sizer.Add(self.rename_ext_text, 0, wx.ALL, 5)
        left_sizer.Add(rename_sizer, 0, wx.EXPAND)

        left_sizer.Add(self.rename_btn, 0, wx.ALL | wx.CENTER, 5)

        # Add a divider
        left_sizer.Add(wx.StaticLine(left_panel), 0, wx.EXPAND | wx.ALL, 5)

        # Add a TextCtrl for displaying OCR results
        self.ocr_result_text = wx.TextCtrl(left_panel, style=wx.TE_MULTILINE)
        left_sizer.Add(self.ocr_result_text, 1, wx.EXPAND | wx.ALL, 5)

        # Add a button to clear OCR text
        self.process_btn = wx.Button(left_panel, label="Process Text")
        self.process_btn.Bind(wx.EVT_BUTTON, self.onProcessText)
        left_sizer.Add(self.process_btn, 0, wx.ALL | wx.CENTER, 5)

        # Add a new TextCtrl to display OCR results in uppercase
        self.processed_ocr_text = wx.TextCtrl(left_panel, style=wx.TE_MULTILINE)
        left_sizer.Add(self.processed_ocr_text, 1, wx.EXPAND | wx.ALL, 5)

        # Add a button to copy processed OCR text
        self.copy_btn = wx.Button(left_panel, label="Copy Processed Text")
        self.copy_btn.Bind(wx.EVT_BUTTON, self.onCopyProcessedText)
        left_sizer.Add(self.copy_btn, 0, wx.ALL | wx.CENTER, 5)

        # Add a button to clear OCR text
        self.clear_btn = wx.Button(left_panel, label="Clear Text")
        self.clear_btn.Bind(wx.EVT_BUTTON, self.onClearText)
        left_sizer.Add(self.clear_btn, 0, wx.ALL | wx.CENTER, 5)

        left_panel.SetSizer(left_sizer)

        # Right panel content: Image display and OCR selection
        self.image_panel = wx.Panel(right_panel, size=(400, 400))
        self.image_sizer = wx.BoxSizer(wx.VERTICAL)
        self.image_panel.SetSizer(self.image_sizer)

        right_sizer.Add(self.image_panel, 1, wx.EXPAND | wx.ALL, 5)
        right_panel.SetSizer(right_sizer)

        # Split the window
        splitter.SplitVertically(left_panel, right_panel)
        splitter.SetSashGravity(0.5)  # Default ratio of left panel width (50% width)
        splitter.SetMinimumPaneSize(250)  # Minimum width for the left panel

        self.SetTitle('Image Viewer with OCR and Selectable Area')

        # Create menu
        self.createMenuBar()

        self.Centre()

    # New function to handle clearing the OCR text area
    def onClearText(self, event):
        """Clear the OCR text area."""
        self.ocr_result_text.Clear()
        self.processed_ocr_text.Clear()

    def convert_date_format(self, date_str):
        date_str = date_str.strip()

        # Check if the input matches the expected format (dd.mm.yy)
        if len(date_str) == 8 and date_str[2] == '.' and date_str[5] == '.' and date_str[:2].isdigit() and date_str[3:5].isdigit() and date_str[6:].isdigit():
            # Split the date string into day, month, and year
            day, month, year = date_str.split(".")
            
            # Rearrange and format the date
            return f"20{year}{month}{day}"
        # Check if the input matches the expected format "dd-mm-yyyy hh:mm:ss"
        elif (len(date_str) == 19 and 
            date_str[2] == '-' and 
            date_str[5] == '-' and 
            date_str[10] == ' ' and 
            date_str[13] == ':' and 
            date_str[16] == ':' and 
            date_str[:2].isdigit() and 
            date_str[3:5].isdigit() and 
            date_str[6:10].isdigit() and 
            date_str[11:13].isdigit() and 
            date_str[14:16].isdigit() and 
            date_str[17:].isdigit()):
            
            # Extract components
            day = date_str[:2]
            month = date_str[3:5]
            year = date_str[6:10]
            hour = date_str[11:13]
            minute = date_str[14:16]
            second = date_str[17:19]

            # Rearrange and format the output
            return f"{year}{month}{day}-{hour}{minute}{second}"
        else:
            # Return the original text if format doesn't match
            return date_str

    def onProcessText(self, event):
        """Convert OCR text to uppercase."""
        current_text = self.ocr_result_text.GetValue()
        print(current_text)
        self.processed_ocr_text.SetValue(self.convert_date_format(current_text))

    def createMenuBar(self):
        """Create the menu bar with an About item."""
        menubar = wx.MenuBar()
        help_menu = wx.Menu()
        
        about_item = help_menu.Append(wx.ID_ABOUT, '&About', 'Information about this program')
        self.Bind(wx.EVT_MENU, self.onAbout, about_item)
        
        menubar.Append(help_menu, '&Help')
        self.SetMenuBar(menubar)

    def onAbout(self, event):
        """Display an About dialog."""
        about_info = wx.adv.AboutDialogInfo()
        about_info.SetName("Image Viewer")
        about_info.SetDescription("Simple image viewer with OCR and selectable area.\nCreated by Ariadie Chandra - 2024")
        about_info.SetVersion(str(VERSION))
        wx.adv.AboutBox(about_info)

    def onChooseFolder(self, event):
        """Handle folder selection and populate listbox with image files."""
        dlg = wx.DirDialog(self, "Choose a directory containing images", "", wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)

        if dlg.ShowModal() == wx.ID_OK:
            self.folder_path = dlg.GetPath()
            self.saveConfig(self.folder_path)  # Save folder path to config
            self.populateImageList()
            self.refresh_btn.Enable()  # Enable the refresh button once a folder is selected

        dlg.Destroy()

    def onRefreshList(self, event):
        """Handle the refresh button press."""
        self.populateImageList()

    def populateImageList(self):
        """List image files from the selected folder."""
        if not self.folder_path:
            return

        # Clear the listbox first
        self.image_listbox.Clear()

        # Populate the listbox with image files
        supported_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
        files = [f for f in os.listdir(self.folder_path) if f.lower().endswith(supported_extensions)]

        for file in files:
            self.image_listbox.Append(file)

    def onImageSelect(self, event):
        """Handle the selection of an image and display it in the panel."""
        selection = self.image_listbox.GetSelection()
        if selection != wx.NOT_FOUND:
            self.current_image = self.image_listbox.GetString(selection)  # Store the current image
            self.rename_base_text.SetValue(os.path.splitext(self.current_image)[0])
            self.rename_ext_text.SetValue(os.path.splitext(self.current_image)[1][1:])  # Remove dot from extension   
            self.rename_btn.Enable()  # Enable the rename button
            self.displayImage(self.current_image)

    def onToggleScale(self, event):
        """Handle the toggle of the Scale to Fit checkbox and refresh the current image."""
        if self.current_image:
            self.displayImage(self.current_image)  # Refresh the image display based on checkbox state

    def displayImage(self, image_file):
        """Display the selected image in the image panel."""
        if not self.folder_path:
            return

        image_path = os.path.join(self.folder_path, image_file)
        image = wx.Image(image_path, wx.BITMAP_TYPE_ANY)

        # Initialize the bitmap variable properly in both cases
        if self.scale_checkbox.GetValue():
            bitmap = self.scaleImageToFit(image)
        else:
            bitmap = wx.Bitmap(image)

        self.image_bitmap = bitmap  # Store the bitmap for use in the selection

        # Clear the sizer first before adding new content
        self.image_sizer.Clear(True)

        # Create a wx.StaticBitmap widget to display the image
        self.image_widget = wx.StaticBitmap(self.image_panel, -1, bitmap)

        # Bind mouse events to the StaticBitmap (image_widget)
        self.image_widget.Bind(wx.EVT_LEFT_DOWN, self.onMouseDown)
        self.image_widget.Bind(wx.EVT_MOTION, self.onMouseDrag)
        self.image_widget.Bind(wx.EVT_LEFT_UP, self.onMouseUp)
        self.image_widget.Bind(wx.EVT_PAINT, self.onPaint)

        # Add the StaticBitmap to the sizer and refresh the panel
        self.image_sizer.Add(self.image_widget, 1, wx.EXPAND | wx.ALL, 5)
        self.image_panel.Layout()

    def scaleImageToFit(self, image):
        """Scale the image while maintaining its aspect ratio to fit the panel."""
        panel_size = self.image_panel.GetSize()
        image_width, image_height = image.GetWidth(), image.GetHeight()
        panel_width, panel_height = panel_size.GetWidth(), panel_size.GetHeight()

        # Calculate the aspect ratios
        image_ratio = image_width / image_height
        panel_ratio = panel_width / panel_height

        # Determine the scaling based on the aspect ratios
        if panel_ratio > image_ratio:
            # Panel is wider relative to height, scale by height
            new_height = panel_height
            new_width = new_height * image_ratio
        else:
            # Panel is taller relative to width, scale by width
            new_width = panel_width
            new_height = new_width / image_ratio

        # Scale the image while maintaining aspect ratio
        scaled_image = image.Scale(int(new_width), int(new_height), wx.IMAGE_QUALITY_HIGH)

        # Return the scaled image as a bitmap
        return wx.Bitmap(scaled_image)
    
    def onCopyProcessedText(self, event):
        """Copy the content of processed_ocr_text to clipboard."""
        processed_text = self.processed_ocr_text.GetValue()
        pyperclip.copy(processed_text)
        wx.MessageBox("Processed text copied to clipboard!", "Success", wx.OK | wx.ICON_INFORMATION)

    def onMouseDown(self, event):
        """Start the selection when the mouse is pressed."""
        self.selection_start = event.GetPosition()
        self.is_selecting = True

    def onMouseDrag(self, event):
        """Update the selection rectangle while dragging."""
        if self.is_selecting:
            self.selection_end = event.GetPosition()
            self.image_widget.Refresh()  # Trigger a repaint to draw the selection rectangle

    def onMouseUp(self, event):
        """Finish the selection and perform OCR."""
        self.is_selecting = False
        self.selection_end = event.GetPosition()

        if (self.selection_start != self.selection_end):
            # Perform OCR on the selected region
            # print(self.selection_start)
            # print(self.selection_end)
            self.performOCR()

    def onPaint(self, event):

        if self.image_widget:
            dc = wx.PaintDC(self.image_widget)
            dc.DrawBitmap(self.image_bitmap, 0, 0, True)
        
        """Draw the selection rectangle."""
        if self.is_selecting and self.selection_start and self.selection_end:
            dc.SetPen(wx.Pen('blue', 2, wx.PENSTYLE_DOT))
            dc.SetBrush(wx.Brush(wx.TRANSPARENT_BRUSH))
            rect = wx.Rect(self.selection_start, self.selection_end)
            dc.DrawRectangle(rect)

    def performOCR(self):
        """Perform OCR on the selected part of the image."""
        if self.image_bitmap and self.selection_start and self.selection_end:
            x1, y1 = self.selection_start
            x2, y2 = self.selection_end
            region = wx.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

            # Convert the wx.Bitmap to PIL image
            img = self.wxBitmapToPilImage(self.image_bitmap)
            cropped_img = img.crop((region.x, region.y, region.x + region.width, region.y + region.height))

            # Perform OCR using pytesseract
            ocr_text = pytesseract.image_to_string(cropped_img)
            
            # Append OCR text to the existing content of ocr_result_text
            current_text = self.ocr_result_text.GetValue()
            new_text = current_text + ocr_text
            self.ocr_result_text.SetValue(new_text)
            
    def wxBitmapToPilImage(self, bitmap):
        """Convert wx.Bitmap to PIL Image."""
        size = bitmap.GetSize()
        img = wx.Image(bitmap.ConvertToImage())
        return Image.frombytes('RGB', (size.width, size.height), img.GetDataBuffer())

    def onRenameFile(self, event):
        """Rename the current image file."""
        new_base_name = self.rename_base_text.GetValue()
        new_ext_name = self.rename_ext_text.GetValue()
        new_file_name = f"{new_base_name}.{new_ext_name}"
        if not new_file_name:
            wx.MessageBox("Please enter a new file name.", "Error", wx.OK | wx.ICON_ERROR)
            return

        old_path = os.path.join(self.folder_path, self.current_image)
        new_path = os.path.join(self.folder_path, new_file_name)

        try:
            os.rename(old_path, new_path)
            self.populateImageList()  # Refresh the list with the new file name
            wx.MessageBox(f"File renamed to {new_file_name}", "Success", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"Error renaming file: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def loadConfig(self):
        """Load folder path from config file if it exists."""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as config_file:
                config_data = json.load(config_file)
                folder_path = config_data.get('folder_path')

                # Verify that the saved folder path still exists
                if folder_path and os.path.exists(folder_path):
                    self.folder_path = folder_path
                    self.populateImageList()
                    self.refresh_btn.Enable()  # Enable the refresh button

    def saveConfig(self, folder_path):
        """Save the selected folder path to the config file."""
        config_data = {'folder_path': folder_path}
        with open(CONFIG_FILE, 'w') as config_file:
            json.dump(config_data, config_file)

class MyApp(wx.App):
    def OnInit(self):
        self.frame = ImageFrame(None, size=(800, 600))
        self.frame.Show()
        return True

if __name__ == '__main__':
    app = MyApp(False)
    app.MainLoop()
