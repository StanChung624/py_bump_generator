# Virtual Bump Generator

Virtual Bump Generator 是一套用來建立及管理虛擬焊錫凸點 (virtual bump, v-bump) 的 Python 工具組，提供終端機 CLI 與 PySide6 GUI 兩種使用介面，支援 CSV、HDF5 與 Moldex3D WDL 格式。無論是批次產生矩形陣列、調整群組屬性，或是視覺化檢查基板區域，都能快速完成。

## 特色
- **雙介面**：`python main.py` 提供互動式 CLI；`python main_ui.py` 提供視覺化 GUI 與 3D Plot。
- **多格式支援**：可匯入/匯出 CSV、HDF5 (`.h5/.vbump`) 與 Moldex3D WDL (weldline/airtrap)。
- **大資料處理**：提供 HDF5 串流寫入，便於處理數十萬筆 v-bump 資料。
- **群組化操作**：可依群組調整直徑、搬移/複製、轉換 WDL，並自動維護 bounding box。
- **可視化工具**：內建 matplotlib 3D 繪圖與 substrate 辨識，快速檢查佈局。

## 專案結構
- `main.py`：終端機互動主程式。
- `main_ui.py`：PySide6 GUI 介面。
- `VBumpDef.py`：`VBump` 資料類別、CSV/HDF5 讀寫、bounding box 計算。
- `createRectangularArea.py`：矩形陣列生成與 HDF5 串流工具。
- `vbumpsManipulation.py`：直徑調整、搬移/複製等操作。
- `fileManipulation.py`：多個 CSV 檔案合併。
- `vbumps2WDL.py`：輸出 Moldex3D WDL、AABB 及繪圖函式。
- `requirements.txt`：依賴套件清單。
- `install.md`：使用 PyInstaller 打包 GUI 的範例指令。
- `model_Run1.h5`、`model_Run1.vbump`：範例資料。

## 安裝與環境
建議使用 Python 3.10 以上版本並建立虛擬環境：
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows 請使用 .venv\\Scripts\\activate
pip install -r requirements.txt
```
若僅需 CLI，可選擇略過 PySide6 相關套件；建議保留完整依賴以便切換模式。

## 快速上手

### CLI 工作流程
```bash
python main.py
```
常用選單功能：
1. `Load VBump CSV`：載入 CSV (可選覆蓋或附加)，並可重設 group ID。
2. `Save VBump CSV`：輸出目前的 v-bump 清單。
3. `Create rectangular area (pitch)`：以 pitch 參數建立矩形陣列。
4. `Create rectangular area (count)`：指定 X/Y 個數自動平均分配。
5. `Modify diameter`：全體或特定群組調整直徑。
6. `Move/Copy vbumps`：依參考點搬移或複製，可設定新直徑與群組。
7. `Export to WDL (weldline)`：匯出 Moldex3D Weldline WDL；當資料量 ≥ 300,000 筆時自動改輸出每群組的 AABB。
8. `Export to WDL (airtrap)`：以中點輸出 Airtrap WDL。
9. `Merge CSV files`：合併多個 CSV 並可立即載入。
10. `Plot vbumps AABB`：使用 matplotlib 繪製各群組 bounding box，可搭配 substrate。
11. `Set substrate box corners`：設定基板框線座標。
0. `Exit`：離開程式。

### GUI 工作流程
```bash
python main_ui.py
```
GUI 介面提供：
- CSV/HDF5/VBUMP 載入與儲存對話框。
- 以 Pitch 或 Count 建立矩形陣列的精靈式流程。
- 直徑調整、搬移/複製、按群組刪除等工具。
- Weldline/Airtrap WDL 一鍵匯出。
- 3D Plot 視窗與 Top/Front/Right/Default 視角按鈕。
- Log 視窗即時顯示所有動作訊息。

若 GUI 無法啟動，請確認 PySide6 與 matplotlib 是否已安裝；macOS 使用者需確保具備 Qt 相關依賴。

## 資料格式說明
- **CSV** 預設編碼為 UTF-8，檔頭如下：
  ```
  # Virtual Bump Configuration file. Unit:mm
  # x0, y0, z0, x1, y1, z1, diameter, group
  ```
- **HDF5 (`to_hdf5`)** 會建立資料集 `vbump`，欄位順序與 CSV 相同，並將總體與各群組的 bounding box 寫入 dataset attribute，便於後續檢索。

## 繪圖與可視化
- CLI 版本在 Plot 期間會暫停主迴圈，請關閉視窗後再回到終端機。
- GUI Plot 可使用滑鼠與視角按鈕操作；設定 substrate 後能清楚顯示與基板的高度關係。

## Moldex3D WDL 匯出
- `vbumps2WDL.py` 會更新模板中的 `ItemTypeInfo`、`NodeInfo` 等資訊，確保 Weldline/Airtrap WDL 可以在 Moldex3D 中正確讀入。
- 當 v-bump 數量過大，系統會改以各群組的 AABB 線框輸出，以避免節點數過多。

## 打包成可執行檔
參考 `install.md` 的範例指令：
```bash
pyinstaller --noconsole --onefile --name "VBumpGenerator" --icon "icon.ico" main_ui.py
```
如需 CLI 版本，可改以 `main.py` 為入口並視需求移除 `--noconsole`。

## 疑難排解
- **ImportError: No module named PySide6**：未安裝 GUI 依賴，請執行 `pip install -r requirements.txt`。
- **Matplotlib backend error**：在無視窗環境可改用 CLI 或指定非互動 backend (Agg)。
- **HDF5 相關錯誤**：請確認 `h5py`、`numpy` 安裝完成且系統有對應 HDF5 函式庫。
- **CSV 亂碼**：讀取時請指定 UTF-8 編碼。

## 貢獻與授權
歡迎透過 Issue/PR 提出建議。提交前建議：
- 執行 `python main.py` 與 `python main_ui.py` 做冒煙測試。
- 確認 CSV/HDF5/WDL 匯入匯出是否正常。

專案授權請依原始條款使用；若尚未指定，建議補上適合的 License。
