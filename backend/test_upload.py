import win32com.client as win32
import pythoncom
import os
import shutil

pythoncom.CoInitialize()

# Simulate what FastAPI does: save uploaded file to temp dir
source_docx = os.path.abspath(os.path.join(os.path.expanduser("~"), "OneHubTemp", "test_input.docx"))
temp_dir = os.path.join(os.path.expanduser("~"), "OneHubTemp", "upload_test")
os.makedirs(temp_dir, exist_ok=True)

# Copy to simulate upload (with Korean filename too)
for test_name in ["test_input.docx", "테스트문서.docx"]:
    file_path = os.path.join(temp_dir, test_name)
    shutil.copy2(source_docx, file_path)
    file_path = os.path.abspath(file_path)

    print(f"\n=== Testing with filename: {test_name} ===")
    print(f"File path: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
    print(f"File size: {os.path.getsize(file_path)}")

    hwp = win32.Dispatch("HWPFrame.HwpObject")
    hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
    hwp.XHwpWindows.Item(0).Visible = False

    result = hwp.Open(file_path, "", "")
    print(f"Open returned: {result}")
    text = hwp.GetTextFile("TEXT", "")
    print(f"Content: {repr(text[:200])}")

    output_hwp = os.path.join(temp_dir, test_name.replace(".docx", ".hwp"))
    hwp.HAction.GetDefault("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)
    hwp.HParameterSet.HFileOpenSave.filename = output_hwp
    hwp.HParameterSet.HFileOpenSave.Format = "HWP"
    hwp.HAction.Execute("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)

    print(f"Output exists: {os.path.exists(output_hwp)}")
    if os.path.exists(output_hwp):
        print(f"Output size: {os.path.getsize(output_hwp)}")

    # Reopen and check
    hwp.Clear(1)
    hwp.Open(output_hwp, "", "")
    text2 = hwp.GetTextFile("TEXT", "")
    print(f"Reopened content: {repr(text2[:200])}")

    hwp.Clear(1)
    hwp.Quit()

    # Cleanup temp upload file
    try:
        os.remove(file_path)
    except:
        pass

pythoncom.CoUninitialize()
print("\nDone")
