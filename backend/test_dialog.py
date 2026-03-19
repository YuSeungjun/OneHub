"""한글 COM 실행 시 뜨는 보안 대화상자의 실제 정보를 수집하는 테스트 스크립트"""
import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import win32com.client as win32
import pythoncom

user32 = ctypes.windll.user32

user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]

def get_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

def get_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value

def monitor_dialogs():
    """새로 뜨는 대화상자를 감지하고 정보를 출력"""
    seen = set()
    for i in range(150):  # 15초
        time.sleep(0.1)
        try:
            dialogs = []
            def on_top(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    cls = get_class(hwnd)
                    title = get_text(hwnd)
                    if hwnd not in seen and (cls == '#32770' or 'hwp' in title.lower() or '한' in title):
                        seen.add(hwnd)
                        dialogs.append((hwnd, cls, title))
                return True

            cb = WNDENUMPROC(on_top)
            user32.EnumWindows(cb, 0)

            for hwnd, cls, title in dialogs:
                print(f"\n=== 대화상자 발견 ===")
                print(f"  HWND: {hwnd}")
                print(f"  Class: {cls}")
                print(f"  Title: '{title}'")
                print(f"  Children:")

                def on_child(child, _):
                    child_cls = get_class(child)
                    child_text = get_text(child)
                    if child_text:
                        print(f"    [{child_cls}] '{child_text}'")
                    return True

                child_cb = WNDENUMPROC(on_child)
                user32.EnumChildWindows(hwnd, child_cb, 0)
        except Exception as e:
            print(f"Error: {e}")

print("대화상자 감시 시작...")
t = threading.Thread(target=monitor_dialogs, daemon=True)
t.start()

print("한글 COM 객체 생성 중...")
pythoncom.CoInitialize()
try:
    hwp = win32.Dispatch("HWPFrame.HwpObject")
    print("COM 객체 생성 완료!")
    hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
    hwp.XHwpWindows.Item(0).Visible = False
    hwp.Quit()
except Exception as e:
    print(f"오류: {e}")
finally:
    pythoncom.CoUninitialize()

t.join(timeout=3)
print("\n테스트 완료")
