# To run this script:
# pip install requests
# Note: tkinter is part of the Python standard library, but on some Linux distributions,
# you may need to install it via package manager, e.g., sudo apt install python3-tk

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil
import subprocess
import platform
import requests
import stat

def download_appimagetool():
    try:
        arch = platform.machine()
        if arch == 'x86_64':
            url = 'https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage'
        elif arch == 'aarch64':
            url = 'https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-aarch64.AppImage'
        else:
            raise ValueError(f"Unsupported architecture: {arch}")
        
        tool_path = 'appimagetool.AppImage'
        if not os.path.exists(tool_path):
            response = requests.get(url)
            response.raise_for_status()
            with open(tool_path, 'wb') as f:
                f.write(response.content)
            os.chmod(tool_path, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH)
        return tool_path
    except Exception as e:
        messagebox.showerror("Download Error", f"Failed to download appimagetool: {str(e)}")
        return None

def locate_file(prompt, initialdir=None, filetypes=None):
    if initialdir is None:
        initialdir = os.getcwd()
    if filetypes is None:
        filetypes = [("All files", "*.*")]
    try:
        return filedialog.askopenfilename(title=prompt, initialdir=initialdir, filetypes=filetypes)
    except Exception as e:
        messagebox.showerror("File Dialog Error", str(e))
        return None

def locate_dir(prompt, initialdir=None):
    if initialdir is None:
        initialdir = os.getcwd()
    try:
        return filedialog.askdirectory(title=prompt, initialdir=initialdir)
    except Exception as e:
        messagebox.showerror("Directory Dialog Error", str(e))
        return None

def is_flutter_app(base_dir):
    # Check for typical Flutter artifacts
    data_path = os.path.join(base_dir, 'data')
    lib_path = os.path.join(base_dir, 'lib')
    if os.path.exists(os.path.join(data_path, 'icudtl.dat')) or os.path.exists(os.path.join(data_path, 'flutter_assets')):
        return True
    if os.path.exists(lib_path) and any(f.startswith('lib') and f.endswith('.so') for f in os.listdir(lib_path)):
        return True
    return False

def build_appimage():
    if platform.system() != 'Linux':
        messagebox.showerror("Error", "This tool only supports Linux.")
        return
    
    app_name = app_name_entry.get().strip()
    exec_path = exec_entry.get().strip()
    icon_path = icon_entry.get().strip()
    support_dirs = [d.strip() for d in support_entry.get().split(',') if d.strip()]
    patch_paths = patch_var.get()
    
    if not app_name:
        messagebox.showerror("Error", "App name is required.")
        return
    
    base_dir = os.path.dirname(exec_path) if exec_path else os.getcwd()
    
    # Verify and prompt if missing
    if not exec_path or not os.path.exists(exec_path):
        exec_path = locate_file("Select Executable", base_dir)
        if not exec_path:
            return
        exec_entry.delete(0, tk.END)
        exec_entry.insert(0, exec_path)
    exec_basename = os.path.basename(exec_path)
    
    if not icon_path or not os.path.exists(icon_path):
        icon_path = locate_file("Select Icon", base_dir, [('Image files', '*.png *.svg *.jpg *.ico')])
        if not icon_path:
            return
        icon_entry.delete(0, tk.END)
        icon_entry.insert(0, icon_path)
    icon_basename = os.path.basename(icon_path)
    icon_base_noext = os.path.splitext(icon_basename)[0]
    
    # Auto-detect Flutter if support_dirs empty
    is_flutter = is_flutter_app(base_dir)
    if not support_dirs and is_flutter:
        support_dirs = ['data', 'lib']
        support_entry.delete(0, tk.END)
        support_entry.insert(0, 'data,lib')
        messagebox.showinfo("Auto-Detect", "Detected possible Flutter app. Auto-added 'data,lib' as supporting folders.")
    
    support_paths = []
    for d in support_dirs:
        full_d = os.path.join(base_dir, d)
        if not os.path.exists(full_d):
            full_d = locate_dir(f"Select {d} Folder", base_dir)
            if not full_d:
                return
        support_paths.append(full_d)
    
    output_appimage = os.path.join(os.getcwd(), f"{app_name.replace(' ', '')}.AppImage")
    appdir = f"{app_name.replace(' ', '')}.AppDir"
    
    try:
        # Create temp AppDir
        if os.path.exists(appdir):
            shutil.rmtree(appdir)
        os.mkdir(appdir)
        
        # Copy executable
        shutil.copy(exec_path, os.path.join(appdir, exec_basename))
        
        # Create AppRun script (better for LD_LIBRARY_PATH)
        apprun_content = f"""#!/bin/sh
HERE="$(dirname "$(readlink -f "${{0}}")")"
export LD_LIBRARY_PATH="${{HERE}}/lib:${{LD_LIBRARY_PATH}}"
exec "${{HERE}}/{exec_basename}" "$@"
"""
        apprun_path = os.path.join(appdir, 'AppRun')
        with open(apprun_path, 'w') as f:
            f.write(apprun_content)
        os.chmod(apprun_path, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH)
        
        # Copy icon
        shutil.copy(icon_path, os.path.join(appdir, icon_basename))
        
        # Copy support dirs
        for sp in support_paths:
            dest = os.path.join(appdir, os.path.basename(sp))
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(sp, dest)
        
        # Generate .desktop
        desktop_filename = f"{app_name.lower().replace(' ', '')}.desktop"
        desktop_content = f"""[Desktop Entry]
Type=Application
Name={app_name}
Exec=AppRun
Icon={icon_base_noext}
Categories=Utility;
"""
        with open(os.path.join(appdir, desktop_filename), 'w') as f:
            f.write(desktop_content)
        
        # Optional path patching (for binaries, use strings and warn if needed)
        if patch_paths:
            try:
                # Simple sed for text-like files; warn for binaries
                for root, dirs, files in os.walk(appdir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.access(file_path, os.X_OK):  # Executable
                            # Check for /usr
                            output = subprocess.check_output(['strings', file_path])
                            if b'/usr' in output:
                                messagebox.showwarning("Path Patching", f"Hardcoded /usr found in {file}. Auto-patching may not work on binaries; consider manual patching.")
                            # Attempt sed anyway (may corrupt if not text)
                            subprocess.call(['sed', '-i', '-e', 's#/usr#././#g', file_path])
            except Exception as e:
                messagebox.showwarning("Patch Warning", f"Path patching failed: {str(e)}. Proceeding without.")
        
        # Download tool if needed
        tool = download_appimagetool()
        if not tool:
            return
        
        # Build AppImage
        subprocess.check_call([f"./{tool}", appdir, output_appimage])
        
        # Make executable
        os.chmod(output_appimage, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH)
        
        # Run to test
        try:
            proc = subprocess.Popen([output_appimage], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Wait a bit to check for immediate errors
            stdout, stderr = proc.communicate(timeout=5)
            if proc.returncode and proc.returncode != 0:
                raise subprocess.CalledProcessError(proc.returncode, output_appimage, stdout, stderr)
            messagebox.showinfo("Success", f"AppImage created at {output_appimage}. It launched successfully (check for app window).")
        except subprocess.TimeoutExpired:
            # App is running (GUI apps don't exit immediately)
            messagebox.showinfo("Success", f"AppImage created at {output_appimage}. It is running (GUI app detected).")
            proc.kill()  # Optional: kill if test only, but let run to show
        except Exception as e:
            messagebox.showerror("Run Error", f"AppImage created, but failed to run: {str(e)}\nStderr: {stderr.decode() if stderr else 'None'}")
        
    except Exception as e:
        messagebox.showerror("Build Error", str(e))
    finally:
        if os.path.exists(appdir):
            shutil.rmtree(appdir)

# GUI Setup
root = tk.Tk()
root.title("AppImage Builder")

tk.Label(root, text="App Name:").grid(row=0, column=0, sticky='w')
app_name_entry = tk.Entry(root)
app_name_entry.grid(row=0, column=1)

tk.Label(root, text="Executable Path:").grid(row=1, column=0, sticky='w')
exec_entry = tk.Entry(root)
exec_entry.grid(row=1, column=1)
tk.Button(root, text="Browse", command=lambda: exec_entry.delete(0, tk.END) or exec_entry.insert(0, locate_file("Select Executable") or '')).grid(row=1, column=2)

tk.Label(root, text="Icon Path:").grid(row=2, column=0, sticky='w')
icon_entry = tk.Entry(root)
icon_entry.grid(row=2, column=1)
tk.Button(root, text="Browse", command=lambda: icon_entry.delete(0, tk.END) or icon_entry.insert(0, locate_file("Select Icon", filetypes=[('Image files', '*.png *.svg *.jpg *.ico')]) or '')).grid(row=2, column=2)

tk.Label(root, text="Supporting Folders (comma-separated, e.g., data,lib):").grid(row=3, column=0, sticky='w')
support_entry = tk.Entry(root)
support_entry.grid(row=3, column=1)
support_entry.insert(0, "data,lib")  # Default for Flutter-like apps

patch_var = tk.BooleanVar(value=False)
tk.Checkbutton(root, text="Patch absolute paths (/usr to relative)? (Experimental, may corrupt binaries)", variable=patch_var).grid(row=4, column=0, columnspan=2, sticky='w')

tk.Label(root, text="Hints:\n- For Flutter apps, include 'data' (with icudtl.dat, flutter_assets) and 'lib' (with .so files).\n- Ensure app is built for Linux and relocatable.\n- If app fails to run in AppImage, check for missing deps or hardcoded paths.\n- AppImage outputs to current directory.\n- Auto-detects Flutter and suggests folders if empty.").grid(row=5, column=0, columnspan=3, sticky='w')

tk.Button(root, text="Build and Run AppImage", command=build_appimage).grid(row=6, column=1)

root.mainloop()
