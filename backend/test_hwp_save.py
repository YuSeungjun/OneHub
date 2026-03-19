import win32com.client as win32
import pythoncom
import os

pythoncom.CoInitialize()
hwp = win32.Dispatch("HWPFrame.HwpObject")
hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
hwp.XHwpWindows.Item(0).Visible = False

test_docx = os.path.abspath(os.path.join(os.path.expanduser("~"), "OneHubTemp", "test_input.docx"))
output_dir = os.path.join(os.path.expanduser("~"), "OneHubTemp")

# Test: Open DOCX then save as HWP using FileSaveAs_S
print("--- Open DOCX and save as HWP ---")
hwp.Open(test_docx, "", "")
text_before = hwp.GetTextFile("TEXT", "")
print(f"Content after Open: {repr(text_before[:200])}")

output_hwp = os.path.join(output_dir, "test_output.hwp")
hwp.HAction.GetDefault("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)
hwp.HParameterSet.HFileOpenSave.filename = output_hwp
hwp.HParameterSet.HFileOpenSave.Format = "HWP"
result = hwp.HAction.Execute("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)
print(f"FileSaveAs_S returned: {result}")
print(f"File exists: {os.path.exists(output_hwp)}")
if os.path.exists(output_hwp):
    print(f"File size: {os.path.getsize(output_hwp)} bytes")
hwp.Clear(1)

# Now reopen the saved HWP and check content
print("--- Reopen saved HWP ---")
hwp.Open(output_hwp, "", "")
text_after = hwp.GetTextFile("TEXT", "")
print(f"Content after reopen: {repr(text_after[:200])}")
hwp.Clear(1)

hwp.Quit()
pythoncom.CoUninitialize()
print("Done")
