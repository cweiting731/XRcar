---
上層:
  - "[[資訊專題(一)]]"
  - "[[XR流程規劃.excalidraw]]"
---
```base
filters:
  and:
    - file.path.startsWith(this.file.folder + "/版更紀錄/")
views:
  - type: table
    name: 資料夾清單
    order:
      - file.name
      - 狀態
      - 修改人
      - 時間
      - file.mtime
      - file.ext
    columnSize:
      file.name: 380
      file.mtime: 193

```
