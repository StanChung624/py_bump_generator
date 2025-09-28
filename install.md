# Install Executional File

``` terminal
pyinstaller ^
    --noconsole ^
    --onefile ^
    --name "VBumpGenerator" ^
    --icon "icon.ico" ^
    --add-data "main.py;." ^
    --add-data "C:\Python311\Lib\site-packages\PySide6\plugins\platforms;PySide6\plugins\platforms" ^
    main_ui.py
```

``` terminal
pyinstaller --noconsole  --onefile --name "VBumpGenerator" --icon "icon.ico" main_ui.py
```
