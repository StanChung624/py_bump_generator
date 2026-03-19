# Install Executional File

First, ensure submodules are initialized and requirements are installed:
``` terminal
git submodule update --init --recursive
pip install --ignore-requires-python ./external/dxfextractor
pip install -r requirements.txt
```

Then, run PyInstaller:
``` terminal
pyinstaller --noconsole  --onefile --name "VBumpGenerator" --icon "icon.ico" --hidden-import="h5py._npystrings" --hidden-import="dxf_extract" --collect-all="ezdxf" main_ui.py
```
