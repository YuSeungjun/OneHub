import win32com.client as win32
import pythoncom
import os

pythoncom.CoInitialize()
hwp = win32.Dispatch("HWPFrame.HwpObject")
hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
hwp.XHwpWindows.Item(0).Visible = False

# Create test DOCX
try:
    from docx import Document
    doc = Document()
    doc.add_paragraph("Hello Test Content 12345")
    test_docx = os.path.join(os.path.expanduser("~"), "OneHubTemp", "test_input.docx")
    os.makedirs(os.path.dirname(test_docx), exist_ok=True)
    doc.save(test_docx)
    print(f"Created test docx: {test_docx}")
except Exception as e:
    print(f"python-docx not available: {e}")
    test_docx = None

if test_docx:
    test_docx = os.path.abspath(test_docx)

    # Test 1: Open(path, "", "")
    print('--- Test 1: Open(path, "", "") ---')
    try:
        result = hwp.Open(test_docx, "", "")
        print(f"Open returned: {result}")
        text = hwp.GetTextFile("TEXT", "")
        print(f"Content length: {len(text)}")
        print(f"Content preview: {repr(text[:200])}")
        hwp.Clear(1)
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: Open(path, "OOXML", "")
    print('--- Test 2: Open(path, "OOXML", "") ---')
    try:
        result = hwp.Open(test_docx, "OOXML", "")
        print(f"Open returned: {result}")
        text = hwp.GetTextFile("TEXT", "")
        print(f"Content length: {len(text)}")
        print(f"Content preview: {repr(text[:200])}")
        hwp.Clear(1)
    except Exception as e:
        print(f"Error: {e}")

    # Test 3: InsertFile 3 params
    print('--- Test 3: InsertFile(path, "OOXML", "") ---')
    try:
        hwp.InsertFile(test_docx, "OOXML", "")
        text = hwp.GetTextFile("TEXT", "")
        print(f"Content length: {len(text)}")
        print(f"Content preview: {repr(text[:200])}")
        hwp.Clear(1)
    except Exception as e:
        print(f"Error: {e}")

    # Test 4: InsertFile 1 param
    print('--- Test 4: InsertFile(path) ---')
    try:
        hwp.InsertFile(test_docx)
        text = hwp.GetTextFile("TEXT", "")
        print(f"Content length: {len(text)}")
        print(f"Content preview: {repr(text[:200])}")
        hwp.Clear(1)
    except Exception as e:
        print(f"Error: {e}")

    # Test 5: HAction FileOpen with OOXML
    print('--- Test 5: HAction FileOpen ---')
    try:
        hwp.HAction.GetDefault("FileOpen", hwp.HParameterSet.HFileOpenSave.HSet)
        hwp.HParameterSet.HFileOpenSave.filename = test_docx
        hwp.HParameterSet.HFileOpenSave.Format = "OOXML"
        result = hwp.HAction.Execute("FileOpen", hwp.HParameterSet.HFileOpenSave.HSet)
        print(f"Execute returned: {result}")
        text = hwp.GetTextFile("TEXT", "")
        print(f"Content length: {len(text)}")
        print(f"Content preview: {repr(text[:200])}")
        hwp.Clear(1)
    except Exception as e:
        print(f"Error: {e}")

    # Test 6: HAction FileOpen with empty format
    print('--- Test 6: HAction FileOpen (auto) ---')
    try:
        hwp.HAction.GetDefault("FileOpen", hwp.HParameterSet.HFileOpenSave.HSet)
        hwp.HParameterSet.HFileOpenSave.filename = test_docx
        hwp.HParameterSet.HFileOpenSave.Format = ""
        result = hwp.HAction.Execute("FileOpen", hwp.HParameterSet.HFileOpenSave.HSet)
        print(f"Execute returned: {result}")
        text = hwp.GetTextFile("TEXT", "")
        print(f"Content length: {len(text)}")
        print(f"Content preview: {repr(text[:200])}")
        hwp.Clear(1)
    except Exception as e:
        print(f"Error: {e}")

hwp.Quit()
pythoncom.CoUninitialize()
print("Done")
